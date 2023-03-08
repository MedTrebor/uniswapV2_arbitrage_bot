from decimal import Decimal
from functools import wraps
from itertools import zip_longest
from typing import Callable, Concatenate, ParamSpec, TypeVar

from utils import CONFIG, Logger, measure_time
from utils._types import Pools
from web3.types import LogReceipt

from .ww3 import Web3, create_pool_sync_filter

log = Logger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


def cache_last_block(f: Callable[Concatenate[int | None, P], R]) -> Callable[P, R]:
    """Decorator that caches previous block number.

    Args:
        f (Callable[Concatenate[int | None, P], R]): Function.

    Returns:
        Callable[P, R]: Wrapped function.
    """
    cached_block = None

    @wraps(f)
    def inner(*args: P.args, **kwargs: P.kwargs) -> R:
        nonlocal cached_block
        r = f(cached_block, *args, **kwargs)
        cached_block = r[2]
        return r

    return inner


@cache_last_block
def get_changed_pools(
    cached_block: int | None, pools: Pools, last_block_number: int
) -> tuple[Pools, Pools, int]:
    """Get pools that have changed reserves with new reserves included.
    If last block is too far for `Sync` filter. Will return all pools.

    Args:
        pools (Pools): Mapping of pool address to pool.
        last_block_number (int): Last block number.

    Returns:
        tuple[Pools, Pools, int]: Updated changed pools, changed pools and
            current block number.
    """
    w3 = Web3()
    conf = CONFIG["event_log"]

    log.debug(f"Getting Sync event logs.")
    log_str = measure_time("Sync event logs downloaded in {}.")

    # getting cached block or new block
    cached_block = cached_block or w3.block_number

    if cached_block - last_block_number > conf["max_blocks"]:
        block_number = w3.block_number
        w3._pool_sync_filter = create_pool_sync_filter(w3.node, block_number)
        log.warning("Last block far away. Will update all pools.")
        return {}, pools, block_number

    try:
        event_logs = w3.pool_sync_filter.get_new_entries()
    except ValueError as err:
        try:
            str_err = err.args[0]["message"]
        except (IndexError, KeyError, TypeError):
            str_err = str(err)
        log.error(f"Sync filter error: {str_err}")

        w3._pool_sync_filter = create_pool_sync_filter(w3.node, last_block_number)
        event_logs = w3.pool_sync_filter.get_new_entries()

    try:
        currnet_block_num = event_logs[-1]["blockNumber"]
    except IndexError:
        currnet_block_num = cached_block

    log.debug(log_str())

    format_log = measure_time("{:,} changed {} extracted from logs in {}.")
    updated_changed_pools, changed_pools = get_pools_from_logs(pools, event_logs)
    pool_s = "pool" if len(changed_pools) == 1 else "pools"
    log.debug(format_log(len(changed_pools), pool_s))

    return updated_changed_pools, changed_pools, currnet_block_num


def get_pools_from_logs(
    pools: Pools, event_logs: list[LogReceipt]
) -> tuple[Pools, Pools]:
    """Get pools that triggered `Sync` event and update their reserves.

    Args:
        pools (Pools): Pools datastructure.
        event_logs (list[LogReceipt]): Sync event log receipts.

    Returns:
        tuple[Pools, Pools]: copied changed pools and changed pools
    """
    updated_changed_pools, changed_pools = {}, {}

    for log_entry in event_logs:
        # getting address if in my pools
        address = log_entry["address"]
        try:
            pool = pools[address]
        except KeyError:
            continue

        # creating changed pool entry
        changed_pools[address] = pool

        # create copied changed pool with new reserves
        updated_changed_pools[address] = changed_pool = {}
        for (key, value), reserve in zip_longest(
            pool.items(), log_entry["args"].values()
        ):
            changed_pool[key] = Decimal(reserve) if reserve else value

    return updated_changed_pools, changed_pools
