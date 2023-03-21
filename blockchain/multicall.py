from concurrent.futures import Future, ThreadPoolExecutor

from eth_abi import decode as decodeABI
from eth_utils import to_checksum_address
from rich.progress import track

from utils import CONFIG, Logger
from utils._types import TxParams
from web3.contract import Contract

from .exceptions import BlockchainError
from .ww3 import Web3

log = Logger(__name__)


def encode(
    contract: Contract,
    func_name: str,
    args: list | None = None,
    address: str | None = None,
) -> tuple[str, str]:
    """Encode contract function call for use in multicall.
    If contract address is provided it will use it instead of `contract.address`.

    Args:
        contract (Contract): Contract.
        func_name (str): Function name.
        args (list | None, optional): Arguments for function. Defaults to None.
        address (str | None, optional): Contract address.

    Examples:
        >>> factory = w3.eth.contract(factory_address, abi=abi)
        >>> multicall.encode(factory, 'allPairs', args=[0])
        (
            '0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73',
            '0x1e3dd18b0000000000000000000000000000000000000000000000000000000000114ad7'
        )

    Returns:
        tuple[str, str]: Multicall call parameter.
    """
    contract_address = address or contract.address
    return contract_address, contract.encodeABI(func_name, args=args)


def decode(encoded_results: bytes, result_types: list[str]) -> list:
    """Decode results from `Multicall2.aggregate`.

    If result type is of type `address` it will be checksummed. Only finds pure
    `address` types. If `address` is in tuple, it will not be checksummed.

    Args:
        encoded_results (bytes): ABI encoded result from multicall.
        result_types (list[str]): Result solidity types used for decoding.

    Examples:
        >>> encoded_results = multicall.call(call_params)
        >>> encoded_result = encoded_results[0]
        >>> multicall.decode(encoded_result, ['uint112', 'uint112', 'uint32'])
        [21532048461572185866620700, 342411387807860783265265, 1664711624]

    Returns:
        list: Decoded result from multicall.
    """
    decoded_results = list(decodeABI(result_types, encoded_results))

    # searching for address type
    address_idxs = []
    for i, res_type in enumerate(result_types):
        if res_type == "address":
            address_idxs.append(i)

    # checksumming address type
    for i in address_idxs:
        decoded_results[i] = to_checksum_address(decoded_results[i])

    return decoded_results


def call(call_parameters: list[tuple[str, str]], retries: int = 0) -> list[bytes]:
    """Call `Multicall2.aggregate` function to get multiple calls in one request.

    Args:
        call_parameters (list[tuple[str, str]]): Parameters for `aggregate` function.
        retries (int): Number of retried call.

    Raises:
        BlockchainError: If ``retries`` reaches maximum retries.

    Returns:
        list[bytes]: ABI encoded results from `aggregate` function.
    """

    w3 = Web3()
    max_size = CONFIG["multicall"]["size"]
    max_retries = CONFIG["max_retries"]
    if retries > max_retries:
        raise BlockchainError(
            f"Maximum retries ({max_retries}) on '{__name__}.call' exceeded."
        )
    if retries:
        log.info(f"'{__name__}.call' retry: {retries}")

    # getting chunk size
    chunks_num, remainder = divmod(len(call_parameters), max_size)
    if remainder != 0:
        chunks_num += 1

    # spliting params
    splitted_params, first_idx, last_idx = [], 0, max_size
    for _ in range(chunks_num):
        splitted_params.append(call_parameters[first_idx:last_idx])
        first_idx = last_idx
        last_idx += max_size

    # if len(splitted_params) == 1 or len(w3.nodes) == 1:
    #     chunked_results, retry_params, retry_idxs = _call_one(splitted_params, w3)

    # else:
    #     chunked_results, retry_params, retry_idxs = _call_many(splitted_params, w3)
    chunked_results, retry_params, retry_idxs = _call_one(splitted_params, w3)

    # retrying
    if retry_idxs:
        retried_results = call(retry_params, retries + 1)
        for (i0, i1), res in zip(retry_idxs, retried_results, strict=True):
            chunked_results[i0][i1] = res

    # flattening results
    results = []
    for chunk_result in chunked_results:
        results.extend(chunk_result)

    return results


def _call_one(
    splitted_params: list[list[tuple[str, str]]], w3: Web3
) -> tuple[
    list[list[tuple[bool, bytes]]], list[tuple[str, str]], list[tuple[int, int]]
]:
    call_results, retry_params, retry_idxs = [], [], []

    for params in track(
        splitted_params,
        description="Downloading data using Multicall",
        transient=True,
    ):
        try:
            call_results.append(
                w3.multicall.functions.tryAggregate(False, params).call()
            )

        except ValueError as error:
            log.error(error)
            call_results.append([(False, b"")] * len(params))

    chunked_results = []
    # validating results
    for i0, results in track(
        enumerate(call_results),
        description="Validating results",
        total=len(call_results),
        transient=True,
    ):
        results_chunk = []
        for i1, (success, res) in enumerate(results):
            if not success or not res:
                retry_params.append(splitted_params[i0][i1])
                retry_idxs.append((i0, i1))

            results_chunk.append(res)

        chunked_results.append(results_chunk)

    return chunked_results, retry_params, retry_idxs


def _call_many(
    splitted_params: list[list[tuple[str, str]]], w3: Web3
) -> tuple[
    list[list[tuple[bool, bytes]]], list[tuple[str, str]], list[tuple[int, int]]
]:
    with ThreadPoolExecutor() as executor:
        # submitting for execution
        futures: list[Future] = []  # type: ignore

        # for params in splitted_params:
        for params in track(
            splitted_params,
            description="Downloading data using Multicall",
            transient=True,
        ):
            future = executor.submit(
                w3.multicall.functions.tryAggregate(False, params).call
            )
            futures.append(future)

        # getting chunked results
        chunked_results, retry_params, retry_idxs = [], [], []
        # for i0, future in enumerate(futures):
        for i0, future in track(
            enumerate(futures),
            description="Unpacking Multicall results",
            total=len(futures),
            transient=True,
        ):
            try:
                future_result = future.result()
            except ValueError as error:
                log.error(error)
                future_result = [(False, b"") for _ in range(len(splitted_params[i0]))]

            chunk_result = []
            for i1, (success, res) in enumerate(future_result):
                # validating results
                if not success or not res:
                    # logging
                    address, encoded_call = splitted_params[i0][i1]
                    # log.error(f"contract({address}) call({encoded_call}) returned 0 bytes")

                    # adding for retry
                    retry_params.append((address, encoded_call))
                    retry_idxs.append((i0, i1))

                chunk_result.append(res)

            chunked_results.append(chunk_result)

    return chunked_results, retry_params, retry_idxs


def try_aggregate(
    call_parameters: list[tuple[str, str | bytes]], tx_params: TxParams | None = None
) -> list[tuple[bool, bytes]]:
    """Call `Multicall2.tryAggregate` function with provided ``call_parameters``.

    Args:
        call_parameters (list[tuple[str, str  |  bytes]]): `tryAggregate` function parameters.
        tx_params (TxParmas | None, optional): Transaction parameters

    Returns:
        list[tuple[bool, bytes]]: List of success and function invocation results.
    """
    w3 = Web3()

    try:
        if not tx_params:
            return w3.multicall.functions.tryAggregate(False, call_parameters).call()
        return w3.multicall.functions.tryAggregate(False, call_parameters).call(
            tx_params
        )

    except ValueError as err:
        log.warning(err)

        if not "out of gas" in str(err):
            raise err from None

        if len(call_parameters) == 1:
            return [(False, b"")]

        idx = len(call_parameters) // 2

        return try_aggregate(call_parameters[:idx], tx_params) + try_aggregate(
            call_parameters[idx:], tx_params
        )


def check_success(
    call_parameters: list[tuple[str, str | bytes]], tx_params: TxParams | None = None
) -> list[bool]:
    """Check if calls encoded in ``call_parameters`` are successful.

    Args:
        call_parameters (list[tuple[str, str  |  bytes]]): `tryAggregate` function parameters.
        tx_params (TxParmas | None, optional): Transaction parameters

    Returns:
        list[bool]: List of success results.
    """
    return [res[0] for res in try_aggregate(call_parameters, tx_params)]


def fast_call(
    call_params: list[tuple[str, str | bytes]], tx_params: TxParams | None = None
) -> list[bytes]:
    # used 'main_node' for fast check #
    if not tx_params:
        return Web3().multicalls[1].functions.aggregate(call_params).call()[1]
    return Web3().multicalls[1].functions.aggregate(call_params).call(tx_params)[1]
