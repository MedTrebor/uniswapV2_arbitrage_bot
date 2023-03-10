from rich import print

import persistance


def main():
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
