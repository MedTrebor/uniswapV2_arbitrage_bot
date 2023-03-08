from utils.logger import Logger, str_obj
from utils._types import Pools

log = Logger(__name__)


def check_pools(changed_pools: Pools, copied_pools: Pools):
    same, diff, diff_pools = 0, 0, []
    for pool_address, pool in copied_pools.items():
        all_pool = changed_pools[pool_address]

        for all_pool_value, changed_pool_value in zip(
            all_pool.values(), pool.values(), strict=True
        ):
            if all_pool_value == changed_pool_value:
                same += 1
                continue

            diff_pools.append((all_pool, pool))
            diff += 1
            break

    if same and diff:
        str_diff_pools = str_obj(diff_pools, True)
        log.warning(
            f"Same pools: {same:,}, Different pools: {diff:,}"
            f"\nPools: {str_diff_pools}"
        )
