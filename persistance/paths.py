import json


def load_no_tx_fee_paths() -> set[str]:
    """Load paths that don't have tokens with transfer fee from storage.

    Returns:
        set[str]: Paths.
    """
    try:
        with open("data/no_tx_fee_paths.json") as file:
            list_paths = json.load(file)
    except FileNotFoundError:
        return set()

    return set(list_paths)


def save_no_tx_fee_paths(no_tx_fee_paths: set[str]) -> None:
    """Save ``no_tx_fee_paths`` to storage.

    Args:
        no_tx_fee_paths (set[str]): Paths that don't have tokens with transfer fee.
    """
    list_paths = list(no_tx_fee_paths)
    try:
        with open("data/no_tx_fee_paths.json", "w") as file:
            json.dump(list_paths, file)
    except KeyboardInterrupt as error:
        with open("data/no_tx_fee_paths.json", "w") as file:
            json.dump(list_paths, file)
        raise error from None


def load_tx_fee_paths() -> set[str]:
    """Load paths that have tokens with transfer fee from storage.

    Returns:
        set[str]: Paths.
    """
    try:
        with open("data/tx_fee_paths.json") as file:
            list_paths = json.load(file)
    except FileNotFoundError:
        return set()

    return set(list_paths)


def save_tx_fee_paths(tx_fee_paths: set[str]) -> None:
    """Save ``tx_fee_paths`` to storage.

    Args:
        no_tx_fee_paths (set[str]): Paths that don't have tokens with transfer fee.
    """
    list_paths = list(tx_fee_paths)
    try:
        with open("data/tx_fee_paths.json", "w") as file:
            json.dump(list_paths, file)
    except KeyboardInterrupt as error:
        with open("data/tx_fee_paths.json", "w") as file:
            json.dump(list_paths, file)
        raise error from None


def load_blacklist_paths() -> set[tuple[str, ...]]:
    """Load paths that don't have tokens with transfer fee from storage.

    Returns:
        set[tuple[str, ...]]: Paths.
    """
    try:
        with open("data/blacklist_paths.json") as file:
            list_paths = json.load(file)
    except FileNotFoundError:
        return set()

    # converting all paths to tuples
    set_paths = set()
    for list_path in list_paths:
        set_paths.add(tuple(list_path))

    return set_paths


def save_blacklist_paths(blacklist_paths: set[tuple[str, ...]]) -> None:
    """Save ``blacklist_paths`` to storage.

    Args:
        blacklist_paths (set[tuple[str, ...]]): Paths that don't have tokens with transfer fee.
    """
    list_paths = list(blacklist_paths)
    try:
        with open("data/blacklist_paths.json", "w") as file:
            json.dump(list_paths, file)
    except KeyboardInterrupt as error:
        with open("data/blacklist_paths.json", "w") as file:
            json.dump(list_paths, file)
        raise error from None


def load_pre_blacklist_paths() -> dict[tuple[str, ...], int]:
    """Load mapping of path to revert count.

    Returns:
        pre_blacklist_paths: dict[tuple[str, ...], int]: Pre blacklist paths.
    """
    try:
        with open("data/pre_blacklist_paths.json") as file:
            str_pre_blacklist = json.load(file)
    except FileNotFoundError:
        return {}

    # converting to tuple
    pre_blacklist = {}
    for str_path, revert_to_count in str_pre_blacklist.items():
        pre_blacklist[tuple(str_path.split("-"))] = revert_to_count

    return pre_blacklist

def save_pre_blacklist_paths(
    pre_blacklist_paths: dict[tuple[str, ...], int]
) -> None:
    """Save ``pre_blacklist_paths`` to storage.

    Args:
        pre_blacklist_paths (dict[tuple[str, ...], int]):
            Mapping of string path to revert count.
    """
    # converting to str before saving
    str_pre_blacklist = {}
    for path, revert_count in pre_blacklist_paths.items():
        str_pre_blacklist["-".join(path)] = revert_count

    try:
        with open("data/pre_blacklist_paths.json", "w") as file:
            json.dump(str_pre_blacklist, file)
    except KeyboardInterrupt as error:
        with open("data/pre_blacklist_paths.json", "w") as file:
            json.dump(str_pre_blacklist, file)
        raise error from None

# def save_pre_blacklist_paths(
#     pre_blacklist_paths: dict[tuple[str, ...], dict[str, int]]
# ) -> None:
#     """Save ``pre_blacklist_paths`` to storage.

#     Args:
#         pre_blacklist_paths (dict[tuple[str, ...], dict[str, int]]):
#             Mapping of string path to revert message to revert count.
#     """
#     # converting to str before saving
#     str_pre_blacklist = {}
#     for path, revert_to_count in pre_blacklist_paths.items():
#         str_pre_blacklist["-".join(path)] = revert_to_count

#     try:
#         with open("data/pre_blacklist_paths.json", "w") as file:
#             json.dump(str_pre_blacklist, file)
#     except KeyboardInterrupt as error:
#         with open("data/pre_blacklist_paths.json", "w") as file:
#             json.dump(str_pre_blacklist, file)
#         raise error from None

# def load_pre_blacklist_paths() -> dict[tuple[str, ...], dict[str, int]]:
#     """Load mapping of path to revert message to revert count.

#     Returns:
#         pre_blacklist_paths: dict[tuple[str, ...], dict[str, int]]: Pre blacklist paths.
#     """
#     try:
#         with open("data/pre_blacklist_paths.json") as file:
#             str_pre_blacklist = json.load(file)
#     except FileNotFoundError:
#         return {}

#     # converting to tuple
#     pre_blacklist = {}
#     for str_path, revert_to_count in str_pre_blacklist.items():
#         pre_blacklist[tuple(str_path.split("-"))] = revert_to_count

#     return pre_blacklist