from datetime import datetime

from rich import print

import persistance
from blockchain import Web3, multicall, burner
from network import prices
from utils import CONFIG, Logger
from web3.contract.contract import Contract
from core import logger
from arbitrage.arguments import decode_arb_args
from rich import traceback

traceback.install(extra_lines=6, show_locals=True)

log = Logger(__name__)


def main():
    prices.get_gas_price()
    w3 = Web3()
    tx_hash = "0x7b1b37c745d27496ddc816e58c01a0c5e0b85a83efa909dcd93dd550da61fb8b"
    receipt = w3.wait_for_tx_receipt(tx_hash)
    tx = w3.eth.get_transaction(tx_hash)
    used_burners = burner.get_used_burnerns(tx_hash)
    log.info(f"Used burners: {used_burners}")

    args = decode_arb_args(tx["input"])

    logger.log_executed_arbs([receipt], [args], used_burners)


if __name__ == "__main__":
    main()
