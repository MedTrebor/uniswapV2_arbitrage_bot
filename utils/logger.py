import re
from contextlib import redirect_stderr, redirect_stdout
from decimal import Decimal
from io import StringIO
from logging import Formatter
from logging import Logger as BaseLogger
from logging import LogRecord, StreamHandler
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from rich import print
from rich.console import Console
from rich.pretty import pprint
from rich.text import Text

import web3

from .config import CONFIG

Path("logs").mkdir(exist_ok=True)


LEVELNAME_TO_NUMBER = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}

console = Console()


def add_level_color(level: int) -> str:
    """Add color to level name.

    Args:
        level (int): Level number.

    Returns:
        str: Level name with color.

    Raises:
        TypeError: if provided level does not match builtin levels.
    """
    match level:
        case 10:
            color = "blue"
            name = "DEBUG"
        case 20:
            color = "green"
            name = "INFO"
        case 30:
            color = "yellow"
            name = "WARNING"
        case 40:
            color = "red"
            name = "ERROR"
        case 50:
            color = "red r"
            name = "CRITICAL"
        case _:
            raise TypeError(f"Provided level number:{level} did not match any level.")

    with console.capture() as capture:
        console.print(name, end="", style=color)
    return capture.get()


LEVELNUMBER_TO_COLORED_NAME = {
    10: add_level_color(10),
    20: add_level_color(20),
    30: add_level_color(30),
    40: add_level_color(40),
    50: add_level_color(50),
}


class StreamFormatter(Formatter):
    concurrent_pattern = re.compile(r"[0-9]+_*[0-9]*$")
    """``+` one or more occurences, `*` zero or moe occurences, `$` ends with."""
    traceback_width = CONFIG["logging"]["traceback_width"]
    show_locals = CONFIG["logging"]["show_locals"]

    def formatException(self, ei) -> str:
        """Format exception using rich exception format."""
        with console.capture() as capture:
            console.print_exception(
                show_locals=self.show_locals,
                width=self.traceback_width,
                suppress=[web3],
            )
        return capture.get()

    def format(self, record: LogRecord) -> str:
        """Format ``record`` to String.

        Args:
            record (LogRecord): LogRecord to format.
        """

        # record.threadName = self.format_concurrent_name(record.threadName, "Thread-")
        # record.processName = self.format_concurrent_name(record.processName, "Process-")
        record.threadName = f"\x1b[2m{record.threadName}\x1b[0m"
        record.processName = f"\x1b[2m{record.processName}\x1b[0m"

        record.name = f"{record.name}\x1b[2m:{record.lineno}\x1b[0m"

        record.levelname = LEVELNUMBER_TO_COLORED_NAME[record.levelno]

        if self.pretty:
            with console.capture() as capture:
                console.print(record.msg)
            record.msg = capture.get()

        return super().format(record)

    def format_concurrent_name(self, name: str, prefix: str) -> str:
        """Formats thread and process names to be equal length. Also adds dim style.

        Args:
            name (str): Thread or Process name to format.
            prefix (str): Prefix of formatted name.

        Returns:
            str: Formatted Thread or Process name.
        """
        # searching for number suffix
        name_match = re.search(self.concurrent_pattern, name)

        if name_match:
            # extracting last three characters
            suffix = name_match.group()[-3:]

            # removing "_" if it's the first character
            if suffix.startswith("_"):
                suffix = suffix[1:]

            # creating name
            name = prefix + suffix

        # adding dim style
        return f"\x1b[2m{name}\x1b[0m"

    def formatTime(self, record: LogRecord, datefmt: str | None = None) -> str:
        """Add dim style to time.

        Args:
            record (LogRecord): LogRecord.
            datefmt (str|None, optional): dateformat used by ``time.strftime()``.

        Returns:
            str: Formatted time.
        """
        formatted_time = super().formatTime(record, datefmt)
        return f"\x1b[2m{formatted_time}\x1b[0m"


class FileFormatter(Formatter):
    """Removes ansi escape sequences."""

    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    def format(self, record: LogRecord) -> str:
        return re.sub(self.ansi_escape, "", super().format(record))


class Logger(BaseLogger):
    """Logs data to `stderr` and `log` file.

    Args:
        name (str): Name of the logger to use when logging.
        pretty (bool, optional): Pretty print messages. Defaults to True.
    """

    def __init__(self, name: str, pretty: bool = True) -> None:
        conf = CONFIG["logging"]
        stream_level = LEVELNAME_TO_NUMBER[conf["stream"]["level"]]
        file_level = LEVELNAME_TO_NUMBER[conf["file"]["level"]]

        self.pretty = pretty

        if name == "__main__":
            name = "main"

        super().__init__(name, min(stream_level, file_level))
        self.__set_stream_handler()
        self.__set_file_handler()

    def __set_file_handler(self):
        conf = CONFIG["logging"]["file"]
        formatter = FileFormatter(conf["format"], conf["date_format"], "{")
        handler = TimedRotatingFileHandler(
            "logs/logs.log",
            conf["rotation"]["when"],
            conf["rotation"]["interval"],
            conf["rotation"]["backup_count"],
        )
        handler.setFormatter(formatter)
        handler.setLevel(LEVELNAME_TO_NUMBER[conf["level"]])
        self.addHandler(handler)

    def __set_stream_handler(self):
        conf = CONFIG["logging"]["stream"]
        formatter = StreamFormatter(conf["format"], conf["date_format"], "{")
        formatter.pretty = self.pretty
        handler = StreamHandler()
        handler.setFormatter(formatter)
        handler.setLevel(LEVELNAME_TO_NUMBER[conf["level"]])
        self.addHandler(handler)


def str_obj(o: object, pretty: bool = False) -> Text:
    """Format object into text used for `rich` printing.

    Args:
        o (object): Object.
        pretty (bool, optional): Use pretty print. Defaults to False.

    Returns:
        str: Formatted text.
    """
    captured = StringIO()
    with redirect_stdout(captured), redirect_stderr(captured):
        if pretty:
            pprint(o, expand_all=True, indent_guides=False)
        else:
            print(o)

    return Text.from_ansi(captured.getvalue())


def str_num(num: int | float | Decimal) -> str:
    """Convert number to pretty string representation.

    Args:
        num (int | float | Decimal): Number.

    Example::
        >>> str_num(Decimal('12345.6789000000'))
        12,345.6789

    Returns:
        str: Pretty number.
    """
    s = f"{num:,.18f}"

    while s.endswith("0"):
        s = s[:-1]

    if s.endswith("."):
        s = s[:-1]

    return s
