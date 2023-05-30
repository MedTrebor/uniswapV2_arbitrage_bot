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
from blockchain.burner import get_burner_addresses, salt_to_calldata

install(extra_lines=6, show_locals=True)
SALT = 5


def main():
    addresses = get_burner_addresses(salt_to_calldata(SALT))

    burners = persistance.load_generator_burners()
    burners.append({"salt": SALT, "addresses": addresses})

    persistance.save_generator_burners(burners)


def migrate():
    burners = persistance.load_burners()
    generator_burners = persistance.load_generator_burners()

    burners.extend(generator_burners)

    persistance.save_burners(burners)
    persistance.save_generator_burners([])


if __name__ == "__main__":
    try:
        migrate()
    except (SystemExit, KeyboardInterrupt):
        print()
