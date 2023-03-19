from rich import print
from rich.traceback import install

from web3 import HTTPProvider, Web3
import web3

install(extra_lines=6, show_locals=True)


def main():
    provider = Web3(HTTPProvider("http://127.0.0.1:8545")).manager.provider

    tx_hash = "0x8177de2f4f8ed70c7f323609c3a1e70f3187aa1f824e79b8a0f4555e07a9dc52"

    res = provider.make_request(
        "debug_traceTransaction", [tx_hash, {"tracer": "callTracer"}]
    )

    print(res)


if __name__ == "__main__":
    main()
