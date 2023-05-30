from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from functools import partial, wraps
from json import JSONDecodeError
from time import perf_counter, sleep
from typing import Any, Callable, Iterator, cast

from eth_account import Account
from eth_typing import AnyAddress, ChecksumAddress, HexStr, Primitives
from eth_utils import address as eth_address
from eth_utils import conversions, currency
from hexbytes import HexBytes
from requests import Session

import persistance
from utils import CONFIG, Logger, WaitPrevious, measure_time, singleton
from utils._types import BlockchainTx, ConfigDict, RawTransaction, TxParams, TxTrace
from utils.datastructures import SecretStr
from web3 import HTTPProvider, IPCProvider
from web3 import Web3 as _Web3
from web3 import WebsocketProvider
from web3._utils.encoding import to_json
from web3._utils.filters import LogFilter
from web3.contract import Contract
from web3.datastructures import AttributeDict
from web3.exceptions import TransactionNotFound
from web3.logs import DISCARD
from web3.middleware import (
    construct_sign_and_send_raw_middleware,
    geth_poa_middleware,
    validation,
)
from web3.types import TxReceipt, Wei

from .exceptions import BlockchainError

validation.METHODS_TO_VALIDATE.clear()

log = Logger(__name__)


@singleton
class Web3:
    """Singleton container class that holds main smart contracts.
    Has support for multiple node providers and switches between them.

    Args:
        conf (ConfigDict, optional): `config_[network].yaml` dictionary.
            Defaults to `CONFIG`.
        no_singleton (bool, optional): Don't create singleton instance.
            Defaults to `False`.
        new_singleton (bool, optional): Create a new singleton instance.
            Don't use old singleton instance. Defaults to `False`.

    Attributes:
        accounts (list[ChecksumAddress]): Account addresses.
        batch_checkers (list[Contracts]): BatchChecker contracts for each node.
        chain_id (int): Chain ID number.
        eth (Eth): Eth class of first node instance.
        factories (list[dict[ChecksumAddress, Contract]]): Factory contracts for each node.
        multicalls (list[Contract]): Multicall contracts for each node.
        nodes (list[_Web3]): web3.py.Web3 instances.
        routers (list[dict[ChecksumAddress, Contract]]): Router contracts for each node.
    """

    __slots__ = (
        "__node_idx",
        "_pool_sync_filter",
        "_sync_node",
        "other_nodes",
        "account",
        "batch_checkers",
        "burner_factory",
        "burner_generator",
        "chain_id",
        # "estimator",
        "eth",
        "factories",
        "http_sessions",
        "main_node",
        "multicalls",
        "nodes",
        "nonces",
        # pending_filter,
        "router",
        "sync_poll",
        "local_poll",
        "transfer_decoder",
        "thread_executor",
    )

    def __init__(self, conf: ConfigDict = CONFIG) -> None:
        self.chain_id = conf["blockchain"]["chain_id"]

        endpoints = conf["blockchain"]["endpoints"]
        poa = conf["blockchain"]["geth_poa_middleware"]

        self.main_node = create_web3_instances(endpoints["main"], poa=poa)[0]
        self._sync_node = create_web3_instances(endpoints["sync"], poa=poa)[0]
        self.other_nodes = create_web3_instances(*endpoints["other"], poa=poa)

        self.sync_poll = WaitPrevious(conf["poll"]["sync_node"])
        self.local_poll = WaitPrevious(conf["poll"]["main_node"])

        ############################# PATCH ################################
        #### put '_sync_node' 1st to be called with 'self.node' propery ####
        self.nodes = [self._sync_node, self.main_node, *self.other_nodes]  #
        ####################################################################
        self.eth = self.main_node.eth
        self.account = create_account(conf["blockchain"]["account"], self.nodes)
        self.burner_generator = create_account(
            conf["blockchain"]["burner_generator"], self.nodes
        )
        self.__node_idx = node_idx(1, conf["poll"]["sync_node"])
        ################################# PATCH #################################
        ######### put factory to `self.main_node` to get local ipc node #########
        self.factories = create_factories(conf["factories"], [self.main_node])  #
        #########################################################################
        self.multicalls = create_multicalls(conf["multicall"]["address"], self.nodes)
        ############################ PATCH ############################
        # put batch checker to 'self.main_mode' to get local ipc node #
        self.batch_checkers = create_batch_chackers(  #################
            conf["batch_checker"]["address"], [self.main_node]  #######
        )  ############################################################

        # self.routers = create_routers(conf["routers"], self.nodes)
        self.router = CONFIG["router"]
        """Router addresses"""
        self._pool_sync_filter = create_pool_sync_filter(
            self._sync_node, persistance.get_last_block()
        )
        self.node_idx
        self.nonces: dict[str, int] = {}  # type ignore
        self.http_sessions = create_http_sessions([endpoints["main"]])
        """Holds `requests.Session` and endpoint wrapped in `SecretStr`."""
        # self.pending_filters: list[TransactionFilter] = [
        #     node.eth.filter("pending") for node in self.nodes
        # ]
        self.node_idx
        self.transfer_decoder = create_transfer_decoder(self.main_node)
        self.burner_factory = CONFIG["burner"]["factory"]

        self.thread_executor = ThreadPoolExecutor(len(self.nodes) * 2, "Web3")
        log.debug("Created Wrapped Web3.")

    def nonce(
        self, address: ChecksumAddress, get_new: bool = False, save: bool = True
    ) -> int:
        """Get nonce for address.

        Args:
            address (ChecksumAddress): Address.
            get_new (bool, optional): Get new nonce from blockchain. Defaults to False.
            save (bool, optional): Save nonce to local `nonces`. Defaults to True.

        Returns:
            int: Nonce.
        """
        _nonce = self.nonces.get(address)

        if get_new or _nonce is None:
            _nonce = self.eth.get_transaction_count(address)

            if save:
                self.nonces[address] = _nonce

        return _nonce

    def wait_for_tx_receipt(self, tx_hash: HexBytes) -> TxReceipt:
        """Wait for transaction receipt while respecting node poll interval.

        Args:
            tx_hash (HexBytes): Transaction hash.

        Returns:
            TxReceipt: Transaction receipt.
        """
        confirmed = False
        start = perf_counter()
        while not confirmed:
            try:
                tx_receipt = self.eth.get_transaction_receipt(tx_hash)
                confirmed = True
            except TransactionNotFound as error:
                if perf_counter() - start > CONFIG["transaction"]["receipt_timeout"]:
                    raise error from None
                continue

        return tx_receipt

    def get_multiple_txs(
        self, txs: list[HexBytes], enclude_empty: bool = False
    ) -> list[BlockchainTx]:
        """Get multiple transactions in single JSON-RPC request.

        Args:
            txs (list[HexBytes]): Transaction hashes.
            enclude_empty (bool): Enclude transactions that are not found.

        Returns:
            list[BlockChainTx]: Transactions.
        """
        # foramtting requests
        requests = [
            {
                "jsonrpc": "2.0",
                "method": "eth_getTransactionByHash",
                "params": [tx.hex()],
                "id": i,
            }
            for i, tx in enumerate(txs)
        ]

        # executing request
        session, secret_url = self.http_sessions[self.node_idx]
        response = session.post(secret_url.str(), json=requests).json()

        # formatting response
        formatted_response = []
        for res in response:
            result = res["result"]
            if not result:
                if enclude_empty:
                    formatted_response.append({})
                continue
            # try:
            #     # transaction is confirmed
            #     result["blockNumber"] = int(result["blockNumber"][2:], 16)
            # except TypeError:
            #     pass

            # try:
            #     result["from"] = self.to_checksum_address(result["from"])
            # except TypeError:
            #     # transaction is not found
            #     if enclude_empty:
            #         formatted_response.append({})
            #     continue

            # result["gas"] = int(result["gas"][2:], 16)
            # result["gasPrice"] = int(result["gasPrice"][2:], 16)
            # result["nonce"] = int(result["nonce"][2:], 16)
            # if result["to"]:
            #     result["to"] = self.to_checksum_address(result["to"])
            # result["value"] = int(result["value"][2:], 16)
            formatted_response.append(result)

        return formatted_response

    def get_codes(self, addresses: list[ChecksumAddress]) -> list[str]:
        """Get blockchain code at each address from ``addresses``.

        Args:
            addresses (list[ChecksumAddress]): List of addresses.

        Returns:
            list[str]: Codes from ``addresses``.
        """
        # foramtting requests
        requests = [
            {
                "jsonrpc": "2.0",
                "method": "eth_getCode",
                "params": [address, "latest"],
                "id": i,
            }
            for i, address in enumerate(addresses)
        ]

        # executing request
        session, secret_url = self.http_sessions[self.node_idx]
        response = session.post(secret_url.str(), json=requests).json()

        # unpacking results
        results = ["" for _ in range(len(addresses))]
        for res in response:
            results[res["id"]] = res["result"]

        return results

    def get_pending_txs(self, sort: bool = True) -> list[RawTransaction]:
        """Get pending transactions.

        Args:
            sort (bool, optional): Sort transactions by gas price. Defaults to True.

        Returns:
            list[RawTransaction]: Transactions.
        """
        # requesting mempool content
        response = self.node.manager.provider.make_request("txpool_content", [])

        # iterating through response and extracting transactions
        pending_txs = []
        for mempool in response["result"].values():
            for address_txs in mempool.values():
                for tx in address_txs.values():
                    # converting gas price to integer
                    tx["gasPrice"] = int(tx["gasPrice"][2:], 16)
                    pending_txs.append(tx)

        if sort:
            # sorting transaction by gas price
            pending_txs.sort(key=lambda x: x["gasPrice"], reverse=True)

        return pending_txs

    # def get_pending_txs(self) -> list[BlockchainTx]:
    #     """Get pending transactions.

    #     Returns:
    #         list[BlockChainTx]: Transactions.
    #     """
    #     pending_txs = self.pending_filters[self.node_idx].get_new_entries()
    #     if pending_txs:
    #         return self.get_multiple_txs(pending_txs)
    #     return []

    def get_transfer_event_logs(
        self, tx_receipt: TxReceipt
    ) -> tuple[AttributeDict, ...]:
        """Get Transfer event logs from ``tx_receipt``.

        Args:
            tx_receipt (TxReceipt): Transaction receipt.

        Returns:
            tuple[AttributeDict, ...]: Transfer event logs.
        """
        return self.transfer_decoder(tx_receipt)

    def trace_transaction(self, tx_hash: str | HexBytes) -> TxTrace:
        """Trace transaction call execution.

        Args:
            tx_hash (str | HexBytes): Transaction hash.

        Returns:
            TxTrace: Tranced transaction calls.
        """
        if isinstance(tx_hash, HexBytes):
            tx_hash = tx_hash.hex()

        retries = 0
        while retries < CONFIG["max_retries"]:
            try:
                response = self.sync_node.manager.provider.make_request(
                    "debug_traceTransaction", [tx_hash, {"tracer": "callTracer"}]
                )

                if isinstance(response["result"], dict):
                    return response["result"]
            except (KeyError, JSONDecodeError):
                pass

            sleep(1 + retries)
            retries += 1

        raise BlockchainError(f"Could not get transaction trace for {tx_hash}")

    def batch_estimate_gas(self, tx_params: TxParams) -> Iterator[int | ValueError]:
        time_passed = measure_time("{}")
        results = [
            self.thread_executor.submit(wrapped_estimate_gas, node, tx_params)
            for node in [self.main_node, self._sync_node]
        ]
        for i, result in enumerate(as_completed(results), start=1):
            res, url = result.result()
            log.debug(
                f"Estimate result : {i:>2}/{len(results):>2} : [default]{url}[/] : {time_passed()} : {res}"
            )
            yield res

    def batch_transact(self, tx_params: TxParams) -> HexBytes:
        results = [
            self.thread_executor.submit(wrapped_transact, node, tx_params)
            for node in self.nodes
        ]

        for result in as_completed(results):
            hash = result.result()
            if isinstance(hash, HexBytes):
                return hash

        raise hash

    @property
    def node_idx(self) -> int:
        """Get next node index while respecting poll interval."""
        return next(self.__node_idx)

    @property
    def node(self) -> _Web3:
        """Get next main node instance while respecting poll interval."""
        return self.nodes[self.node_idx]

    @property
    def local_node(self) -> _Web3:
        """Get local node instance while respecting poll interval."""
        self.local_poll()
        return self.main_node

    @property
    def node(self) -> _Web3:
        """Get next main node instance while respecting poll interval."""
        return self.nodes[self.node_idx]

    @property
    def sync_node(self) -> _Web3:
        """Get sync node instance while respecting poll interval."""
        self.sync_poll()
        return self._sync_node

    @property
    def multicall(self) -> Contract:
        """Get next `Multicall` contract while respecting poll interval."""
        return self.multicalls[self.node_idx]

    # @property
    # def router(self) -> dict[ChecksumAddress, Contract]:
    #     """Get next address to `Router` mapping while respecting poll interval."""
    #     return self.routers[self.node_idx]

    @property
    def factory(self) -> dict[ChecksumAddress, Contract]:
        """Get next address to `Factory` mapping while respecting poll interval."""
        # patched to get main_node factory
        return self.factories[0]

    @property
    def batch_checker(self) -> Contract:
        """Get next `BatchChecker` while respecting poll interval."""
        # getting main_node batch checker
        # PATCHED
        return self.batch_checkers[0]

    @property
    def block_number(self) -> int:
        """Get block number using next in line node."""
        return self.node.eth.block_number

    @property
    def pool_sync_filter(self) -> LogFilter:
        """Get filter for `Sync` event on pool while respecting poll interval."""
        self.node_idx
        return self._pool_sync_filter

    @staticmethod
    @wraps(conversions.to_bytes)
    def to_bytes(
        primitive: Primitives = None, hexstr: HexStr = None, text: str = None
    ) -> bytes:
        return conversions.to_bytes(primitive, hexstr, text)

    @staticmethod
    @wraps(conversions.to_int)
    def to_int(
        primitive: Primitives = None, hexstr: HexStr = None, text: str = None
    ) -> int:
        """
        Converts value to its integer representation.
        Values are converted this way:

        * primitive:

        * bytes, bytearrays: big-endian integer
        * bool: True => 1, False => 0
        * hexstr: interpret hex as integer
        * text: interpret as string of digits, like '12' => 12
        """
        return conversions.to_int(primitive, hexstr, text)

    @staticmethod
    @wraps(conversions.to_hex)
    def to_hex(
        primitive: Primitives = None, hexstr: HexStr = None, text: str = None
    ) -> HexStr:
        """
        Auto converts any supported value into its hex representation.
        Trims leading zeros, as defined in:
        https://github.com/ethereum/wiki/wiki/JSON-RPC#hex-value-encoding
        """
        return conversions.to_hex(primitive, hexstr, text)

    @staticmethod
    @wraps(conversions.to_text)
    def to_text(
        primitive: Primitives = None, hexstr: HexStr = None, text: str = None
    ) -> str:
        return conversions.to_text(primitive, hexstr, text)

    @staticmethod
    @wraps(to_json)
    def to_json(obj: dict) -> str:
        """
        Convert a complex object (like a transaction object) to a JSON string
        """
        return to_json(obj)

    @staticmethod
    @wraps(currency.to_wei)
    def to_wei(number: int | float | str | Decimal, unit: str) -> Wei:
        """
        Takes a number of a unit and converts it to wei.
        """
        return cast(Wei, currency.to_wei(number, unit))

    @staticmethod
    @wraps(currency.from_wei)
    def from_wei(number: int, unit: str) -> int | Decimal:
        """
        Takes a number of wei and converts it to any other ether unit.
        """
        return currency.from_wei(number, unit)

    @staticmethod
    @wraps(eth_address.is_address)
    def is_address(value: Any) -> bool:
        """
        Is the given string an address in any of the known formats?
        """
        return eth_address.is_address(value)

    @staticmethod
    @wraps(eth_address.is_checksum_address)
    def is_checksum_address(value: Any) -> bool:
        return eth_address.is_checksum_address(value)

    @staticmethod
    @wraps(eth_address.to_checksum_address)
    def to_checksum_address(value: AnyAddress | str | bytes) -> ChecksumAddress:
        """
        Makes a checksum address given a supported format.
        """
        return eth_address.to_checksum_address(value)

    def sync_test(self, max_retries: int = CONFIG["max_retries"]) -> None:
        """Test sync between nodes.

        Args:
            max_retries (int, optional): Maximum retries if unsynced.
                Defaults to `CONFIG["max_retries"]`.

        Raises:
            BlockchainError: If nodes are unsynced after ``max_retries``.
        """
        # testing sync
        retries = 0
        while True:
            if retries > max_retries:
                raise BlockchainError("Nodes are not synced.")
            with ThreadPoolExecutor() as executor:
                # getting block number from blockchain
                futures = [
                    executor.submit(self.node.eth.get_block_number)
                    for _ in range(len(self.nodes))
                ]
                results = [future.result() for future in futures]
                print(results)

            # testing block numer equality
            unequal = False
            for i, result in enumerate(results):
                if i == 0:
                    continue
                if result != results[i - 1]:
                    unequal = True

            if unequal:
                retries += 1
                continue

            log.info(f"Blockchain nodes are synced.")
            return

    def __del__(self):
        try:
            self.thread_executor.shutdown(cancel_futures=True)
            for session, _ in self.http_sessions:
                session.close()
        except AttributeError:
            return


# def create_web3_instances(conf: BlockchainConf) -> list[_Web3]:
#     """Create Web3 instances and add middleware if necessary.

#     Args:
#         conf (Blockchain): Blockchain network configuration.

#     Returns:
#         list[_Web3]: Web3 instances.
#     """
#     nodes = []
#     for endpoint in conf["endpoints"]:
#         endpoint = endpoint.str()
#         if endpoint.startswith("http"):
#             provider = HTTPProvider(endpoint)
#         elif endpoint.startswith("ws"):
#             provider = WebsocketProvider(endpoint)
#         elif endpoint.endswith(".ipc"):
#             provider = IPCProvider(endpoint)
#         node = _Web3(provider)
#         if conf["geth_poa_middleware"]:
#             node.middleware_onion.inject(geth_poa_middleware, layer=0)
#         nodes.append(node)
#     return nodes


def create_web3_instances(*urls: SecretStr, poa: bool = False) -> list[_Web3]:
    """Create Web3 instances and add PoA middleware if necessary.

    Args:
        urls (SecretStr): Endpoint URL.
        poa (bool, optional): Proof of Authority. Defaults to False.

    Returns:
        list[_Web3]: Web3 instances.
    """
    nodes = []
    for url in urls:
        endpoint = url.str()
        if endpoint.startswith("http"):
            provider = HTTPProvider(endpoint)
        elif endpoint.startswith("ws"):
            provider = WebsocketProvider(endpoint)
        elif endpoint.endswith(".ipc"):
            provider = IPCProvider(endpoint)
        node = _Web3(provider)
        if poa:
            node.middleware_onion.inject(geth_poa_middleware, layer=0)
        nodes.append(node)
    return nodes


def create_account(pk: SecretStr, nodes: list[_Web3]) -> ChecksumAddress:
    """Create account that will autosign transactions.

    Args:
        pk (SecretStr): Private key.
        nodes (list[_Web3]): Web3 instances.

    Returns:
        ChecksumAddress: Account addresse.
    """
    account = Account.from_key(pk.str())
    auto_signer = construct_sign_and_send_raw_middleware(account)
    for node in nodes:
        node.middleware_onion.add(auto_signer)

    return account.address


def node_idx(nodes_count: int, poll_interval: int | float) -> Iterator[int]:
    """Generate indecies for next node and wait between to avoid spamming them.

    Args:
        nodes_count (int): Number of nodes.
        poll_interval (int | float): Poll interval.

    Yields:
        int: Next node index.
    """
    poll_timer = WaitPrevious(poll_interval)
    while True:
        poll_timer()
        for i in range(nodes_count):
            yield i


def create_factories(
    factory_mapping: dict[ChecksumAddress, int | str], nodes: list[_Web3]
) -> list[dict[ChecksumAddress, Contract]]:
    """Create factory contracts for each node instance.
    Contracts are arranged to match node instances indecies.

    Args:
        factory_mapping (dict[ChecksumAddress, int  |  str]): Factory address to
            fee type or fee numerator.
        nodes (list[_Web3]): Web3 instances.

    Returns:
        list[dict[ChecksumAddress, Contract]]: Factory address to list of contract instances.
    """
    abi = persistance.get_factory_abi()

    factories = []
    for node in nodes:
        node_factories = {}
        for address in factory_mapping.keys():
            node_factories[address] = node.eth.contract(address, abi=abi)
        factories.append(node_factories)

    return factories


def create_multicalls(address: ChecksumAddress, nodes: list[_Web3]) -> list[Contract]:
    """Create multicall contracts for each node instances.

    Args:
        address (Multicall): Multicall address.
        nodes (list[_Web3]): Web3 instances.

    Returns:
        list[Contract]: Multicall contracts.
    """
    abi = persistance.get_multicall_abi()

    return [node.eth.contract(address, abi=abi) for node in nodes]


def create_batch_chackers(
    address: ChecksumAddress, nodes: list[_Web3]
) -> list[Contract]:
    """Create BatchChecker contracts for each node instances.

    Args:
        address (Multicall): BatchChecker address.
        nodes (list[_Web3]): Web3 instances.

    Returns:
        list[Contract]: BatchChecker contracts.
    """
    abi = persistance.get_abi("BatchCheckerV4")
    return [node.eth.contract(address, abi=abi) for node in nodes]


# def create_routers(
#     addresses: dict[str, ChecksumAddress], nodes: list[_Web3]
# ) -> list[dict[ChecksumAddress, Contract]]:
#     """Create Router contracts for each node instance.

#     Args:
#         addresses (dict[str, ChecksumAddress]): Router addresses.
#         nodes (list[_Web3]): Web3 instances.

#     Returns:
#         list[dict[ChecksumAddress, Contract]]: Routers.
#     """
#     routers = []
#     for node in nodes:
#         node_routers = {}
#         for name, address in addresses.items():
#             abi = persistance.get_abi(name)
#             node_routers[address] = node.eth.contract(address, abi=abi)
#         routers.append(node_routers)

#     return routers


def create_pool_sync_filter(node: _Web3, block_number: int) -> LogFilter:
    """Create sync filter for pool contract.

    Args:
        node (_Web3): Web3 instance.
        block_nubmer (int): Last block number

    Returns:
        LogFilter: Pool sync filter.
    """
    new_block_number = node.eth.block_number
    if new_block_number - block_number > CONFIG["event_log"]["max_blocks"]:
        # using latest block because all pools will be updated
        block_number = "latest"  # type: ignore

    abi = persistance.get_pair_abi()
    pair = node.eth.contract(abi=abi)

    log_filter = pair.events.Sync.create_filter(fromBlock=block_number)

    return log_filter


def create_http_sessions(endpoints: list[SecretStr]) -> list[tuple[Session, SecretStr]]:
    """Create pair of session and url for each endpoint.

    Args:
        endpoints (list[SecretStr]): URLs.

    Returns:
        list[tuple[Session, SecretStr]]: Session and url wrapped in `SecretStr`.
    """
    sessions = []

    for endpoint in endpoints:
        str_endpoint = endpoint.str()

        # converting wss to https
        if str_endpoint.startswith("wss"):
            str_endpoint = "https" + str_endpoint[3:]

        # converting ws to http
        elif str_endpoint.startswith("ws"):
            str_endpoint = "http" + str_endpoint[2:]

        sessions.append((Session(), SecretStr(str_endpoint)))

    return sessions


def create_transfer_decoder(
    node: _Web3,
) -> Callable[[TxReceipt], tuple[AttributeDict, ...]]:
    token = node.eth.contract(abi=persistance.get_abi("Token"))

    return partial(token.events.Transfer().process_receipt, errors=DISCARD)


def wrapped_estimate_gas(
    node: _Web3, tx_params: TxParams
) -> tuple[object | ValueError, str]:
    url = getattr(
        node.manager.provider,
        "endpoint_uri",
        getattr(node.manager.provider, "ipc_path", ""),
    )

    gas_time = measure_time(f"[default]{url}[/] : {'{}'}")
    try:
        res = node.eth.estimate_gas(tx_params)
    except ValueError as err:
        res = err

    log.debug(gas_time())

    return res, url


def wrapped_transact(node: _Web3, tx_params: TxParams) -> HexBytes | ValueError:
    try:
        return node.eth.send_transaction(tx_params)
    except ValueError as error:
        return error
