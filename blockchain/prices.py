from copy import deepcopy
from decimal import Decimal
from threading import Lock

from eth_typing import ChecksumAddress
from rich import print

from utils import CONFIG, Logger
from utils._types import Pools

from . import multicall
from .exceptions import PriceNotFound, BlockchainError
from .update import apply_updates, create_update_params
from .ww3 import Web3


log = Logger(__name__)


_prices: dict[ChecksumAddress, dict[ChecksumAddress, Decimal]] = {}
_lock: Lock = Lock()
_weth: ChecksumAddress = CONFIG["weths"][0]
_gas_price: Decimal


def update_prices(price_pools: Pools) -> None:
    """Update prices of tokens and gas price.

    Args:
        price_pools (Pools): Pools to get prices from.
    """
    global _gas_price, _lock

    update_price_pools(price_pools)
    all_reserves = extract_all_reserves(price_pools)
    update_global_prices(all_reserves)

    # with _lock:
    #     _gas_price = Web3().eth.gas_price
    _gas_price = Decimal(int(3e9))


def get_price(base_token: ChecksumAddress, quote_token: ChecksumAddress) -> Decimal:
    """Get amount of ``quote_token`` needed to get 1 ``base_token``.

    Args:
        base_token (ChecksumAddress): Base token address.
        quote_token (ChecksumAddress): Quote token address.

    Raises:
        PriceNotFound: If there is no entry for ``base_token``/``quote_token`` price.

    Returns:
        Decimal: ``quote_token`` needed to get ` ``base_token``.
    """
    # return 1 if both tokens are eth
    if base_token in CONFIG["weths"] and quote_token in CONFIG["weths"]:
        return Decimal(1)

    global _prices, _lock

    with _lock:
        try:
            return _prices[base_token][quote_token]
        except KeyError:
            raise PriceNotFound(base_token, quote_token) from None


def get_prices() -> dict[ChecksumAddress, dict[ChecksumAddress, Decimal]]:
    """Ged deepcopy of token to token to price mapping.

    Returns:
        dict[ChecksumAddress, dict[ChecksumAddress, Decimal]]: Token to token to price mapping.
    """
    global _prices, _lock

    with _lock:
        return deepcopy(_prices)


def get_weth_prices() -> dict[ChecksumAddress, Decimal]:
    """Get mapping of token to weth price.

    Returns:
        dict[ChecksumAddress, Decimal]: Token to weth price mapping.
    """
    global _prices, _lock, _weth

    with _lock:
        return _prices[_weth]


def get_weth_price(quote_token: ChecksumAddress) -> Decimal:
    """Get amount of ``quote_token`` needed to get 1 `WETH`.

    Args:
        quote_token (ChecksumAddress): Quote token address.

    Raises:
        PriceNotFound: If there is no entry for ``WETH``/``quote_token``.

    Returns:
        Decimal: Amount of ``quote_token`` needed to get 1 `WETH`.
    """
    if quote_token in CONFIG["weths"]:
        return Decimal(1)

    global _prices, _lock, _weth

    with _lock:
        try:
            return _prices[_weth][quote_token]
        except KeyError:
            raise PriceNotFound(_weth, quote_token)


def get_nonweth_price(base_token: ChecksumAddress) -> Decimal:
    """Get amount of ``WETH`` needed to get 1 ``base_token``.

    Args:
        base_token (ChecksumAddress): Base token address.

    Raises:
        PriceNotFound: If there is no entry for ``base_token``/`WETH`.

    Returns:
        Decimal: Amount of ``WETH`` needed to get 1 ``base_token``.
    """
    if base_token in CONFIG["weths"]:
        return Decimal(1)

    global _prices, _lock, _weth

    with _lock:
        try:
            return _prices[base_token][_weth]
        except KeyError:
            raise PriceNotFound(base_token, _weth) from None


def get_gas_price() -> Decimal:
    """Get gas price.

    Returns:
        Decimal: Gas price in `WEI`.
    """
    global _gas_price, _lock

    with _lock:
        return _gas_price


def update_price_pools(price_pools: Pools) -> None:
    """Update reserves and fee numerators for ``price_pools``.

    Args:
        price_pools (Pools): Pools to get prices from.
    """
    multicall_params = create_update_params(price_pools)
    encoded_updates = multicall.fast_call(multicall_params)

    # check if all results are present
    retries = 0
    while not all(encoded_updates):
        if retries >= CONFIG["max_retries"]:
            raise BlockchainError(
                f"Maximum retries ({CONFIG['max_retries']:,})"
                " for updating price pools exceeded"
            )
        # use sync node for retry calls
        encoded_updates = multicall.call(multicall_params)
        retries += 1

    apply_updates(price_pools, encoded_updates)


def extract_all_reserves(
    price_pools: Pools,
) -> dict[ChecksumAddress, dict[ChecksumAddress, list[tuple[Decimal, Decimal]]]]:
    """Extract reserves from ``price_pools`` and group them together.

    Args:
        price_pools (Pools): Pools to get prices from.

    Returns:
        dict[ChecksumAddress, dict[ChecksumAddress, list[tuple[Decimal, Decimal]]]]:
            Token to token to list of (reserve0, reserve1).
    """
    all_reserves: dict[
        ChecksumAddress, dict[ChecksumAddress, list[tuple[Decimal, Decimal]]]
    ] = {}
    for pool in price_pools.values():
        # getting pair tokens and reserves
        tokens, reserves = ["", ""], [Decimal(0), Decimal(0)]
        for (token, reserve), i in zip(pool.items(), range(2)):
            tokens[i] = token
            reserves[i] = reserve

        # add to all reserves only in one direction
        try:
            token0_reserves = all_reserves[tokens[0]]
            try:
                token0_reserves[tokens[1]].append((reserves[0], reserves[1]))
            except KeyError:
                token0_reserves[tokens[1]] = [(reserves[0], reserves[1])]
        except KeyError:
            all_reserves[tokens[0]] = {tokens[1]: [(reserves[0], reserves[1])]}

    return all_reserves


def update_global_prices(
    all_reserves: dict[
        ChecksumAddress, dict[ChecksumAddress, list[tuple[Decimal, Decimal]]]
    ]
):
    """Update global `_prices` mapping.

    Args:
        all_reserves (dict[ ChecksumAddress, dict[ChecksumAddress, list[tuple[Decimal, Decimal]]] ]):
            Token to token to list of (reserve0, reserve1).
    """
    global _prices, _lock

    # update global prices
    with _lock:
        for token0, token_1_to_resreves in all_reserves.items():
            for token1, reserves in token_1_to_resreves.items():
                # getting sum of reserves
                reserve0 = reserve1 = Decimal(0)
                for _reserve0, _reserve1 in reserves:
                    reserve0 += _reserve0
                    reserve1 += _reserve1

                # first token update
                token0_price = reserve1 / reserve0

                try:
                    token0_prices = _prices[token0]
                    token0_prices[token1] = token0_price

                except KeyError:
                    _prices[token0] = {token1: token0_price}

                # second token update
                token1_price = reserve0 / reserve1

                try:
                    token1_prices = _prices[token1]
                    token1_prices[token0] = token1_price

                except KeyError:
                    _prices[token1] = {token0: token1_price}


def add_weth_prices() -> None:
    """Add all combinations of weth to weth mappings with 1 as price."""
    global _lock, _prices

    with _lock:
        for weth0 in CONFIG["weths"]:
            for weth1 in CONFIG["weths"]:
                try:
                    weth0_prices = _prices[weth0]
                    weth0_prices[weth1] = Decimal(1)

                except KeyError:
                    _prices[weth0] = {weth1: Decimal(1)}
