from multiprocessing import Pipe, Process
from multiprocessing.connection import Connection
from typing import Callable

from utils import CONFIG, Logger
from utils.decorators import singleton, singleton_instances

from .exceptions import InjectionError
from .task_management import TaskManager
from .work import worker

log = Logger(__name__)


@singleton
class ProcessManager:
    """Process Manager singleton.
    Args:
        process_num (int, optional): Number of worer processes to spawn.
            Defaults to `CONFIG['multiprocessing']['workers']`.
        no_singleton (bool, optional): Don't create singleton. Defaults to False.
        new_singleton (bool, optional): Create new singleton instance.
            Defaults to False.

    Attributes:
        count (int): Total number of spawned proccesses.
        result_receiver (Connection): Result receiving socket.
        task_senders (list[Connection]): Task sending socket for each worker.
        processes (list[Process]): All worker processes.
    """

    __slots__ = ("count", "processes", "result_receiver", "task_senders")

    def __init__(self, process_num: int = CONFIG["multiprocessing"]["workers"]) -> None:
        self.count = process_num
        """Total number of spawned proccesses."""
        self.result_receiver, result_sender = Pipe()
        self.processes: list[Process] = []  # type: ignore

        self.task_senders: list[Connection] = []  # type: ignore
        for i in range(process_num):
            # pipe for receiving and sending task
            task_receiver, task_sender = Pipe()
            self.task_senders.append(task_sender)

            # starting process and assigning task sockets
            process = Process(
                name=f"Process-{i + 1}",
                target=worker,
                args=(task_receiver, result_sender, i),
                daemon=True,
            )
            self.processes.append(process)
            process.start()

    def inject_function(self, func: Callable) -> None:
        """Inject function to all processes.

        Args:
            func (Callable): Function.
        """
        for taks_sender in self.task_senders:
            taks_sender.send(("inject_function", [func], {}, False))

        # checking if injection is ok
        for _ in range(self.count):
            result = self.result_receiver.recv()
            if result[0] is not None:
                raise InjectionError(result[0])

    def kill(self) -> None:
        """Kill all worker processes. Also deletes instance from singleton."""
        for process in self.processes:
            process.terminate()
            process.join()
            process.close()

        try:
            if singleton_instances[type(self)] == self:
                del singleton_instances[type(self)]
        except KeyError:
            pass

        log.debug(f"{self} at {hex(id(self))} killed.")

    def task_manager(self) -> TaskManager:
        """Create new `TaskManager`.

        Retrurns:
            TaskManager: Task manager object.
        """
        return TaskManager(self.task_senders, self.result_receiver)

    def __repr__(self) -> str:
        if type(self) in singleton_instances:
            return f"ProcessManager(process_num={self.count})"
        else:
            return f"ProcessManager(process_num={self.count}, no_singleton=True)"
