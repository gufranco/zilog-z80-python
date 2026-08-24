"""Run every instruction the manual prints a timing for, and count the T states.

hardware.json holds all 217 rows of the manual's per-instruction timing tables.
Until this file existed, 54 of them were compared against a run and the other 163
were a record nothing executed: correct as a transcription and inert as a check.

The gap mattered. Driving all of them found OUT (C),r spending eight T states
where the manual prints twelve, because the write was guarded on a port device
being attached and dropped its machine cycle when one was not. No suite saw it,
because a suite always attaches ports.

Nothing here is looked up. A printed row names a family, such as SBC A, r, so the
family is expanded into the concrete instructions it covers, each is assembled,
stepped, and the bus is asked what it spent. The expansion comes from the package
disassembler, which walks an opcode the way the part walks it, so an instruction
this names and an instruction the core executes cannot disagree about which one
it is.
"""

from __future__ import annotations

import itertools
import json
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, NamedTuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from z80 import core, memory, opcodes  # noqa: E402

RECORD = ROOT / "conformance" / "hardware.json"

START = 0x0100
"""Where a probe instruction is assembled, clear of the vectors and of zero."""

OPERAND = 0x01
"""The byte every operand slot is filled with.

One value everywhere keeps the disassembly predictable, so a displacement, an
immediate byte and both halves of an immediate word all read as 01.
"""

PREFIXES: tuple[tuple[int, ...], ...] = (
    (),
    (0xCB,),
    (0xED,),
    (0xDD,),
    (0xFD,),
    (0xDD, 0xCB),
    (0xFD, 0xCB),
)

REGISTERS = ("b", "c", "d", "e", "h", "l", "a")

PRIME = chr(0x2032)
"""The mark the manual sets on the alternate register file, as in EX AF, AF.

The disassembler writes a plain apostrophe, so one is turned into the other
here rather than either side being changed to suit the match.
"""

FAMILIES: dict[str, tuple[str, ...]] = {
    "r": REGISTERS,
    "r'": REGISTERS,
    "b": tuple(str(one) for one in range(8)),
    "cc": ("nz", "z", "nc", "c", "po", "pe", "p", "m"),
    "dd": ("bc", "de", "hl", "sp"),
    "ss": ("bc", "de", "hl", "sp"),
    "qq": ("bc", "de", "hl", "af"),
    "pp": ("bc", "de", "ix", "sp"),
    "rr": ("bc", "de", "iy", "sp"),
    "p": tuple(f"${one:02x}" for one in (0x00, 0x08, 0x10, 0x18, 0x20, 0x28, 0x30, 0x38)),
    "n": (f"${OPERAND:02x}",),
    "(n)": (f"(${OPERAND:02x})",),
    "nn": (f"${OPERAND:02x}{OPERAND:02x}",),
    "(nn)": (f"(${OPERAND:02x}{OPERAND:02x})",),
    "(IX+d)": (f"(ix+${OPERAND:02x})",),
    "(IY+d)": (f"(iy+${OPERAND:02x})",),
    "(IX + d)": (f"(ix+${OPERAND:02x})",),
    "(IY + d)": (f"(iy+${OPERAND:02x})",),
}

RELATIVE = ("jr", "djnz")
"""Jumps the disassembler resolves to an address, so they are matched by shape.

Every other instruction is matched by its exact disassembly. These cannot be,
because the text names where the jump lands rather than the offset in the byte.
"""

SETUPS: tuple[dict[str, int], ...] = (
    {"f": 0x00, "bc": 0x0001},
    {"f": 0xFF, "bc": 0x0001},
    {"f": 0x00, "bc": 0x0002},
    {"f": 0xFF, "bc": 0x0002},
    {"f": 0x00, "bc": 0x0100},
    {"f": 0xFF, "bc": 0x0100},
    {"f": 0x00, "bc": 0x0200},
    {"f": 0xFF, "bc": 0x0200},
)
"""Enough starting states to reach both arms of every conditional row.

A page that prints two rows prints them because the instruction costs different
amounts depending on state: a condition met or not, a block counter reaching zero
or not. Both flag words cover the conditions, and the counter values cover a
block instruction ending on this iteration or repeating. Nothing here is set
after bc, because writing b would silently overwrite half of it.
"""


class Row(NamedTuple):
    """One printed row, and what a run of it spent."""

    page: int
    instruction: str
    printed: int
    measured: tuple[int, ...]

    @property
    def agrees(self) -> bool:
        return self.printed in self.measured


def rows() -> list[dict[str, Any]]:
    held: list[dict[str, Any]] = json.loads(RECORD.read_text())["facts"]["instructionTiming"][
        "rows"
    ]
    return held


INDEX_PREFIXES = (0xDD, 0xFD)


def catalogue() -> dict[str, tuple[int, ...]]:
    """Every instruction the disassembler names, keyed by the text it prints.

    An index prefix that produces no index operand is dropped. The part accepts
    DD before JR and spends four more T states on it, but that is a redundant
    prefix rather than a second instruction, and letting it in would widen the
    set of totals a row is allowed to match until the check stopped being one.
    """
    found: dict[str, tuple[int, ...]] = {}
    for byte in range(256):
        for prefix in PREFIXES:
            head = (*prefix, OPERAND, byte) if len(prefix) == 2 else (*prefix, byte)
            raw = (*head, OPERAND, OPERAND, OPERAND, OPERAND)
            one = opcodes.decode(raw)
            if one.text.startswith("db"):
                continue
            indexed = "ix" in one.text or "iy" in one.text
            if prefix and prefix[0] in INDEX_PREFIXES and not indexed:
                continue
            found.setdefault(one.text, raw[: one.size])
    return found


def operands(name: str) -> tuple[str, list[str]]:
    """The mnemonic and the operands of a printed row name."""
    parts = name.split(None, 1)
    head = parts[0].rstrip(",").lower()
    tail = parts[1] if len(parts) > 1 else ""
    pieces = [one.strip() for one in tail.split(",")] if tail else []
    pieces = [one for one in pieces if one]
    if len(pieces) == 1 and " " in pieces[0]:
        pieces = pieces[0].split()
    return head, pieces


def spellings(name: str) -> list[str]:
    """Every concrete instruction a printed row covers, as the disassembler prints it.

    RES is the one row name that omits an operand the instruction takes. Its page
    prints RES r where the BIT and SET pages print BIT b, r, so the bit is put
    back here rather than into the record, which says what the page says.
    """
    head, pieces = operands(name)
    if head == "res" and pieces and pieces[0] not in FAMILIES["b"]:
        pieces = ["b", *pieces]
    choices = [FAMILIES.get(one, (one.lower().replace(PRIME, "'"),)) for one in pieces]
    if not choices:
        return [head]
    return [f"{head} {','.join(one)}" for one in itertools.product(*choices)]


def relative(name: str) -> tuple[str, str | None] | None:
    """The mnemonic and condition of a relative jump, or None for anything else."""
    head, pieces = operands(name)
    if head not in RELATIVE:
        return None
    conditions = [one.lower() for one in pieces if one.lower() != "e"]
    return head, conditions[0] if conditions else None


def encodings_for(name: str, known: dict[str, tuple[int, ...]]) -> list[tuple[int, ...]]:
    """The bytes of every instruction a printed row covers."""
    shape = relative(name)
    if shape is None:
        return [known[one] for one in spellings(name) if one in known]
    head, condition = shape
    found = []
    for text, raw in known.items():
        parts = text.split(None, 1)
        if parts[0] != head:
            continue
        if condition is not None and not parts[1].startswith(f"{condition},"):
            continue
        found.append(raw)
    return found


def spend(program: Sequence[int], setup: dict[str, int]) -> int:
    """The T states this core spends on one instruction, assembled and stepped."""
    space = memory.SparseMemory()
    for offset, byte in enumerate(program):
        space.write8(START + offset, byte)
    cpu = core.Cpu(space)
    cpu.registers.pc = START
    for name, value in setup.items():
        setattr(cpu.registers, name, value)
    cpu.step()
    return len(cpu.bus)


def measure(name: str, known: dict[str, tuple[int, ...]]) -> tuple[int, ...]:
    """Every T-state total the instructions a row covers can spend."""
    found: set[int] = set()
    for program in encodings_for(name, known):
        for setup in SETUPS:
            found.add(spend(program, setup))
    return tuple(sorted(found))


def survey(held: Iterable[dict[str, Any]] | None = None) -> list[Row]:
    """Every printed row, beside what a run of it spent."""
    known = catalogue()
    cache: dict[str, tuple[int, ...]] = {}
    found = []
    for row in rows() if held is None else held:
        name = row["instruction"]
        if name not in cache:
            cache[name] = measure(name, known)
        found.append(Row(row["manualPage"], name, row["tStates"], cache[name]))
    return found


def report(found: Sequence[Row]) -> str:
    """What was checked, and anything that disagreed. Never a bare pass."""
    wrong = [one for one in found if not one.agrees]
    uncovered = [one for one in found if not one.measured]
    lines = [
        f"{len(found)} printed rows, {len(found) - len(wrong)} reproduced by a run, "
        f"{len(wrong)} not, {len(uncovered)} reaching no instruction at all"
    ]
    lines.extend(
        f"  page {one.page} {one.instruction!r}: printed {one.printed}, measured {list(one.measured)}"
        for one in wrong
    )
    return "\n".join(lines)


def main(held: Iterable[dict[str, Any]] | None = None) -> int:
    found = survey(held)
    print(report(found))
    return 0 if all(one.agrees for one in found) else 1


if __name__ == "__main__":
    sys.exit(main())
