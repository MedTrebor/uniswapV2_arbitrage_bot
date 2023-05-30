from copy import deepcopy
from decimal import Decimal
from threading import Lock, Thread
from typing import Optional

import persistance
from blockchain import prices
from utils import CONFIG, Logger, WaitPrevious, singleton
from utils._types import GasParams, Pools

log = Logger(__name__)


class PricePollNotRunning(Exception):
    pass


@singleton
class PricePollInterval:
    """Start ETH and gas price polling object.
    Used for accessing gas parameters without waiting for response from server.
    Singleton object.

    Args:
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
        "_mid_gas_price",
        "_min_gas_price",
        "_max_gas_price",
        "_lock",
        "_low_gas_price",
        "_poll_interval",
        "_price_pools",
        "_running",
        "_server_poll",
        "_thread",
    )

    def __init__(
        self,
        poll_interval: int | float = CONFIG["poll"]["main"],
        start: bool = False,
    ) -> None:
        self._price_pools = create_price_pools()
        self._poll_interval = WaitPrevious(poll_interval)
        self._lock = Lock()
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
    def is_running(self) -> bool:
        """Check if price pool is running."""
        with self._lock:
            return self._running

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
    def low_gas_price(self) -> Decimal:
        """Low gas price."""
        with self._lock:
            if self._error:
                error, self._error = self._error, PricePollNotRunning()
                raise error from None

            return self._low_gas_price

    @property
    def mid_gas_price(self) -> Decimal:
        """Medium gas price."""
        with self._lock:
            if self._error:
                error, self._error = self._error, PricePollNotRunning()
                raise error from None

            return self._mid_gas_price

    @property
    def max_gas_price(self) -> Decimal:
        """Maximum to pay for gas."""
        with self._lock:
            if self._error:
                error, self._error = self._error, PricePollNotRunning()
                raise error from None

            return self._max_gas_price

    @property
    def gas_prices(self) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        """Minumum, low, medium and maximum gas prices."""
        with self._lock:
            if self._error:
                error, self._error = self._error, PricePollNotRunning()
                raise error from None

            return (
                self._min_gas_price,
                self._low_gas_price,
                self._mid_gas_price,
                self._max_gas_price,
            )

    def __get_gas_params(self):
        """Poll ETH and gas price on predefined interval.
        Intended to be ran at seperate thread.
        """
        try:
            self._poll_interval()
            prices.update_prices(self._price_pools)

            with self._lock:
                gas_price = prices.get_gas_price()
                self._min_gas_price = round(
                    gas_price * Decimal(CONFIG["price"]["min_gas_multiplier"]), 0
                )
                self._low_gas_price = round(
                    gas_price * Decimal(CONFIG["price"]["low"]["multiplier"]), 0
                )
                self._mid_gas_price = round(
                    gas_price * Decimal(CONFIG["price"]["mid"]["multiplier"]), 0
                )
                self._max_gas_price = round(
                    gas_price * Decimal(CONFIG["price"]["max_gas_multiplier"]), 0
                )

                self._gas_params = {"gasPrice": int(self._min_gas_price)}

                # remove error on first run
                self._error = None

            while self._running:
                self._poll_interval()
                prices.update_prices(self._price_pools)

                with self._lock:
                    gas_price = prices.get_gas_price()
                    self._min_gas_price = round(
                        gas_price * Decimal(CONFIG["price"]["min_gas_multiplier"]),
                        0,
                    )
                    self._low_gas_price = round(
                        gas_price * Decimal(CONFIG["price"]["low"]["multiplier"]), 0
                    )
                    self._mid_gas_price = round(
                        gas_price * Decimal(CONFIG["price"]["mid"]["multiplier"]), 0
                    )
                    self._max_gas_price = round(
                        gas_price * Decimal(CONFIG["price"]["max_gas_multiplier"]),
                        0,
                    )

                    self._gas_params = {"gasPrice": int(self._min_gas_price)}

        except Exception as error:
            with self._lock:
                self._running = False
                log.exception(error)
                self._error = error

    def __del__(self) -> None:
        self.kill()


def create_price_pools() -> Pools:
    all_pools = persistance.load_pools()

    tokens = set(CONFIG["paths"]["tokens"])
    weths = set(CONFIG["weths"])
    tokens.difference_update(weths)

    price_pools = {}

    for pool_address, pool in all_pools.items():
        # search token
        has_weth = has_regular = False
        for token_address, _ in zip(pool.keys(), range(2)):
            if token_address in tokens:
                has_regular = True
                continue
            if token_address in weths:
                has_weth = True

        # add to price pools
        if has_regular and has_weth:
            price_pools[pool_address] = deepcopy(pool)

    return price_pools
