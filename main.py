import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from multiprocessing.managers import SyncManager
from multiprocessing.pool import Pool as ProcessPool
from time import perf_counter, sleep, time

import arbitrage
import blockchain
import persistance
from core import PricePollInterval, loader, logger, processes, whitelist
from network import prices
from utils import CONFIG, BlockTime, Logger, TimePassed, WaitPrevious, measure_time

log = Logger(__name__)


def main(process_mngr: SyncManager, process_pool: ProcessPool):
    log.info("[i][b u]ARBITRAGE BOT[/] started.")

    network = CONFIG["blockchain"]["name"]

    w3 = blockchain.Web3(new_singleton=True)
    price = PricePollInterval(network, new_singleton=True)

    thread_executor = ThreadPoolExecutor(thread_name_prefix="Thread")

    poll_main = WaitPrevious(CONFIG["poll"]["main"])
    poll_pools = TimePassed(CONFIG["poll"]["pools"])
    save_pre_blacklist = TimePassed()
    save_pools = TimePassed(60 * 5)

    (
        pools,
        pool_numbers,
        last_block,
        blacklist_paths,
        pre_blacklist_paths,
        burners,
    ) = loader.load_data()

    # NOT WORKING
    # blockchain.remove_all_used_burners(burners)
    #
    # persistance.save_burners(burners)

    # SKIP CREATING BURNERS
    blockchain.create_burners(burners, w3.account)
    persistance.save_burners(burners)

    price.start()

    if not CONFIG["download_pools"]:
        poll_pools()
        processes.share_pools(process_mngr, process_pool, network, pools)
        pool_to_paths = loader.build_paths(pools, blacklist_paths, process_pool)
        processes.share_paths(process_mngr, process_pool, network, pool_to_paths)

    try:
        # main loop
        while True:
            poll_main()

            # getting new pools
            if poll_pools():
                new_pools, pool_numbers = loader.get_new_pools(pool_numbers)

                if new_pools:
                    pools.update(new_pools)

                    log_str = measure_time("Updated {:,} new {} in {}.")
                    blockchain.update_pools(new_pools)
                    pool_s = "pool" if len(new_pools) == 1 else "pools"
                    log.info(log_str(len(new_pools), pool_s))

                log_str = measure_time("Finished filtering pools in {}.")
                blockchain.filter_pools(pools, pool_numbers)
                log.debug(log_str())

                # sharing pools with workers
                processes.share_pools(process_mngr, process_pool, network, pools)

                log_str = measure_time("Finished building paths in {}.")
                pool_to_paths = loader.build_paths(pools, blacklist_paths, process_pool)
                log.debug(log_str())

                # sharing paths with workers
                processes.share_paths(
                    process_mngr, process_pool, network, pool_to_paths
                )

                persistance.save_pools(pools)
                persistance.save_pool_numbers(pool_numbers)

            # save all pools that have change to not miss updating
            to_update = {}
            # getting first changed pools
            (
                updated_changed_pools,
                changed_pools,
                last_block,
            ) = blockchain.get_changed_pools(pools, last_block)

            if len(updated_changed_pools) != len(changed_pools):
                # if all pools are updated
                log_str = measure_time("All pools updated in {}.")
                blockchain.update_pools(changed_pools)
                processes.update_pools(
                    process_mngr, process_pool, changed_pools, network
                )
                persistance.save_pools(pools)
                persistance.save_last_block(last_block)
                save_pools()
                log.info(log_str())
                continue

            # first changed pools needs to be empty to proceed
            while changed_pools:
                to_update.update(changed_pools)
                changed_pools = blockchain.get_changed_pools(pools, last_block)[1]

            # getting newest first pool (first time they change)
            while not changed_pools:
                block_time = BlockTime()
                start = block_start = perf_counter()

                (
                    updated_changed_pools,
                    changed_pools,
                    last_block,
                ) = blockchain.get_changed_pools(pools, last_block)

            to_update.update(changed_pools)
            changed_log = f"{len(changed_pools):,} changed pools in {timedelta(seconds=perf_counter() - start)}."
            end_log = "\n" + changed_log + "\n"

            # updating pools
            start = perf_counter()
            blockchain.update_pools(to_update)
            update_log = (
                f"Finished updating pools in {timedelta(seconds=perf_counter()-start)}."
            )
            log.debug(update_log)
            end_log += update_log + "\n"

            log_str = measure_time("New pools exported to workers in {}.")
            processes.update_pools(process_mngr, process_pool, to_update, network)
            export_log = log_str()
            log.debug(log_str())
            end_log += export_log + "\n"

            # TEMP: checking if reserve is ok in sync event
            # if len(copied_pools) == len(changed_pools):
            #     checker.check_pools(changed_pools, copied_pools)

            # getting gas params for checker and real execution
            (
                min_gas_price,
                low_gas_price,
                mid_gas_price,
                max_gas_price,
            ) = price.gas_prices
            eth_price = prices.eth_price

            start = perf_counter()
            raw_arbitrages = processes.search_arbs(
                process_mngr,
                changed_pools,
                min_gas_price,
                low_gas_price,
                mid_gas_price,
                max_gas_price,
                eth_price,
                process_pool,
                network,
            )
            arbitrage_s = "arbitrage" if len(raw_arbitrages) == 1 else "arbitrages"
            arb_log = f"Calculated {len(raw_arbitrages):,} potential {arbitrage_s} in {timedelta(seconds=perf_counter()-start)}."
            log.debug(arb_log)
            end_log += arb_log + "\n"

            # iterage through potentially profitable arbitrages
            if raw_arbitrages:
                to_blacklist = set()

                start = perf_counter()
                potential_arbs = arbitrage.check_arbs(
                    raw_arbitrages,
                    blacklist_paths,
                    pre_blacklist_paths,
                    pools,
                    min_gas_price,
                    low_gas_price,
                    mid_gas_price,
                    max_gas_price,
                    to_blacklist,
                )
                check_log = f"Checked {len(raw_arbitrages):,} potential {arbitrage_s} in {timedelta(seconds=perf_counter()-start)}."
                log.debug(check_log)
                end_log += check_log + "\n"

                # proceed to execution only if maximum delay wasn't breached
                if potential_arbs:
                    logger.log_potential_arbs(potential_arbs)

                    end_log += f"Checked all in {timedelta(seconds=perf_counter() - block_start)}."
                    log.info(end_log)
                    end_log = None

                    # tx_receipts = None
                    tx_receipts, arb_args = arbitrage.exe_arbs(
                        potential_arbs,
                        price.gas_params,
                        pools,
                        burners,
                        block_time,
                    )

                    if tx_receipts:
                        # removing used burners
                        used_burners = []
                        for receipt in tx_receipts:
                            used_burners.extend(
                                blockchain.get_used_burnerns(receipt["transactionHash"])
                            )
                            log.info(
                                f"Last block: {last_block:,}, Execution block: {receipt['blockNumber']:,}"
                            )
                        log.info(f"Used burners: {used_burners}")
                        blockchain.remove_used_burners(burners, used_burners)
                        persistance.save_burners(burners)

                        logger.log_executed_arbs(tx_receipts, arb_args, used_burners)

                        blockchain.create_burners(burners, w3.account)
                        persistance.save_burners(burners)

                log.debug(
                    "Finished checking potential arbitrages in "
                    f"{timedelta(seconds=perf_counter() - start)}."
                )

                if to_blacklist:
                    if end_log:
                        end_log += f"Checked all in {timedelta(seconds=perf_counter() - block_start)}."
                        log.info(end_log)

                    count = len(to_blacklist)
                    path_s = "path" if count == 1 else "paths"
                    log.info(f"Blacklisted {count:,} {path_s}.")

                    persistance.save_pre_blacklist_paths(pre_blacklist_paths)
                    persistance.save_blacklist_paths(blacklist_paths)

                    log_str = measure_time(
                        "Removed blacklisted paths in workers in {}."
                    )
                    processes.remove_blacklisted(
                        process_mngr, process_pool, pool_to_paths, to_blacklist, network
                    )
                    log.debug(log_str())

                # exit if executed
                # if potential_arbs:
                #     exit()

            if save_pre_blacklist():
                persistance.save_pre_blacklist_paths(pre_blacklist_paths)

            if save_pools():
                persistance.save_pools(pools)
                persistance.save_last_block(last_block)

    except (KeyboardInterrupt, SystemExit) as error:
        raise error

    except BaseException as error:
        restart_conf = CONFIG["restart"]
        log.exception(error)
        # TEMP
        exit()
        try:
            # cooldown has passed
            if time() - last_wait > restart_conf["cooldown"]:
                wait = restart_conf["wait"]
            # increase timer if cooldown hasn't passed
            else:
                wait *= restart_conf["multiplier"]
                wait = min(wait, restart_conf["max_wait"])
        except UnboundLocalError:
            # first time error
            wait = restart_conf["wait"]

        last_wait = time()
        log.warning(f"Restarting in {timedelta(seconds=wait)}.")
        sleep(wait)

    finally:
        thread_executor.shutdown(True, cancel_futures=True)
        price.kill()


if __name__ == "__main__":
    print("\033]0;ARBITRAGE BOT\007")
    multiprocessing.current_process().name = "BSC"

    lock = multiprocessing.Lock()
    multiprocessing.Process(
        target=whitelist.main, args=[lock], name="Whitelister", daemon=True
    ).start()

    process_mngr, process_pool = processes.create_process_pool()

    try:
        while True:
            main(process_mngr, process_pool)
    except (KeyboardInterrupt, SystemExit):
        print()
    except BaseException as error:
        log.critical(error, exc_info=True)
    finally:
        process_pool.close()
        process_pool.join()
        process_pool.terminate()
        process_mngr.shutdown()
        process_mngr.join()
