import json
from decimal import Decimal

from rich.progress import track

from utils._types import Pools


def save_pools(pools: Pools) -> None:
    """Save pools datastructure to storage.

    Args:
        pools (Pools): Pools datastructure.
    """
    # converting Decimal to integer
    int_pools = {}
    for pool_address, pool in pools.items():
        int_pool = {}
        for key, value in pool.items():
            int_flag = key == "fee_numerator" or key.startswith("0x")
            int_pool[key] = int(value) if int_flag else value
        int_pools[pool_address] = int_pool

    # saving integer pool
    try:
        with open("data/pools.json", "w") as file:
            json.dump(int_pools, file)
    except KeyboardInterrupt as error:
        with open("data/pools.json", "w") as file:
            json.dump(int_pools, file)
        raise error from None


def save_pool_numbers(pools_numbers: dict[str, int]) -> None:
    """Save pool numbers to storage.

    Args:
        pools_numbers (dict[str, int]): Mapping of factory address to pools count.
    """
    try:
        with open("data/pool_numbers.json", "w") as file:
            json.dump(pools_numbers, file)
    except KeyboardInterrupt as error:
        with open("data/pool_numbers.json", "w") as file:
            json.dump(pools_numbers, file)
        raise error from None


def load_pools() -> Pools | None:
    """Load pools datastructure from storage if it exists.

    Returns:
        Pools | None: Pools datastructure.
    """
    # loading integer pools
    try:
        with open("data/pools.json") as file:
            int_pools = json.load(file)
    except FileNotFoundError:
        return None

    # converting to Decimal
    pools = {}
    for pool_address, int_pool in int_pools.items():
        pool = {}
        for key, value in int_pool.items():
            dec_flag = key == "fee_numerator" or key.startswith("0x")
            pool[key] = Decimal(value) if dec_flag else value
        pools[pool_address] = pool

    return pools


def load_pool_numbers() -> dict[str, int] | None:
    """Load pool numbers from storage if it exists.

    Returns:
        dict[str, int] | None: Mapping of factory address to pools count.
    """
    try:
        with open("data/pool_numbers.json") as file:
            return json.load(file)
    except FileNotFoundError:
        return None


def save_unwatched_pools(pool_data: dict[str, list[int]]):
    """Save unwatched pools to storage.

    Args:
        pool_data (dict[str, list[int]]): Mapping of pool address to block numbers
    """
    # getting unwatched pools from storage
    try:
        with open("data/unwatched_pools.json") as file:
            unwatched_pools = json.load(file)
    except FileNotFoundError:
        unwatched_pools = {}

    # updating unwatched pools
    for address, block_numbers in pool_data.items():
        unwatched_pool = unwatched_pools.get(address, [])

        for block_number in block_numbers:
            if block_number in unwatched_pool:
                # checking if block number is already added
                continue
            unwatched_pool.append(block_number)

        unwatched_pool.sort()
        unwatched_pools[address] = unwatched_pool

    # saving unwatched pools to storage
    try:
        with open("data/unwatched_pools.json", "w") as file:
            json.dump(unwatched_pools, file, indent=2)
    except KeyboardInterrupt as error:
        with open("data/unwatched_pools.json", "w") as file:
            json.dump(unwatched_pools, file, indent=2)
        raise error from None


def save_all_pools(pools: Pools) -> None:
    """Save pools datastructure to storage.

    Args:
        pools (Pools): Pools datastructure.
    """
    # converting Decimal to integer
    int_pools = {}
    for pool_address, pool in track(
        pools.items(),
        description="Converting to integers",
        total=len(pools),
        transient=True,
    ):
        int_pool = {}
        for key, value in pool.items():
            int_flag = key == "fee_numerator" or key.startswith("0x")
            int_pool[key] = int(value) if int_flag else value
        int_pools[pool_address] = int_pool

    # saving integer pool
    try:
        with open("data/all_pools.json", "w") as file:
            json.dump(int_pools, file)
    except KeyboardInterrupt as error:
        with open("data/all_pools.json", "w") as file:
            json.dump(int_pools, file)
        raise error from None


def load_all_pools() -> Pools:
    """Load all pools from storage.

    Returns:
        Pools: Pools datastructure.
    """
    try:
        with open("data/all_pools.json") as file:
            int_pools = json.load(file)
    except FileNotFoundError:
        return {}

    # converting to Decimal
    pools = {}
    for pool_address, int_pool in int_pools.items():
        pool = {}
        for key, value in int_pool.items():
            dec_flag = key == "fee_numerator" or key.startswith("0x")
            pool[key] = Decimal(value) if dec_flag else value
        pools[pool_address] = pool

    return pools


def save_all_pool_numbers(all_pool_numbers: dict[str, int]) -> None:
    """Save all pool numbers to storage.

    Args:
        all_pool_numbers (dict[str, int]): Mapping of factory address to pools count.
    """
    try:
        with open("data/all_pool_numbers.json", "w") as file:
            json.dump(all_pool_numbers, file)
    except KeyboardInterrupt as error:
        with open("data/all_pool_numbers.json", "w") as file:
            json.dump(all_pool_numbers, file)
        raise error from None


def load_all_pool_numbers() -> dict[str, int] | None:
    """Load all pool numbers from storage if it exists.

    Returns:
        dict[str, int] | None: Mapping of factory address to pools count.
    """
    try:
        with open("data/all_pool_numbers.json") as file:
            return json.load(file)
    except FileNotFoundError:
        return None


def save_pool_names(pool_names: dict[str, dict[str, int | list[str]]]) -> None:
    """Save pool names to storage

    Args:
        pool_names (dict[str, str]): Mapping of pool name to number of swaps
            and pool addresses.
    """
    try:
        with open("data/pool_names.json", "w") as file:
            json.dump(pool_names, file)
    except KeyboardInterrupt as error:
        with open("data/pool_names.json", "w") as file:
            json.dump(pool_names, file)
        raise error from None


def load_pool_names() -> dict[str, dict[str, int | list[str]]]:
    """Load pool pool names from storage.

    Returns:
        dict[str, dict[str, int | list[str]]]: Mapping of pool name to number of swaps
            and pool addresses.
    """
    try:
        with open("data/pool_names.json") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


def save_proxy_pools(pools):
    # converting Decimal to integer
    int_pools = {}
    for pool_address, pool in track(
        pools.items(),
        description="Converting to integers",
        total=len(pools),
        transient=True,
    ):
        int_pool = {}
        for key, value in pool.items():
            int_flag = key == "fee_numerator" or key.startswith("0x")
            int_pool[key] = int(value) if int_flag else value
        int_pools[pool_address] = int_pool

    # saving integer pool
    try:
        with open("data/proxy_pools.json", "w") as file:
            json.dump(int_pools, file)
    except KeyboardInterrupt as error:
        with open("data/proxy_pools.json", "w") as file:
            json.dump(int_pools, file)
        raise error from None
