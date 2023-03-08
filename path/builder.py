from datetime import timedelta
from multiprocessing.pool import AsyncResult
from multiprocessing.pool import Pool as ProcessPool
from time import perf_counter

from utils import CONFIG, Logger

log = Logger(__name__)


def build_paths(
    graph: dict[str, dict[str, list[str]]],
    tokens: list[str],
    length: int,
    blacklist_paths: set[tuple[str, ...]],
    process_pool: ProcessPool,
) -> dict[str, tuple[tuple[str, ...], ...]]:
    """Build all possible paths with maximum provided ``length`` that
    start and end with given ``tokens``.

    Note:
        Path is a list containg `token`, `pool` `token` sequence.
        There will always be 1 `token` more than `pool`.


    Args:
        graph (dict[str, dict[str, list[str]]]): Graph datastructure.
        tokens (list[str]): List of token addresses.
        length (int): Maximum length.
        blacklist_paths (set[tuple[str, ...]]): Blacklisted paths.
        process_pool (ProcessPool): Process pool.

    Returns:
        dict[str, tuple[tuple[str, ...], ...]]: Mapping of pool address to
            paths
    """
    # normalizing length value
    compare_length = length * 2 - 1

    # pool_to_paths: dict[str, list[int]] = {}  # type: ignore
    pool_to_paths: dict[str, list[tuple[str, ...]]] = {}  # type: ignore

    tasks = []
    for token in tokens:
        final_tokens = set(CONFIG["weths"]) if token in CONFIG["weths"] else {token}

        tasks.append(
            process_pool.apply_async(
                find_paths,
                [graph, token, final_tokens, compare_length, blacklist_paths],
            )
        )

    for task in tasks:
        map_paths(pool_to_paths, task.get())

    tuplize_paths(pool_to_paths)
    return pool_to_paths  # type: ignore


def find_paths(
    graph: dict[str, dict[str, list[str]]],
    start_token: str,
    final_tokens: set[str],
    compare_length: int,
    blacklist_paths: set[tuple[str, ...]],
) -> list[tuple[str, ...]]:
    """Find paths starting at ``start_token`` and ending at ``final_tokens``.

    Args:
        graph (dict[str, dict[str, list[str]]]): Graph datastructure.
        start_token (str): Address of token.
        final_tokens (set[str]): Final tokens.
        compare_length (int): Length of paths where it no longer adds to stack
            and tries to finalize path.
        blacklist_paths (set[tuple[str, ...]]): Blacklisted paths.

    Returns:
        list[tuple[str, ...]]: List of paths.
    """
    log.debug(f"Creating paths from {start_token} to {final_tokens}.")
    start_time = perf_counter()

    stack: list[list[str]] = [[start_token]]  # type: ignore
    current_path: list[str] = []  # type: ignore
    final_paths: list[tuple[str, ...]] = []  # type: ignore

    while True:
        try:
            # getting current token and clearing stack2
            current_token = stack[-1].pop()
            try:
                current_path.append(stack[-1].pop())
            except IndexError:
                # in case only first token is in stack
                pass
            current_path.append(current_token)

        # if stack2 is ampty, clear stack1
        except IndexError:
            stack.pop()
            current_path.pop()

            # there are no more paths
            if not current_path:
                break

            current_path.pop()
            continue

        if len(current_path) == compare_length:
            # try to finalize paths
            _finalize_path(
                graph, final_tokens, current_path, final_paths, blacklist_paths
            )
            stack.append([])
            continue

        # finding neighbors and adding them to stack
        stack.append(
            _find_neighbors(
                graph,
                current_token,
                final_tokens,
                current_path,
                final_paths,
                blacklist_paths,
            )
        )

    log.debug(
        f"Created {len(final_paths):,} paths from {start_token} to "
        f"{final_tokens} in {timedelta(seconds=perf_counter() - start_time)}."
    )

    return final_paths


def _finalize_path(
    graph: dict[str, dict[str, list[str]]],
    final_tokens: set[str],
    current_path: list[str],
    final_paths: list[tuple[str, ...]],
    blacklist_paths: set[tuple[str, ...]],
) -> None:
    """Add final pool and token to current path fo finalize it
    and add it to ``final_paths``.

    Args:
        graph (dict[str, dict[str, list[str]]]): Graph datastructure.
        final_tokens (set[str]): Finish tokens.
        current_path (list[str]): Path datastrucure.
        final_paths (list[tuple[str, ...]]): List of paths.
        blacklist_paths (set[tuple[str, ...]]): Blacklisted paths.
    """
    for final_token in final_tokens:

        try:
            final_pools = graph[current_path[-1]][final_token]
        except KeyError:
            # no final token in neighbor tokens
            continue

        for pool in final_pools:
            if pool in current_path:
                # pool already visited
                continue

            final_path = current_path.copy()
            final_path.append(pool)
            final_path.append(final_token)
            final_path = tuple(final_path)

            # check if path is blacklisted
            if final_path in blacklist_paths:
                continue

            final_paths.append(final_path)


def _find_neighbors(
    graph: dict[str, dict[str, list[str]]],
    current_token: str,
    final_tokens: set[str],
    current_path: list[str],
    final_paths: list[tuple[str, ...]],
    blacklist_paths: set[tuple[str, ...]],
) -> list[str]:
    """Add neighbor tokens and pools to ``stack`` or if it's
    finished to ``final_paths``.

    Args:
        graph (dict[str, dict[str, list[str]]]): Graph datastructure.
        current_token (str): Find neighbors of ``current_token``.
        final_tokens (set[str]): End tokens.
        current_path (list[str]): Current created path.
        final_paths (list[tuple[str, ...]]): List of finished paths.
        blacklist_paths (set[tuple[str, ...]]): Blacklisted paths.

    Returns:
        list[str]: Stack2 (substack).
    """
    stack2 = []
    # finding neighbors
    for neighbor_token, pools in graph[current_token].items():
        # end case
        if neighbor_token in final_tokens:
            for pool in pools:
                if pool in current_path:
                    continue

                final_path = current_path.copy()
                final_path.append(pool)
                final_path.append(neighbor_token)
                final_path = tuple(final_path)

                # check if path is blacklisted
                if final_path in blacklist_paths:
                    continue

                final_paths.append(final_path)
            continue

        # adding to stack
        for pool in pools:
            if pool in current_path:
                continue

            stack2.append(pool)
            stack2.append(neighbor_token)

    return stack2


def map_paths(
    pool_to_paths: dict[str, list[tuple[str, ...]]], paths: list[tuple[str, ...]]
) -> None:
    """Map paths to pools that they path through.

    Args:
        pool_to_paths (dict[str, list[int]]): Mapping of pool address to path index.
        paths (list[list[str]]): List of path datastructure.
        start_idx (int): Index at which to start mapping.
    """
    for path in paths:
        for i in range(1, len(path), 2):
            try:
                pool_to_paths[path[i]].append(path)
            except KeyError:
                pool_to_paths[path[i]] = [path]


def tuplize_paths(pool_to_paths: dict[str, list[tuple[str, ...]]]):
    for address, paths in pool_to_paths.items():
        pool_to_paths[address] = tuple(paths)  # type: ignore
