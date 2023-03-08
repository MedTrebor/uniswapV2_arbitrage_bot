from datetime import timedelta
from decimal import Decimal
from time import perf_counter

import persistance
from utils import Logger
from utils._types import Pools

from . import multicall
from .ww3 import Web3

log = Logger(__name__)


def update_pools(pools: Pools) -> None:
    """Update reserves and fee numerators for provided ``pools``.

    Args:
        pools (Pools): Pools datastructure.
    """
    if not pools:
        log.debug("No pools to updated.")
        return

    log.debug("Encoding pool update multicall parameters.")
    start = perf_counter()
    multicall_params = create_update_params(pools)
    log.debug(f"Encoding completed in {timedelta(seconds=perf_counter()-start)}.")

    log.debug("Downloading reserves and fees.")
    start = perf_counter()
    encoded_updates = multicall.call(multicall_params)
    log.debug(f"Download completed in {timedelta(seconds=perf_counter()-start)}.")

    log.debug(f"Applying downloaded reserves and fees to pools.")
    start = perf_counter()
    apply_updates(pools, encoded_updates)
    log.debug(f"Applying completed in {timedelta(seconds=perf_counter()-start)}.")


def create_update_params(pools: Pools) -> list[tuple[str, str]]:
    """Create parameters for updating pools via Multicall.

    Args:
        pools (Pools): Pools.

    Returns:
        list[tuple[str, str]]: Multicall.call parameters.
    """
    w3 = Web3()
    encoded_params = []
    get_reserves_selector, swap_fee_selector, get_pair_fees_selector = "", "", ""
    address_prefix = 24 * "0"

    pair = w3.eth.contract(abi=persistance.get_pair_abi())
    factory = w3.eth.contract(abi=persistance.get_factory_abi())

    for address, pool in pools.items():
        # ENCODING RESERVES
        # caching selector in first iteration
        if not get_reserves_selector:
            encoded = multicall.encode(pair, "getReserves", address=address)
            get_reserves_selector = encoded[1]

        encoded_params.append((address, get_reserves_selector))

        # ENCODING FEE
        fee_type = pool["fee_type"]

        if fee_type == "pool":
            # caching selector on first encounter
            if not swap_fee_selector:
                encoded = multicall.encode(pair, "swapFee", address=address)
                swap_fee_selector = encoded[1]

            encoded_params.append((address, swap_fee_selector))

        elif fee_type.startswith("0x"):
            # caching selector on first enocunter
            if not get_pair_fees_selector:
                encoded = multicall.encode(
                    factory, "getPairFees", [address], address=fee_type
                )
                get_pair_fees_selector = encoded[1][:10]

            # fee_type is factory address
            # concatenating selector + 12 bytes zeroes prefix + 20 bytes lower case address
            encoded_params.append(
                (
                    fee_type,
                    get_pair_fees_selector + address_prefix + address[2:].lower(),
                )
            )

    return encoded_params


def apply_updates(pools: Pools, encoded_updates: list[bytes]) -> None:
    """Apply updated reserves and fees to pools.

    Args:
        pools (Pools): Pools.
        encoded_updates (list[bytes]): Multicall.tryAggregate results.
    """
    reserve_type = ["uint112", "uint112", "uint32"]
    uint32, uint256 = ["uint32"], ["uint256"]

    i = 0
    for pool in pools.values():
        # applying reserves
        *reserves, _ = multicall.decode(encoded_updates[i], reserve_type)
        i += 1

        for token_key, reserve in zip(pool.keys(), reserves):
            pool[token_key] = Decimal(reserve)

        # applying fee numerator
        fee_type = pool["fee_type"]

        if fee_type == "pool":
            fee = multicall.decode(encoded_updates[i], uint32)[0]
            i += 1

            pool["fee_numerator"] = Decimal(10_000 - fee * 10)

        elif fee_type.startswith("0x"):
            fee = multicall.decode(encoded_updates[i], uint256)[0]
            i += 1

            pool["fee_numerator"] = Decimal(10_000 - fee)

    # sanity check
    assert i == len(encoded_updates), "Results length don't match pools"
