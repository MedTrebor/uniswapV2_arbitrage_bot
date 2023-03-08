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
        *args: object
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
