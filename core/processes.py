from array import array
from copy import copy
import sys
from decimal import Decimal
from math import ceil
from multiprocessing import Manager
from multiprocessing.managers import SyncManager, ValueProxy
from multiprocessing.pool import Pool
from multiprocessing.process import current_process
from multiprocessing.synchronize import Lock
from threading import current_thread
from random import randrange
from ctypes import c_ulonglong

import arbitrage
import path
from utils import CONFIG, Logger, str_obj, measure_time
from utils._types import Pools
from utils.datastructures import Arbitrage
from path.blacklist import remove_from_paths

ID: int = 0
POOLS: dict[str, Pools] = {}
PATHS: dict[str, dict[str, tuple[tuple[str, ...], ...]]] = {}
LOCK: Lock


log = Logger(__name__)


def init_process(counter: ValueProxy, lock: Lock) -> None:
    with lock:
        global LOCK, ID
        LOCK = lock

        class NoTraceback:
            def write(*args):
                pass

        # sys.stderr = NoTraceback()

        num = counter.value
        ID = num

        current_process().name = f"Worker-{num}"
        current_thread().name = f"MainThread"

        counter.value += 1

        log.debug(f"[default b]{current_process().name}[/] initiated.")


def _share_pools(network: str, pools: Pools, finish_arr: array) -> None:
    global POOLS
    try:
        del POOLS[network]
    except KeyError:
        pass
    POOLS[network] = pools
    log.debug(f"Pools shared for {network}.")

    finish_arr[ID - 1] = 1
    while not all(finish_arr):
        continue


def _share_paths(
    network: str, paths: dict[str, tuple[tuple[str, ...], ...]], finish_arr: array
) -> None:
    global PATHS
    try:
        del PATHS[network]
    except KeyError:
        pass
    PATHS[network] = paths
    log.debug(f"Paths shered for {network}.")

    finish_arr[ID - 1] = 1
    while not all(finish_arr):
        continue


def share_paths(
    process_manager: SyncManager,
    process_pool: Pool,
    network: str,
    paths: dict[str, tuple[tuple[str, ...], ...]],
) -> None:
    log_str = measure_time("{:,} paths exported to workers in {}.")

    workers = CONFIG["multiprocessing"]["workers"]
    finish_arr = process_manager.Array("i", [0] * workers)
    for _ in process_pool.starmap(
        _share_paths,
        [(network, paths, finish_arr) for _ in range(workers)],
    ):
        pass
    # PATHS[network] = paths
    log.info(log_str(sum([len(_paths) for _paths in paths.values()])))


def share_pools(
    process_manager: SyncManager, process_pool: Pool, network: str, pools: Pools
) -> None:
    log_str = measure_time("{:,} pools exported to workers in {}.")

    workers = CONFIG["multiprocessing"]["workers"]
    finish_arr = process_manager.Array("i", [0] * workers)
    for _ in process_pool.starmap(
        _share_pools,
        [(network, pools, finish_arr) for _ in range(workers)],
    ):
        pass
    # POOLS[network] = pools
    log.info(log_str(len(pools)))


def _update_pools(new_pools: Pools, network: str, finished_arr: array) -> int:
    try:
        POOLS[network].update(new_pools)
    except KeyError:
        POOLS[network] = new_pools

    finished_arr[ID - 1] = 1
    while not all(finished_arr):
        continue

    return ID


def update_pools(
    process_manager: SyncManager, process_pool: Pool, new_pools: Pools, network: str
) -> None:
    workers = CONFIG["multiprocessing"]["workers"]
    finished_arr = process_manager.Array("i", [0] * workers)

    ids = {id: False for id in range(1, workers + 1)}

    for id in process_pool.starmap(
        _update_pools, [(new_pools, network, finished_arr) for _ in range(workers)]
    ):
        if ids[id]:
            log.error("ID {id} already updated pools.")
        ids[id] = True

    if not all(ids.values()):
        log.error(f"Not all workers updated: {str_obj(ids, True)}")


def get_updated_pools(network: str, changed_pools: Pools) -> Pools:
    POOLS[network].update(changed_pools)
    return POOLS[network]


def create_process_pool() -> tuple[SyncManager, Pool]:
    manager: SyncManager = Manager()
    counter = manager.Value("i", 1)
    lock = manager.Lock()

    process_pool = manager.Pool(
        CONFIG["multiprocessing"]["workers"], init_process, [counter, lock]
    )

    with lock:
        return manager, process_pool


def search_arbs(
    manager: SyncManager,
    changed_pools: Pools,
    min_gas_price: Decimal,
    max_gas_price: Decimal,
    eth_price: Decimal,
    process_pool: Pool,
    network: str,
) -> list[Arbitrage]:
    workers = CONFIG["multiprocessing"]["workers"]

    lock = manager.Lock()
    last_idx = manager.Value(c_ulonglong, 0)

    ids = {id: False for id in range(1, workers + 1)}
    arbs = []

    for arbs_chunk, id in process_pool.starmap(
        _search_arbs,
        [
            (
                changed_pools,
                min_gas_price,
                max_gas_price,
                eth_price,
                network,
                lock,
                last_idx,
            )
            for _ in range(workers)
        ],
    ):

        if ids[id]:
            log.error(f"ID {id} already used.")
        ids[id] = True
        arbs.extend(arbs_chunk)

    if not all(ids.values()):
        log.error(f"Not all ids: {str_obj(ids, True)}")

    return arbs


def _search_arbs(
    changed_pools: Pools,
    min_gas_price: Decimal,
    max_gas_price: Decimal,
    eth_price: Decimal,
    network: str,
    lock: Lock,
    last_idx: ValueProxy,
) -> tuple[list[Arbitrage], int]:
    try:
        POOLS[network].update(changed_pools)

        unique_paths = path.get_unique_paths(changed_pools, PATHS[network])

        workers_count = CONFIG["multiprocessing"]["workers"]

        chunk_size = ceil(len(unique_paths) / workers_count)

        # determin which chunk to use
        with lock:
            start_idx = copy(last_idx.value)
            end_idx = start_idx + chunk_size
            last_idx.value = end_idx

        return (
            arbitrage.search_for_arbitrages(
                POOLS[network],
                unique_paths[start_idx:end_idx],
                min_gas_price,
                max_gas_price,
                eth_price,
            ),
            ID,
        )
    except BaseException as error:
        log.exception(error)
        raise error from None


def remove_blacklisted(
    process_manager: SyncManager,
    process_pool: Pool,
    pool_to_paths: dict[str, tuple[tuple[str, ...], ...]],
    to_remove: set[tuple[str, ...]],
    network: str,
) -> None:
    workers = CONFIG["multiprocessing"]["workers"]
    finished_arr = process_manager.Array("i", [0] * workers)

    tasks = [
        process_pool.apply_async(
            _remove_blacklisted, [to_remove, network, finished_arr]
        )
        for _ in range(workers)
    ]

    remove_from_paths(pool_to_paths, to_remove)

    for task in tasks:
        task.wait()


def _remove_blacklisted(
    to_remove: set[tuple[str, ...]], network: str, finished_arr: array
) -> None:
    try:
        paths = PATHS[network]
    except KeyError:
        pass
    else:
        remove_from_paths(paths, to_remove)

    finished_arr[ID - 1] = 1
    while not all(finished_arr):
        continue
