import os
import sys
from pyaml_env import parse_config
from argparse import ArgumentParser

from ._types import ConfigDict
from .datastructures import SecretStr

CONFIG: ConfigDict = {}  # type: ignore


def load_config() -> None:
    """Load `config.yaml` and do conversion and safety checks."""
    network = get_network()

    global CONFIG
    CONFIG = parse_config(f"config_{network}.yaml")

    # Hiding sensitive info
    hide_sensitive_info(CONFIG)

    # if no ignored coins, converting to list
    if not CONFIG["paths"]["ignored"]:
        CONFIG["paths"]["ignored"] = []


def get_network() -> str:
    """Get network name.

    Returns:
        str: Network name.
    """
    program = os.path.basename(sys.argv[0])
    if program == "pytest" or program == "uvicorn":
        return "test"

    parser = ArgumentParser(
        "Arbitrage Bot", description="Arbitrage between UniswapV2 type exchanges."
    )
    parser.add_argument(
        "-n",
        metavar="NETWORK",
        help="blockchain network name",
        choices=["bsc", "ganache", "bsc_fork"],
        default="bsc",
        required=False,
        dest="network",
    )
    return parser.parse_args().network


def hide_sensitive_info(config: dict) -> None:
    config["blockchain"]["account"] = SecretStr(config["blockchain"]["account"])
    config["blockchain"]["endpoints"]["main"] = SecretStr(config["blockchain"]["endpoints"]["main"])
    config["blockchain"]["endpoints"]["sync"] = SecretStr(config["blockchain"]["endpoints"]["sync"])
    config["blockchain"]["endpoints"]["other"] = [
        SecretStr(url) for url in config["blockchain"]["endpoints"]["other"]
    ]

    config["price"]["url"] = SecretStr(config["price"]["url"])


load_config()
