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
from blockchain.burner import get_burner_addresses

install(extra_lines=6, show_locals=True)
GAS_PRICE = int(1e9) + 1
CALLDATA = "0x01"


def main():
    addresses = get_burner_addresses(CALLDATA)

    burners = persistance.load_burners()
    burners.append({"salt": 1, "addresses": addresses})

    persistance.save_burners(burners)


if __name__ == "__main__":
    try:
        main()
    except (SystemExit, KeyboardInterrupt):
        print()
