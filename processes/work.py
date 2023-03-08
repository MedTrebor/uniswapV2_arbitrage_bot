from multiprocessing import current_process
from multiprocessing.connection import Connection
from typing import Callable

from utils import Logger

from .exceptions import UnknownFunctionError

log = Logger(__name__)


def worker(receiver: Connection, sender: Connection, id: int) -> None:
    """Infinite function that runs on seperate process. Collects and
    executes task given by another process and optionaly returns task results.

    Args:
        receiver (Connection): Task receiving socket.
        sender (Connection): Result sending socket.
        id (int): Process identification number.
    """

    def inject_function(function: Callable) -> None:
        """Inject ``function`` to mapping of function name to function.

        This way it avoids pickling and unpickling for every task.

        Args:
            func (Callable): Function.
        """
        nonlocal functions
        functions[function.__name__] = function

    def raise_unknown_function(function_name: str):
        """Deliberately raise `UnknownFunctionError` for unrecognized function.

        Args:
            function_name (str): Name of Unrecognized function.

        Raises:
            UnknownFunctionError: When function is unknown.
        """
        raise UnknownFunctionError(f"Unknown function: {function_name!r}")

    def receive_task() -> tuple[Callable, list, dict, bool]:
        """Receive task through `receiver` socket.

        Returns:
            tuple[Callable, list, dict, bool]: Function to be executed,
                arguments, keyword arguments and do not return result flag.
        """
        received = receiver.recv()
        func, args, kwargs, no_return = received

        try:
            return functions[func], args, kwargs, no_return
        except KeyError as error:
            return raise_unknown_function, [error.args[0]], {}, False

    log.debug(f"Started [bold default]{current_process().name}[/].")

    functions = {"inject_function": inject_function}

    while True:
        func, args, kwargs, no_return = receive_task()

        # logging variables
        args_repr = []
        for arg in args:
            try:
                if len(arg) > 10 and not isinstance(arg, str):
                    args_repr.append(str(type(arg)))
                else:
                    args_repr.append(repr(arg))
            except TypeError:
                args_repr.append(repr(arg))

        kwargs_repr = []
        for key, value in kwargs.items():
            try:
                if len(value) > 10 and not isinstance(value, str):
                    kwargs_repr.append(f"{key}={type(value)}")
                else:
                    kwargs_repr.append(f"{key}={value!r}")
            except TypeError:
                kwargs_repr.append(f"{key}={value!r}")

        kwargs_repr = [f"{key}={value!r}" for key, value in kwargs.items()]
        args_kwargs = ", ".join(args_repr + kwargs_repr)

        try:
            result = func(*args, **kwargs)
            try:
                if len(result) > 10 and not isinstance(result, str):
                    result_repr = str(type(result))
                else:
                    result_repr = repr(result)
            except TypeError:
                result_repr = repr(result)
            log.debug(f"{func.__name__}({args_kwargs}) [bold green]->[/] {result_repr}")
        except BaseException as error:
            result = error
            log.debug(f"{func.__name__}({args_kwargs}) [bold red]->[/] {result!r}")

        sender.send((result, id, no_return))
