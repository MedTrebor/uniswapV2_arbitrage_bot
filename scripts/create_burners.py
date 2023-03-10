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

    acc = w3.account

    tx_params = {
        "from": acc,
        "to": CONFIG["burner"]["factory"],
        "value": 1,
        "nonce": w3.nonce(acc),
        "gasPrice": GAS_PRICE,
        "chainId": w3.chain_id,
    }
    gas = w3.eth.estimate_gas(tx_params)
    tx_params["gas"] = int(gas * 1.2)

    start = perf_counter()
    while True:
        try:
            tx_hash = w3.eth.send_transaction(tx_params)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, 120, 2)
            break
        except ValueError as err:
            print(err)
            if "nonce" in str(err):
                return
            sleep(120)
        except TimeExhausted as err:
            print(err)

    print(dict(receipt))
    print(f"Confirmed in {timedelta(seconds=perf_counter() - start)}")
    sleep(3)


if __name__ == "__main__":
    try:
        main()
    except (SystemExit, KeyboardInterrupt):
        print()
