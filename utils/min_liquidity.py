from decimal import Decimal

from pyaml_env import parse_config

from .config import CONFIG
from ._types import TokenParmas, ChecksumAddress


PRICES: dict[ChecksumAddress, TokenParmas] = parse_config("prices.yaml")
"""Dictionary containg mapping of token address to price and decimals."""

MIN_LIQUIDITY: dict[str, Decimal] = {}  # type: ignore
"""Dictionary containg mapping of token address to minimum liquidity.
"""


def load_min_liquidity() -> None:
    """Load `min_liquidity.yaml` and convert it to mapping
    of token address to minimum liquidity.
    """
    global MIN_LIQUIDITY
    MIN_LIQUIDITY = {}

    min_liqidity = Decimal(CONFIG["filter"]["min_liquidity"])
    d10 = Decimal(10)

    for address, data in PRICES.items():
        MIN_LIQUIDITY[address] = Decimal(
            round(
                min_liqidity
                / Decimal(data["price"])
                * (d10 ** Decimal(data["decimals"]))
            )
        )


load_min_liquidity()
