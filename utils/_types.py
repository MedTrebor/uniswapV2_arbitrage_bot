from decimal import Decimal
from typing import TypedDict

from eth_typing import ChecksumAddress

from .datastructures import SecretStr


class Multiprocessing(TypedDict):
    workers: int
    min_chunk: int


class TransactionConf(TypedDict):
    max_delay: int | float
    gas_limit_multiplier: int | float
    min_profit: int
    gas_reductions: int
    reduction_denominator: int | float
    final_tx: int | float
    estimation_confirms: int
    receipt_timeout: int | float


class PollConf(TypedDict):
    main: int | float
    main_node: int | float
    sync_node: int | float
    pools: int | float
    price: int | float
    burners: int | float


class RestartConf(TypedDict):
    wait: int | float
    multiplier: int | float
    max_wait: int | float
    cooldown: int | float


class LoggingStream(TypedDict):
    level: str
    format: str
    date_format: str


class LoggingRotation(TypedDict):
    when: str
    interval: int
    backup_count: int


class LoggingFile(LoggingStream):
    rotation: LoggingRotation


class Logging(TypedDict):
    stream: LoggingStream
    file: LoggingFile
    traceback_width: int
    show_locals: bool


class TokenParmas(TypedDict):
    price: int
    decimals: int


class EndpointsConf(TypedDict):
    main: SecretStr
    sync: SecretStr
    other: list[SecretStr]


class BlockchainConf(TypedDict):
    name: str
    account: SecretStr
    burner_generator: SecretStr
    endpoints: EndpointsConf
    estimator: SecretStr
    chain_id: int
    geth_poa_middleware: bool


class EventLog(TypedDict):
    max_blocks: int
    block_time: int


class Multicall(TypedDict):
    address: ChecksumAddress
    size: int


class Filter(TypedDict):
    min_liquidity: int | float
    exclude: int


class Paths(TypedDict):
    length: int
    tokens: list[ChecksumAddress]
    ignored: list[ChecksumAddress]


class GasPriceConf(TypedDict):
    multiplier: int | float
    ratio: int | float


class Price(TypedDict):
    url: SecretStr
    correction: float
    low: GasPriceConf
    mid: GasPriceConf
    high: GasPriceConf
    min_gas_multiplier: int | float
    # optimal_gas_multiplier: int | float
    max_gas_multiplier: int | float


class BatchChecker(TypedDict):
    address: ChecksumAddress
    size: int


class BurnerConf(TypedDict):
    enabled: bool
    factory: ChecksumAddress
    min: int
    gas_price: int


class ConfigDict(TypedDict):
    r"""Dictionary that contains configuration from `config_[network].yaml`.

    Also hides environment variables to prevent logging sensitive information.

    To access hidden text use `.str()` method to convert to builtin ``str``::

        >>> CONFIG["email"]["password"]
        <SecretStr>
        >>> CONFIG["email"]["password"].str()
        'SomeSecretPassword'
    """
    download_pools: bool
    multiprocessing: Multiprocessing
    max_retries: int
    timeout: int | float
    transaction: TransactionConf
    poll: PollConf
    restart: RestartConf
    burner: BurnerConf
    logging: Logging
    blockchain: BlockchainConf
    event_log: EventLog
    multicall: Multicall
    filter: Filter
    paths: Paths
    weths: list[ChecksumAddress]
    price: Price
    min_gas_limits: dict[str, int]
    router: ChecksumAddress
    router_multicall: ChecksumAddress
    batch_checker: BatchChecker
    factories: dict[ChecksumAddress, int | str]
    blacklist: int


PRICES: dict[ChecksumAddress, TokenParmas]
"""Dictionary containg mapping of token address to price and decimals."""


MIN_LIQUIDITY: dict[ChecksumAddress, Decimal]
"""Dictionary containg mapping of token address to minimum liquidity.
"""


CallArgs = TypedDict(
    "CallArgs",
    {
        "from": str,
        "to": str,
        "nonce": int,
        "gasPrice": int,
        "maxFeePerGas": int,
        "maxPriorityFeePerGas": int,
        "gas": int,
        "value": int,
        "chainId": int,
    },
    total=False,
)


class GasParams(TypedDict, total=False):
    """Data about gas prices.
    For legacy blockchain: `{'gasPrice': int}`.
    For post london blockchain: `{'maxFeePerGas': int, 'maxPriorityFeePerGas': int}`.
    """

    gasPrice: int
    maxFeePerGas: int
    maxPriorityFeePerGas: int


class PoolFixedKeys(TypedDict):
    fee_type: str
    fee_numerator: Decimal


Pool = PoolFixedKeys | dict[str, Decimal]
"""Pool dictionary datastructure.

    Reserves can be accessed by providing token address as key.

    Example::
        >>> pool['0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c']
        Decimal(1239812937945)
        >>> pool['0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56']
        Decimal(1238857959698059)
        >>> pool['fee_type']
        'fixed'
        >>> pool['fee_numerator']
        Decimal(9970)
    """


Pools = dict[str, Pool]
"""Mapping of pool address to `Pool` datastructure.

    Example::
        >>> pools["0x804678fa97d91B974ec2af3c843270886528a9E6"]
        {
            '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c': Decimal(1239812937945),
            '0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56': Decimal(1238857959698059)
            'fee_type': '0x3cd1c46068daea5ebb0d3f55f6915b10648062b8',
            'fee_numerator': Decimal(9989)
        }
"""


ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
"""EVM address with all zeroes."""


BlockchainTx = TypedDict(
    "BlockchainTx",
    {
        "blockHash": str | None,
        "blockNumber": int | None,
        "from": ChecksumAddress,
        "gas": int,
        "gasPrice": int,
        "hash": str,
        "input": str,
        "nonce": int,
        "to": ChecksumAddress | None,
        "transactionIndex": str | None,
        "value": int,
        "type": str,
        "v": str,
        "r": str,
        "s": str,
    },
)
"""Formatted blockahin transaction."""


RawTransaction = TypedDict(
    "RawTransaction",
    {
        "blockHash": str | None,
        "blockNumber": str | None,
        "from": str,
        "gas": str,
        "gasPrice": int,
        "hash": str,
        "input": str,
        "nonce": str,
        "to": str | None,
        "transactionIndex": str | None,
        "value": str,
        "type": str,
        "v": str,
        "r": str,
        "s": str,
    },
)


class BurnersData(TypedDict):
    """Burners created with ``salt`` and lower case addresses without `0x`."""

    salt: int
    addresses: list[str]


BatchCheckerArgs = tuple[ChecksumAddress, list[bytes]]
"""Arguments for `BatchCheckerV4.checkArbs` function."""

BatchCheckerResult = tuple[bool, int, int]
"""`BatchChecker` results:
    * success: `bool`
    * profit: `uint112`
    * gas_usage: `uint32`
"""

TxParams = TypedDict(
    "TxParams",
    {
        "from": str,
        "to": str,
        "value": str,
        "nonce": int,
        "gas": int,
        "gasPrice": int,
        "maxFeePerGas": int,
        "maxPriorityFeePerGas": int,
        "chainId": int,
        "data": str,
    },
    total=False,
)


class SwapData(TypedDict):
    pair: ChecksumAddress
    fee_numerator: int
    is0_in: bool


class ArbArgs(TypedDict, total=False):
    selector: str
    swaps_data: list[SwapData]
    amount_in: int
    tx_cost: int
    token_in: ChecksumAddress
    first_token_out: ChecksumAddress
    token_out: ChecksumAddress
    burners_len: int
    burners: list[ChecksumAddress]


class PendingBurners(TypedDict):
    """time (float): UNIX time
    addresses (str): burners addresses in lowercase without `0x`.
    """

    time: float
    addresses: list[str]


TxTrace = TypedDict(
    "TxTrace",
    {
        "type": str,
        "from": str,
        "to": str,
        "gas": str,
        "gasUsed": str,
        "input": str,
        "output": str,
        "calls": list[dict],
    },
    total=False,
)


# class TxStats(TypedDict):
#     total: int
#     success: int
#     fail: int
#     success_rate: int | float
#     profit: int | float


class TxStats(TypedDict):
    uptime: int
    total: int
    success: int
    fail: int
    success_rate: int | float
    bnb_profit: int
    usd_profit: int


class TokenBalance(TypedDict):
    symbol: str
    balance: int
    wei_balance: int


class BalanceStats(TypedDict):
    time: str
    executor: int
    burner_generator: int
    router: list[TokenBalance]
    bnb_price: float
    burners: int
