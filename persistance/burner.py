import json
from utils._types import BurnersData, PendingBurners
from eth_typing import ChecksumAddress


def load_burners() -> list[BurnersData]:
    """Load burners from storage.

    Returns:
        list[BurnersData]: Burner data.
    """
    try:
        with open("data/burners.json") as file:
            return json.load(file)
    except FileNotFoundError:
        return []


def save_burners(burners: list[BurnersData]) -> None:
    """Save burners to storage

    Args:
        burners (list[BurnersData]): Burner data.
    """
    try:
        with open("data/burners.json", "w") as file:
            json.dump(burners, file, indent=2)

    except KeyboardInterrupt as error:
        with open("data/burners.json", "w") as file:
            json.dump(burners, file, indent=2)
        raise error from None


def load_pending_burners() -> list[PendingBurners]:
    """Load pending burners from storage.

    Returns:
        list[PendingBurners]: Pending burners time and addresses.
    """
    try:
        with open("data/pending_burners.json") as file:
            return json.load(file)
    except FileNotFoundError:
        return []


def save_pending_burners(pending_burners: list[PendingBurners]) -> None:
    """Save ``pending_burners`` to storage.

    Args:
        pending_burners (list[PendingBurners]): Pending burners time and addresses.
    """
    try:
        with open("data/pending_burners.json", "w") as file:
            json.dump(pending_burners, file, indent=2)

    except KeyboardInterrupt as error:
        with open("data/pending_burners.json", "w") as file:
            json.dump(pending_burners, file, indent=2)
        raise error from None
