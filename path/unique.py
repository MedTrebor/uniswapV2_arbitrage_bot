from rich.progress import track

from utils import Logger
from utils._types import Pools

log = Logger(__name__)


def get_unique_paths(
    pools: Pools, pool_to_paths: dict[str, tuple[tuple[str, ...], ...]]
) -> list[tuple[str, ...]]:
    """Filter out paths that contain ``pools`` whithout repating same path.

    Args:
        pools (Pools): Pools datastructure.
        pool_to_paths (dict[str, tuple[tuple[str, ...], ...]]): Pool to paths mapping.

    Returns:
        list[tuple[str, ...]]: List of paths.
    """
    unique_paths_s, unique_paths = set(), []
    for pool_address in pools.keys():
        try:
            for path in pool_to_paths[pool_address]:
                if path not in unique_paths_s:
                    unique_paths_s.add(path)
                    unique_paths.append(path)
        except KeyError:
            continue

    return unique_paths
