from datetime import datetime
from decimal import Decimal

from eth_typing import ChecksumAddress

import persistance
from arbitrage.calculator import calc_gas_cost
from blockchain import Web3, multicall
from network import prices
from network.prices import wei_usd_price
from utils import CONFIG, Logger, str_num
from utils._types import ArbArgs
from utils.datastructures import Arbitrage
from web3.datastructures import AttributeDict
from web3.types import TxReceipt

log = Logger(__name__)

SYMBOLS = {
    "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c": "WBNB",
    "0x0efb5FD2402A0967B92551d6AF54De148504A115": "WBNB(FST)",
    "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56": "BUSD",
    "0x55d398326f99059fF775485246999027B3197955": "USDT",
    "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d": "USDC",
    "0x1AF3F329e8BE154074D8769D1FFa4eE058B1DBc3": "DAI",
    "0x14016E85a25aeb13065688cAFB43044C2ef86784": "TUSD",
}


def log_executed_arbs(
    tx_receipts: list[TxReceipt],
    arb_args: list[ArbArgs],
    used_burners: list[ChecksumAddress],
):
    for receipt, args in zip(tx_receipts, arb_args, strict=True):
        status, style = get_tx_status(receipt["status"], args["burners"], used_burners)
        tx_hash = receipt["transactionHash"].hex()
        url = "https://bscscan.com/tx/" + tx_hash

        log_str = f"{style}ARBITRAGE EXECUTED[/]\n[b]STATUS[/]: {status}\n"
        log_str += f"[b]TRANSACTION HASH[/]: [not b blue link={url}]{tx_hash}[/]\n"
        log_str += get_tx_log(status, receipt, args)

        _log = log.error if status == "revert" else log.info
        _log(log_str)


def get_tx_status(
    status: bool,
    arg_burners: list[ChecksumAddress],
    used_burners: list[ChecksumAddress],
) -> tuple[str, str]:
    if not status:
        return "revert", "[b u i red]"

    for address in arg_burners:
        if address not in used_burners:
            status = False
            break

    if status:
        return "success", "[b u i green]"

    return "no profit", "[b u i yellow]"


def get_tx_log(
    status: str,
    tx_receipt: TxReceipt,
    arb_args: ArbArgs,
) -> str:
    burn_cost = Decimal(36_930) * Decimal(CONFIG["burner"]["gas_price"])
    gas_price = Decimal(tx_receipt["effectiveGasPrice"])
    gas_used = Decimal(tx_receipt["gasUsed"])

    str_gas_price = str_num(gas_price / Decimal(1e9))
    str_gas_used = f"{gas_used:,}"

    # revert and no profit case
    if status == "revert" or status == "no profit":
        # getting and saving loss
        loss = gas_price * gas_used
        if status == "no profit":
            loss += burn_cost
        save_tx_stats(-loss)

        str_loss = str_num(loss / Decimal(1e18))

        log_str = f"[b]GAS PRICE[/]: [yellow]{str_gas_price}[/] GWEI\n"
        log_str += f"[b]GAS USED[/]: [orange1]{str_gas_used}[/]\n"
        log_str += f"[b]LOSS[/]: [red]{str_loss}[/] BNB"

        return log_str

    # success case
    transfer_logs = Web3().get_transfer_event_logs(tx_receipt)

    arb_type = (
        "flash arbitrage"
        if transfer_logs[0]["args"]["to"] == CONFIG["router"]
        else "arbitrage"
    )
    amount_in = Decimal(arb_args["amount_in"])
    amount_out = get_amount_out(transfer_logs)
    path = get_path(transfer_logs)
    token_in, token_out = path[0], path[-1]

    wei_price = wei_usd_price(token_out)
    gas_cost = calc_gas_cost(gas_price, gas_used, wei_price)

    bruto_profit = amount_out - amount_in
    burners_cost = burn_cost * arb_args["burners_len"]
    neto_profit = bruto_profit - gas_cost - burners_cost

    # saving balancer stats
    save_tx_stats(neto_profit // wei_price)

    # getting decimals denominator
    try:
        decimals_denominator = prices.token_decimals(token_out)
    except KeyError:
        decimals_denominator = Decimal("1e18")

    # getting decimal numbers
    dec_neto_profit = neto_profit / decimals_denominator
    dec_bruto_profit = bruto_profit / decimals_denominator
    dec_amount_in = amount_in / decimals_denominator
    dec_amount_out = amount_out / decimals_denominator
    dec_gas_cost = gas_cost / decimals_denominator

    # creating string representations
    str_symbol_in = f"[magenta not b]{SYMBOLS[token_in]}[/]"
    str_symbol_out = f"[magenta not b]{SYMBOLS[token_out]}[/]"
    str_path = symbolize_path(path)
    str_amount_in = str_num(dec_amount_in)
    str_amount_out = str_num(dec_amount_out)
    str_bruto_profit = str_num(dec_bruto_profit)
    str_neto_profit = str_num(dec_neto_profit)
    str_gas_cost = str_num(dec_gas_cost)

    # constructing log string
    log_str = f"[b]TYPE[/]: {arb_type}\n"
    log_str += f"[b]PATH[/]: {str_path}\n"
    log_str += f"[b]AMOUNT IN[/]: {str_amount_in} {str_symbol_in}\n"
    log_str += f"[b]AMOUNT OUT[/]: {str_amount_out} {str_symbol_out}\n"
    log_str += (
        f"[b]BRUTO PROFIT[/]: [not b green]{str_bruto_profit}[/] {str_symbol_out}\n"
    )
    log_str += f"[b]GAS PRICE[/]: [yellow]{str_gas_price}[/] GWEI\n"
    log_str += f"[b]GAS USED[/]: [orange1]{str_gas_used}[/]\n"
    log_str += f"[b]GAS COST[/]: [not b red]{str_gas_cost}[/] {str_symbol_out}\n"
    if arb_args["burners_len"]:
        log_str += f"[b]BURNERS BURNED[/]: {arb_args['burners_len']}\n"
    log_str += f"[b]NETO PROFIT[/]: [green]{str_neto_profit}[/] {str_symbol_out}"

    return log_str


def get_amount_out(transfer_logs: tuple[AttributeDict, ...]) -> Decimal:
    last_idx = len(transfer_logs) - 1
    if transfer_logs[0]["args"]["to"] == CONFIG["router"]:
        last_idx -= 1

    return Decimal(transfer_logs[last_idx]["args"]["value"])


def get_path(transfer_logs: tuple[AttributeDict, ...]) -> list[ChecksumAddress]:
    path = []
    start, end = 0, len(transfer_logs) - 1
    for i, event in enumerate(transfer_logs):
        token = event["address"]

        # checking for type
        if i == 0 and event["args"]["to"] == CONFIG["router"]:
            start, end = end, end - 1

        # start
        if i == start:
            token_in = token
            continue

        # end
        elif i == end:
            token_out = token
            continue

        if token not in path:
            path.append(token)

    path.insert(0, token_in)
    path.append(token_out)

    return path


def symbolize_path(path: list[ChecksumAddress]) -> str:
    # getting symbols from blockchain
    multicall_args = [(address, "0x95d89b41") for address in path]
    encoded_symbols = multicall.call(multicall_args)
    symbols = [multicall.decode(sym, ["string"])[0] for sym in encoded_symbols]

    sym_path = []
    for address, symbol in zip(path, symbols, strict=True):
        try:
            token = f"[magenta not b]{SYMBOLS[address]}[/]"
        except KeyError:
            token = f"[magenta not b]{symbol}[/]"

        sym_path.append(token)

    return " -> ".join(sym_path)


def save_tx_stats(wei_profit: Decimal) -> None:
    tx_stats = persistance.load_tx_stats()

    tx_stats["total"] += 1
    if wei_profit > 0:
        tx_stats["success"] += 1
    else:
        tx_stats["fail"] += 1
    tx_stats["success_rate"] = tx_stats["success"] / (
        tx_stats["success"] + tx_stats["fail"]
    )
    tx_stats["profit"] += int(wei_profit)

    persistance.save_tx_stats(tx_stats)


def log_potential_arbs(potential_arbs: list[tuple[Arbitrage, Decimal, Decimal]]):
    if len(potential_arbs) == 1:
        log_str = "[b u]ARBITRAGE FOUND[/]\n"
        log_str += get_arb_log_str(*potential_arbs[0])

    else:
        log_str = "[b u]ARBITRAGES FOUND[/]"
        for i, potential_arb in enumerate(potential_arbs, start=1):
            log_str += f"\n[i u]{i:,}[/]\n"
            log_str += get_arb_log_str(*potential_arb)

    log.info(log_str)


def get_arb_log_str(arb: Arbitrage, gas_limit: Decimal, gas_price: Decimal) -> str:
    symbols = {
        "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c": "WBNB",
        "0x0efb5FD2402A0967B92551d6AF54De148504A115": "WBNB(FST)",
        "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56": "BUSD",
        "0x55d398326f99059fF775485246999027B3197955": "USDT",
        "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d": "USDC",
        "0x1AF3F329e8BE154074D8769D1FFa4eE058B1DBc3": "DAI",
        "0x14016E85a25aeb13065688cAFB43044C2ef86784": "TUSD",
    }

    token_in, token_out = arb.path[0], arb.path[-1]
    symbol_in, symbol_out = symbols[token_in], symbols[token_out]

    try:
        decimals_denominator = prices.token_decimals(token_out)
    except KeyError:
        decimals_denominator = Decimal("1e18")

    # calculating decimal numbers
    dec_bruto_profit = arb.bruto_profit / decimals_denominator
    dec_neto_profit = arb.neto_profit / decimals_denominator
    dec_amount_in = arb.amount_in / decimals_denominator

    # creating string representations for numbers
    str_symbol_in = f"[default not b]{symbol_in}[/]"
    str_symbol_out = f"[default not b]{symbol_out}[/]"
    str_bruto_profit = str_num(dec_bruto_profit)
    str_neto_profit = str_num(dec_neto_profit)
    str_amount_in = str_num(dec_amount_in)
    str_gas_limit = f"{gas_limit:,}"
    str_gas_price = str_num(gas_price / Decimal("1e9"))

    str_path = symbolize_path_local(arb.path)

    # creating log strings
    log_str = f"[b]PATH[/]: [default not b]{str_path}[/]\n"
    log_str += f"[b]AMOUNT IN[/]: [blue]{str_amount_in}[/] {str_symbol_in}\n"
    log_str += f"[b]GAS PRICE[/]: [yellow]{str_gas_price}[/] GWEI\n"
    log_str += f"[b]GAS LIMIT[/]: [orange1]{str_gas_limit}[/]\n"
    log_str += (
        f"[b]BRUTO PROFIT[/]: [not b green]{str_bruto_profit}[/] {str_symbol_out}\n"
    )
    log_str += f"[b]NETO PROFIT[/]: [green]{str_neto_profit}[/] {str_symbol_out}"

    # saving success stats
    success_stats = persistance.load_success_stats()
    success_stats[str(datetime.now())] = {
        "path": arb.path,
        "token_in": symbol_in,
        "token_out": symbol_out,
        "amount_in": str_amount_in,
        "gas_limit": str_gas_limit,
        "bruto_profit": str_bruto_profit,
        "neto_profit": str_neto_profit,
    }
    persistance.save_success_stats(success_stats)

    return log_str


def symbolize_path_local(path: list[ChecksumAddress]) -> str:
    sym_path = []
    for token in path:
        try:
            sym_path.append(SYMBOLS[token])
        except KeyError:
            sym_path.append(token)

    return " -> ".join(sym_path)
