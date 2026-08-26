"""A Zilog Z80, held to a per-opcode conformance suite rather than to confidence.

The model is named at construction, because the family shipped observable
differences between its parts and a package that hard-codes one of them is wrong
for half the boards it runs on.

    from z80 import Cpu

    cpu = Cpu("z80")
    cpu.step()

Memory is optional. Leave it out and the part gets its own, scrambled the way a
board is at power on; pass one when the program under test needs to see it.

    from z80 import Cpu, Ports, SparseMemory

    cpu = Cpu("z84c00", SparseMemory(), ports=Ports())

Nothing starts cleared. Memory and registers hold what they held, because hardware
does, and a model that starts at zero hides the class of bug that only appears on
real silicon.
"""

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
    """A processor of the named model, sharing one interface across the family.

    There is no default model. This package covers three parts that differ in
    ways a caller can be caught by, and choosing one of them quietly would hide
    that. Naming nothing raises and lists every model there is, which is a better
    first meeting with this package than a part somebody did not pick.

    The model comes first because it is the thing a caller always knows and
    memory is the thing they often do not care about yet. Omitting it hands back
    a part with memory of its own, scrambled rather than cleared, which is what a
    board holds before anything has written to it.

    `fill` is the one way across this family to ask for a store holding one byte
    everywhere. It is not what a board hands over and it is not the default: a
    caller asking for zeroes is asking for something no machine does, so they
    have to say so. What it is for is a run that has to get through a few dozen
    instructions without meeting an opcode that stops the part, which is what
    every check of a cycle budget needs and what scrambled memory cannot give.
    """
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
