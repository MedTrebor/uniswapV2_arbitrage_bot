from datetime import datetime

from rich import print

import persistance
from blockchain import Web3, get_weth_price, multicall, update_prices, prices
from core.price import create_price_pools
from utils import CONFIG
from web3.contract.contract import Contract
from rich.traceback import install

install(extra_lines=6, show_locals=True)


def main():
    w3 = Web3()
    update_prices(create_price_pools())
    all_stats = persistance.load_balance_stats()

    token_abi = persistance.get_ERC20_abi()
    tokens = [w3.eth.contract(add, abi=token_abi) for add in CONFIG["paths"]["tokens"]]

    bnb_price = get_bnb_price()

    tokens_balance = get_tokens_balance(tokens)
    executor_balance = w3.eth.get_balance(w3.account)
    burner_generator_balance = w3.eth.get_balance(w3.burner_generator)

    stats = {
        "time": str(datetime.now()),
        "executor": executor_balance,
        "burner_generator": burner_generator_balance,
        "router": tokens_balance,
        "bnb_price": bnb_price,
        "burners": get_burners_count(),
    }
    all_stats.append(stats)

    persistance.save_balance_stats(all_stats)


def get_tokens_balance(tokens: list[Contract]) -> dict[str, int]:
    router = CONFIG["router"]
    parmas = [multicall.encode(token, "symbol") for token in tokens]
    parmas += [multicall.encode(token, "balanceOf", [router]) for token in tokens]

    encoded = multicall.call(parmas)
    half = len(encoded) // 2

    symbols = [multicall.decode(enc, ["string"])[0] for enc in encoded[:half]]
    balances = [multicall.decode(enc, ["uint256"])[0] for enc in encoded[half:]]

    wei_prices = [float(get_weth_price(t.address)) for t in tokens]

    tokens_info = []
    for symbol, balance, wei_price in zip(symbols, balances, wei_prices, strict=True):
        wei_balance = balance if wei_price == 1 else int(balance // wei_price)
        current_info = {
            "symbol": symbol,
            "balance": balance,
            "wei_balance": wei_balance,
        }

        for token_info in tokens_info:
            if token_info["symbol"] == symbol:
                token_info["balance"] += balance

                if wei_price == 1:
                    wei_balance = token_info["balance"]
                else:
                    wei_balance = int(token_info["balance"] // wei_price)

                token_info["wei_balance"] = wei_balance
                current_info = None

        if current_info:
            tokens_info.append(current_info)

    return tokens_info


def get_bnb_price() -> float:
    return float(get_weth_price("0x55d398326f99059fF775485246999027B3197955"))


def get_burners_count() -> int:
    all_burners_data = persistance.load_burners()

    count = 0
    for data in all_burners_data:
        count += len(data["addresses"])

    return count


if __name__ == "__main__":
    main()
