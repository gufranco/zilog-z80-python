from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import exercisers  # noqa: E402
from z80 import MODELS, Cpu, Memory  # noqa: E402

CALLER = 0xF000

STACK = 0xDFF0

CALL = 0xCD

HALT = 0x76

LIMIT = 200

DATA_PORT = 0xBE

CONTROL_PORT = 0xBF

NOTHING_THERE = 0xFF

ADDRESS_MASK = 0x3FFF

SIZE = 0x4000

NOTHING_TO_RUN = 2

USAGE_ERROR = 3

INDENT = 2

USAGE = "usage: cputype.py [--write] [image, folder or zip ...]"


class VideoMemory:
    __slots__ = ("address", "cells", "latched")

    def __init__(self) -> None:
        self.cells = bytearray(SIZE)
        self.latched: int | None = None
        self.address = 0

    def read(self, port: int) -> int:
        if port & 0xFF != DATA_PORT:
            return NOTHING_THERE
        value = self.cells[self.address]
        self.address = (self.address + 1) & ADDRESS_MASK
        self.latched = None
        return value

    def write(self, port: int, value: int) -> None:
        if port & 0xFF == CONTROL_PORT:
            self.control(value)
        elif port & 0xFF == DATA_PORT:
            self.cells[self.address] = value
            self.address = (self.address + 1) & ADDRESS_MASK
            self.latched = None

    def control(self, value: int) -> None:
        if self.latched is None:
            self.latched = value
            return
        self.address = ((value << 8) | self.latched) & ADDRESS_MASK
        self.latched = None


def answer(image: bytes, routine: int, model: str) -> int:
    space = Memory(image=image)
    for offset, byte in enumerate((CALL, routine & 0xFF, routine >> 8, HALT)):
        space.write8(CALLER + offset, byte)
    cpu = Cpu(model, space, ports=VideoMemory())
    cpu.reset()
    cpu.registers.pc = CALLER
    cpu.registers.sp = STACK
    cpu.run_until(lambda part: part.held(), limit=LIMIT)
    return int(cpu.registers.l)


def answers(image: bytes, routine: int) -> dict[str, int]:
    return {model: answer(image, routine, model) for model in sorted(MODELS)}


def main(argv: Sequence[str], where: Path | str | None = None, kept: Path = exercisers.KEPT) -> int:
    parsed = exercisers.options(argv)
    if parsed is None:
        print(USAGE)
        return USAGE_ERROR
    _jobs, write, given = parsed
    held = exercisers.record(where)
    wanted = [one for one in held["cartridges"] if "routine" in one]
    found = exercisers.images(
        exercisers.places_from(given, kept), {one["sha256"] for one in wanted}
    )
    if not found:
        print(f"SKIPPED none of the {len(wanted)} pinned images is on this machine")
        return NOTHING_TO_RUN
    good = True
    for one in wanted:
        if one["sha256"] not in found:
            print(f"SKIPPED {one['id']}: not on this machine")
            continue
        measured: dict[str, Any] = answers(found[one["sha256"]], one["routine"])
        same = measured == one.get("answers")
        print(f"{'ran' if same else 'DIFFERS'} {one['id']}: {json.dumps(measured)}")
        good = same and good
        one["answers"] = measured
    if write:
        Path(where or exercisers.RECORD).write_text(json.dumps(held, indent=INDENT) + "\n")
    return 0 if good else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
