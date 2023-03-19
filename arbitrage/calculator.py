from datetime import timedelta
from decimal import Decimal, InvalidOperation, getcontext
from math import ceil
from multiprocessing.pool import Pool as ProcessPool
from time import perf_counter

from network import wei_usd_price
from utils import CONFIG, MIN_GAS_LIMITS, Logger
from utils._types import GasParams, Pools
from utils.datastructures import Arbitrage

from .exceptions import BigNumberError

getcontext().prec = 40

D10_000 = Decimal(10_000)


log = Logger(__name__)


def search_for_arbitrages(
    pools: Pools,
    paths: list[tuple[str, ...]],
    min_gas_price: Decimal,
    low_gas_price: Decimal,
    mid_gas_price: Decimal,
    max_gas_price: Decimal,
    eth_price: Decimal
    # process_pool: ProcessPool,
) -> list[Arbitrage]:
    """Check if there are arbitrage oportunities for ``paths``.

    Args:
        pools (Pools): All pools.
        paths (list[tuple[str, ...]]): List of unique paths.
        min_gas_price (Decimal): Minimum gas price.
        low_gas_price (Decimal): Low gas price.
        mid_gas_price (Decimal): Medium gas price.
        max_gas_price (Decimal): Maximum gas price.
        process_pool (ProcessPool): Process pool.

    Returns:
        list[Arbitrage]: Arbitrage datastructure.
    """
    # split for multiprocessing if there are enough paths
    # len_before = len(paths)
    # log.debug("Splitting paths.")
    # start = perf_counter()
    # _paths = split_paths(paths)
    # if len(_paths) == 1:
    #     log.debug(
    #         "Didn't split paths. Will use single process. Executed in"
    #         f" {timedelta(seconds=perf_counter() - start)}."
    #     )
    # else:
    #     log.debug(
    #         f"Split {len_before:,} paths to {len(_paths):,} chunks "
    #         f"with {len(_paths[0]):,} paths in {timedelta(seconds=perf_counter() - start)}."
    #     )

    # calculate and get profitable paths
    start = perf_counter()
    # eth_price = prices.eth_price * Decimal(CONFIG["price"]["correction"])
    eth_price = eth_price * Decimal(CONFIG["price"]["correction"])

    potential_arbs = calculate_profitability(
        pools,
        paths,
        min_gas_price,
        low_gas_price,
        mid_gas_price,
        max_gas_price,
        eth_price,
    )

    #########################
    ## FIX MULTIPROCESSING ##
    #########################

    # if len(_paths) == 1:
    #     potential_arbs = calculate_profitability(
    #         pools, _paths[0], gas_params, eth_price
    #     )

    # else:
    #     futures = [
    #         process_executor.submit(
    #             calculate_profitability, pools, paths_chunk, gas_params, eth_price
    #         )
    #         for paths_chunk in _paths[:-1]
    #     ]

    #     potential_arbs = calculate_profitability(
    #         pools, _paths[-1], gas_params, eth_price
    #     )

    #     for future in as_completed(futures):
    #         potential_arbs.extend(future.result())

    oportunitiy_s = "oportunity" if len(potential_arbs) == 1 else "oportunities"
    log.debug(
        f"Found {len(potential_arbs):,} arbitrage {oportunitiy_s}"
        f" in {timedelta(seconds=perf_counter() - start)}."
    )

    # sorting
    start = perf_counter()
    potential_arbs.sort(reverse=True)
    log.debug(
        f"Finished sorting arbitrages in {timedelta(seconds=perf_counter() - start)}."
    )

    return potential_arbs


def split_paths(paths: list[list[str]]) -> list[list[list[str]]]:
    """Split paths to chunks for multiprocessing.

    Args:
        paths (list[list[str]]): Paths.

    Returns:
        list[list[list[str]]]: Splitted paths.
    """
    mul_conf = CONFIG["multiprocessing"]
    chunks = mul_conf["workers"] + 1

    # if path is short don't split
    if len(paths) < chunks * mul_conf["min_chunk"]:
        return [paths]

    # splitting
    chunk_size = ceil(len(paths) / chunks)
    splitted_paths = []
    start_idx, stop_idx = 0, chunk_size

    for _ in range(chunks):
        splitted_paths.append(paths[start_idx:stop_idx])
        start_idx = stop_idx
        stop_idx += chunk_size

    return splitted_paths


def calculate_profitability(
    pools: Pools,
    paths: list[tuple[str, ...]],
    min_gas_price: Decimal,
    low_gas_price: Decimal,
    mid_gas_price: Decimal,
    max_gas_price: Decimal,
    eth_price: Decimal,
) -> list[Arbitrage]:
    """Make calculations on ``paths`` and filter out only potentially
    profitable paths.

    Args:
        pools (Pools): Pools.
        paths (list[tuple[str, ...]]): Paths.
        min_gas_price (Decimal): Minimum gas price.
        low_gas_price (Decimal): Low gas price.
        mid_gas_price (Decimal): Medium gas price.
        max_gas_price (Decimal): Maximum gas price.
        eth_price (Decimal): Price of ETH.

    Raises:
        InvalidOperation: If `Decimal` encountered error.

    Returns:
        list[Arbitrage]: Potentially profitable arbitrages.
    """
    low_multiplier = Decimal(CONFIG["price"]["low"]["ratio"])
    mid_multiplier = Decimal(CONFIG["price"]["mid"]["ratio"])
    high_multipler = Decimal(CONFIG["price"]["high"]["ratio"])
    min_profit = Decimal(CONFIG["transaction"]["min_profit"])
    burn_enabled = CONFIG["burner"]["enabled"]
    burn_cost = Decimal(36_930) * Decimal(CONFIG["burner"]["gas_price"])

    potential_arbs = []

    for path in paths:
        try:
            # getting virtual reserves
            reserve_in, reserve_out = get_virtual_reserves(pools, path)

            if reserve_in >= reserve_out or reserve_in <= 0 or reserve_out <= 0:
                continue

            # getting optimal amount in
            fee_numerator = pools[path[1]]["fee_numerator"]
            amount_in = optimal_amount_in(reserve_in, reserve_out, fee_numerator)
            if amount_in <= 0:
                continue

            # getting amount out and bruto profit
            try:
                amount_out = get_path_amount_out(amount_in, pools, path)
            except BigNumberError:
                amount_in //= Decimal(1.2)
                amount_out = get_path_amount_out(amount_in, pools, path)

            bruto_profit = amount_out - amount_in
            if bruto_profit <= 0:
                continue

            ########
            # TEST #
            opt_amount_in, opt_profit, i = tweak_amount_in(
                amount_in, bruto_profit, path, pools
            )

            if i:
                # profit_diff = (opt_profit / bruto_profit) - Decimal(1)
                # log.info(f"{i / 100:.2%} amount in. Profit: {profit_diff:.2%}")
                amount_in = opt_amount_in
                bruto_profit = opt_profit

            ########

            # getting gas limit and wei price
            gas_limit: Decimal = MIN_GAS_LIMITS[len(path)]
            wei_price = wei_usd_price(path[0], eth_price)

            # getting burners count and gas usage after burning
            if burn_enabled:
                burners_count, gas_usage = get_burners_values(gas_limit)
            else:
                burners_count, gas_usage = 0, gas_limit

            burners_cost = round(burners_count * burn_cost * wei_price, 0)

            if bruto_profit - burners_cost <= 0:
                continue

            # getting optimal price and checking if it's above minimum gas price
            optimal_gas_price = calc_optimal_gas_price(
                bruto_profit - burners_cost, gas_usage, wei_price, low_multiplier
            )
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

            # getting gas price
            gas_price = min(optimal_gas_price, max_gas_price)

            gas_cost = calc_gas_cost(gas_price, gas_usage, wei_price)
            tx_cost = amount_in + gas_cost + burners_cost

            # calculating profitability
            neto_profit = bruto_profit - gas_cost - burners_cost
            if neto_profit <= 0:
                continue

            wei_profit = neto_profit // wei_price
            if wei_profit < min_profit:
                continue

        except (InvalidOperation, BigNumberError):
            continue

        potential_arbs.append(
            Arbitrage(
                path,
                amount_in,
                tx_cost,
                bruto_profit,
                neto_profit,
                wei_profit,
                optimal_gas_price,
                burners_cost,
                burners_count,
            )
        )

    return potential_arbs


def get_virtual_reserves(pools: Pools, path: list[str]) -> tuple[Decimal, Decimal]:
    """Calculate virtual reserves for given ``path``.

    Args:
        pools (Pools): Pools datastructure.
        path (list[str]): `token`, `pool`, `token`... list

    Returns:
        tuple[Decimal, Decimal]: Virtual reserve in, virtual reserve out.
    """
    pool = pools[path[1]]

    # called virtual becaouse of reusable variable
    virtual_in = pool[path[0]]  # reserve_in_a
    virtual_out = pool[path[2]]  # reserve_out_a

    for i in range(3, len(path), 2):
        pool = pools[path[i]]

        fee_numerator = pool["fee_numerator"]

        reserve_in_a = virtual_in
        reserve_out_a = virtual_out

        reserve_in_b = pool[path[i - 1]]
        reserve_out_b = pool[path[i + 1]]

        virtual_in = (D10_000 * reserve_in_a * reserve_in_b) / (
            D10_000 * reserve_in_b + fee_numerator * reserve_out_a
        )
        virtual_out = (fee_numerator * reserve_out_a * reserve_out_b) / (
            D10_000 * reserve_in_b + fee_numerator * reserve_out_a
        )

    return round(virtual_in, 0), round(virtual_out, 0)


def optimal_amount_in(
    reserve_in: Decimal, reserve_out: Decimal, fee_numerator: Decimal
) -> Decimal:
    """Calculate optimal amount in fro given reserves.

    Args:
        reserve_in (Decimal): Reserve in.
        reserve_out (Decimal): Reserve out.

    Returns:
        Decimal: Optimal amount in.
    """
    return (
        Decimal.sqrt(reserve_in * reserve_out * fee_numerator * D10_000)
        - reserve_in * D10_000
    ) // fee_numerator


def get_path_amount_out(amount_in: Decimal, pools: Pools, path: list[str]) -> Decimal:
    """Given ``amount_in`` get amount out for path.

    Args:
        amount_in (Decimal): Amount of token in.
        pools (Pools): Pools.
        path (list[str]): Paths.

    Returns:
        Decimal: Amount of token out.
    """
    for i in range(1, len(path), 2):
        pool = pools[path[i]]
        reserve_in = pool[path[i - 1]]
        reserve_out = pool[path[i + 1]]

        if amount_in > reserve_in:
            raise BigNumberError()

        amount_in_with_fee = amount_in * pool["fee_numerator"]
        amount_out = (
            amount_in_with_fee
            * reserve_out
            // (reserve_in * D10_000 + amount_in_with_fee)
        )

        if amount_out > reserve_out:
            raise BigNumberError()

        amount_in = amount_out

    return amount_out


def tweak_amount_in(
    amount_in0: Decimal, profit0: Decimal, path: tuple[str, ...], pools: Pools
) -> tuple[Decimal, Decimal, int]:
    best_amount_in = amount_in0
    best_profit = profit0
    best_i = 0

    for i in range(1, 30):
        amount_in = round(amount_in0 * Decimal(i / 100 + 1), 0)
        amount_out = get_path_amount_out(amount_in, pools, path)
        profit = amount_out - amount_in

        if profit > best_profit:
            best_amount_in = amount_in
            best_profit = profit
            best_i = i

        elif profit < best_profit:
            break

    return best_amount_in, best_profit, best_i


def calc_gas_cost(gas_price: Decimal, gas_limit: Decimal, price: Decimal) -> Decimal:
    """Calculate cost of the transaction execution given the WEI ``price`` of the token.

    Example::
        >>> eth_price = Decimal('1173.80')
        >>> usdt_decimals = Decimal('1e6')
        >>> wei_price = eth_price * usdt_decimals / Decimal('1e18')
        >>> gas_limit = Decimal(203_383)
        >>> gas_price = Decimal(5_000_000_000}  # 5 GWEI
        >>> calculate_gas_cost(gas_price, gas_limit, wei_price)
        Decimal('1193655')

    Args:
        gas_params (Decimal): Gas price.
        gas_limit (Decimal): Gas limit of the transaction.
        price (Decimal): Wei price.

    Returns:
        Decimal: Cost of the transaction execution.
    """
    return round(gas_price * gas_limit * price, 0)


def get_amount_out(
    amount_in: Decimal,
    reserve_in: Decimal,
    reserve_out: Decimal,
    fee_numerator: Decimal,
) -> Decimal:
    """Get amount out.

    Args:
        amount_in (Decimal): Amount in.
        reserve_in (Decimal): Reserve for token in.
        reserve_out (Decimal): Reserve for token out.
        fee_numerator (Decimal): Fee numerator.

    Returns:
        Decimal: Amount out.
    """
    amount_in_with_fee = amount_in * fee_numerator
    return (
        amount_in_with_fee * reserve_out // (reserve_in * D10_000 + amount_in_with_fee)
    )


def calc_optimal_gas_price(
    bruto_profit: Decimal,
    gas_usage: Decimal,
    wei_price: Decimal,
    profit_multiplier: Decimal,
) -> Decimal:
    """Calculate optimal gas price according to ``profit_multiplier``.
    ``profit_multiplier`` has to be in range from `0` to `1`. If
    ``profit_multiplier`` is `0` gas price will be `0`. If
    ``profit_multiplier`` is `1` neto profit will be `0`.

    Example::
        >>> bruto_profit = Decimal(41)
        >>> profit_multiplier = Decimal(0.5)
        >>> gas_usage = Decimal(3)
        >>> wei_price = Decimal(2)
        >>> calc_optimal_gas_price(
        ...     bruto_profit, gas_usage, wei_price, profit_multiplier
        ... )
        Decimal('3')

    Args:
        bruto_profit (Decimal): Bruto profit.
        gas_usage (Decimal): Gas usage (gas limit).
        wei_price (Decimal): Price of arbitraged token.
        profit_multiplier (Decimal): Profit multiplier.

    Returns:
        Decimal: Optimal gas price.
    """
    return round((bruto_profit * profit_multiplier) / (gas_usage * wei_price), 0)


def get_burners_values(gas_usage: Decimal) -> tuple[int, Decimal]:
    """Get maximum number of burners to use based on ``gas_usage``
    and ``gas_usage`` after burning gas reduction.

    Note:
        * Burn execution cost is `6,114` gas
        * Burner address calldata cost is `320` gas
        * Burn cost is `6,434` gas
        * Selfdestruct refund is `24,000` gas
        * Burn gas reduction is `17,566` gas

    Args:
        gas_usage (Decimal): Gas usage.

    Returns:
        tuple[int, Decimal]: Number of burners to use and gas usage.
    """
    gas_reduction, burn_cost = Decimal(17_566), Decimal(6_434)
    total_gas = gas_usage
    count = 0

    while True:
        total_gas += burn_cost
        new_gas_usage = max(gas_usage - gas_reduction, total_gas // 2)

        # checking if gas reduction is greater than previous
        if new_gas_usage >= gas_usage:
            break

        gas_usage = new_gas_usage
        count += 1

    return count, round(gas_usage * Decimal(1.2), 0)
