from datetime import datetime
from decimal import Decimal
from time import time

from eth_typing import ChecksumAddress

import persistance
from arbitrage.calculator import calc_gas_cost
from blockchain import Web3, get_weth_price, multicall
from network import prices
from utils import CONFIG, Logger, str_num, uptime
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
    tx_receipts: list[TxReceipt], arbs: list[Arbitrage], arb_args: list[ArbArgs]
):
    for receipt, arb, args in zip(tx_receipts, arbs, arb_args, strict=True):
        status, style = get_tx_status(receipt["status"], receipt)
        tx_hash = receipt["transactionHash"].hex()
        url = "https://bscscan.com/tx/" + tx_hash

        log_str = f"{style}ARBITRAGE EXECUTED[/]\n[b]STATUS[/]: {status}\n"
        log_str += f"[b]TRANSACTION HASH[/]: [not b blue link={url}]{tx_hash}[/]\n"
        log_str += get_tx_log(status, receipt, arb, args)

        _log = log.error if status == "revert" else log.info
        _log(log_str)


def get_tx_status(status: bool, tx_receipt: TxReceipt) -> tuple[str, str]:
    if not status:
        return "revert", "[b u i red]"

    if tx_receipt["gasUsed"] < 100_000:
        return "no profit", "[b u i yellow]"

    if status:
        return "success", "[b u i green]"


def get_tx_log(
    status: str,
    tx_receipt: TxReceipt,
    arb: Arbitrage,
    arb_args: ArbArgs,
) -> str:
    noprofit_paths = persistance.load_noprofit_paths()
    gas_price = Decimal(tx_receipt["effectiveGasPrice"])
    gas_used = Decimal(tx_receipt["gasUsed"])

    str_gas_price = str_num(gas_price / Decimal(1e9))
    str_gas_used = f"{gas_used:,}"
    str_path = symbolize_path(arb.path)

    # revert and no profit case
    if status == "revert" or status == "no profit":
        # getting and saving loss
        loss = gas_price * gas_used
        save_tx_stats(False, -loss, Decimal(0))

        # updating nonprofitable paths
        noprofit_count = noprofit_paths.get(arb.token_path, 0)
        noprofit_count += 1
        noprofit_paths[arb.token_path] = noprofit_count
        persistance.save_noprofit_paths(noprofit_paths)

        str_loss = str_num(loss / Decimal(1e18))
        str_noprofit_count = str_num(noprofit_count)

        log_str = f"[b]PATH[/]: {str_path}\n"
        log_str += f"[b]NO PROFIT COUNT[/]: [default not b]{str_noprofit_count}[/]\n"
        log_str += f"[b]GAS PRICE[/]: [yellow]{str_gas_price}[/] GWEI\n"
        log_str += f"[b]GAS USED[/]: [orange1]{str_gas_used}[/]\n"
        log_str += f"[b]LOSS[/]: [red]{str_loss}[/] BNB"

        return log_str

    # removing path from nonprofitable paths
    if arb.token_path in noprofit_paths:
        log.info(
            f"Path profitable after {noprofit_paths[arb.token_path]:,} nonprofitable transactions."
        )
        noprofit_paths[arb.token_path] -= 1
        persistance.save_noprofit_paths(noprofit_paths)

    # success case
    transfer_logs = Web3().get_transfer_event_logs(tx_receipt)

    arb_type = (
        "flash arbitrage"
        if transfer_logs[0]["args"]["to"] == CONFIG["router"]
        else "arbitrage"
    )
    amount_in = Decimal(arb_args["amount_in"])
    amount_out = get_amount_out(transfer_logs)
    token_in, token_out = arb.path[0], arb.path[-1]

    wei_price = get_weth_price(token_out)
    gas_cost = calc_gas_cost(gas_price, gas_used, wei_price)

    bruto_profit = amount_out - amount_in
    neto_profit = bruto_profit - gas_cost

    # saving transaction stats
    if token_in in CONFIG["weths"]:
        bnb_profit = neto_profit
        usd_profit = Decimal(0)
    else:
        bnb_profit = -(gas_price * gas_used)
        usd_profit = bruto_profit
    save_tx_stats(True, bnb_profit, usd_profit)

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
    str_symbol_in = f"[default not b]{SYMBOLS[token_in]}[/]"
    str_symbol_out = f"[default not b]{SYMBOLS[token_out]}[/]"
    str_path = symbolize_path(arb.path)
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

    sym_path = ""
    for i, (address, symbol) in enumerate(zip(path, symbols, strict=True)):
        if i % 2 == 0:
            if i:
                sym_path += " -> "
            style = "[magenta b]"
        else:
            style = "[default]"
            sym_path += " - "

        try:
            sym_path += f"{style}{SYMBOLS[address]}[/]"
        except KeyError:
            sym_path += f"{style}{symbol}[/]"

    return sym_path


def save_tx_stats(is_success: bool, bnb_profit: Decimal, usd_profit: Decimal) -> None:
    tx_stats = persistance.load_tx_stats()

    tx_stats["uptime"] = uptime.total()
    tx_stats["total"] += 1
    if is_success:
        tx_stats["success"] += 1
    else:
        tx_stats["fail"] += 1
    tx_stats["success_rate"] = tx_stats["success"] / tx_stats["total"]
    tx_stats["bnb_profit"] += int(bnb_profit)
    tx_stats["usd_profit"] += int(usd_profit)

    persistance.save_tx_stats(tx_stats)


# def save_tx_stats(wei_profit: Decimal) -> None:
#     tx_stats = persistance.load_tx_stats()

#     tx_stats["total"] += 1
#     if wei_profit > 0:
#         tx_stats["success"] += 1
#     else:
#         tx_stats["fail"] += 1
#     tx_stats["success_rate"] = tx_stats["success"] / (
#         tx_stats["success"] + tx_stats["fail"]
#     )
#     tx_stats["profit"] += int(wei_profit)

#     persistance.save_tx_stats(tx_stats)


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
