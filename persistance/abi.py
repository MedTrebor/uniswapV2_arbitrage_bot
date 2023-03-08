import json


def get_abi(contract: str) -> list:
    """Get ABI of contract from storage.

    Args:
        contract (str): Contract name withot `.json` extension.

    Returns:
        list: ABI of provided contract.
    """
    with open(f"blockchain/contracts/abi/{contract}.json") as file:
        return json.load(file)


def get_factory_abi() -> list:
    """Get ABI of the `UniswapV2Factory`.

    Returns:
        list: ABI of the `UniswapV2Factory`.
    """
    return get_abi("UniswapV2Factory")


def get_pair_abi() -> list:
    """Get ABI of the `UniswapV2Pair`.

    Returns:
        list: ABI of the `UniswapV2Pair`.
    """
    return get_abi("UniswapV2Pair")


def get_multicall_abi() -> list:
    """Get ABI of the `Multicall2`.

    Returns:
        list: ABI of the `Multicall2`.
    """
    return get_abi("Multicall2")


def get_ERC20_abi() -> list:
    """Get ABI of the `ERC20`.

    Returns:
        list: ABI of the `ERC20`.
    """
    return get_abi("IERC20")
