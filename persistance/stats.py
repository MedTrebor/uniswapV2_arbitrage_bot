import json
from copy import deepcopy
from decimal import Decimal

from utils._types import TxStats


def save_tx_stats(tx_stats: TxStats):
    try:
        with open("data/tx_stats.json", "w") as file:
            json.dump(tx_stats, file, indent=2)
    except KeyboardInterrupt as error:
        with open("data/tx_stats.json", "w") as file:
            json.dump(tx_stats, file, indent=2)
        raise error from None


def load_tx_stats() -> TxStats:
    try:
        with open("data/tx_stats.json") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"total": 0, "success": 0, "fail": 0, "success_rate": 0, "profit": 0}
