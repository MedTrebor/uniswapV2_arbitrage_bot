from time import sleep

from eth_typing import ChecksumAddress
from eth_utils.address import to_checksum_address
from eth_utils.crypto import keccak
from hexbytes import HexBytes

from utils import CONFIG, Logger, measure_time, str_obj
from utils._types import ArbArgs, BurnersData, TxTrace
from web3.exceptions import TimeExhausted
from web3.types import TxReceipt

from . import multicall
from .exceptions import BurnersCreationError
from .ww3 import Web3

log = Logger(__name__)

BURNER_HASH = keccak(
    hexstr="77700fed3a25eee9d525a5671b5995fd489fcd3218585732ff3d5260186008f3"
).hex()


def create_burners(
    burners: list[BurnersData],
    exe_acc: ChecksumAddress,
) -> None:
    """Create burner contracts if necessary.

    Args:
        burners (list[BurnersData]): Burners data.
        exe_acc (ChecksumAddress): Transaction execution account.

    Raises:
        BurnersCreationError: If burners creation failed.
    """
    # checking if burners are enabled
    if not CONFIG["burner"]["enabled"]:
        return

    try:
        if len(burners) > 1 or len(burners[0]["addresses"]) >= CONFIG["burner"]["min"]:
            # don't create burners if burners count above configured minimum
            return
    except IndexError:
        pass

    # getting salt and calldata
    try:
        salt = 0 if not burners else burners[0]["salt"] + 1
    except IndexError:
        salt = 0
    salt = 0 if salt > 1 else salt
    calldata = salt_to_calldata(salt)

    # executing transaction
    success = exe_tx(exe_acc, calldata)
    if not success:
        raise BurnersCreationError(CONFIG["burner"]["factory"], exe_acc)

    # getting contract addresses
    addresses = get_burner_addresses(calldata)

    burners.append({"salt": salt, "addresses": addresses})


def salt_to_calldata(salt: int) -> str:
    """Convert salt to calldata.

    Args:
        salt (int): Salt.

    Returns:
        str: Hex calldata.
    """
    if not salt:
        return "0x"

    calldata = hex(salt)[2:]
    if len(calldata) % 2 == 1:
        calldata = "0" + calldata

    return "0x" + calldata


def exe_tx(acc: ChecksumAddress, calldata: str) -> bool:
    """Execute creation of burners on chain.

    Args:
        acc (ChecksumAddress): Accaunt to send transaction from.
        calldata (str): Calldata for the transaction.

    Returns:
        bool: Success.
    """
    w3 = Web3()

    tx_params = {
        "from": acc,
        "to": CONFIG["burner"]["factory"],
        "value": 1,
        "nonce": w3.nonce(acc, True),
        "gasPrice": CONFIG["burner"]["gas_price"],
        "chainId": w3.chain_id,
        "data": calldata,
    }
    tx_params["gas"] = int(w3.node.eth.estimate_gas(tx_params) * 1.2)

    tx_hash = w3.node.eth.send_transaction(tx_params)
    log.info(
        "Burner creation transaction sent.\nTransaction hash: [not b blue]"
        f"{tx_hash.hex()}[/]\nTransaction parameters: {str_obj(tx_params)}"
    )
    w3.nonces[acc] += 1

    log_str = measure_time(
        "{a} creation of burners confirmed in {t}.\n[b]Transaction hash:[/]"
        " [not b blue link=https://bscscan.com/tx/{b}]{b}"
    )

    send_tx = True
    while True:
        try:
            if send_tx:
                tx_hash = w3.node.eth.send_transaction(tx_params)
            receipt = w3.node.eth.wait_for_transaction_receipt(tx_hash, 120, 3)
            break

        except ValueError as err:
            log.warning(err)
            if "nonce" in str(err):
                send_tx = False
                sleep(CONFIG["poll"]["main"])
                continue
            sleep(120)

        except TimeExhausted as err:
            log.warning(err)

    status = "[green]Successful[/]" if receipt["status"] else "[red]Failed[/]"
    _log = log.info if receipt["status"] else log.error
    _log(log_str(a=status, b=tx_hash.hex()))

    success = True if receipt["status"] else False
    return success


def get_burner_addresses(calldata: str = "") -> list[str]:
    """Get addresses of burners.

    Args:
        calldata (str, optional): Calldata used for creating burners.
            Defaults empty string.

    Returns:
        list[str]: List of hex addresses without `0x` prefix.
    """
    # getting salt
    if not calldata or calldata == "0x":
        salt = 0
    else:
        # removing 0x from calldata
        if calldata.startswith("0x"):
            calldata = calldata[2:]

        zeroes_to_add = 64 - len(calldata)
        calldata += "0" * zeroes_to_add
        salt = int(calldata, 16)

    # calculating addresses
    addresses = []
    for _salt in range(salt, salt + 256):
        hex_salt = int_to_hex32(_salt)
        hexstr = "0xff" + CONFIG["burner"]["factory"][2:] + hex_salt + BURNER_HASH
        address = keccak(hexstr=hexstr)[12:].hex()
        addresses.append(address)

    return addresses


def int_to_hex32(num: int) -> str:
    """Convert integer to hex string left padded to 32 bytes.

    Args:
        num (int): Number

    Returns:
        str: Hex string without `0x`.
    """
    not_padded = hex(num)[2:]
    padding = "0" * (64 - len(not_padded))
    return padding + not_padded


# def get_used_burnerns(tx_hash: HexBytes | str) -> list[ChecksumAddress]:
#     """Get burner addresses used in transaction with provided ``tx_hash``.

#     Args:
#         tx_hash (HexBytes | str): Transaction hash.

#     Returns:
#         list[ChecksumAddress]: Burner addresses
#     """
#     tx_trace = Web3().trace_transaction(tx_hash)

#     return get_burners_from_tx(tx_trace)


def get_used_burnerns(tx_receipt: TxReceipt, arb_arg: ArbArgs) -> list[ChecksumAddress]:
    """Get burner addresses used in transaction.

    Args:
        tx_receipt (TxReceipt): Transaction receipt.
        arb_arg (ArbArgs): Arbitrage transaction arguments.

    Returns:
        list[ChecksumAddress]: Burner addresses
    """
    if tx_receipt["gasUsed"] < 60_000:
        return [to_checksum_address(arb_arg["burners"][0])]
    else:
        return [to_checksum_address(burner) for burner in arb_arg["burners"]]


def get_burners_from_tx(tx_trace: TxTrace) -> list[ChecksumAddress]:
    """Find all burners used in ``tx_trace``.

    Args:
        tx_trace (TxTrace): Transaction trace.

    Returns:
        list[ChecksumAddress]: Burner addresses that are destroyed.
    """
    selfdestructs = []
    if tx_trace["type"] == "SELFDESTRUCT" and tx_trace["to"] == Web3().account.lower():
        selfdestructs.append(to_checksum_address(tx_trace["from"]))

    for _call in tx_trace.get("calls", []):
        selfdestructs.extend(get_burners_from_tx(_call))

    return selfdestructs


def remove_used_burners(
    burners: list[BurnersData], used_burners: list[ChecksumAddress]
):
    """Remove used burner addresses from ``burners``.

    Args:
        burners (list[BurnersData]): Burners data.
        used_burners (list[ChecksumAddress]): Used burner addresses.
    """
    for address in used_burners:
        try:
            burners[0]["addresses"].remove(address[2:].lower())
        except ValueError:
            burners[1]["addresses"].remove(address[2:].lower())

        if not burners[0]["addresses"]:
            del burners[0]


def remove_all_used_burners(
    all_burners: tuple[list[BurnersData], list[BurnersData]]
) -> None:
    """Remove all used burners.

    Args:
        all_burners (tuple[list[BurnersData], list[BurnersData]]):
            Burners data for each account.
    """
    accs = Web3().accounts

    all_removed = []

    # going throught burners for each account
    for i0, _burners_data in enumerate(all_burners):
        # index of burners data to remove
        burners_data_to_remove = []

        # going through burners for each salt
        for i1, burners_data in enumerate(_burners_data):
            # index of address
            address_to_remove = []

            # burners addresses
            burners = burners_data["addresses"]

            call_params = [(to_checksum_address(add), "") for add in burners]
            results = multicall.check_success(call_params, {"from": accs[i0]})

            # checking result for each address
            for i2, result in enumerate(results):
                if not result:
                    address_to_remove.append(i2)

            # removing addresses
            for i, remove_idx in enumerate(address_to_remove):
                all_removed.append(to_checksum_address(burners[remove_idx - i]))
                del burners[remove_idx - i]

            # removing if no more addresses
            if not len(burners):
                burners_data_to_remove.append(i1)

        # removing burners data
        for i, remove_idx in enumerate(burners_data_to_remove):
            del _burners_data[remove_idx - i]

    # logging
    if all_removed:
        log.warning(f"Removed {len(all_removed):,} burners: {str_obj(all_removed)}")
