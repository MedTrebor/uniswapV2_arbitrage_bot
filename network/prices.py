from decimal import Decimal
from time import sleep

import requests

from utils import CONFIG, PRICES, Logger
from utils._types import GasParams

from .exceptions import GasPriceError

log = Logger(__name__)

LEGACY_NETWORKS = {"bsc"}

D1 = Decimal(1)
D10 = Decimal(10)
D1E9 = Decimal("1e9")
D1E18 = Decimal("1e18")

eth_price: Decimal


def get_gas_params(network: str) -> GasParams:
    """Get maximum gas parameters for every account and gas parameters for ``network``.
    If it's legacy network it uses `gasPrice`, and if it's post london network,
    it uses `maxFeePerGas` and `maxPriorityFeePerGas`.

    Args:
        network (str): Network name.

    Raises:
        requests.HTTPError: If status code was for error and maximum retries occured.
        requests.ConnectionError: If there was no connection and maximum retries occured.

    Returns:
        GasParams: `gasPrice`, `maxFeePerGas`, `maxPriorityFeePerGas`.
    """
    if network in LEGACY_NETWORKS:
        gas_price = get_gas_price()

        return {"gasPrice": gas_price}


def get_gas_price(retries: int = 0) -> int:
    """Get WEI gas prices.

    Args:
        retries (int, optional): Retry cont. Used for error. Defaults to 0.

    Raises:
        requests.HTTPError: If status code was for error and maximum retries occured.
        requests.ConnectionError: If there was no connection and maximum retries occured.

    Returns:
        int: Fastest gas price in WEI.
    """
    global eth_price
    conf = CONFIG["price"]

    if retries:
        # logging and waiting to avoid spaming the server
        log.info(f"'{__name__}.get_gas_price' retry: {retries}")
        sleep(CONFIG["poll"]["price"] + retries)

    try:
        # getting response and converting to JSON
        response = requests.get(conf["url"].str())
        response.raise_for_status()
        response = response.json()

    except requests.HTTPError as error:
        # handling HTTPError
        if retries == CONFIG["max_retries"]:
            raise error from None
        log.error(f"Gas price request failed with status code:{response.status_code}")
        return get_gas_price(retries + 1)

    except requests.ConnectionError as error:
        # handling ConnectionError
        if retries == CONFIG["max_retries"]:
            raise error from None
        log.error("Failed to establish connection")
        return get_gas_price(retries + 1)

    if response["status"] == "0":
        # bad response error
        log.error("Failed to get successful response")
        if retries == CONFIG["max_retries"]:
            raise GasPriceError(response)
        return get_gas_price(retries + 1)

    # getting fast gas price and converting to WEI
    gwei_price = Decimal(response["result"]["FastGasPrice"])

    if gwei_price == 0:
        # no gas price error
        log.error("Got 0 gas price")
        if retries == CONFIG["max_retries"]:
            raise GasPriceError(response)
        return get_gas_price(retries + 1)

    # updating eth price
    eth_price = Decimal(response["result"]["UsdPrice"])

    return round(gwei_price * D1E9)


def wei_usd_price(address: str, _eth_price: Decimal | None = None) -> Decimal:
    """Get price of 1 WEI(1e-18 ETH) in USD token(with provided ``address``).
    Looks at token decimals to give appropriate price. If token is WETH, price is 1.

    Args:
        address (str): Token address.
        _eth_price (Decimal | None, optional): ETH price in USD.
            Defaults to global ``eth_price``.

    Returns:
        Decimal: Price of WEI in token.
    """
    if not _eth_price:
        _eth_price = eth_price

    if _is_price_token(address):
        return D1

    return _eth_price * token_decimals(address) / D1E18


def _is_price_token(address: str) -> bool:
    """Check if token is price token.

    Note:
        Price token is main token and price for it should not
            be calculated.

    Args:
        address (str): Token address.

    Returns:
        bool: `True` or `False`.
    """
    price_tokens = CONFIG["weths"]

    return address in price_tokens


def token_decimals(address: str) -> Decimal:
    """Get multiplier for decimals.

    Example:
        >>> usdt = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
        >>> _token_decimals(usdt)
        Decimal('1E+6')

    Args:
        address (str): Token address.

    Returns:
        Decimal: Multiplier.
    """
    ### INTEGRATE DIFFERENT CHAINS ###
    ##################################
    return D10 ** Decimal(PRICES[address]["decimals"])
