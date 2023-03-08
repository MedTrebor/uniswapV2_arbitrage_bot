from decimal import Decimal
from threading import Lock, Thread
from typing import Optional

from network.prices import get_gas_params
from utils import CONFIG, Logger, WaitPrevious, singleton
from utils._types import GasParams

log = Logger(__name__)


class PricePollNotRunning(Exception):
    pass


@singleton
class PricePollInterval:
    """Start ETH and gas price polling object.
    Used for accessing gas parameters without waiting for response from server.
    Singleton object.

    Args:
        network (str): Blockchain network name.
        poll_interval (int | float, optional): Poll interval.
            Defaults to `CONFIG['poll']['main']`
        start (bool): Start polling thread.
        no_singleton (bool, optional): Don't create singleton instance.
            Defaults to `False`.
        new_singleton (bool, optional): Create a new singleton instance.
            Don't use old singleton instance. Defaults to `False`.
    """

    __slots__ = (
        "_error",
        "_gas_params",
        "_min_gas_price",
        "_max_gas_price",
        "_lock",
        "_network",
        "_poll_interval",
        "_running",
        "_server_poll",
        "_thread",
    )

    def __init__(
        self,
        network: str,
        poll_interval: int | float = CONFIG["poll"]["main"],
        start: bool = False,
    ) -> None:
        self._poll_interval = WaitPrevious(poll_interval)
        self._lock = Lock()
        self._network = network
        self._running = False
        self._error: Optional[Exception] = PricePollNotRunning()
        if start:
            self.start()

    def start(self) -> bool:
        """Start polling in separate thread if not yet started.

        Returns:
            bool: True if polling has started, False if polling is
                already in progress.
        """
        if self._running:
            return False

        self._running = True
        self._thread = Thread(target=self.__get_gas_params, name="Price", daemon=True)
        self._thread.start()
        return True

    def kill(self) -> None:
        """Stop polling."""
        try:
            self._running = False
            self._thread.join()
            self._error = PricePollNotRunning()
        except AttributeError:
            return

    def restart(self) -> None:
        """Restart polling."""
        self.kill()
        self.start()

    @property
    def gas_params(self) -> GasParams:
        """`gasPrice` or `maxFeePerGas` and `maxPriorityFeePerGas`."""
        with self._lock:

            if self._error:
                error, self._error = self._error, PricePollNotRunning()
                raise error from None

            return self._gas_params

    @property
    def min_gas_price(self) -> Decimal:
        """Minimum needed to pay for gas."""
        with self._lock:

            if self._error:
                error, self._error = self._error, PricePollNotRunning()
                raise error from None

            return self._min_gas_price

    @property
    def max_gas_price(self) -> Decimal:
        """Maximum to pay for gas."""
        with self._lock:

            if self._error:
                error, self._error = self._error, PricePollNotRunning()
                raise error from None

            return self._max_gas_price

    @property
    def gas_prices(self) -> tuple[Decimal, Decimal]:
        """Minumum gas price and maximum gas price."""
        with self._lock:

            if self._error:
                error, self._error = self._error, PricePollNotRunning()
                raise error from None

            return self._min_gas_price, self._max_gas_price

    def __get_gas_params(self):
        """Poll ETH and gas price on predefined interval.
        Intended to be ran at seperate thread.
        """
        try:
            self._poll_interval()

            gas_params = get_gas_params(self._network)
            with self._lock:

                try:
                    gas_price = Decimal(gas_params["gasPrice"])
                    self._min_gas_price = round(
                        gas_price * Decimal(CONFIG["price"]["min_gas_multiplier"]), 0
                    )
                    self._max_gas_price = round(
                        gas_price * Decimal(CONFIG["price"]["max_gas_multiplier"]), 0
                    )

                    self._gas_params = {"gasPrice": int(self._min_gas_price)}

                except KeyError:
                    #############################
                    ### IMPLEMENT DYNAMIC FEE ###
                    #############################
                    raise NotImplementedError("Dynamic fee not implemented") from None

                # remove error on first run
                self._error = None

            while self._running:
                self._poll_interval()

                gas_params = get_gas_params(self._network)
                with self._lock:
                    try:
                        gas_price = Decimal(gas_params["gasPrice"])
                        self._min_gas_price = round(
                            gas_price * Decimal(CONFIG["price"]["min_gas_multiplier"]),
                            0,
                        )
                        self._max_gas_price = round(
                            gas_price * Decimal(CONFIG["price"]["max_gas_multiplier"]),
                            0,
                        )

                        self._gas_params = {"gasPrice": int(self._min_gas_price)}

                    except KeyError:
                        raise NotImplementedError(
                            "Dynamic fee not implemented"
                        ) from None

        except Exception as error:
            with self._lock:
                self._running = False
                log.exception(error)
                self._error = error

    def __del__(self) -> None:
        self.kill()
