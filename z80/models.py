from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, override

from .errors import UnknownCarryRule, UnknownModelError

if TYPE_CHECKING:
    from .core import Cpu
    from .memory import SparseMemory


ZILOG_CARRY = "zilog"

NEC_CARRY = "nec"

CARRY_RULES = (ZILOG_CARRY, NEC_CARRY)


class Model:
    __slots__ = (
        "aliases",
        "carry_rule",
        "floating_output",
        "interrupt_clears_parity",
        "name",
        "summary",
        "verified",
    )

    def __init__(
        self,
        name: str,
        summary: str,
        floating_output: int,
        carry_rule: str = ZILOG_CARRY,
        interrupt_clears_parity: bool = False,
        verified: bool = True,
        aliases: Sequence[str] = (),
    ) -> None:
        if carry_rule not in CARRY_RULES:
            raise UnknownCarryRule(
                f"{carry_rule} is not a carry flag rule; there are {', '.join(CARRY_RULES)}"
            )
        self.name = name
        self.summary = summary
        self.floating_output = floating_output
        self.carry_rule = carry_rule
        self.interrupt_clears_parity = interrupt_clears_parity
        self.verified = verified
        self.aliases = tuple(aliases)

    def build(self, memory: SparseMemory, **options: Any) -> Cpu:
        from .core import Cpu

        cpu = Cpu(memory, **options)
        cpu.model = self.name
        cpu.floating_output = self.floating_output
        cpu.carry_rule = self.carry_rule
        cpu.interrupt_clears_parity = self.interrupt_clears_parity
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
        interrupt_clears_parity=True,
        aliases=(
            "z8400",
            "nmosz80",
            "z0840004psc",
            "z0840006psc",
            "z0840008psc",
            "mostekmk3880",
            "mk3880",
            "mk3880n",
            "sharplh0080",
            "lh0080",
            "lh0080a",
            "u880",
            "ud880d",
            "kr1858vm1",
            "t34vm1",
            "mme",
            "goldstargms z80",
            "thesysz80",
        ),
    ),
    Model(
        name="upd780c",
        summary=(
            "NEC uPD780C, an NMOS second source that is not a copy. The output with "
            "no source sends nothing, as the Zilog NMOS part does, and the two "
            "undocumented flag bits after a carry instruction come from the "
            "accumulator alone rather than from the accumulator and the latch."
        ),
        floating_output=0x00,
        carry_rule=NEC_CARRY,
        verified=False,
        aliases=("necupd780c", "d780c", "d780c1", "d780c2", "upd780", "upd780c1", "upd780c2"),
    ),
    Model(
        name="z84c00",
        summary=(
            "Zilog Z84C00, the CMOS part. The same instruction set, and the output "
            "with no source sends every bit instead of none. Later parts in the "
            "family behave as this one does."
        ),
        floating_output=0xFF,
        verified=False,
        aliases=(
            "cmosz80",
            "z80c",
            "z8400c",
            "z84c0006",
            "z84c0008",
            "z84c0010",
            "z84c0020",
            "toshibatmpz84c00",
            "tmpz84c00",
            "t84c00",
            "kr1858vm3",
        ),
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


def lookup(name: str | None) -> Model:
    if name is None:
        raise UnknownModelError(
            "no model was named, and this package will not choose one for you."
            f" Name one of: {', '.join(sorted(MODELS))}"
        )
    found = _BY_ALIAS.get(_normalise(name))
    if found is None:
        raise UnknownModelError(
            f"{name} is not a model this family covers; it has {', '.join(sorted(MODELS))}"
        )
    return found
