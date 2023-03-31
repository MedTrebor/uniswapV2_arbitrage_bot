from datetime import timedelta
from time import perf_counter, sleep

from rich import print
from rich.traceback import install

import persistance
from blockchain import Web3
from blockchain.burner import get_burner_addresses, salt_to_calldata
from utils import CONFIG, str_obj
from web3.exceptions import TimeExhausted

install(extra_lines=6, show_locals=True)

COUNT = 5
GAS_PRICE = int(1e9) + 1
SALT = 0


def main():
    global COUNT, SALT
    w3 = Web3()

    acc = w3.account
    nonce = w3.nonce(acc)

    burners = persistance.load_burners()
    salt = SALT

    for i in range(1, COUNT + 1):
        print(f"[b u]CREATION {i}/{COUNT}\n")

        calldata = salt_to_calldata(salt)

        create_burners(w3, acc, nonce, calldata)

        addresses = get_burner_addresses(calldata)
        burners.append({"salt": salt, "addresses": addresses})
        persistance.save_burners(burners)

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
    tx_params["gas"] = int(gas * 1.2)

    print(f"Sending transaction: {str_obj(tx_params)}")
    start = perf_counter()

    send_tx = True
    while True:
        try:
            if send_tx:
                tx_hash = w3.node.eth.send_transaction(tx_params)
            receipt = w3.node.eth.wait_for_transaction_receipt(tx_hash, 120, 3)
            break

        except ValueError as err:
            print(err)
            if "nonce" in str(err):
                send_tx = False
                sleep(CONFIG["poll"]["main"])
                continue
            sleep(120)

        except TimeExhausted as err:
            print(err)

    print(dict(receipt))
    print(f"Confirmed in {timedelta(seconds=perf_counter() - start)}\n")
    sleep(3)


if __name__ == "__main__":
    try:
        main()
    except (SystemExit, KeyboardInterrupt):
        print()
