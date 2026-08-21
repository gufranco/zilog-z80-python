"""Which parts of the Z80 family this package covers, and what separates them.

The instruction set did not change across the family. One instruction's behaviour
did. There is an output instruction whose opcode names no source register, and
what it sends was never specified because the instruction was never documented.
The NMOS parts send nothing at all. The CMOS parts send every bit. Software that
reached for it did so knowing which board it was running on.

That is the whole observable difference, and it is enough to matter: a program
that clears a device register with it works on one part and sets every bit of the
same register on the other.

The remaining differences are in timing and in what happens when an interrupt
lands mid-instruction, neither of which a per-instruction model can observe. They
are not modelled here rather than modelled badly.

Adding a model means adding an entry here and holding it to a conformance suite. A
model with no suite behind it does not belong in this table, because then its
fidelity would be a claim rather than a measurement.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, override

if TYPE_CHECKING:
    from .core import Cpu
    from .memory import SparseMemory


class UnknownModelError(Exception):
    pass


class Model:
    """One part of the family: what it is, and how to build one."""

    def __init__(
        self,
        name: str,
        summary: str,
        floating_output: int,
        aliases: Sequence[str] = (),
    ) -> None:
        self.name = name
        self.summary = summary
        self.floating_output = floating_output
        self.aliases = tuple(aliases)

    def build(self, memory: SparseMemory, **options: Any) -> Cpu:
        from .core import Cpu

        cpu = Cpu(memory, **options)
        cpu.model = self.name
        cpu.floating_output = self.floating_output
        return cpu

    @override
    def __repr__(self) -> str:
        return f"<Model {self.name}, output with no source sends {self.floating_output:#04x}>"


_CATALOGUE = (
    Model(
        name="z80",
        summary=(
            "Zilog Z80, the original NMOS part, and the second sources built from the "
            "same design. The output instruction that names no source sends nothing, "
            "which is what the silicon leaves on the bus rather than a decision "
            "anybody made."
        ),
        floating_output=0x00,
        aliases=("z8400", "nmosz80", "upd780c", "u880", "kr1858vm1", "mostekmk3880"),
    ),
    Model(
        name="z84c00",
        summary=(
            "Zilog Z84C00, the CMOS part. The same instruction set, and the output "
            "with no source sends every bit instead of none. Later parts in the "
            "family behave as this one does."
        ),
        floating_output=0xFF,
        aliases=("cmosz80", "z80c", "z8400c", "z180", "ez80"),
    ),
)

MODELS = {model.name: model for model in _CATALOGUE}

_BY_ALIAS: dict[str, Model] = {}
for _model in _CATALOGUE:
    _BY_ALIAS[_model.name] = _model
    for _alias in _model.aliases:
        _BY_ALIAS[_alias] = _model


def _normalise(name: str) -> str:
    return str(name).strip().lower().replace("-", "").replace("_", "")


def describe(name: str) -> Model:
    """The model of that name, however it happens to be written."""
    found = _BY_ALIAS.get(_normalise(name))
    if found is None:
        raise UnknownModelError(
            f"{name} is not a model this family covers; it has {', '.join(sorted(MODELS))}"
        )
    return found
