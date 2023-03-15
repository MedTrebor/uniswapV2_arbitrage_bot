from time import perf_counter, sleep

from rich import print
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn

from web3 import HTTPProvider, IPCProvider, Web3
from web3.middleware import geth_poa_middleware, validation
from rich.traceback import install


install(extra_lines=6, show_locals=True)

validation.METHODS_TO_VALIDATE.clear()


def main():
    w3_remote = Web3(HTTPProvider("https://bsc-dataseed1.defibit.io/"))
    w3_local = Web3(IPCProvider("/mnt/ssd_sata3/bsc/geth.ipc"))

    remote_block = w3_remote.eth.block_number
    local_block = w3_local.eth.block_number

    print(f"remote: {remote_block:,}")
    print(f"local:  {local_block:,}")

    tx = w3_local.eth.get_transaction(
        "0x67bd0f50d88d07af2cd6d4b07ce7f9050ec8efdd857a4587d5ba7cbc9bc8c5e8"
    )
    print(dict(tx))
    exit()

    print()
    with Progress(
        " [b]{task.description}[/]:",
        "[yellow]{task.fields[cur_block]:,}[/]/[green]{task.fields[end_block]:,}[/]",
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>6.2f}%"),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task(
            "Synchronizing",
            total=short_block(remote_block),
            completed=short_block(local_block),
            cur_block=local_block,
            end_block=remote_block,
        )

        start = perf_counter()
        while local_block < remote_block:
            sleep(0.1)
            local_block = w3_local.eth.block_number

            if perf_counter() - start > 4.5:
                start = perf_counter()
                remote_block = w3_remote.eth.block_number
                progress.update(
                    task,
                    total=short_block(remote_block),
                    completed=short_block(local_block),
                    cur_block=local_block,
                    end_block=remote_block,
                )

            else:
                progress.update(
                    task, completed=short_block(local_block), cur_block=local_block
                )


def short_block(num: int) -> int:
    str_num = str(num)
    return int(str_num[2:])


if __name__ == "__main__":
    try:
        main()

    except (SystemExit, KeyboardInterrupt):
        print()
