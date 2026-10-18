from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from z80 import Cpu, SparseMemory  # noqa: E402

RECORD = json.loads((ROOT / "conformance" / "hardware.json").read_text())

FACTS = RECORD["facts"]

ROWS = FACTS["instructionTiming"]["rows"]

FLAG = {name: 1 << bit for name, bit in FACTS["flagRegister"]["bits"].items()}

START = 0x0100

STACK = 0x8000

REFRESH = {"i": 0x56, "r": 0x78}


def loaded(
    program: Sequence[int],
    setup: Mapping[str, int] | None = None,
    model: str = "z80",
    recording: bool = True,
    **options: Any,
) -> Any:
    space = SparseMemory()
    for offset, byte in enumerate(program):
        space.write8(START + offset, byte)
    cpu = Cpu(model, space, recording=recording, **options)
    cpu.registers.pc = START
    cpu.registers.sp = STACK
    for name, value in (setup or {}).items():
        setattr(cpu.registers, name, value)
    return cpu


def ran(program: Sequence[int], setup: Mapping[str, int] | None = None, **options: Any) -> Any:
    cpu = loaded(program, setup, **options)
    cpu.step()
    return cpu


def shaped(
    program: Sequence[int],
    shape: str,
    setup: Mapping[str, int] | None = None,
    **options: Any,
) -> Any:
    return ran(program, {**REFRESH, **(setup or {})}, shape=shape, **options)


def acknowledged(shape: str = "manual") -> Any:
    cpu = loaded((0x00,), {**REFRESH, "iff1": True, "im": 1}, shape=shape)
    cpu.irq(0xFF)
    return cpu


def spent(program: Sequence[int], setup: Mapping[str, int] | None = None) -> int:
    states: int = ran(program, setup).bus.states
    return states


def cycle_lengths(cpu: Any) -> list[int]:
    starts = [start for start, _ in cpu.bus.cycles]
    ends = [*starts[1:], cpu.bus.states]
    return [end - start for start, end in zip(starts, ends, strict=True)]


def cycle_names(cpu: Any) -> list[str]:
    return [
        name
        for (_, name), length in zip(cpu.bus.cycles, cycle_lengths(cpu), strict=True)
        for _ in range(length)
    ]


def entries_of(cpu: Any, kind: str) -> list[tuple[int, int | None, str]]:
    return [
        entry for name, entry in zip(cycle_names(cpu), cpu.bus.log, strict=True) if name == kind
    ]


def pins_of(cpu: Any, kind: str) -> list[str]:
    return [pins for _, _, pins in entries_of(cpu, kind)]


def row(page: int) -> dict[str, Any]:
    found = [entry for entry in ROWS if entry["manualPage"] == page]
    if len(found) != 1:
        raise AssertionError(f"manual page {page} has {len(found)} timing rows, expected one")
    only: dict[str, Any] = found[0]
    return only
