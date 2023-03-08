def get_bytecode(contract: str) -> str:
    """Get bytecode of contract from storage.

    Args:
        contract (str): Contract name without `.bin` extension.

    Returns:
        str: Bytecode of the provided contract.
    """
    with open(f"blockchain/contracts/bytecode/{contract}.bin", "rb") as file:
        return file.read().hex()


def get_factory_bytecode() -> str:
    """Get bytecode of the `UniswapV2Factory`.

    Returns:
        str: Bytecode of the `UniswapV2Factory`.
    """
    return get_bytecode("UniswapV2Factory")


def get_multicall_bytecode() -> str:
    """Get bytecode of the `Multicall2`.

    Returns:
        str: Bytecode of the `Multicall2`.
    """
    return get_bytecode("Multicall2")