from multiprocessing import Lock

import requests
from eth_abi import decode as abi_decode

from utils import Logger, WaitPrevious
from web3 import HTTPProvider, Web3
from web3.contract import Contract
from web3.middleware import geth_poa_middleware, validation
from web3.types import TxData
from whitelisting._types import TxReceipt
from whitelisting.decorators import cache_last_block, wait
from whitelisting.selectors import get_swap_selectors
from whitelisting.storage import load_tokens, save_tokens

validation.METHODS_TO_VALIDATE.clear()

URL = "https://bsc-dataseed.binance.org/"
waiter = WaitPrevious(0.5)


log = Logger(__name__)


def _main(lock: Lock):
    w3 = Web3(HTTPProvider(URL))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    tokens = load_tokens(lock)
    tokens_count = len(tokens)

    short_selectors, long_selectors = get_swap_selectors()
    swap_selectors = {*short_selectors, *long_selectors}

    while True:
        txs = get_new_txs(w3)

        if not txs:
            continue

        filter_router_txs(txs, swap_selectors)

        if not txs:
            continue

        tx_receipts = get_tx_receipts(txs)

        assert len(txs) == len(
            tx_receipts
        ), f"Transactions ({len(txs)}) and receipts ({len(tx_receipts)})"
        " don't have equal lenth."

        filter_valid_txs(txs, tx_receipts)

        if not txs:
            continue

        new_tokens = get_tokens(txs, short_selectors, long_selectors)

        tokens.update(new_tokens)

        if len(tokens) != tokens_count:
            save_tokens(tokens, lock)
            tokens_count = len(tokens)


@wait(waiter)
@cache_last_block
def get_new_txs(last_block: int, w3: Web3) -> tuple[list[TxData], int]:
    block_number = w3.eth.block_number

    if last_block == block_number:
        return [], block_number

    return w3.eth.get_block(block_number, True)["transactions"], block_number


def filter_router_txs(txs: list[TxData], selectors: set[str]) -> None:
    to_remove = []
    for i, tx in enumerate(txs):
        if tx["input"][:10] in selectors:
            continue

        to_remove.append(i)

    for offest, idx in enumerate(to_remove):
        del txs[idx - offest]


@wait(waiter)
def get_tx_receipts(txs: list[TxData]) -> list[TxReceipt]:
    request_param = [
        {
            "jsonrpc": "2.0",
            "method": "eth_getTransactionReceipt",
            "params": [tx["hash"].hex()],
            "id": i,
        }
        for i, tx in enumerate(txs)
    ]
    response = requests.post(URL, json=request_param).json()

    return [res["result"] for res in response]


def filter_valid_txs(txs: list[TxData], receipts: list[TxReceipt]) -> None:
    to_remove = []
    for i, receipt in enumerate(receipts):
        if receipt["status"] == "0x0":
            to_remove.append(i)

    for offset, idx in enumerate(to_remove):
        del txs[idx - offset]


def get_tokens(router: Contract, txs: list[TxData]) -> set[str]:
    toekns = set()
    for tx in txs:
        addresses = router.decode_function_input(tx["input"])[1]["path"]

        toekns.update(addresses)

    return toekns


def get_tokens(
    txs: list[TxData], short_selectors: set[str], long_selectors: set[str]
) -> set[str]:
    short_type = ["uint256", "address[]", "address", "uint256"]
    long_type = ["uint256", "uint256", "address[]", "address", "uint256"]

    tokens = set()
    for tx in txs:
        data = tx["input"]
        selector = data[:10]

        try:
            if selector in short_selectors:
                decoded = abi_decode(short_type, bytes.fromhex(data[10:]))

            elif selector in long_selectors:
                decoded = abi_decode(long_type, bytes.fromhex(data[10:]))

        except OverflowError:
            continue

        path = decoded[-3]

        tokens.update((Web3.to_checksum_address(add) for add in path))

    return tokens


def main(lock: Lock):
    log.info("[i][b u]WHITELISTER[/] started.")

    while True:
        try:
            _main(lock)
        except (KeyboardInterrupt, SystemExit):
            print()
            exit()
        except BaseException as error:
            # log.error(error)
            continue


if __name__ == "__main__":
    main(Lock())
