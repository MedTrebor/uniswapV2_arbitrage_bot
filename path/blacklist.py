def remove_from_paths(
    pool_to_paths: dict[str, tuple[tuple[str, ...], ...]],
    to_blacklist: set[tuple[str, ...]],
) -> None:
    updated_pool_to_paths = {}

    # going through each pool withi its paths
    for pool_address, paths in pool_to_paths.items():

        to_remove = set()

        for path in paths:
            if path in to_blacklist:
                # adding to_removed to be later removed from paths
                to_remove.add(path)

        if to_remove:
            updated_pool_to_paths[pool_address] = tuple(
                set(paths).difference(to_remove)
            )

    # updating paths
    pool_to_paths.update(updated_pool_to_paths)
