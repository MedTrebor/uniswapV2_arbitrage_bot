import re
import sys
from time import sleep

from eth_typing import ChecksumAddress
from rich.console import Console

import persistance
import web3
from blockchain import Web3
from utils import CONFIG, measure_time, str_obj
from web3.exceptions import TimeExhausted

c = Console()

GAS_PRICE = int(1e9) + 1  # 1.000000001 GWEI
# KEEP_AMOUNT = int(0.5e18)  # 0.5 WBNB for each token
KEEP_AMOUNT = int(1e18)


def main():
    w3 = Web3()

    abi = persistance.get_abi("WETH")
    wbnb = w3.eth.contract(CONFIG["weths"][0], abi=abi)
    wbnb_fst = w3.eth.contract(CONFIG["weths"][1], abi=abi)

    wbnb_balance = wbnb.functions.balanceOf(CONFIG["router"]).call()
    wbnb_fst_balance = wbnb_fst.functions.balanceOf(CONFIG["router"]).call()

    amounts = [get_amount_out(wbnb_balance), get_amount_out(wbnb_fst_balance, 0)]
    wbnbs = [wbnb.address, wbnb_fst.address]

    tx_params = create_tx(w3, amounts, wbnbs)

    execute_tx(w3, tx_params)


def execute_tx(w3: Web3, tx_params: dict):
    c.print(f"[b]Sending Transaction[/]: {str_obj(tx_params)}\n")

    log_str = measure_time(
        "[b]Transaction Hash[/]: [blue not b link=https://bscscan.com/tx/{h}]{h}[/]\n"
        "[b]Gas used[/]: [orange1]{g:,}[/]\n"
        "[b]Confirmed in[/]: {t}\n"
    )

    send_tx = True
    while True:
        try:
            if send_tx:
                tx_hash = w3.eth.send_transaction(tx_params)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, 30, 3)
            break
        except ValueError as err:
            try:
                msg = err.args[0]["message"]
            except (KeyError, TypeError, AttributeError, IndexError):
                msg = str(err)

            c.print(f"[red]ERROR[/]: {msg}")

            if "transaction underpriced" == msg:
                sleep(3)
                continue

            if "nonce" in msg:
                send_tx = False
                sleep(3)
                continue

            sleep(30)

        except TimeExhausted as err:
            str_err = re.sub(r"HexBytes\('|'\)", "", str(err))
            c.print(f"[red]ERROR[/]: {str_err}")

    c.print(log_str(h=receipt["transactionHash"].hex(), g=receipt["gasUsed"]))


def create_tx(w3: Web3, amounts: list[int], wbnbs: list[ChecksumAddress]) -> dict:
    calldata = int_to_uint256(amounts[0])
    calldata += lower_address(wbnbs[0])
    calldata += int_to_uint256(amounts[1])
    calldata += lower_address(wbnbs[1])

    acc = w3.account

    tx_params = {
        "from": acc,
        "to": CONFIG["router_multicall"],
        "nonce": w3.nonce(acc),
        "gasPrice": GAS_PRICE,
        "chainId": w3.chain_id,
        "data": calldata,
    }
    tx_params["gas"] = int(w3.eth.estimate_gas(tx_params) * 1.2)

    return tx_params


def get_amount_out(balance: int, keep_amount: int = KEEP_AMOUNT) -> int:
    return balance - keep_amount


def int_to_uint256(num: int) -> str:
    hex_num = hex(num)[2:]
    return "0" * (64 - len(hex_num)) + hex_num


def lower_address(address: ChecksumAddress) -> str:
    if address.startswith("0x"):
        return address[2:].lower()

    return address.lower()


if __name__ == "__main__":
    sys.stdout.write("\033]0;MULTI REFUEL\007")
    sys.stdout.flush()
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        print()
    except:
        c.print_exception(extra_lines=6, show_locals=True, suppress=[web3])
