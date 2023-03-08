from datetime import timedelta
from decimal import Decimal
from time import perf_counter

import persistance
from utils import CONFIG, Logger
from utils._types import Pools
from web3.contract import Contract

from . import multicall
from .ww3 import Web3

log = Logger(__name__)


def get_pools(
    pools_numbers: dict[str, int] | None = None
) -> tuple[Pools, dict[str, int]]:
    """Get all the pools and number of pools from configured factories.

    If ``pools_numbers`` is provided it will get only the pools created
    after the provided number.

    Args:
        pools_numbers (dict[str, int] | None, optional): Dictionary containg
            mapping of pool address to number of pools. Defaults to None.

    Returns:
        tuple[Pools, dict[str, int]]: Mapping of pool address
            to pool and mapping of factory address to number of pools.
    """
    w3 = Web3()
    factory_contracts = [contract for contract in w3.factories[0].values()]
    latest_pools_numbers = get_pool_numbers(factory_contracts)

    # if no new pools exit the function
    if pools_numbers == latest_pools_numbers:
        log.debug("No new pools.")
        return {}, pools_numbers

    max_retries = CONFIG["max_retries"]

    # getting new pools numbers ranges
    log.debug("Downloading pool numbers ranges.")
    start = perf_counter()
    pool_numbers_ranges = get_pool_numbers_ranges(pools_numbers, latest_pools_numbers)
    log.debug(
        f"Pool numbers ranges downloaded in {timedelta(seconds=perf_counter()-start)}."
    )

    # preparing data for multicall
    log.debug("Preparing pool addresses parameters.")
    start = perf_counter()
    pools_call_params = prepare_pool_addresses_params(
        factory_contracts, pool_numbers_ranges
    )
    log.debug(
        f"Pool addresses parameters prepared in {timedelta(seconds=perf_counter()-start)}."
    )

    # getting pool addresses from blockchain
    log.debug("Downloading pool addresses.")
    start = perf_counter()
    pool_addresses = get_pool_addresses(pools_call_params, max_retries)
    log.debug(
        f"Pool addresses downloaded in {timedelta(seconds=perf_counter()-start)}."
    )

    # preparing data for multicall
    log.debug("Encoding tokens parameters.")
    start = perf_counter()
    tokens_params = prepare_tokens_params(pool_addresses)
    log.debug(
        f"Tokens parameters encoded in {timedelta(seconds=perf_counter()-start)}."
    )

    # getting tokens from blockchain
    log.debug("Downloading tokens.")
    start = perf_counter()
    tokens, invalid_pool_addresses = get_tokens(tokens_params, max_retries)
    log.debug(f"Tokens downloaded in {timedelta(seconds=perf_counter()-start)}.")

    # creating pools
    log.debug("Creating pools datastructure.")
    start = perf_counter()
    pools = create_pools(
        pool_addresses, tokens, CONFIG["factories"], invalid_pool_addresses
    )
    # logging
    count = len(pools)
    pool_s = "pool" if count == 1 else "pools"
    count = f"{count:,}" if count else "No"
    log.debug(f"{count} {pool_s} created in {timedelta(seconds=perf_counter()-start)}.")

    return pools, latest_pools_numbers


def get_pool_numbers(factory_contracts: list[Contract]) -> dict[str, int]:
    """Get pool count for each factory.

    Args:
        factory_contracts (list[Contract]): Factory contracts.

    Returns:
        dict[str, int]: Mapping of factory address to number of pools.
    """
    # encoding parameters for multicall
    multiacall_params = [
        multicall.encode(factory, "allPairsLength") for factory in factory_contracts
    ]

    # getting pools count
    encoded_results = multicall.call(multiacall_params)

    # decoding results
    uint256 = ["uint256"]
    decoded_results = [multicall.decode(res, uint256) for res in encoded_results]

    # inserting to factory_address: pool_count dictionary
    pool_numbers = {}
    for factory, result in zip(factory_contracts, decoded_results, strict=True):
        pool_numbers[factory.address] = result[0]

    return pool_numbers


def get_pool_numbers_ranges(
    old_pools_numbers: dict[str, int] | None, latest_pools_numbers: dict[str, int]
) -> list[tuple[int, int]]:
    """Get ranges of new pools numbers. First index is the first new pool and last index
    is length of pools (last index + 1).

    Args:
        old_pools_numbers (dict[str, int] | None): Mapping of old pools numbers or None.
        latest_pools_numbers (dict[str, int]): Mapping of latest pools numbers.

    Returns:
        list[tuple[int, int]]: List of first pool index and total pool count (last index + 1).
    """
    pools_numbers_ranges = []

    # create range if there are old_pools_numbers
    if old_pools_numbers:
        for factory_address, pools_number in latest_pools_numbers.items():
            old_pools_number = old_pools_numbers.get(factory_address, 0)
            pools_numbers_ranges.append((old_pools_number, pools_number))

    # create range if there are no old_pools_numbers
    else:
        for pools_number in latest_pools_numbers.values():
            pools_numbers_ranges.append((0, pools_number))

    return pools_numbers_ranges


def prepare_pool_addresses_params(
    factory_contracts: list[Contract], pool_numbers_ranges: list[tuple[int, int]]
) -> dict[str, list[tuple[str, str]]]:
    """Encode arguments for multicall call.

    Args:
        factory_contracts (list[Contract]): List of factory contracts.
        pool_numbers_ranges (list[tuple[int, int]]):
            Pool address index ranges.

    Returns:
        dict[str, list[tuple[str, str]]]: List of parameters for multicall call.
    """
    pools_addresses_params = {}

    for factory, (start_idx, stop_idx) in zip(
        factory_contracts, pool_numbers_ranges, strict=True
    ):
        # encoding arguments for one factory at a time

        single_factory_params = []
        factory_address = factory.address
        selector = ""

        for arg in range(start_idx, stop_idx):

            # caching selector in first iteration
            if not selector:
                encoded = multicall.encode(factory, "allPairs", [arg])
                selector = encoded[1][:10]
                single_factory_params.append(encoded)
                continue

            # converting argument to 256-bit hexadecimal
            hex_num = hex(arg)[2:]
            if len(hex_num) < 64:
                hex_num = "0" * (64 - len(hex_num)) + hex_num

            single_factory_params.append((factory_address, selector + hex_num))

        if not single_factory_params:
            continue

        pools_addresses_params[factory_address] = single_factory_params

    return pools_addresses_params


def get_pool_addresses(
    pools_call_params: dict[str, list[tuple[str, str]]],
    max_retreis: int,
    retries: int = 0,
) -> dict[str, list[str]]:
    """Get pool addresses by executing calls to Multicall2.

    Args:
        pools_call_params (dict[str, list[tuple[str, str]]]):
            Factory address to `Multicall` call parameters.
        max_retreis (int): Maximum retries before giving up
        retries (int, optional): Retry count. Used for reccursion.
            Defaults to 0.

    Returns:
        dict[str, list[str]]: Factory address to pool adddresses mapping.
    """
    # handling retries
    if retries > max_retreis:
        factory_address = [address for address in pools_call_params.keys()][0]
        count = len(pools_call_params[factory_address])
        invalid_idxs = [int(i[1][10:], 16) for i in pools_call_params[factory_address]]
        pool_s = "pool" if count == 1 else "pools"
        is_are = "is" if count == 1 else "are"
        idx_s = "index" if count == 1 else "indecies"
        invalid_idxs = invalid_idxs[0] if count == 1 else invalid_idxs
        log.error(
            f"{count:,} {pool_s} in Factory({factory_address}) {is_are} invalid."
            f"\nInvalid {pool_s} {idx_s}: {invalid_idxs}"
        )
        return {}

    zero_address = "0x0000000000000000000000000000000000000000"
    address_lst = ["address"]

    pool_addresses = {}
    for factory_address, single_pools_call_params in pools_call_params.items():
        # executing call to multicall
        encoded_addresses = multicall.call(single_pools_call_params)

        assert len(encoded_addresses) == len(
            single_pools_call_params
        ), "pool address count mismatch"

        # decoding addresses
        decoded_addresses, zero_address_idxs = [], []
        for i, address in enumerate(encoded_addresses):
            decoded_address = multicall.decode(address, address_lst)[0]

            # bad addresses index collecting
            if decoded_address == zero_address:
                zero_address_idxs.append(i)
                continue

            decoded_addresses.append(decoded_address)

        # retrying if there are bad addresses
        if zero_address_idxs:
            # logging
            count = len(zero_address_idxs)
            pool_s = "pool" if count == 1 else "pools"
            if not retries:
                log.warning(
                    f"{count:,} invalid {pool_s} in Factory({factory_address})."
                    " Retrying..."
                )

            # executing retry
            retry_call_params = {
                factory_address: [
                    single_pools_call_params[i] for i in zero_address_idxs
                ]
            }
            retried_addresses = get_pool_addresses(
                retry_call_params, max_retreis, retries + 1
            )

            if retried_addresses:
                decoded_addresses.extend(retried_addresses[factory_address])
                count = len(retried_addresses[factory_address])
                if not retries and count:
                    pool_s = "pool" if count == 1 else "pools"
                    log.info(f"Fixed {count:,} {pool_s}")

        pool_addresses[factory_address] = decoded_addresses

    return pool_addresses


def prepare_tokens_params(
    pool_addresses: dict[str, list[str]]
) -> dict[str, list[tuple[str, str]]]:
    """Encode tokens parameters to arguments used for multicall call.

    Args:
        pool_addresses (dict[str, list[str]]): Factory address to pool adddresses.

    Returns:
        dict[str, list[tuple[str, str]]]: Factory address to multicall
            encoded token calls.
    """
    pair_abi = persistance.get_pair_abi()
    pari_contract = Web3().eth.contract(abi=pair_abi)

    token_params = {}

    for factory_address, single_pool_addresses in pool_addresses.items():
        single_token_params = []
        for i, address in enumerate(single_pool_addresses):
            # cache encoded function calls
            if i == 0:
                _, token0 = multicall.encode(pari_contract, "token0", address=address)
                _, token1 = multicall.encode(pari_contract, "token1", address=address)

            single_token_params.append((address, token0))
            single_token_params.append((address, token1))

        token_params[factory_address] = single_token_params

    return token_params


def get_tokens(
    encoded_params: dict[str, list[tuple[str, str]]],
    max_retreis: int,
    retries: int = 0,
) -> tuple[dict[str, list[str]], dict[str, set[str]]]:
    """Get tokens and invalid pools from blockchain.

    Note:
        Pool address is omitted because there are twice as many tokens than pools.

    Args:
        encoded_params (dict[str, list[tuple[str, str]]]):
            Factory address to multicall token addreess call.
        max_retreis (int): Maximum retries before giving up
        retries (int, optional): Retry count. Used for reccursion.
            Defaults to 0.

    Returns:
        dict[str, list[str]]: Factory address to tokens mapping and
            factory address to pool address mapping
    """
    zero_address = "0x0000000000000000000000000000000000000000"
    address_lst = ["address"]

    # handling retries
    if retries > max_retreis:
        factory_address = [address for address in encoded_params.keys()][0]
        invalid_pools = {param[0] for param in encoded_params[factory_address]}
        count = len(invalid_pools)
        pool_s = "pool" if count == 1 else "pools"
        is_are = "is" if count == 1 else "are"
        log.error(
            f"{count:,} {pool_s} in Factory({factory_address}) {is_are} invalid."
            f"\nInvalid {pool_s}: {invalid_pools}"
        )
        return {}, {
            factory_address: {param[0] for param in encoded_params[factory_address]}
        }

    tokens, invalid_pools = {}, {}
    for factory_address, multicall_args in encoded_params.items():
        # executing call to blockchain
        encoded_addresses = multicall.call(multicall_args)
        assert len(encoded_addresses) == len(
            multicall_args
        ), "token address length mismatch"

        # decoding addresses
        decoded_addresses, invalid_idxs = [], []
        for i, encoded_address in enumerate(encoded_addresses):
            decoded_address = multicall.decode(encoded_address, address_lst)[0]

            # bad address index collecting
            if decoded_address == zero_address:
                invalid_idxs.append(i)

            decoded_addresses.append(decoded_address)

        # retrying if threre are bad addresses
        if invalid_idxs:
            # logging
            count = len(invalid_idxs)
            token_s = "token" if count == 1 else "tokens"
            if not retries:
                log.warning(
                    f"{count:,} invalid {token_s} in Factory({factory_address})."
                    " Retrying..."
                )

            # executing retry
            retry_call_params = {
                factory_address: [multicall_args[i] for i in invalid_idxs]
            }
            retried_addresses, retry_invalid_pools = get_tokens(
                retry_call_params, max_retreis, retries + 1
            )

            # merging retry results
            if retried_addresses:
                fix_count = 0
                for i, retried_address in zip(
                    invalid_idxs, retried_addresses[factory_address], strict=True
                ):
                    if decoded_addresses[i] != retried_address:
                        fix_count += 1
                    decoded_addresses[i] = retried_address

                # logging
                if fix_count and not retries:
                    pool_s = "pool" if fix_count == 1 else "pools"
                    log.info(
                        f"Fixed {fix_count:,} {pool_s} in Factory({factory_address})"
                    )

            invalid_pools.update(retry_invalid_pools)

        tokens[factory_address] = decoded_addresses

    return tokens, invalid_pools


def create_pools(
    pool_addresses: dict[str, list[str]],
    tokens: dict[str, list[str]],
    fees: dict[str, int | str],
    invalid_pool_addresses: dict[str, set[str]],
) -> Pools:
    """Create pools datatstrucute.

    Args:
        pool_addresses (dict[str, list[str]]): Factory address to pool addresses mapping.
        tokens (dict[str, list[str]]): Factory address to token addresses mapping.
        fees (dict[str, int  |  str]): Factory address to fee numerator or fee type mapping.
        invalid_pool_addresses (dict[str, set[str]]): Factory address to pool address mapping.

    Returns:
        Pools: Pools datastructure.
    """
    D0 = Decimal(0)

    pools = {}

    for factory_address, single_pool_addresses in pool_addresses.items():
        single_invalid_addesses = invalid_pool_addresses.get(factory_address, set())

        # getting fee
        fee = fees[factory_address]
        if type(fee) is int:
            fee_type = "fixed"
            fee_numerator = Decimal(fee)
        elif fee == "factory":
            fee_type = factory_address
            fee_numerator = D0
        else:
            fee_type = fee
            fee_numerator = D0

        single_token_addresses = tokens[factory_address]

        # sanity check
        assert len(single_pool_addresses) * 2 == len(
            single_token_addresses
        ), "pool address count and token address count mismatch"

        # creating pools
        i = 0
        for pool_address in single_pool_addresses:
            # skipping invalid pools
            if pool_address in single_invalid_addesses:
                i += 2
                continue

            pools[pool_address] = {
                single_token_addresses[i]: D0,
                single_token_addresses[i + 1]: D0,
                "fee_type": fee_type,
                "fee_numerator": fee_numerator,
            }
            i += 2

    return pools
