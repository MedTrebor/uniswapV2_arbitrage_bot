from rich import print
from rich.pretty import pprint
from utils import CONFIG
from core.logger import str_num
from utils._types import BalanceStats

import persistance


def main():
    all_balance_stats = persistance.load_balance_stats()
    read_tx_stats()

    read_balance(all_balance_stats[-1])


def read_balance(balance_stats: BalanceStats):
    burn_cost = 36_930 * CONFIG["burner"]["gas_price"]

    time = balance_stats["time"][: balance_stats["time"].find(".")]
    bnb = balance_stats["executor"]

    usd = 0
    for token_balance in balance_stats["router"]:
        if token_balance["symbol"] == "WBNB":
            bnb += token_balance["balance"]
        else:
            usd += token_balance["balance"]

    burners = balance_stats["burners"] * burn_cost

    bnb_price = balance_stats["bnb_price"]

    bnb_total = str_num((usd // bnb_price + bnb + burners) / 1e18)
    usd_total = str_num((bnb * bnb_price + usd + burners * bnb_price) / 1e18)

    bnb = str_num(bnb / 1e18)
    usd = str_num(usd / 1e18)
    burners = str_num(burners / 1e18)

    print(
        "\n"
        f"[b]BALANCE TIME[/]: {time}\n"
        f"[b]BNB PRICE[/]:    {bnb_price}\n"
        f"[b]BALANCES[/]:     {bnb} BNB\n"
        f"              {usd} USD\n"
        f"[b]BURNERS[/]:      {burners} BNB\n"
        f"[b]TOTAL IN BNB[/]: {bnb_total} BNB\n"
        f"[b]TOTAL IN USD[/]: {usd_total} USD\n"
    )


def read_tx_stats():
    tx_stats = persistance.load_tx_stats()
    profit = f"{tx_stats['profit'] / 1e18:,}"

    if "." in profit:
        while profit.endswith("0"):
            profit = profit[:-1]
        if profit.endswith("."):
            profit = profit[:-1]

    style = "[default not b]"

    print(
        "\n"
        f"[b]TOTAL TRANSACTIONS[/]: {style}{tx_stats['total']:,}[/]\n"
        f"[b]SUCCESS COUNT[/]:      {style}{tx_stats['success']:,}[/]\n"
        f"[b]FAIL COUNT[/]:         {style}{tx_stats['fail']:,}[/]\n"
        f"[b]SUCCESS RATE[/]:       {style}{tx_stats['success_rate']:.2%}[/]\n"
        f"[b]PROFIT[/]:             {style}{profit} BNB\n"
    )


if __name__ == "__main__":
    main()
