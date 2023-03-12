from datetime import timedelta
from time import perf_counter, sleep

from eth_typing import ChecksumAddress
from rich import print
from rich.traceback import install

import persistance
from blockchain import Web3
from utils import CONFIG
from web3.contract.contract import Contract
from web3.exceptions import TimeExhausted

install(extra_lines=6, show_locals=True)
GAS_PRICE = int(1e9) + 1


def main():
    w3 = Web3()

    abi = persistance.get_abi("WETH")
    wbnb_fst = w3.eth.contract(CONFIG["weths"][1], abi=abi)

    amount = wbnb_fst.functions.balanceOf(CONFIG["router"]).call()
    unwrap_withdraw(w3, amount, wbnb_fst.address)


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

    start = perf_counter()
    send_tx = True
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
                sleep(3)
                continue
            sleep(120)

        except TimeExhausted as err:
            print(err)

    print(dict(receipt))
    print(f"Confirmed in {timedelta(seconds=perf_counter() - start)}")


def int_to_uint256(num: int) -> str:
    hex_num = hex(num)[2:]
    return "0" * (64 - len(hex_num)) + hex_num


if __name__ == "__main__":
    try:
        main()
    except (SystemExit, KeyboardInterrupt):
        print()
