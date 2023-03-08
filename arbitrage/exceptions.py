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
