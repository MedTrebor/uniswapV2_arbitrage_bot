import sys
from datetime import timedelta
from time import perf_counter, sleep

from eth_typing import ChecksumAddress
from rich import print
from rich.console import Console

import persistance
import web3
from blockchain import Web3
from utils import CONFIG, str_obj
from web3.contract.contract import Contract
from web3.exceptions import TimeExhausted

c = Console()

AMOUNT = int(1e18)
GAS_PRICE = int(1e9) + 1


def main():
    w3 = Web3()

    abi = persistance.get_abi("WETH")
    wbnb = w3.eth.contract(CONFIG["weths"][0], abi=abi)
    wbnb_fst = w3.eth.contract(CONFIG["weths"][1], abi=abi)

    wbnb_balance = wbnb.functions.balanceOf(w3.router).call()
    wbnb_fst_balance = wbnb_fst.functions.balanceOf(w3.router).call()

    unwrap_amount = wbnb_fst_balance
    wrap_amount = AMOUNT - wbnb_balance

    unwrap_withdraw(w3, unwrap_amount, wbnb_fst.address)
    wrap(w3, wbnb, wrap_amount)
    transfer_wbnb(w3, wbnb, wrap_amount)


def unwrap_withdraw(w3: Web3, amount: int, wbnb_address: ChecksumAddress):
    selector = "00"
    hex_amount = int_to_uint256(amount)
    lower_address = wbnb_address[2:].lower()

    acc = w3.account

    tx_params = {
        "from": acc,
        "to": w3.router,
        "nonce": w3.nonce(acc),
        "gasPrice": GAS_PRICE,
        "chainId": w3.chain_id,
        "data": "0x" + selector + hex_amount + lower_address,
    }
    gas = w3.eth.estimate_gas(tx_params)
    tx_params["gas"] = int(gas * 1.2)
    w3.nonces[acc] += 1

    print(f"[b]Sending Transaction[/]: {str_obj(tx_params)}")

    send_tx = True
    start = perf_counter()
    while True:
        try:
            if send_tx:
                tx_hash = w3.eth.send_transaction(tx_params)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, 120, 2)
            break
        except ValueError as err:
            print(err)
            if "nonce" in str(err):
                send_tx = False
                continue
            sleep(120)
        except TimeExhausted as err:
            print(err)

    print(dict(receipt))
    print(f"Confirmed in {timedelta(seconds=perf_counter() - start)}")
    sleep(3)


def wrap(w3: Web3, wbnb: Contract, amount: int):
    acc = w3.account

    tx_params = {
        "from": acc,
        "value": amount,
        "nonce": w3.nonce(acc),
        "gasPrice": GAS_PRICE,
        "chainId": w3.chain_id,
    }
    tx = wbnb.functions.deposit()
    gas = tx.estimate_gas(tx_params)
    tx_params["gas"] = int(gas * 1.2)
    w3.nonces[acc] += 1

    print(f"[b]Sending Transaction[/]: {str_obj(tx_params)}")

    send_tx = True
    start = perf_counter()
    while True:
        try:
            if send_tx:
                tx_hash = tx.transact(tx_params)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, 120, 2)
            break
        except ValueError as err:
            print(err)
            if "nonce" in str(err):
                send_tx = False
                continue
            sleep(120)
        except TimeExhausted as err:
            print(err)

    print(dict(receipt))
    print(f"Confirmed in {timedelta(seconds=perf_counter() - start)}")
    sleep(3)


def transfer_wbnb(w3: Web3, wbnb: Contract, amount: int):
    acc = w3.account

    tx_params = {
        "from": acc,
        "nonce": w3.nonce(acc),
        "gasPrice": GAS_PRICE,
        "chainId": w3.chain_id,
    }
    tx = wbnb.functions.transfer(CONFIG["router"], amount)
    gas = tx.estimate_gas(tx_params)
    tx_params["gas"] = int(gas * 1.2)
    w3.nonces[acc] += 1

    print(f"[b]Sending Transaction[/]: {str_obj(tx_params)}")

    send_tx = True
    start = perf_counter()
    while True:
        try:
            if send_tx:
                tx_hash = tx.transact(tx_params)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, 120, 2)
            break
        except ValueError as err:
            print(err)
            if "nonce" in str(err):
                send_tx = False
                continue
            sleep(120)
        except TimeExhausted as err:
            print(err)

    print(dict(receipt))
    print(f"Confirmed in {timedelta(seconds=perf_counter() - start)}")
    sleep(3)


def int_to_uint256(num: int) -> str:
    hex_num = hex(num)[2:]
    return "0" * (64 - len(hex_num)) + hex_num


if __name__ == "__main__":
    sys.stdout.write("\033]0;REWRAP\007")
    sys.stdout.flush()
    try:
        main()
    except (SystemExit, KeyboardInterrupt):
        print()
    except BaseException as error:
        c.print_exception(extra_lines=6, show_locals=True, suppress=[web3])
