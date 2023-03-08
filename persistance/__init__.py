from pathlib import Path

from .abi import *
from .burner import *
from .bytecode import *
from .last_block import *
from .other import *
from .paths import *
from .pools import *
from .stats import *

Path("data").mkdir(exist_ok=True)
