from time import perf_counter, sleep

from rich import print
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn

from web3 import HTTPProvider, IPCProvider, Web3
from web3.middleware import geth_poa_middleware, validation
from rich.traceback import install
from utils import CONFIG


install(extra_lines=6, show_locals=True)

validation.METHODS_TO_VALIDATE.clear()


def main():
    w3_remote = Web3(HTTPProvider("https://bsc-dataseed1.defibit.io/"))
    w3_local = Web3(IPCProvider("/home/medtrebor/bsc/data/geth.ipc"))

    remote_block = w3_remote.eth.block_number
    local_block = w3_local.eth.block_number

    # print(f"remote: {remote_block:,}")
    # print(f"local:  {local_block:,}")

    # exit()

    print()
    with Progress(
        " [b]{task.description}[/]:",
        "[{task.fields[delay_style]}]{task.fields[cur_block]:,}[/]/"
        "[{task.fields[rem_style]}]{task.fields[rem_block]:,}[/]",
        # " [b {task.fields[delay_style]}]{task.fields[delay]:>6.1f}[/]s",
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>6.2f}%"),
        TimeRemainingColumn(),
        "\n",
        transient=True,
    ) as progress:
        task = progress.add_task(
            "Synchronizing",
            total=short_block(remote_block),
            completed=short_block(local_block),
            cur_block=local_block,
            rem_block=remote_block,
            delay_style="default not b",
            delay=0,
            rem_style="green",
        )

        delay = 0
        delay_counter = start = perf_counter()
        # while local_block < remote_block:
        while True:
            sleep(0.01)
            local_block = w3_local.eth.block_number

            if local_block == remote_block:
                delay = 0
                delay_counter = 0
                delay_style = "green"
                rem_style = "green"

            elif local_block < remote_block:
                if not delay_counter:
                    delay_counter = perf_counter()
                delay += perf_counter() - delay_counter
                delay_counter = perf_counter()
                if delay < 0.1:
                    delay_style = "green"
                elif delay > 0.5:
                    delay_style = "red"
                else:
                    delay_style = "yellow"
                rem_style = "green"

            elif local_block > remote_block:
                if not delay_counter:
                    delay_counter = perf_counter()
                delay -= perf_counter() - delay_counter
                delay_counter = perf_counter()
                if delay > -0.1:
                    rem_style = "green"
                if delay < -0.5:
                    rem_style = "red"
                else:
                    rem_style = "yellow"
                delay_style = "i green"

            if perf_counter() - start > 0.1:
                start = perf_counter()
                remote_block = w3_remote.eth.block_number
                progress.update(
                    task,
                    total=short_block(remote_block),
                    completed=short_block(local_block),
                    cur_block=local_block,
                    rem_block=remote_block,
                    delay=delay,
                    delay_style=delay_style,
                    rem_style=rem_style,
                )

            else:
                progress.update(
                    task,
                    completed=short_block(local_block),
                    cur_block=local_block,
                    delay=delay,
                    delay_style=delay_style,
                    rem_style=rem_style,
                )


def short_block(num: int) -> int:
    str_num = str(num)
    return int(str_num[3:])


if __name__ == "__main__":
    try:
        main()

    except (SystemExit, KeyboardInterrupt):
        print("\n")
