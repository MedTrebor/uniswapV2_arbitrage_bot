import json


# def save_last_block(block_number: int, block_timestamp: int) -> None:
#     """Save last block number to storage.

#     Args:
#         block_number (int): Last block number.
#         block_timestamp (int): Last block timestamp.
#     """
#     try:
#         with open("data/last_block.json", "w") as file:
#             json.dump({"number": block_number, "timestamp": block_timestamp}, file)
#     except KeyboardInterrupt as error:
#         with open("data/last_block.json", "w") as file:
#             json.dump({"number": block_number, "timestamp": block_timestamp}, file)
#         raise error from None


# def get_last_block() -> tuple[int, int]:
#     """Get last block number and last block timestamp from storage if it exists.

#     Returns:
#         tuple[int, int]: Last block number and last block timestamp or `(0, 0)` if
#             there is no `last_block.json`.
#     """
#     try:
#         with open("data/last_block.json") as file:
#             last_block = json.load(file)
#             return last_block["number"], last_block["timestamp"]
#     except FileNotFoundError:
#         return 0, 0


def save_last_block(block_number: int) -> None:
    """Save last block number to storage.

    Args:
        block_number (int): Last block number.
    """
    try:
        with open("data/last_block.json", "w") as file:
            json.dump({"number": block_number}, file)
    except KeyboardInterrupt as error:
        with open("data/last_block.json", "w") as file:
            json.dump({"number": block_number}, file)
        raise error from None


def get_last_block() -> int:
    """Get last block number from storage if it exists.

    Returns:
        int: Last block number.
    """
    try:
        with open("data/last_block.json") as file:
            last_block = json.load(file)
            return last_block["number"]
    except FileNotFoundError:
        return 0