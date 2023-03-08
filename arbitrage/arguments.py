from decimal import Decimal

from eth_typing import ChecksumAddress
from eth_utils.address import to_checksum_address

from utils import CONFIG, Logger
from utils._types import ArbArgs, BatchCheckerArgs, Pools
from utils.datastructures import Arbitrage

from .exceptions import ArbArgsDecodeError, ArbitrageError

log = Logger(__name__)


def create_arb_args(arb: Arbitrage, pools: Pools, burners: list[str] = []) -> str:
    """Create arguments for arbitrage transaction.

    Args:
        arb (Arbitrage): Arbitrage datastructure.
        pools (Pools): Pools datastructure.
        burners (list[str], optional): Burners addresses.

    Raises:
        ArbitrageError: If selector can not be extracted.

    Returns:
        str: Arbitrage transaction arguments (calldata).
    """
    path = arb.path

    # getting tokens for arguments
    token_in, token_out = shift_address(path[0]), shift_address(path[-1])
    first_token_out = shift_address(path[2])
    same = token_in == token_out

    # getting selector
    match len(arb), same:
        case (2, True):
            selector = "01"
        case (2, False):
            selector = "02"
        case (3, True):
            selector = "03"
        case (3, False):
            selector = "04"
        case _:
            raise ArbitrageError(f"Selector can't be extracted for {arb}")

    # getting amount in and transaction cost
    amount_in = to_hex_uint112(arb.amount_in)
    tx_cost = to_hex_uint112(arb.tx_cost)

    # getting pairs, fee numerators and is 0 ins
    pairs, fee_numerators, is_0_ins = [], [], []
    for i in range(1, len(path), 2):
        pair = path[i]
        pairs.append(shift_address(pair))

        pool = pools[pair]

        for token in pool.keys():
            is_0_in = "01" if token == path[i - 1] else "00"
            is_0_ins.append(is_0_in)
            break

        fee_numerators.append(to_hex_uint16(pool["fee_numerator"]))

    # getting hexadecimal burners
    if burners:
        hex_burners = to_hex_uint8(len(burners)) + "".join(burners)
    else:
        hex_burners = "01" if CONFIG["burner"]["enabled"] else ""

    # packing it all
    args = (
        "0x"
        + selector
        + pairs[0]
        + amount_in
        + fee_numerators[0]
        + is_0_ins[0]
        + pairs[1]
        + fee_numerators[1]
        + is_0_ins[1]
    )

    if len(pairs) == 3:
        args += pairs[2] + fee_numerators[2] + is_0_ins[2]

    args += tx_cost + token_in + first_token_out

    if not same:
        args += token_out

    return args + hex_burners


def create_all_batch_args(arbs: list[Arbitrage], pools: Pools) -> BatchCheckerArgs:
    """Create arguments for `BatchChecker.checkArbs` call.

    Args:
        arbs (list[Arbitrage]): Arbitrage datastructures.
        pools (Pools): Pools datastructures.

    Returns:
        BatchCheckerArgs: `BatchChecker.checkArbs` arguments.
    """
    router_address = CONFIG["router"]
    chunk = CONFIG["batch_checker"]["size"]

    # creating all batch checker arguments
    all_batch_args = []
    for i in range(0, len(arbs), chunk):

        # creating arguments for each arb
        arb_args = [
            bytes.fromhex(create_arb_args(arb, pools)[2:])
            for arb in arbs[i : i + chunk]
        ]

        all_batch_args.append((router_address, arb_args))

    return all_batch_args


def decode_arb_args(calldata: str) -> ArbArgs:
    """Decode encoded arbitrage arguments (calldata).

    Args:
        calldata (str): Arbitrage arguments.

    Returns:
        ArbArgs: Decoded arbitrage arguments.
    """
    if calldata.startswith("0x"):
        calldata = calldata[2:]

    selector = calldata[:2]
    match selector:
        case "01":
            swaps = 2
            tx_cost = int(calldata[126:154], 16)
            token_in = unshift_address(calldata[154:196])
            first_token_out = unshift_address(calldata[196:238])
            token_out = ""
            try:
                burners_len = int(calldata[238:240], 16)
            except ValueError:
                burners_len = 0
            burners_start = 240
        case "02":
            swaps = 2
            tx_cost = int(calldata[126:154], 16)
            token_in = unshift_address(calldata[154:196])
            first_token_out = unshift_address(calldata[196:238])
            token_out = unshift_address(calldata[238:280])
            try:
                burners_len = int(calldata[280:282], 16)
            except ValueError:
                burners_len = 0
            burners_start = 282
        case "03":
            swaps = 3
            tx_cost = int(calldata[174:202], 16)
            token_in = unshift_address(calldata[202:244])
            first_token_out = unshift_address(calldata[244:286])
            token_out = ""
            try:
                burners_len = int(calldata[286:288], 16)
            except ValueError:
                burners_len = 0
            burners_start = 288
        case "04":
            swaps = 3
            tx_cost = int(calldata[174:202], 16)
            token_in = unshift_address(calldata[202:244])
            first_token_out = unshift_address(calldata[244:286])
            token_out = unshift_address(calldata[286:328])
            try:
                burners_len = int(calldata[328:330], 16)
            except ValueError:
                burners_len = 0
            burners_start = 330
        case _:
            raise ArbArgsDecodeError()

    amount_in = int(calldata[44:72], 16)

    swaps_data = []
    for i in range(swaps):
        data = {}

        if i == 0:
            data["pair"] = unshift_address(calldata[2:44])
            data["fee_numerator"] = int(calldata[72:76], 16)
            data["is0_in"] = bool(int(calldata[76:78], 16))

        elif i == 1:
            data["pair"] = unshift_address(calldata[78:120])
            data["fee_numerator"] = int(calldata[120:124], 16)
            data["is0_in"] = bool(int(calldata[124:126], 16))

        else:
            data["pair"] = unshift_address(calldata[126:168])
            data["fee_numerator"] = int(calldata[168:172], 16)
            data["is0_in"] = bool(int(calldata[172:174], 16))

        swaps_data.append(data)

    burners = []
    for i in range(burners_start, burners_start + burners_len * 40, 40):
        address = calldata[i : i + 40]
        if not address:
            break
        burners.append(to_checksum_address(address))

    args = {
        "selector": selector,
        "swaps_data": swaps_data,
        "amount_in": amount_in,
        "tx_cost": tx_cost,
        "token_in": token_in,
        "first_token_out": first_token_out,
        "token_out": token_out,
        "burners_len": burners_len,
        "burners": burners,
    }
    if not args["token_out"]:
        del args["token_out"]

    return args


def shift_address(address: ChecksumAddress | str) -> str:
    """Shift address left by 1 bit.

    Args:
        address (ChecksumAddress | str): Hex string address (with or without 0x).

    Returns:
        str: 21 byte hex without `0x`.
    """
    # removing 0x from address
    if address.startswith("0x"):
        address = address[2:]

    # shifting left by 1 bit
    hex_shifted = hex(int(address, 16) << 1)[2:]

    # padding zeroes left to match 21 bytes length
    return "0" * (42 - len(hex_shifted)) + hex_shifted


def unshift_address(shifted_address: str) -> ChecksumAddress:
    """Unshift address. Shift ``shifted_address`` by 1 bit right.

    Args:
        shifted_address (str): Address shifted by 1 bit left.

    Returns:
        ChecksumAddress: Checksummed address.
    """
    unshifted_address = hex(int(shifted_address, 16) >> 1)[2:]
    unshifted_address = "0x" + "0" * (40 - len(unshifted_address)) + unshifted_address

    return to_checksum_address(unshifted_address)


def to_hex_uint112(num: int | Decimal) -> str:
    """Convert number to hex string with length of 14 bytes without `0x`.

    Args:
        num (int | Decimal): Number.

    Note:
        Does not check if ``num`` exceeds maximum uint112 value.

    Returns:
        str: Hexadecimal string without `0x`.
    """
    hex_num = hex(int(num))[2:]
    return "0" * (28 - len(hex_num)) + hex_num


def to_hex_uint16(num: int | Decimal) -> str:
    """Convert number to hex string with length of 2 bytes without `0x`.

    Args:
        num (int | Decimal): Number.

    Note:
        Does not check if ``num`` exceeds maximum uint16 value.

    Returns:
        str: Hexadecimal string without `0x`.
    """
    hex_num = hex(int(num))[2:]
    return "0" * (4 - len(hex_num)) + hex_num


def to_hex_uint8(num: int | Decimal) -> str:
    """Convert number to hex string with length of 1 bytes without `0x`.

    Args:
        num (int | Decimal): Number.

    Note:
        Does not check if ``num`` exceeds maximum uint8 value.

    Returns:
        str: Hexadecimal string without `0x`.
    """
    hex_num = hex(int(num))[2:]
    return "0" * (2 - len(hex_num)) + hex_num
