import json
from copy import deepcopy
from decimal import Decimal

from utils._types import TxStats, BalanceStats


# def save_tx_stats(tx_stats: TxStats):
#     try:
#         with open("data/tx_stats.json", "w") as file:
#             json.dump(tx_stats, file, indent=2)
#     except KeyboardInterrupt as error:
#         with open("data/tx_stats.json", "w") as file:
#             json.dump(tx_stats, file, indent=2)
#         raise error from None


# def load_tx_stats() -> TxStats:
#     try:
#         with open("data/tx_stats.json") as file:
#             return json.load(file)
#     except (FileNotFoundError, json.JSONDecodeError):
#         return {"total": 0, "success": 0, "fail": 0, "success_rate": 0, "profit": 0}


def save_balance_stats(stats: list[BalanceStats]) -> None:
    try:
        with open("data/balance_stats.json", "w") as file:
            json.dump(stats, file, indent=2)
    except KeyboardInterrupt as err:
        with open("data/balance_stats.json", "w") as file:
            json.dump(stats, file, indent=2)
        raise err from None


def load_balance_stats() -> list[BalanceStats]:
    try:
        with open("data/balance_stats.json") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def load_tx_stats() -> TxStats:
    try:
        with open("data/tx_stats.json") as file:
            return json.load(file)
    except FileNotFoundError:
        return {
            "uptime": 0,
            "total": 0,
            "success": 0,
            "fail": 0,
            "success_rate": 0,
            "bnb_profit": 0,
            "usd_profit": 0,
        }


def save_tx_stats(tx_stats: TxStats) -> None:
    _tx_stats = tx_stats.copy()
    _tx_stats["uptime"] = int(tx_stats["uptime"])

    try:
        with open("data/tx_stats.json", "w") as file:
            json.dump(_tx_stats, file, indent=2)

    except KeyboardInterrupt as err:
        with open("data/tx_stats.json", "w") as file:
            json.dump(_tx_stats, file, indent=2)
        raise err from None


def load_uptime() -> float:
    try:
        with open("data/uptime.txt") as file:
            return float(file.read())

    except FileNotFoundError:
        return 0.0

    except ValueError:
        return float(load_tx_stats()["uptime"])


def save_uptime(uptime: float) -> None:
    try:
        with open("data/uptime.txt", "w") as file:
            file.write(str(uptime))
    except KeyboardInterrupt as err:
        with open("data/uptime.txt", "w") as file:
            file.write(str(uptime))
        raise err from None
