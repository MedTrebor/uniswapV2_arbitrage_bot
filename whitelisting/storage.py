import json
from multiprocessing import Lock


def save_tokens(tokens: set[str], lock: Lock) -> None:
    try:
        with lock:
            with open("data/whitelist_tokens.json", "w") as file:
                json.dump(list(tokens), file)
    except KeyboardInterrupt:
        with lock:
            with open("data/whitelist_tokens.json", "w") as file:
                json.dump(list(tokens), file)


def load_tokens(lock: Lock) -> set[str]:
    try:
        with lock:
            with open("data/whitelist_tokens.json") as file:
                return set(json.load(file))
    except FileNotFoundError:
        return set()
