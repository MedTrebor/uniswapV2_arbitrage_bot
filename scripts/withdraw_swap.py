from datetime import timedelta
from decimal import Decimal
from time import perf_counter, sleep

from eth_typing import ChecksumAddress
from rich import print
from rich.traceback import install

import persistance
from arbitrage.arguments import to_hex_uint16, to_hex_uint112
from arbitrage.calculator import get_amount_out
from blockchain import Web3, update_pools
from path import build_graph
from path.builder import find_paths
from utils import CONFIG, measure_time
from utils._types import Pools
from web3.contract.contract import Contract
from web3.exceptions import TimeExhausted

install(extra_lines=6, show_locals=True)

GAS_PRICE = int(1e9) + 1
TOKEN = "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56"
KEEP_AMOUNT = Decimal(int(3e20))
SLIPPAGE = Decimal("0.999")


def main():
    w3 = Web3()

    all_pools = persistance.load_pools()
    paths = create_paths(all_pools)
    pools = extract_pools(paths, all_pools)

    update_pools(pools)

    token = get_token(w3)

    amount = Decimal(token.functions.balanceOf(CONFIG["router"]).call()) - KEEP_AMOUNT
    amount_out, pair, weth = get_best_pair(pools, amount)

    calldata = create_calldata(amount, amount_out, pair, weth, pools)

    execute_tx(w3, calldata)


def execute_tx(w3: Web3, calldata: str) -> None:
    acc = w3.account
    raw_tx_params = {
        "from": acc,
        "to": CONFIG["router_multicall"],
        "nonce": w3.nonce(acc),
        "gasPrice": GAS_PRICE,
        "chainId": w3.chain_id,
        "data": calldata,
    }

    log_str = measure_time(
        "[b]Transaction Hash[/]: [blue not b link=https://bscscan.com/tx/{h}]{h}[/]\n"
        "[b]Gas used[/]: [orange1]{g:,}[/]\n"
        "[b]Confirmed in[/]: {t}\n"
    )
    while True:
        try:
            gas = w3.eth.estimate_gas(raw_tx_params)
            tx_params = raw_tx_params.copy()
            tx_params["gas"] = int(gas * 1.2)
            tx_hash = w3.eth.send_transaction(tx_params)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, 120, 3)
            break
        except ValueError as err:
            print(err)
            sleep(120)
        except TimeoutError as err:
            print(err)

    print(log_str(h=receipt["transactionHash"].hex(), g=receipt["gasUsed"]))


def create_calldata(
    _amount_in: Decimal,
    amount_out: Decimal,
    _pair: ChecksumAddress,
    weth: ChecksumAddress,
    pools: Pools,
) -> str:
    amount_in = to_hex_uint112(_amount_in)
    pair = _pair[2:].lower()
    fee_numerator = to_hex_uint16(pools[_pair]["fee_numerator"])

    for token in pools[_pair].keys():
        is_0_in = "01" if token == TOKEN else "00"
        break

    min_amount_out = to_hex_uint112(round(amount_out * SLIPPAGE))
    token = TOKEN[2:].lower()
    weth = weth[2:].lower()

    return (
        "0x"
        + amount_in
        + pair
        + fee_numerator
        + is_0_in
        + min_amount_out
        + token
        + weth
    )


def get_best_pair(
    pools: Pools, amount_in: Decimal
) -> tuple[Decimal, ChecksumAddress, ChecksumAddress]:
    best_amount_out, best_pair, weth = Decimal(0), "", ""

    for pair, pool in pools.items():
        reserve_in = pool[TOKEN]
        for key, value in pool.items():
            if key != TOKEN and key.startswith("0x"):
                weth = key
                reserve_out = value
        fee_numerator = pool["fee_numerator"]

        amount_out = get_amount_out(amount_in, reserve_in, reserve_out, fee_numerator)
        if amount_out > best_amount_out:
            best_amount_out, best_pair = amount_out, pair

    return amount_out, best_pair, weth


def create_paths(all_pools: Pools) -> list[tuple[str, ...]]:
    graph = build_graph(all_pools)
    return find_paths(graph, TOKEN, set(CONFIG["weths"]), 1, set(), set())


def extract_pools(paths: list[tuple[str, ...]], all_pools: Pools) -> Pools:
    pools = {}
    for _, address, _ in paths:
        pools[address] = all_pools[address]

    return pools


def get_token(w3: Web3) -> Contract:
    abi = persistance.get_ERC20_abi()
    return w3.eth.contract(TOKEN, abi=abi)


if __name__ == "__main__":
    main()
