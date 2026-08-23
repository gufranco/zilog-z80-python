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

from . import blocks, bus, core, flags, memory, models, opcodes, registers
from .clock import Clock, ClockClosed
from .core import RunLimit
from .memory import UNSET_SEED, Memory, Ports, SparseMemory
from .models import MODELS, Model, UnknownModelError, describe
from .opcodes import Truncated, decode, disassemble
from .registers import Registers
from .version import VERSION

__version__ = VERSION

DEFAULT_MODEL = "z80"


def Cpu(  # noqa: N802
    model: str = DEFAULT_MODEL, memory: Any = None, **options: Any
) -> core.Cpu:
    """A processor of the named model, sharing one interface across the family.

    The model comes first because it is the thing a caller always knows and
    memory is the thing they often do not care about yet. Omitting it hands back
    a part with memory of its own, scrambled rather than cleared, which is what a
    board holds before anything has written to it.
    """
    return describe(model).build(SparseMemory() if memory is None else memory, **options)


__all__ = [
    "DEFAULT_MODEL",
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
    "UnknownModelError",
    "__version__",
    "blocks",
    "bus",
    "core",
    "decode",
    "describe",
    "disassemble",
    "flags",
    "memory",
    "models",
    "opcodes",
    "registers",
]
