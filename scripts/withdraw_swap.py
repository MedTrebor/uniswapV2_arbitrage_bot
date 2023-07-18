from decimal import Decimal
from math import ceil
from time import perf_counter, sleep

from eth_typing import ChecksumAddress
from hexbytes import HexBytes
from rich import print
from rich.traceback import install

import persistance
import web3
from arbitrage.arguments import to_hex_uint16, to_hex_uint112
from arbitrage.calculator import get_amount_out
from blockchain import Web3, update_pools
from path import build_graph
from path.builder import find_paths
from utils import CONFIG, measure_time, str_obj
from utils._types import Pools
from web3.contract.contract import Contract
from web3.exceptions import ContractLogicError, TimeExhausted

install(extra_lines=6, show_locals=True, suppress=[web3])

BUSD = "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56"
USDT = "0x55d398326f99059fF775485246999027B3197955"

TOKEN = BUSD
KEEP_AMOUNT = Decimal(int(40e19))  # 400.00
SLIPPAGE = Decimal("0.999")  # 0.1%

START_GAS_PRICE = int(1e9) + 1  # 1.000000001 GWEI
END_GAS_PRICE = int(3e9)  # 3 GWEI
INCREASE_TIME = 300


def main():
    w3 = Web3()

    all_pools = persistance.load_pools()
    paths = create_paths(all_pools)
    pools = extract_pools(paths, all_pools)
    token = get_token(w3)
    nonce = w3.nonce(w3.account)
    amount = Decimal(token.functions.balanceOf(CONFIG["router"]).call()) - KEEP_AMOUNT
    gas_price, gas_change = START_GAS_PRICE, perf_counter()

    log_str = measure_time(
        "[b]Transaction Hash[/]: [blue not b link=https://bscscan.com/tx/{h}]{h}[/]\n"
        "[b]Gas used[/]: [orange1]{g:,}[/]\n"
        "[b]Confirmed in[/]: {t}\n"
    )
    while True:
        try:
            update_pools(pools)

            amount_out, pair, weth = get_best_pair(pools, amount)

            calldata = create_calldata(amount, amount_out, pair, weth, pools)

            gas_price, gas_change = change_gas_price(gas_price, gas_change)

            tx_hash, gas_used = execute_tx(w3, calldata, nonce, gas_price)
            break
        except ContractLogicError as err:
            print(f"[red]ERROR[/]: {str(err)}")
            sleep(3)
        except ValueError as err:
            try:
                msg = err.args[0]["message"]
                if msg == "replacement transaction underpriced":
                    gas_change = 0
                print(f"[red]ERROR[/]: {msg}")
            except (KeyError, TypeError, AttributeError, IndexError):
                print(err)
            sleep(30)
        except TimeExhausted as err:
            print(f"[red]ERROR[/]: {str(err)}")

    print(log_str(h=tx_hash.hex(), g=gas_used))


def change_gas_price(current_gas_price: int, last_change: float) -> tuple[int, float]:
    if current_gas_price >= END_GAS_PRICE:
        return current_gas_price, last_change
    
    if perf_counter() - last_change > INCREASE_TIME:
        gas_increase1 = ceil(current_gas_price * 1.1)
        gas_increase2 = ceil(gas_increase1 * 1.1)

        if gas_increase2 > END_GAS_PRICE:
            gas_increase1 = gas_increase2

        return gas_increase1, perf_counter()

    return current_gas_price, last_change


def execute_tx(
    w3: Web3, calldata: str, nonce: int, gas_price: int
) -> tuple[HexBytes, int]:
    acc = w3.account
    raw_tx_params = {
        "from": acc,
        "to": CONFIG["router_multicall"],
        "nonce": nonce,
        "gasPrice": gas_price,
        "chainId": w3.chain_id,
        "data": calldata,
    }
    print(f"[b]Sending transaction[/]: {str_obj(raw_tx_params)}")

    gas = w3.eth.estimate_gas(raw_tx_params)
    tx_params = raw_tx_params.copy()
    tx_params["gas"] = int(gas * 1.2)
    tx_hash = w3.eth.send_transaction(tx_params)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, 30, 3)

    return receipt["transactionHash"], receipt["gasUsed"]


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
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        print()
