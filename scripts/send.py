from rich.console import Console

import web3
from blockchain import Web3
from utils import CONFIG, GasPriceRange, measure_time, str_obj
from web3.exceptions import TimeExhausted

c = Console()

AMOUNT = int(17e16)  # 0.18 BNB
TO = "0x6ad9aEf9E10FC17D2a36769719F18ae17F6a38af"  # burner generator
START_GAS_PRICE = int(1e9) + 1  # 1.000000001 GWEI
END_GAS_PRICE = int(3e9)  # 3 GWEI
INCREASE_INTERVAL = 200


def main():
    w3 = Web3()

    nonce = w3.nonce(w3.account)

    log_str = measure_time(
        "[b]Transaction Hash[/]: [blue not b link=https://bscscan.com/tx/{h}]{h}[/]\n"
        "[b]Executed in[/]: {t}\n"
    )
    for gas_price in GasPriceRange(START_GAS_PRICE, END_GAS_PRICE):
        tx_params = {
            "from": w3.account,
            "to": TO,
            "value": AMOUNT,
            "nonce": nonce,
            "gasPrice": gas_price,
            "chainId": w3.chain_id,
        }

        c.print(f"[b]Sending Transaction[/]: {str_obj(tx_params)}\n")

        tx_params["gas"] = w3.eth.estimate_gas(tx_params)

        try:
            tx_hash = w3.eth.send_transaction(tx_params).hex()
        except ValueError as err:
            print_exc = False
            try:
                msg = err.args[0]["message"]
                if "nonce" not in msg:
                    c.print(f"[red]ERROR[/]: {err.args[0]['message']}")
                    continue
            except (KeyError, TypeError, AttributeError, IndexError):
                print_exc = True
            if print_exc:
                c.print_exception(extra_lines=6, show_locals=True, suppress=[web3])
                continue

        try:
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, INCREASE_INTERVAL, 1)
            break
        except TimeExhausted as err:
            c.print(str(err))
            continue

    try:
        receipt
        c.print(log_str(h=tx_hash))
    except UnboundLocalError:
        c.print("[red]ERROR[/]: Transaction failed!")


if __name__ == "__main__":
    print("\033]0;SEND\007")
    try:
        main()
    except (SystemError, KeyboardInterrupt):
        print()
    except BaseException:
        c.print_exception(extra_lines=6, show_locals=True, suppress=[web3])
