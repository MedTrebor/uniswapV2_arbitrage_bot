from utils._types import Pools


def build_graph(pools: Pools) -> dict[str, dict[str, list[str]]]:
    """Build graph(adjacency list) out of pools.

    Args:
        pools (Pools): Pools datastracture.

    Returns:
        dict[str, dict[str, list[str]]]: Adjacency list.
            Mapping of `token_address` to `token_address` to `pool_addresses`.
    """
    adj_list: dict[str, dict[str, list[str]]] = {}  # type: ignore

    # iterating through every pool
    for pool_address, pool in pools.items():
        # extracting token addresses
        token0_address, token1_address = [
            address for address, _ in zip(pool.keys(), range(2))
        ]

        # build adjacency list for token0
        try:
            adj_tokens0 = adj_list[token0_address]

            try:
                adj_tokens0[token1_address].append(pool_address)
            except KeyError:
                adj_tokens0[token1_address] = [pool_address]

        except KeyError:
            adj_list[token0_address] = {token1_address: [pool_address]}

        # build adjacency list for token1
        try:
            adj_tokens1 = adj_list[token1_address]

            try:
                adj_tokens1[token0_address].append(pool_address)
            except KeyError:
                adj_tokens1[token0_address] = [pool_address]

        except KeyError:
            adj_list[token1_address] = {token0_address: [pool_address]}

    return adj_list
