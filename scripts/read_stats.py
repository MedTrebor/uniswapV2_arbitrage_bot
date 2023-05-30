from datetime import timedelta
from rich import print
from rich.pretty import pprint
from utils import CONFIG
from core.logger import str_num
from utils._types import BalanceStats
from blockchain import update_prices, get_weth_price
from core.price import create_price_pools

import persistance


def main():
    update_prices(create_price_pools())
    all_balance_stats = persistance.load_balance_stats()
    read_tx_stats()

    read_balance(all_balance_stats[-1])


def read_balance(balance_stats: BalanceStats):
    burn_cost = 36_930 * CONFIG["burner"]["gas_price"]

    time = balance_stats["time"][: balance_stats["time"].find(".")]
    bnb = balance_stats["executor"] + balance_stats["burner_generator"]

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
        f" [b]BALANCE TIME[/]: {time}\n"
        f" [b]BNB PRICE[/]:    {bnb_price}\n"
        f" [b]BALANCES[/]:     {bnb} BNB\n"
        f"               {usd} USD\n"
        f" [b]BURNERS[/]:      {burners} BNB\n"
        f" [b]TOTAL IN BNB[/]: {bnb_total} BNB\n"
        f" [b]TOTAL IN USD[/]: {usd_total} USD\n"
    )


def read_tx_stats():
    bnb_price = float(get_weth_price("0x55d398326f99059fF775485246999027B3197955"))

    tx_stats = persistance.load_tx_stats()
    uptime = timedelta(seconds=tx_stats["uptime"])

    bnb_profit = str_num(tx_stats["bnb_profit"] / 1e18)
    usd_profit = str_num(tx_stats["usd_profit"] / 1e18)
    total_bnb_profit = str_num(
        (tx_stats["bnb_profit"] + tx_stats["usd_profit"] // bnb_price) / 1e18
    )
    total_usd_profit = str_num(
        (tx_stats["usd_profit"] + int(tx_stats["bnb_profit"] * bnb_price)) / 1e18
    )

    style = "[default not b]"

    print(
        "\n"
        f" [b]UPTIME[/]:             {style}{uptime}[/]\n"
        f" [b]TOTAL TRANSACTIONS[/]: {style}{tx_stats['total']:,}[/]\n"
        f" [b]SUCCESS COUNT[/]:      {style}{tx_stats['success']:,}[/]\n"
        f" [b]FAIL COUNT[/]:         {style}{tx_stats['fail']:,}[/]\n"
        f" [b]SUCCESS RATE[/]:       {style}{tx_stats['success_rate']:.2%}[/]\n"
        f" [b]BNB PROFIT[/]:         {style}{bnb_profit} BNB\n"
        f" [b]USD PROFIT[/]:         {style}{usd_profit} USD\n"
        f" [b]TOTAL BNB PROFIT[/]:   {style}{total_bnb_profit} BNB\n"
        f" [b]TOTAL USD PROFIT[/]:   {style}{total_usd_profit} USD\n"
        f" [b]BNB PRICE[/]:          {style}{bnb_price:,.2f}\n"
    )


if __name__ == "__main__":
    main()
