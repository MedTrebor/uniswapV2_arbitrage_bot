from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from time import perf_counter
from typing import Iterator

from hexbytes import HexBytes

from blockchain import Web3
from network.prices import wei_usd_price
from utils import CONFIG, BlockTime, Logger, measure_time, str_obj
from utils._types import ArbArgs, BurnersData, GasParams, Pools, TxParams
from utils.datastructures import Arbitrage
from web3.exceptions import ContractLogicError
from web3.types import TxReceipt

from .arguments import create_arb_args, decode_arb_args
from .calculator import calc_gas_cost
from .exceptions import ArbitrageError, LateTransaction, MixedEstimation, NotProfitable

log = Logger(__name__)


def exe_arbs(
    potential_arbs: list[tuple[Arbitrage, Decimal, Decimal]],
    gas_params: GasParams,
    pools: Pools,
    burners: list[BurnersData],
    block_time: BlockTime,
) -> tuple[list[TxReceipt], list[Arbitrage], list[ArbArgs]]:
    w3 = Web3()

    # formatting transaction parameters
    transactions = format_transactions(w3, potential_arbs, pools, gas_params, burners)

    # executing transactions
    tx_hashes, arbs, arb_args = execute_transactions(
        w3, transactions, potential_arbs, block_time
    )

    # checking if trnasactions were submitted
    if not tx_hashes:
        return [], [], []

    # confirming transactions
    conf_s = "confirmations" if len(tx_hashes) > 1 else "confirmation"
    log_obj = tx_hashes if len(tx_hashes) > 1 else tx_hashes[0].hex()
    log.info(f"Waiting for {conf_s}: {log_obj}")

    # getting transaction receipts
    tx_receipts = [w3.wait_for_tx_receipt(tx_hash) for tx_hash in tx_hashes]

    return tx_receipts, arbs, arb_args


def format_transactions(
    w3: Web3,
    arbs_with_gas: list[tuple[Arbitrage, Decimal, Decimal]],
    pools: Pools,
    gas_params: GasParams,
    burners: list[BurnersData],
) -> list[TxParams]:
    account = w3.account
    burners = deepcopy(burners)

    transactions = []
    for arb, gas_usage, gas_price in arbs_with_gas:
        burner_addresses = get_burner_addresses(burners, arb.burners_count)
        arb_args = create_arb_args(arb, pools, burner_addresses)
        tx_params = create_tx_params(w3, arb_args, gas_params, gas_price, gas_usage)

        transactions.append(tx_params)
        w3.nonces[account] += 1

    return transactions


def reduce_gas(
    final_gas_price: Decimal, gas_reductions: int, reduction_denominator: Decimal
) -> Iterator[Decimal]:
    gas_price = final_gas_price
    for _ in range(gas_reductions):
        gas_price //= reduction_denominator
        yield gas_price


def recalculate_arb(arb: Arbitrage, gas_usage: Decimal, gas_price: Decimal):
    wei_price = wei_usd_price(arb.path[0])
    gas_cost = calc_gas_cost(gas_price, gas_usage, wei_price)
    neto_profit = arb.bruto_profit - gas_cost - arb.burners_cost
    wei_profit = neto_profit // wei_price

    arb.tx_cost = arb.amount_in + gas_cost + arb.burners_cost
    arb.neto_profit = neto_profit
    arb.wei_profit = wei_profit
    arb.gas_price = gas_price


def create_tx_params(
    w3: Web3,
    calldata: str,
    gas_params: GasParams | None = None,
    gas_price: Decimal | None = None,
    gas_limit: Decimal | None = None,
) -> TxParams:
    # creating base transaction parameters
    account = w3.account
    tx_params = {
        "from": account,
        "to": CONFIG["router"],
        "nonce": w3.nonce(account),
        "gas": int(int(gas_limit) * CONFIG["transaction"]["gas_limit_multiplier"]),
        "chainId": w3.chain_id,
        "data": calldata,
    }

    match gas_params:
        case None:
            # no gas parameters
            return tx_params

        case {"gasPrice": _}:
            # legacy transaction
            tx_params["gasPrice"] = int(gas_price)

        case {"maxFeePerGas": max_gas_fee, "maxPriorityFeePerGas": priority_fee}:
            # post london transaction
            base_fee = max_gas_fee - priority_fee
            tx_params["maxFeePerGas"] = int(gas_price)
            tx_params["maxPriorityFeePerGas"] = int(gas_price - base_fee)

    return tx_params


def get_burner_addresses(burners: list[BurnersData], count: int) -> list[str]:
    """Get next in line burner addresses from ``burners``.

    Args:
        burners (list[BurnersData]): Burners data.
        count (int): Number of burner addresses to get.

    Returns:
        list[str]: Burner addresses.
    """
    burner_addresses = []

    while len(burner_addresses) < count:
        try:
            burner_addresses.append(burners[0]["addresses"].pop())
        except IndexError:
            try:
                del burners[0]
            except IndexError:
                raise ArbitrageError("Not enough burners") from None

    return burner_addresses


def execute_transactions(
    w3: Web3,
    transactions: list[TxParams],
    potential_arbs: list[tuple[Arbitrage, Decimal, Decimal]],
    block_time: BlockTime,
) -> tuple[list[HexBytes], list[Arbitrage], list[ArbArgs]]:
    confirms = CONFIG["transaction"]["estimation_confirms"]
    tx_hashes, all_arb_args, arbs = [], [], []

    # executing transaction in each wave (increasing gas price)
    for tx_params, (arb, *_) in zip(transactions, potential_arbs, strict=True):
        try:
            arb_args = decode_arb_args(tx_params["data"])
            log.info(
                f"{datetime.now()}\n"
                f"ArbRouterV4{str_obj(arb_args, True)}\n"
                f"Transaction parameters: {str_obj(tx_params, True)}"
            )

            # checking gas
            gas_timer = measure_time("Gas estimetion time: {}")
            profitables, nonprofitables, errors = 0, 0, 0
            try:
                for gas in w3.batch_estimate_gas(tx_params):
                    if isinstance(gas, ContractLogicError) or isinstance(
                        gas, ValueError
                    ):
                        errors += 1
                        if errors >= confirms:
                            raise gas
                        continue

                    if gas < 60_000:
                        nonprofitables += 1
                        if nonprofitables >= confirms:
                            raise NotProfitable()
                        continue

                    profitables += 1
                    if profitables >= confirms:
                        if block_time() > CONFIG["transaction"]["final_tx"]:
                            raise LateTransaction(block_time())
                        break

                if profitables < confirms:
                    raise MixedEstimation(profitables, nonprofitables, errors)

            except (ContractLogicError, ValueError) as error:
                log.info(gas_timer())
                log.error(error)
                w3.nonces[w3.account] -= 1
                continue

            except (NotProfitable, LateTransaction, MixedEstimation) as error:
                log.info(gas_timer())
                log.warning(error)
                w3.nonces[w3.account] -= 1
                continue

            # executing transaction on each node
            tx_hash = w3.batch_transact(tx_params)

            log.info(gas_timer())

            tx_hashes.append(tx_hash)
            all_arb_args.append(arb_args)
            arbs.append(arb)

        except ValueError as error:
            # transaction is underpriced or mined
            log.error(error)
            break

    return tx_hashes, arbs, all_arb_args


# def format_transactions(
#     w3: Web3,
#     arbs_with_gas: list[tuple[Arbitrage, Decimal, Decimal]],
#     pools: Pools,
#     gas_params: GasParams,
#     burners: list[BurnersData],
# ) -> list[list[TxParams]]:
#     account = w3.account
#     gas_reductions = CONFIG["transaction"]["gas_reductions"]
#     reduction_denominator = Decimal(CONFIG["transaction"]["reduction_denominator"])
#     burners = deepcopy(burners)

#     # creating empty array for each trancacion (gas reductions + final transaction)
#     transactions = [[] for _ in range(gas_reductions + 1)]

#     for arb, gas_usage, final_gas_price in arbs_with_gas:
#         i = gas_reductions

#         # formatting final transaction
#         burner_addresses = get_burner_addresses(burners, arb.burners_count)
#         arb_args = create_arb_args(arb, pools, burner_addresses)
#         tx_params = create_tx_params(
#             w3, arb_args, gas_params, final_gas_price, gas_usage
#         )

#         transactions[i].append(tx_params)
#         i -= 1

#         # formatting transactions with lower gas price
#         for gas_price in reduce_gas(
#             final_gas_price, gas_reductions, reduction_denominator
#         ):
#             # mutating arb to match lower gas
#             recalculate_arb(arb, gas_usage, gas_price)

#             # foramtting transaction
#             arb_args = create_arb_args(arb, pools, burner_addresses)
#             tx_params = create_tx_params(w3, arb_args, gas_params, gas_price, gas_usage)

#             transactions[i].append(tx_params)
#             i -= 1

#         w3.nonces[account] += 1

#     return transactions


# def execute_transactions(
#     w3: Web3,
#     transactions: list[list[TxParams]],
#     block_time: BlockTime,
# ) -> tuple[list[HexBytes], list[ArbArgs]]:
#     confirms = CONFIG["transaction"]["estimation_confirms"]

#     # time of the final transaction (perf_counter)
#     final_tx_time = block_time.start_time + CONFIG["transaction"]["final_tx"]

#     # creating slot for each transaction in one wave
#     tx_hashes = [None] * len(transactions[0])
#     all_arb_args = [None] * len(transactions[0])
#     remove_idxs = []

#     # calculating wave wait durations
#     wait_count = len(transactions) - 1
#     wave_duration = (final_tx_time - perf_counter()) / wait_count

#     # executing transaction in each wave (increasing gas price)
#     for wave, wave_transactions in enumerate(transactions):
#         # FORCE REMOVED UNDERPRICED TRANSACTIONS
#         if wave == 0:
#             continue
#         # if wave:
#         #     # calculating wait time
#         #     target = final_tx_time - (wave_duration * (wait_count - wave))
#         #     wait_time = target - perf_counter()

#         #     # waiting for next transaction
#         #     if wait_time > 0:
#         #         sleep(wait_time)

#         try:
#             # going through all arb transactions in single wave
#             for i, tx_params in enumerate(wave_transactions):
#                 arb_args = decode_arb_args(tx_params["data"])
#                 log.info(
#                     f"{datetime.now()}\n"
#                     f"ArbRouterV4{str_obj(arb_args, True)}\n"
#                     f"Transaction parameters: {str_obj(tx_params, True)}"
#                 )

#                 # checking gas
#                 gas_timer = measure_time("Gas estimetion time: {}")
#                 profitables, nonprofitables, errors = 0, 0, 0
#                 try:
#                     for gas in w3.batch_estimate_gas(tx_params):
#                         if isinstance(gas, ValueError):
#                             errors += 1
#                             if errors >= confirms:
#                                 raise gas
#                             continue

#                         if gas < 60_000:
#                             nonprofitables += 1
#                             if nonprofitables >= confirms:
#                                 raise NotProfitable()
#                             continue

#                         profitables += 1
#                         if profitables >= confirms:
#                             if block_time() > CONFIG["transaction"]["final_tx"]:
#                                 raise LateTransaction(block_time())
#                             break

#                     if profitables < confirms:
#                         raise MixedEstimation(profitables, nonprofitables, errors)

#                     # if w3.estimator.eth.estimate_gas(tx_params) < 60_000:
#                     #     raise NotProfitable()
#                     # if block_time() > CONFIG["transaction"]["final_tx"]:
#                     #     raise LateTransaction(block_time())
#                 except ValueError as error:
#                     log.info(gas_timer())
#                     log.error(error)
#                     w3.nonces[w3.account] -= 1
#                     remove_idxs.append(i)
#                     continue
#                 except NotProfitable as error:
#                     log.info(gas_timer())
#                     log.warning(error)
#                     w3.nonces[w3.account] -= 1
#                     remove_idxs.append(i)
#                     continue
#                 except LateTransaction as error:
#                     log.info(gas_timer())
#                     log.warning(error)
#                     w3.nonces[w3.account] -= 1
#                     remove_idxs.append(i)
#                     continue
#                 except MixedEstimation as error:
#                     log.info(gas_timer())
#                     log.warning(error)
#                     w3.nonces[w3.account] -= 1
#                     remove_idxs.append(i)
#                     continue

#                 # executing transaction on each node
#                 tx_hash = w3.batch_transact(tx_params)

#                 log.info(gas_timer())

#                 tx_hashes[i] = tx_hash
#                 all_arb_args[i] = arb_args

#         except ValueError as error:
#             # transaction is underpriced or mined
#             log.error(error)
#             break

#     # removing bad transactions
#     for i, rm_idx in enumerate(remove_idxs):
#         del tx_hashes[rm_idx - i]
#         del all_arb_args[rm_idx - i]

#     return tx_hashes, all_arb_args
