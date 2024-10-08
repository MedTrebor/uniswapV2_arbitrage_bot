from dataclasses import dataclass
from decimal import Decimal
from typing import Iterator, Literal

from eth_typing import ChecksumAddress


class SecretStr:
    """Hide sensitive information when logging.

    Args:
        text (str): Text to hide.
    """

    __slots__ = ("__text",)

    def __init__(self, text: str) -> None:
        self.__text = text

    def __str__(self) -> Literal["<SecretStr>"]:
        return "<SecretStr>"

    def __repr__(self) -> Literal["<SecretStr>"]:
        return "<SecretStr>"

    def str(self) -> str:
        """Convert ``SecretString`` to builtin ``str``."""
        return self.__text


@dataclass(slots=True)
class Arbitrage:
    """Class for storing arbitrage data."""

    path: tuple[str | ChecksumAddress, ...]
    amount_in: Decimal
    tx_cost: Decimal
    bruto_profit: Decimal
    neto_profit: Decimal
    wei_profit: Decimal
    gas_price: Decimal
    burners_cost: Decimal
    burners_count: int

    def tokens(self) -> Iterator[str | ChecksumAddress]:
        for i in range(0, len(self.path), 2):
            yield self.path[i]

    def pairs(self) -> Iterator[str | ChecksumAddress]:
        for i in range(1, len(self.path), 2):
            yield self.path[i]

    @property
    def token_in(self) -> str | ChecksumAddress:
        return self.path[0]

    @property
    def token_path(self) -> tuple[str | ChecksumAddress, ...]:
        return tuple([self.path[i] for i in range(0, len(self.path), 2)])

    def __lt__(self, other: object) -> bool:
        return self.gas_price < other.gas_price

    def __le__(self, other: object) -> bool:
        return self.gas_price <= other.gas_price

    def __gt__(self, other: object) -> bool:
        return self.gas_price > other.gas_price

    def __ge__(self, other: object) -> bool:
        return self.gas_price >= other.gas_price

    def __hash__(self) -> int:
        return hash(self.path)

    def __len__(self) -> int:
        return len(self.path) // 2
