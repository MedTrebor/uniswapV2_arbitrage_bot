from datetime import datetime

from rich import print

import persistance
from blockchain import Web3, multicall, burner
from network import prices
from utils import CONFIG
from web3.contract.contract import Contract
from core import logger
from arbitrage.arguments import decode_arb_args


def main():
    prices.get_gas_price()
    w3 = Web3()
    tx_hash = "0x8f2ea69f7d83b1889fd55d7844fde84c8b22903bafd24303a1c098a78d7cea49"
    receipt = w3.wait_for_tx_receipt(tx_hash)
    tx = w3.eth.get_transaction(tx_hash)
    used_burners = burner.get_used_burnerns(tx_hash)

    args = decode_arb_args(tx["input"])

    logger.log_executed_arbs([receipt], [args], used_burners)


if __name__ == "__main__":
    main()
