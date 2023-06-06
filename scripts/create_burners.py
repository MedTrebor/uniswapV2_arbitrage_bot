from datetime import timedelta
from random import randint
from time import perf_counter, sleep

from rich import print
from rich.traceback import install

import persistance
from blockchain import Web3
from blockchain.burner import get_burner_addresses, salt_to_calldata
from utils import CONFIG, measure_time, str_obj
from web3.exceptions import TimeExhausted

install(extra_lines=6, show_locals=True)

COUNT = 19
GAS_PRICE = int(1e9) + 1
SALT = 0


def main():
    global COUNT, SALT
    w3 = Web3()

    acc = w3.burner_generator
    nonce = w3.nonce(acc)

    salt = SALT

    for i in range(1, COUNT + 1):
        print(f"[b u]CREATION {i}/{COUNT}\n")

        calldata = salt_to_calldata(salt)

        create_burners(w3, acc, nonce, calldata)

        burners = persistance.load_generator_burners()
        addresses = get_burner_addresses(calldata)
        burners.append({"salt": salt, "addresses": addresses})
        persistance.save_generator_burners(burners)

        nonce += 1
        salt += 1
        print()


def create_burners(w3: Web3, acc: str, nonce: int, calldata: str):
    tx_params = {
        "from": acc,
        "to": CONFIG["burner"]["factory"],
        "value": 1,
        "nonce": nonce,
        "gasPrice": GAS_PRICE,
        "chainId": w3.chain_id,
        "data": calldata,
    }
    gas = w3.eth.estimate_gas(tx_params)
    gas_range = (int(gas * 1.15), int(gas * 1.3))
    tx_params["gas"] = int(gas * 1.2)

    print(f"[b]Sending Transaction[/]: {str_obj(tx_params, True)}")
    log_str = measure_time(
        "[b]Transaction Hash[/]: [blue not b link=https://bscscan.com/tx/{h}]{h}[/]\n"
        "[b]Gas used[/]: [orange1]{g:,}[/]\n"
        "[b]Confirmed in[/]: {t}\n"
    )

    send_tx = True
    while True:
        try:
            if send_tx:
                # tx_params["gas"] = randint(*gas_range)
                tx_hash = w3.eth.send_transaction(tx_params)

            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, 30, 3)
            break

        except ValueError as err:
            print(err)
            if "nonce" in str(err):
                send_tx = False
                sleep(CONFIG["poll"]["main"])
                continue
            sleep(30)

        except TimeExhausted as err:
            print(err)

    print(log_str(h=tx_hash.hex(), g=receipt["gasUsed"]))
    sleep(3)


if __name__ == "__main__":
    try:
        main()
    except (SystemExit, KeyboardInterrupt):
        print()
