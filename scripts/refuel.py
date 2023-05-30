import re
import sys
from math import ceil
from time import perf_counter, sleep
from typing import Iterator

from eth_typing import ChecksumAddress
from rich import print
from rich.console import Console

import persistance
import web3
from blockchain import Web3
from utils import CONFIG, measure_time, str_num, str_obj
from web3.exceptions import TimeExhausted

c = Console()
MIN_GAS_PRICE = int(1e9) + 1
MAX_GAS_PRICE = int(3e9)
GAS_INCREMENT_TIME = 300


def main():
    w3 = Web3()

    abi = persistance.get_abi("WETH")
    wbnb = w3.eth.contract(CONFIG["weths"][0], abi=abi)
    wbnb_fst = w3.eth.contract(CONFIG["weths"][1], abi=abi)

    wbnb_balance = wbnb.functions.balanceOf(CONFIG["router"]).call()
    wbnb_fst_balance = wbnb_fst.functions.balanceOf(CONFIG["router"]).call()

    amount = wbnb_fst_balance + wbnb_balance - int(1e18)

    print(f"[b]Amount[/]: {str_num(amount / 1e18)} WBNB\n")

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
        "gasPrice": MIN_GAS_PRICE,
        "chainId": w3.chain_id,
        "data": "0x" + selector + hex_amount + lower_address,
    }
    gas = w3.eth.estimate_gas(tx_params)
    tx_params["gas"] = int(gas * 1.2)
    w3.nonces[acc] += 1

    print(f"[b]Sending Transaction[/]: {str_obj(tx_params, True)}\n")

    gas_timer = perf_counter()
    log_str = measure_time(
        "[b]Transaction Hash[/]: [blue not b link=https://bscscan.com/tx/{h}]{h}[/]\n"
        "[b]Gas used[/]: [orange1]{g:,}[/]\n"
        "[b]Confirmed in[/]: {t}\n"
    )
    send_tx = True
    while True:
        try:
            if send_tx:
                if perf_counter() - gas_timer > GAS_INCREMENT_TIME:
                    tx_params["gasPrice"] = ceil(tx_params["gasPrice"] * 1.1)
                    print(
                        f"[b]Sending Replacement Transaction[/]: {str_obj(tx_params, True)}\n"
                    )
                    gas_timer = perf_counter()

                    if tx_params["gasPrice"] > MAX_GAS_PRICE:
                        tx_params["gasPrice"] = MAX_GAS_PRICE
                        gas_timer = perf_counter() + 1_000_000

                tx_hash = w3.eth.send_transaction(tx_params)

            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, 30, 3)
            break

        except ValueError as err:
            try:
                msg = err.args[0]["message"]
            except (KeyError, TypeError, AttributeError, IndexError):
                msg = str(err)

            print(f"[red]ERROR[/]: {msg}")

            if "nonce" in msg:
                send_tx = False
                sleep(3)
                continue

            sleep(30)

        except TimeExhausted as err:
            str_err = re.sub(r"HexBytes\('|'\)", "", str(err))
            print(f"[red]ERROR[/]: {str_err}")

    print(log_str(h=tx_hash.hex(), g=receipt["gasUsed"]))


def int_to_uint256(num: int) -> str:
    hex_num = hex(num)[2:]
    return "0" * (64 - len(hex_num)) + hex_num


def iter_nodes(w3: Web3) -> Iterator[web3.Web3]:
    while True:
        for node in w3.nodes:
            yield node


if __name__ == "__main__":
    sys.stdout.write("\033]0;REFUEL\007")
    sys.stdout.flush()
    try:
        main()
    except (SystemExit, KeyboardInterrupt):
        print()
    except:
        c.print_exception(extra_lines=6, show_locals=True, suppress=[web3])
