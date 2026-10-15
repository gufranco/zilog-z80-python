from typing import Any

from . import blocks as blocks
from . import bus as bus
from . import core as core
from . import errors as errors
from . import flags as flags
from . import memory as memory
from . import models as models
from . import opcodes as opcodes
from . import registers as registers
from .clock import Clock
from .errors import (
    ClockClosed,
    RunLimit,
    Truncated,
    UnknownCarryRule,
    UnknownModelError,
    UnknownShape,
)
from .memory import UNSET_SEED, Memory, Ports, SparseMemory
from .models import MODELS, Model
from .opcodes import decode, disassemble
from .registers import Registers
from .version import VERSION

__version__ = VERSION


def Cpu(  # noqa: N802
    model: str | None = None,
    memory: Any = None,
    fill: int | None = None,
    **options: Any,
) -> core.Cpu:
    if fill is not None and memory is None:
        memory = Memory(fill=fill)
    return models.lookup(model).build(SparseMemory() if memory is None else memory, **options)


__all__ = [
    "MODELS",
    "UNSET_SEED",
    "Clock",
    "ClockClosed",
    "Cpu",
    "Memory",
    "Model",
    "Ports",
    "Registers",
    "RunLimit",
    "SparseMemory",
    "Truncated",
    "UnknownCarryRule",
    "UnknownModelError",
    "UnknownShape",
    "__version__",
    "decode",
    "disassemble",
]
