class ArbitrageError(Exception):
    pass


class BigNumberError(ArbitrageError):
    """Number is larger than max uint112."""

    pass


class BatchDecodeError(ArbitrageError):
    """Error during decoding of `BatchChecker` results."""

    pass


class ArbArgsDecodeError(ArbitrageError):
    """Error during arbitrage arguments decoding."""

    pass


class LateTransaction(ArbitrageError):
    """Raised when it is too late to send transaction."""

    def __init__(self, delay: float, *args: object) -> None:
        """Raised when it is too late to send transaction.

        Args:
            delay (float): Time passed since block start.
        """
        super().__init__(*args)
        self.delay = delay

    def __str__(self) -> str:
        return f"{self.delay:,.2f} is to late to send transaction."


class NotProfitable(ArbitrageError):
    """Raised when non profitable transaction is estimated."""

    def __str__(self) -> str:
        return "Non profitable transaction estimated"


class MixedEstimation(ArbitrageError):
    """Raised when mixed results in gas estimation."""

    def __init__(
        self, profitables: int, nonprofitables: int, errors: int, *args: object
    ) -> None:
        super().__init__(*args)
        self.profitables = profitables
        self.nonprofitables = nonprofitables
        self.errors = errors

    def __str__(self) -> str:
        return (
            f"Mixed Results in gas estimation. "
            f"Profitables: {self.profitables:,}  "
            f"Nonprofitables: {self.nonprofitables:,}  "
            f"Errors: {self.errors:,}"
        )
