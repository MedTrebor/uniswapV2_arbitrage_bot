from decimal import Decimal

from utils import CONFIG, MIN_LIQUIDITY, Logger
from utils._types import Pools

from .pools import get_pool_addresses, prepare_pool_addresses_params
from .ww3 import Web3

log = Logger(__name__)


def filter_pools(_pools: Pools, pools_numbers: dict[str, int]) -> None:
    """Filter pools by removing low liquidity pools.

    Args:
        _pools (dict[str, dict[str, Decimal]]): Pools datastructure.
        pools_numbers (dict[str, int]): Mapping of factory address to pool count.
    """
    global_min_liquidity = Decimal(CONFIG["filter"]["min_liquidity"])
    factories = [factory for factory in Web3().factories[0].values()]

    # getting excluded ranges
    excluded_ranges = get_excluded_ranges(pools_numbers, CONFIG["filter"]["exclude"])

    # preparing parameters for multicall (single process)
    pools_call_params = prepare_pool_addresses_params(factories, excluded_ranges)

    if not pools_call_params:
        remove_low_liquidity_pools(_pools, set(), MIN_LIQUIDITY, global_min_liquidity)

    # get pool addresses
    pool_addresses = get_pool_addresses(pools_call_params, CONFIG["max_retries"])
    excluded_pool_addresses = to_excluded_addresses(pool_addresses)

    # removing low liquidity
    remove_low_liquidity_pools(
        _pools, excluded_pool_addresses, MIN_LIQUIDITY, global_min_liquidity
    )


def get_excluded_ranges(
    pools_numbers: dict[str, int], exclude_num: int
) -> list[tuple[int, int]]:
    """Get ranges of pools that will be excluded. If pool count is smaller
    than excluded number range will be `(pool_count, pool_count)`.

    Args:
        pools_numbers (dict[str, int]): Mapping of factory address to pool count.
        exclude_num (int): Number of last pools to exclude.

    Returns:
        list[tuple[int, int]]: List of excluded ranges.
    """
    excluded_ranges = []
    for pool_count in pools_numbers.values():
        first_idx = pool_count - exclude_num if pool_count > exclude_num else 0
        excluded_ranges.append((first_idx, pool_count))

    return excluded_ranges


def to_excluded_addresses(pool_addresses: dict[str, list[str]]) -> set[str]:
    """Make set of excluded pool addresses.

    Args:
        pool_addresses (dict[str, list[str]]): Factory to pool addresses mapping.

    Returns:
        set[str]: Excluded pool addresses.
    """
    excluded_pools = set()
    for addresses in pool_addresses.values():
        for address in addresses:
            excluded_pools.add(address)

    return excluded_pools


def remove_low_liquidity_pools(
    _pools: Pools,
    excluded_pool_addresses: set[str],
    min_liquidity_tokens: dict[str, Decimal],
    global_min_liquidity: Decimal,
) -> None:
    """Remove pools with liquidity lower than provided in
    ``min_liquidity_tokens``.

    Note:
        Depending on order of fields in `Pool`. First two fields have to be reserves.

    Args:
        _pools (Pools): Pools datastructure.
        excluded_pool_addresses (set[str]): Addresses of pools not to remove.
        min_liquidity_tokens (dict[str, Decimal]): Mapping of token address to minimum liqudity.
        global_min_liquidity (Decimal): Minimum liquidity for all tokens.
    """
    remove_addresses = []
    for pool_address, pool_data in _pools.items():

        if pool_address in excluded_pool_addresses:
            # skip excluded
            continue

        for (token_address, reserve), _ in zip(pool_data.items(), range(2)):
            # checking if token is in minimum liquidity watch list
            if token_address in min_liquidity_tokens:
                if reserve < min_liquidity_tokens[token_address]:
                    remove_addresses.append(pool_address)
                break

            # checking if reserve is smaller than global min liquidity
            if reserve < global_min_liquidity:
                remove_addresses.append(pool_address)
                break

    # removing low liquidity pools
    for remove_address in remove_addresses:
        del _pools[remove_address]

    # logging
    if remove_addresses:
        pool_s = "pool" if len(remove_addresses) == 1 else "pools"
        log.info(f"Removed {len(remove_addresses):,} low liquidity {pool_s}.")
