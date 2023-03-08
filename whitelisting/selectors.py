from web3 import Web3

SWAP_SHORT_SIGNATURES = [
    "swapExactETHForTokens(uint256,address[],address,uint256)",
    "swapETHForExactTokens(uint256,address[],address,uint256)",
]

SWAP_LONG_SIGNATURES = [
    "swapExactTokensForTokens(uint256,uint256,address[],address,uint256)",
    "swapTokensForExactTokens(uint256,uint256,address[],address,uint256)",
    "swapTokensForExactETH(uint256,uint256,address[],address,uint256)",
    "swapExactTokensForETH(uint256,uint256,address[],address,uint256)",
]


def get_swap_selectors() -> tuple[set[str], set[str]]:
    short_selectors, long_selectors = set(), set()
    for signature in SWAP_SHORT_SIGNATURES:
        short_selectors.add(Web3.keccak(text=signature).hex()[:10])

    for signature in SWAP_LONG_SIGNATURES:
        long_selectors.add(Web3.keccak(text=signature).hex()[:10])

    return short_selectors, long_selectors


def get_pair_tokens_selectors() -> tuple[str, str]:
    token0 = Web3.keccak(text="token0()")
    token1 = Web3.keccak(text="token1()")

    return token0, token1
