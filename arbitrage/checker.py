from decimal import Decimal
from time import perf_counter, sleep
from typing import Sequence

from eth_typing import ChecksumAddress

from blockchain import Web3
from network import prices
from network.prices import wei_usd_price
from utils import CONFIG, Logger, measure_time, str_num
from utils._types import (
    BatchCheckerArgs,
    BatchCheckerResult,
    CallArgs,
    Pools,
    RawTransaction,
)
from utils.datastructures import Arbitrage

from .arguments import create_all_batch_args
from .calculator import calc_gas_cost, calc_optimal_gas_price, get_burners_values
from .exceptions import ArbitrageError, BatchDecodeError

log = Logger(__name__)


def check_arbs(
    raw_arbs: list[Arbitrage],
    blacklist_paths: set[tuple[str, ...]],
    pre_blacklist_paths: dict[tuple[str, ...], int],
    pools: Pools,
    min_gas_price: Decimal,
    low_gas_price: Decimal,
    mid_gas_price: Decimal,
    max_gas_price: Decimal,
    to_blacklist: set[tuple[str, ...]],
) -> list[tuple[Arbitrage, Decimal, Decimal]]:
    w3 = Web3()
    call_params = {"from": w3.account}

    successful, reverted = batch_check(raw_arbs, pools, call_params, w3)

    if reverted:
        length = len(reverted)
        is_are = "is" if length == 1 else "are"
        arbitrage_s = "arbitrage" if length == 1 else "arbitrages"
        log.debug(f"There {is_are} {length:,} reverting {arbitrage_s}.")

        handle_reverted(
            reverted,
            blacklist_paths,
            pre_blacklist_paths,
            to_blacklist,
        )

    if successful:
        profitables = handle_successful(
            successful,
            min_gas_price,
            low_gas_price,
            mid_gas_price,
            max_gas_price,
            pre_blacklist_paths,
        )
        filter_profitables(profitables, max_gas_price)

        # canceling there are no profitables or too much time has passed
        # block_time_passed = perf_counter() - block_start
        # if block_time_passed > CONFIG["transaction"]["max_delay"]:
        #     log.warning(f"Slow transaction processing: {block_time_passed:,}.")
        #     return []
        # if not profitables:
        #     return profitables

        # waiting to fetch pending transaction
        # sleep(CONFIG["transaction"]["max_delay"] - block_time_passed)

        # checking if gas prices are high enough
        # log_str = measure_time("Downloaded {:,} pending transactions in {}.")
        # pending_txs = w3.get_pending_txs()
        # check_gas_prices(profitables, pending_txs)
        # log.info(log_str(len(pending_txs)))

        return profitables

    return []


def batch_check(
    raw_arbs: list[Arbitrage],
    pools: Pools,
    call_params: CallArgs,
    w3: Web3,
) -> tuple[
    list[tuple[Arbitrage, BatchCheckerResult]],
    list[tuple[Arbitrage, BatchCheckerResult]],
]:
    all_batch_args = create_all_batch_args(raw_arbs, pools)

    batch_results = exe_batch_check_arbs(w3, all_batch_args, call_params)

    successful, reverted = [], []
    for arb, result in zip(raw_arbs, batch_results, strict=True):
        if result[0]:
            successful.append((arb, result))
        else:
            reverted.append((arb, result))

    return successful, reverted


def exe_batch_check_arbs(
    w3: Web3, all_batch_args: list[BatchCheckerArgs], call_params: CallArgs
) -> list[BatchCheckerResult]:
    batch_results = []
    for batch_args in all_batch_args:
        try:
            batch_results.extend(
                decode_batch_results(
                    w3.batch_checker.functions.checkArbs(*batch_args).call(call_params)
                )
            )
        except ValueError as error:
            log.error(f"Error in batch checking: {error}")

            # append error if splitting is not possible
            if len(batch_args[1]) == 1:
                batch_results.append((False, 0, 0))
                continue

            # splitting to 2 halves
            half_idx = len(batch_args[1]) // 2
            retry_batch_args = [
                (batch_args[0], batch_args[1][:half_idx]),
                (batch_args[0], batch_args[1][half_idx:]),
            ]

            batch_results.extend(
                exe_batch_check_arbs(w3, retry_batch_args, call_params)
            )

    return batch_results


def decode_batch_results(batch_results: bytes) -> list[BatchCheckerResult]:
    if len(batch_results) % 19:
        raise BatchDecodeError(
            "Batch checking results have invalid length: "
            f"({len(batch_results):,} modulo 19 = {len(batch_results) % 19})"
        )

    decoded = []
    for i in range(0, len(batch_results), 19):
        success = bool(batch_results[i])
        profit = int.from_bytes(batch_results[i + 1 : i + 15], "big")
        gas = int.from_bytes(batch_results[i + 15 : i + 19], "big")

        decoded.append((success, profit, gas))

    return decoded


def handle_successful(
    successful: list[tuple[Arbitrage, BatchCheckerResult]],
    min_gas_price: Decimal,
    low_gas_price: Decimal,
    mid_gas_price: Decimal,
    max_gas_price: Decimal,
    pre_blacklist_paths: dict[tuple[str, ...], int],
) -> list[tuple[Arbitrage, Decimal, Decimal]]:
    recalculated_arbs = []

    low_multiplier = Decimal(CONFIG["price"]["low"]["ratio"])
    mid_multiplier = Decimal(CONFIG["price"]["mid"]["ratio"])
    high_multipler = Decimal(CONFIG["price"]["high"]["ratio"])
    eth_price = prices.eth_price * Decimal(CONFIG["price"]["correction"])
    min_profit = Decimal(CONFIG["transaction"]["min_profit"])
    burn_enabled = CONFIG["burner"]["enabled"]
    burn_cost = Decimal(36_930) * Decimal(CONFIG["burner"]["gas_price"])

    for arb, batch_result in successful:
        # removing from pre blacklist
        try:
            del pre_blacklist_paths[arb.path]
        except KeyError:
            pass

        bruto_profit = Decimal(batch_result[1])
        if bruto_profit == 0:
            # no profit result
            continue

        # getting gas cost and estimated gas usage
        gas_est = Decimal(batch_result[2] + 23_640)
        wei_price = wei_usd_price(arb.path[0], eth_price)

        # getting burners count and gas usage after burning
        if burn_enabled:
            burners_count, gas_usage = get_burners_values(gas_est)
        else:
            burners_count, gas_usage = 0, gas_est

        burners_cost = round(burners_count * burn_cost * wei_price, 0)

        if bruto_profit - burners_cost <= 0:
            continue

        # getting optimal gas price
        optimal_gas_price = calc_optimal_gas_price(
            bruto_profit - burners_cost, gas_usage, wei_price, low_multiplier
        )

        # regulating optimal price not to be higher than configured maximum
        if optimal_gas_price < min_gas_price:
            continue

        if optimal_gas_price > low_gas_price:
            optimal_gas_price = calc_optimal_gas_price(
                bruto_profit - burners_cost, gas_usage, wei_price, mid_multiplier
            )
        if optimal_gas_price > mid_gas_price:
            optimal_gas_price = calc_optimal_gas_price(
                bruto_profit - burners_cost, gas_usage, wei_price, high_multipler
            )

        # FIX BY IGNORING ALL ARBS WITH POOLS WITH HIGH GAS PRICE
        # SKIPPING TX WHERE GAS PRICE IS ABOVE MAXIMUM
        # if optimal_gas_price > max_gas_price:
        #     gwei_price = str_num(optimal_gas_price / Decimal(1e9))
        #     log.warning(f"Optimal gas price ({gwei_price} GWEI) for {arb} is too high")
        #     recalculated_arbs = []
        #     break

        # gas_price = min(optimal_gas_price, max_gas_price)
        gas_price = optimal_gas_price

        # calculate gas cost in arbitraged token
        gas_cost = calc_gas_cost(gas_price, gas_usage, wei_price)

        neto_profit = bruto_profit - gas_cost - burners_cost

        # checking for profit
        if neto_profit <= 0:
            continue

        # checking if profit is below minimum defined profit
        wei_profit = neto_profit // wei_price
        if wei_profit < min_profit:
            continue

        # correcting arbitrage params
        arb.tx_cost = arb.amount_in + gas_cost + burners_cost
        arb.bruto_profit = bruto_profit
        arb.neto_profit = neto_profit
        arb.wei_profit = wei_profit
        arb.gas_price = gas_price
        arb.burners_cost = burners_cost
        arb.burners_count = burners_count

        recalculated_arbs.append((arb, gas_usage, gas_price))

    return recalculated_arbs


def filter_profitables(
    profitables: list[tuple[Arbitrage, Decimal, Decimal]], max_gas_price: Decimal
) -> None:
    # sorting by gas price
    profitables.sort(key=lambda x: x[0], reverse=True)

    # getting unique pools
    to_exclude_idx, all_pairs = [], set()
    for i, (arb, *_) in enumerate(profitables):
        # iterating through all pairs
        current_pairs = set()
        for pair in arb.pairs():
            if pair in all_pairs:
                # pair is already in more profitable arbitrage
                to_exclude_idx.append(i)
                current_pairs.clear()
                break

            current_pairs.add(pair)

        all_pairs.update(current_pairs)

        # removing high gas price arbs
        if current_pairs and arb.gas_price > max_gas_price:
            gwei_price = str_num(arb.gas_price / Decimal(1e9))
            log.warning(f"Optimal gas price ({gwei_price} GWEI) for {arb} is too high.")

            to_exclude_idx.append(i)
            continue


    # removing less profitable arbs with same pairs
    for i, idx in enumerate(to_exclude_idx):
        del profitables[idx - i]


def handle_reverted(
    reverted: list[tuple[Arbitrage, BatchCheckerResult]],
    blacklist_paths: set[tuple[str, ...]],
    pre_blacklist_paths: dict[tuple[str, ...], int],
    to_blacklist: set[tuple[str, ...]],
) -> None:
    target_count = CONFIG["blacklist"]

    for arb, batch_result in reverted:
        path = arb.path

        # checking for case where router didn't detect nonprofitable tx
        if batch_result[2] > 0:
            ArbitrageError(
                f"BatchChecker did not detect nonprofitable transaction: {arb}"
            )

        try:
            pre_blacklist_paths[path] += 1

            # add for blacklisting if count has reached configured count
            if pre_blacklist_paths[path] >= target_count:
                to_blacklist.add(path)

        except KeyError:
            # if path is new
            pre_blacklist_paths[path] = 1

    # blacklisting
    for path in to_blacklist:
        blacklist_paths.add(path)
        del pre_blacklist_paths[path]


def check_gas_prices(
    profitables: list[tuple[Arbitrage, Decimal, Decimal]],
    pending_txs: list[RawTransaction],
) -> None:
    remove_idxs = []

    for i, profitable in enumerate(profitables):
        arb = profitable[0]

        for tx in pending_txs:
            if tx["gasPrice"] < arb.gas_price:
                # skip lower gas price pending transactions
                break

            if has_addresses(tx["input"], arb.path):
                # remove if higher gas transaction has path address
                remove_idxs.append(i)

                # logging
                log.warning(f"Gas price lower than competition's ({tx['hash']})\n{arb}")
                break

    # removing
    for i, rm_idx in enumerate(remove_idxs):
        del profitables[rm_idx - i]


def has_addresses(data: str, addresses: Sequence[ChecksumAddress]):
    has_address = False

    for address in addresses:
        if address[2:].lower() in data:
            if has_address:
                return True
            has_address = True

    return False
