from multiprocessing.pool import Pool as ProcessPool
from typing import Optional

import blockchain
import path
import persistance
from utils import CONFIG, Logger, measure_time
from utils._types import Pools

log = Logger(__name__)


def load_data() -> (
    tuple[Pools, dict[str, int], int, set[tuple[str, ...]], dict[tuple[str, ...], int]]
):
    """Load data from storage or download if storage is empty.

    Returns:
        tuple[
            Pools, dict[str, int], int, dict[str, list[int]],
            list[list[str]], set[tuple[str, ...]], dict[tuple[str, ...],
            int]
        ]: Pools, pool numbers, last block info, pool to path index mapping,
            paths, blacklisted paths, pre blacklisted paths (path to revert
            message to revert count mapping).
    """
    # loading data from storage
    pools = persistance.load_pools()
    pool_numbers = persistance.load_pool_numbers()
    blacklist_paths = persistance.load_blacklist_paths()
    pre_blacklist_paths = persistance.load_pre_blacklist_paths()
    last_block_number = persistance.get_last_block()

    update_all_pools = False

    # load all pools from storage
    if not pools:
        update_all_pools = True

        pools = persistance.load_all_pools()
        pool_numbers = persistance.load_all_pool_numbers()

    # get all pools if there are none
    if not pools:
        pools, pool_numbers = get_all_pools()

    # update pools if all pools are downloaded or loaded
    if update_all_pools:
        log_str = measure_time("Updated all pools [default not b]({:,})[/] in {}.")
        blockchain.update_pools(pools)
        log.info(log_str(len(pools)))

    return (
        pools,
        pool_numbers,
        last_block_number,
        blacklist_paths,
        pre_blacklist_paths,
    )


def get_all_pools() -> tuple[Pools, dict[str, int]]:
    """Download all pools from blockchain.

    Returns:
        tuple[Pools, dict[str, int]]: Pools.
    """
    log.info("Getting all pools.")
    log_str = measure_time("All pools downloaded in {}.")
    pools, pool_numbers = blockchain.get_pools()
    log.info(log_str())

    log_str = measure_time("All pools saved in {}.")
    persistance.save_all_pools(pools)
    persistance.save_all_pool_numbers(pool_numbers)
    log.info(log_str())

    return pools, pool_numbers


def get_new_pools(
    pool_numbers: dict[str, int], all_pools: Optional[Pools] = None
) -> tuple[Pools, dict[str, int]]:
    """Download newly added pools.

    Args:
        pool_numbers (dict[str, int]): Factory address to pool count mapping.
        all_pools (Pools): Pools without filtering.

    Returns:
        tuple[Pools, dict[str, int]]: Pools and factory address to pool count mapping.
    """
    log.info("Getting new pools.")

    log_str = measure_time("{:,} {} downloaded in {}.")
    new_pools, pool_numbers = blockchain.get_pools(pool_numbers)
    pool_s = "pool" if len(new_pools) == 1 else "pools"
    log.info(log_str(len(new_pools), pool_s))

    if all_pools:
        all_pools.update(new_pools)

        log_str = measure_time("New pools saved in {}.")
        persistance.save_all_pools(all_pools)
        persistance.save_all_pool_numbers(pool_numbers)
        log.info(log_str())

    return new_pools, pool_numbers


def update_and_filter_pools(pools: Pools, pool_numbers: dict[str, int]) -> Pools:
    """Update pool data and remove low liquidity pools.

    Args:
        pools (Pools): Pools
        pool_numbers (dict[str, int]): Factory address to pool count mapping.

    Returns:
        Pools: Pools.
    """
    log.info("Updating pools")

    log_str = measure_time("Finished updating pools in {}.")
    blockchain.update_pools(pools)
    log.info(log_str())

    log_str = measure_time("Finished filtering pools in {}.")
    blockchain.filter_pools(pools, pool_numbers)
    log.info(log_str())

    log_str = measure_time("Finished saving {:,} pools in {}.")
    persistance.save_pools(pools)
    persistance.save_pool_numbers(pool_numbers)
    log.info(log_str(len(pools)))

    return pools


def build_paths(
    pools: Pools, blacklist_paths: set[str], process_pool: ProcessPool
) -> dict[str, tuple[tuple[str, ...], ...]]:
    """Build paths.

    Args:
        pools (Pools): Pools
        blacklist_paths (set[str]): Blacklisted paths.
        process_pool (ProcessPool): Porcess Pool.

    Returns:
        dict[str, tuple[tuple[str, ...], ...]]: Pool address to paths.
    """
    log_str = measure_time("Finished building graph in {}.")
    graph = path.build_graph(pools)
    log.debug(log_str())

    pool_to_paths = path.build_paths(
        graph,
        CONFIG["paths"]["tokens"],
        CONFIG["paths"]["length"],
        blacklist_paths,
        process_pool,
        set(CONFIG["paths"]["ignored"]),
    )

    return pool_to_paths
