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

OPERAND = 0x01

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


class Row(NamedTuple):
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
    parts = name.split(None, 1)
    head = parts[0].rstrip(",").lower()
    tail = parts[1] if len(parts) > 1 else ""
    pieces = [one.strip() for one in tail.split(",")] if tail else []
    pieces = [one for one in pieces if one]
    if len(pieces) == 1 and " " in pieces[0]:
        pieces = pieces[0].split()
    return head, pieces


def spellings(name: str) -> list[str]:
    head, pieces = operands(name)
    if head == "res" and pieces and pieces[0] not in FAMILIES["b"]:
        pieces = ["b", *pieces]
    choices = [FAMILIES.get(one, (one.lower().replace(PRIME, "'"),)) for one in pieces]
    if not choices:
        return [head]
    return [f"{head} {','.join(one)}" for one in itertools.product(*choices)]


def relative(name: str) -> tuple[str, str | None] | None:
    head, pieces = operands(name)
    if head not in RELATIVE:
        return None
    conditions = [one.lower() for one in pieces if one.lower() != "e"]
    return head, conditions[0] if conditions else None


def encodings_for(name: str, known: dict[str, tuple[int, ...]]) -> list[tuple[int, ...]]:
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
    found: set[int] = set()
    for program in encodings_for(name, known):
        for setup in SETUPS:
            found.add(spend(program, setup))
    return tuple(sorted(found))


def survey(held: Iterable[dict[str, Any]] | None = None) -> list[Row]:
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
