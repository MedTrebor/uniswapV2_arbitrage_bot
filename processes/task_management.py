from multiprocessing.connection import Connection
from typing import Iterator

from .exceptions import MaxTasksError


class TaskManager:
    """Mange assigning tasks to worker processes and receiving them.
    Number of tasks that can be asssigned is limited to number of worker
    processes and than `TaskManager` should be discarded.

    Args:
        task_senders (list[Connection]): Task sending socket for each process.
        result_receiver (Connection): Result receiving socket.

    Attributes:
        task_senders (list[Connection]): Task sending socket for each process.
        result_receiver (Connection): Result receiving socket.
        max_tasks (int): Maximum tasks that can be assigned.
        processes_used (int): Worker processes already used.
    """

    __slots__ = ("max_tasks", "processes_used", "result_receiver", "task_senders")

    def __init__(
        self,
        task_senders: list[Connection],
        result_receiver: Connection,
    ) -> None:
        self.task_senders = task_senders
        self.result_receiver = result_receiver
        self.max_tasks = len(task_senders)
        self.processes_used = 0

    def submit(
        self,
        func_name: str,
        args: list | tuple = [],
        kwargs: dict = {},
        no_return: bool = False,
    ) -> None:
        """Submit function with provided name for execution in other process.

        Args:
            func_name (str): Function name.
            args (list | tuple, optional): Function arguments. Defaults to [].
            kwargs (dict, optional): Function keyword arguments. Defaults to {}.
            no_return (bool, optional): Do not return result. Defaults to False.

        Raises:
            MaxTasksError: If all processes are used.
        """
        if self.processes_used == self.max_tasks:
            raise MaxTasksError(f"Maximum tasks ({self.max_tasks} assigned")

        self.task_senders[self.processes_used].send(
            (func_name, args, kwargs, no_return)
        )
        self.processes_used += 1

    def results(self, ordered: bool = True, raise_error: bool = True) -> Iterator:
        """Iterate over task results.

        Args:
            ordered (bool, optional): Iterate in order task was submitted.
                Defaults to True.
            raise_error (bool, optional): Raise error if task raised error.
                Defaults to True.

        Raises:
            exception: If task raised exception.

        Yields:
            Any: result from submitted task.
        """
        _results = [None] * self.processes_used
        yielded = -1
        unyielded = []
        exception = None

        for _ in range(self.processes_used):
            result, idx, no_return = self.result_receiver.recv()

            # if exception is raised
            if exception:
                continue

            # if result is excpetion
            if raise_error and isinstance(result, BaseException):
                exception = result
                continue

            # if yield in order as submitted
            if ordered:

                # if result is next in order
                if idx - 1 == yielded:
                    yielded = idx
                    if not no_return:
                        yield result

                    # search if there are next in order results already received
                    while unyielded and unyielded[-1] - 1 == yielded:
                        yielded = unyielded.pop()
                        result, no_return = _results[yielded]
                        if not no_return:
                            yield result

                # result is not next in order
                else:
                    unyielded.append(idx)
                    unyielded.sort(reverse=True)
                    _results[idx] = (result, no_return)

            # if results are not ordered
            else:
                if not no_return:
                    yield result

        # if exception should be raised
        if exception:
            raise exception
