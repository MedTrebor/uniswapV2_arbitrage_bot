from eth_typing import ChecksumAddress


class BlockchainError(Exception):
    """Raised when error occured in blockchain."""

    pass


class MulticallGasError(BlockchainError):
    """Error indicating that 'out of gas' was raised during call.

    Args:
        results (list[bytes] | list[tuple[bool, bytes]] | None, optional):
            `multicall.call` results. Defaults to None.
        error_idxs (list[int] | None, optional): Indecies of 'out of gas' calls.
            Defaults to None.
        args (tuple, optional): any arguments.

    Attributes:
        results (list[bytes] | list[tuple[bool, bytes]] | None):
            `multicall.call` results.
        error_idxs (list[int] | None): Indecies of 'out of gas' calls.
        args (tuple): any arguments.
    """

    def __init__(
        self,
        results: list[bytes] | list[tuple[bool, bytes]] | None = None,
        error_idxs: list[int] | None = None,
        *args: object,
    ) -> None:
        self.results = results
        self.error_idxs = error_idxs
        super().__init__(*args)


class BurnersCreationError(BlockchainError):
    """Error raised when creating burners was unsuccessful.

    Args:
        factory (ChecksumAddress): `BurnerFactory` address.
        exe_acc (ChecksumAddress): Account that was executing transaction.
        args (tuple, optional): Any argunments.

    Attributes:
        factory (ChecksumAddress): `BurnerFactory` address.
        exe_acc (ChecksumAddress): Account that was executing transaction.
    """

    def __init__(
        self, factory: ChecksumAddress, exe_acc: ChecksumAddress, *args: object
    ) -> None:
        self.factory = factory
        self.exe_acc = exe_acc
        super().__init__(*args)


class PriceNotFound(BlockchainError):
    """Raised when price for provided tokens is not found.

    Args:
        base_token (ChecksumAddress): Base token address
        quote_token (ChecksumAddress): Quite token address

    Attributes:
        base_token (ChecksumAddress): Base token address
        quote_token (ChecksumAddress): Quite token address
    """

    def __init__(
        self, base_token: ChecksumAddress, quote_token: ChecksumAddress, *args: object
    ) -> None:
        super().__init__(*args)
        self.base_token = base_token
        self.quote_token = quote_token

    def __str__(self) -> str:
        return f"Price not found for {self.base_token}/{self.quote_token}"
