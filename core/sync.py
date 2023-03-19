from utils import CONFIG, BlockTime, Logger
from blockchain import Web3
from threading import Lock, Thread


log = Logger(__name__)

_current_block: int
_block_time: BlockTime
_running: bool = False
_lock: Lock = Lock()


def _sync_worker() -> None:
    global _block_time, _current_block, _running, _lock
    w3 = Web3()

    last_block = w3.sync_node.eth.block_number

    log.info("Node Sync started.")

    while _running:
        new_block = w3.sync_node.eth.block_number

        if new_block != last_block:
            with _lock:
                _current_block = new_block
                _block_time = BlockTime()
            last_block = new_block


def start() -> None:
    global _running
    _running = True

    thread = Thread(target=_sync_worker, name="SyncThread", daemon=True)
    thread.start()


def kill() -> bool:
    global _running

    _running = False

    log.info("Node Sync ended.")

    return not _running


def block() -> int:
    global _current_block, _lock
    with _lock:
        return _current_block


def block_time() -> BlockTime:
    global _block_time, _lock
    with _lock:
        return _block_time
