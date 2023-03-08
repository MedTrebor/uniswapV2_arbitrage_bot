import json
from datetime import datetime


def save_router_stats(router_stats: dict) -> None:
    """Save router success, fail stats.

    Args:
        router_stats (dict): Router stats.
    """
    try:
        with open("data/router_stats.json", "w") as file:
            json.dump(router_stats, file)
    except KeyboardInterrupt as err:
        with open("data/router_stats.json", "w") as file:
            json.dump(router_stats, file)
        raise err from None


def load_router_stats() -> dict:
    """Load router stats from storage.

    Returns:
        dict: Router stats.
    """
    try:
        with open("data/router_stats.json") as file:
            return json.load(file)
    except FileNotFoundError:
        return {"success": 0, "error": 0}


def save_router_support_fee_stats(router_stats: dict) -> None:
    """Save router support fee success, fail stats.

    Args:
        router_stats (dict): Router support fee stats.
    """
    try:
        with open("data/router_support_fee_stats.json", "w") as file:
            json.dump(router_stats, file)
    except KeyboardInterrupt as err:
        with open("data/router_support_fee_stats.json", "w") as file:
            json.dump(router_stats, file)
        raise err from None


def load_router_support_fee_stats() -> dict:
    """Load router support fee stats from storage.

    Returns:
        dict: Router support fee stats.
    """
    try:
        with open("data/router_support_fee_stats.json") as file:
            return json.load(file)
    except FileNotFoundError:
        return {"success": 0, "error": 0}


def load_success_stats() -> dict:
    """Load success stats from storage.

    Returns:
        dict: Success stats.
    """
    try:
        with open("data/success_stats.json") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


def save_success_stats(success_stats: dict, indent=2) -> None:
    """Save success stats to storage.

    Args:
        success_stats (dict): Success stats.
    """
    try:
        with open("data/success_stats.json", "w") as file:
            json.dump(success_stats, file, indent=2)
    except KeyboardInterrupt as error:
        with open("data/success_stats.json", "w") as file:
            json.dump(success_stats, file, indent=2)
        raise error from None


def load_no_tx_fee_stats() -> dict:
    """Load no transfer fee stats from storage.

    Returns:
        dict: no transfer fee stats.
    """
    try:
        with open("data/no_tx_fee_stats.json") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


def save_no_tx_fee_stats(no_tx_fee_stats: dict) -> None:
    """Save no transfer fee stats from storage.

    Args:
        no_tx_fee_stats (dict): no transfer fee stats.
    """
    try:
        with open("data/no_tx_fee_stats.json", "w") as file:
            json.dump(no_tx_fee_stats, file, indent=2)
    except KeyboardInterrupt as error:
        with open("data/no_tx_fee_stats.json", "w") as file:
            json.dump(no_tx_fee_stats, file, indent=2)
        raise error from None


def load_gas_limit_error() -> dict:
    """Load gas limit error stats from storage.

    Returns:
        dict: Gas limit error stats.
    """
    try:
        with open("data/gas_limit_error.json") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


def save_gas_limit_error(gas_limit_error: dict) -> None:
    """Save gas limit error stats to storage.

    Args:
        gas_limit_error (dict): Gas limit error stats.
    """
    try:
        with open("data/gas_limit_error.json", "w") as file:
            json.dump(gas_limit_error, file, indent=2)
    except KeyboardInterrupt as error:
        with open("data/gas_limit_error.json", "w") as file:
            json.dump(gas_limit_error, file, indent=2)
        raise error from None


def save_error(error: BaseException):
    """Save error to storage.

    Args:
        error (BaseException): Error.
    """
    error_type = str(type(error))
    start_idx = error_type.index("'") + 1
    stop_idx = error_type.index("'", start_idx)
    error_type = error_type[start_idx:stop_idx]

    error_str = f"{error_type}: {str(error)}"

    try:
        with open("data/errors.json") as file:
            errors = json.load(file)
    except FileNotFoundError:
        errors = {}

    errors[str(datetime.now())] = error_str

    try:
        with open("data/errors.json", "w") as file:
            json.dump(errors, file, indent=2)
    except KeyboardInterrupt:
        with open("data/errors.json", "w") as file:
            json.dump(errors, file, indent=2)
        exit()


def save_reverted_stats(stats: dict):
    try:
        with open("data/reverted_stats.json", "w") as file:
            json.dump(stats, file, indent=2)
    except KeyboardInterrupt as error:
        with open("data/reverted_stats.json", "w") as file:
            json.dump(stats, file, indent=2)
        raise error from None


def load_reverted_stats() -> dict:
    try:
        with open("data/reverted_stats.json") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
