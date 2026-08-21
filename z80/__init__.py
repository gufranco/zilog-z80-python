"""A Zilog Z80, held to a per-opcode conformance suite rather than to confidence.

The model is chosen at construction, because the family shipped one observable
difference between its NMOS and CMOS parts and a package that hard-codes either
one is wrong for half the boards it runs on.

    from z80 import describe, Ports, SparseMemory

    cpu = describe("z80").build(SparseMemory(), ports=Ports())
    cpu.step()

Nothing starts cleared. Memory and registers hold what they held, because hardware
does, and a model that starts at zero hides the class of bug that only appears on
real silicon.
"""

from . import blocks, bus, core, flags, memory, models, opcodes, registers
from .core import Cpu, StepLimit
from .memory import Ports, SparseMemory
from .models import MODELS, Model, UnknownModelError, describe
from .opcodes import decode, disassemble
from .registers import Registers
from .version import VERSION

__version__ = VERSION

__all__ = [
    "MODELS",
    "Cpu",
    "Model",
    "Ports",
    "Registers",
    "SparseMemory",
    "StepLimit",
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
