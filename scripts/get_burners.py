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

COUNT = 30


def main():
    global COUNT
    w3 = Web3()

    burners = []

    for salt in range(COUNT):
        calldata = salt_to_calldata(salt)

        addresses = get_burner_addresses(calldata)
        checksum_addresses = [w3.to_checksum_address(a) for a in addresses]

        codes = w3.get_codes(checksum_addresses)

        unused = [a for a, c in zip(addresses, codes, strict=True) if c != "0x"]
        if unused:
            burners.append({"salt": salt, "addresses": unused})

    print(burners)


if __name__ == "__main__":
    try:
        main()
    except (SystemExit, KeyboardInterrupt):
        print()
