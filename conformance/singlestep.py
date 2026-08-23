"""Hold the core to the published per-opcode suite.

The suite states, for one thousand cases per opcode, every register and every byte
of memory before and after a single instruction, plus every port transaction in
the order it happened. That is a definition of correct that does not depend on
anyone's reading of a datasheet, so where the two disagree the suite wins and the
disagreement is a defect here.

A case names only the memory it cares about. Anything it does not name is left
holding whatever it held, which is the point: an instruction that reads a byte the
case never mentioned is reading something undefined, and a run that quietly
answered zero would hide it.

Usage:
    python3 conformance/singlestep.py <suite-directory> [--limit N] [--opcode NAME]
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from z80 import bus, core, memory

USAGE = "usage: singlestep.py <suite-directory> [--limit N] [--opcode NAME]"

REGISTERS = (
    "a",
    "b",
    "c",
    "d",
    "e",
    "f",
    "h",
    "l",
    "i",
    "r",
    "pc",
    "sp",
    "wz",
    "ix",
    "iy",
    "af_",
    "bc_",
    "de_",
    "hl_",
    "im",
    "p",
    "q",
    "iff1",
    "iff2",
    "ei",
)

BOOLEAN = ("iff1", "iff2")

REPORT_LIMIT = 20

FIELD_LIMIT = 6


class Usage(Exception):
    pass


class ScriptedPorts:
    """Answers reads with what the case says the port gave, in the order it gave it."""

    def __init__(self, expected: Sequence[Sequence[Any]]) -> None:
        self.answers = [entry for entry in expected if entry[2] == "r"]
        self.log: list[list[Any]] = []

    def read(self, address: int) -> int:
        answered = len([entry for entry in self.log if entry[2] == "r"])
        value = self.answers[answered][1] if answered < len(self.answers) else 0
        self.log.append([address, value, "r"])
        return value

    def write(self, address: int, value: int) -> None:
        self.log.append([address, value, "w"])


def machine_for(
    initial: dict[str, Any],
    ports: ScriptedPorts,
    recording: bool = False,
    shape: str = bus.RECORDING,
) -> core.Cpu:
    """A machine holding exactly what the case says it held, and nothing else.

    One builder for both runners. The cycle comparison asks for the bus to be
    recorded; the state comparison does not, because holding a tuple per T state
    across a million and a half cases costs more than the comparison it feeds.

    The caller supplies the ports rather than the expected transactions, so that
    it keeps its own reference to them. Reaching back through the machine for the
    log would mean asking a core that accepts any port space to promise it was
    handed this one.

    The pin shape defaults to the recorded one here, which is the opposite of the
    core's own default. A machine built to be compared against the corpus has to
    draw its pins the way the corpus does, and the corpus simplifies the strobes
    by its generator's own documented choice. Everywhere else the manual wins.
    """
    space = memory.SparseMemory()
    for address, value in initial["ram"]:
        space.write8(address, value)
    cpu = core.Cpu(space, ports, recording=recording, shape=shape)
    for name in REGISTERS:
        if name in initial:
            value = initial[name]
            setattr(cpu.registers, name, bool(value) if name in BOOLEAN else value)
    return cpu


def differences(cpu: core.Cpu, final: dict[str, Any]) -> list[tuple[str, Any, Any]]:
    found: list[tuple[str, Any, Any]] = []
    for name in REGISTERS:
        if name not in final:
            continue
        expected = final[name]
        actual = getattr(cpu.registers, name)
        if name in BOOLEAN:
            expected, actual = bool(expected), bool(actual)
        if expected != actual:
            found.append((name, expected, actual))
    for address, value in final["ram"]:
        actual = cpu.memory.read8(address)
        if actual != value:
            found.append((f"ram[{address:04X}]", value, actual))
    return found


def check(case: dict[str, Any]) -> list[tuple[str, Any, Any]]:
    expected_ports = case.get("ports", [])
    ports = ScriptedPorts(expected_ports)
    cpu = machine_for(case["initial"], ports)
    cpu.step()
    found = differences(cpu, case["final"])
    seen = [list(entry) for entry in ports.log]
    if seen != [list(entry) for entry in expected_ports]:
        found.append(("ports", expected_ports, seen))
    return found


def report(name: str, case: dict[str, Any], found: Sequence[tuple[str, Any, Any]]) -> None:
    print(f"FAIL {name} {case['name']}")
    for field, expected, actual in found[:FIELD_LIMIT]:
        print(f"  {field}: expected {expected}, got {actual}")


def options(argv: Sequence[str]) -> tuple[Path, int | None, str | None]:
    if not argv:
        raise Usage(USAGE)
    directory = None
    limit = None
    opcode = None
    rest = list(argv)
    while rest:
        item = rest.pop(0)
        if item == "--limit":
            if not rest:
                raise Usage(USAGE)
            limit = int(rest.pop(0))
        elif item == "--opcode":
            if not rest:
                raise Usage(USAGE)
            opcode = rest.pop(0)
        elif directory is None:
            directory = item
        else:
            raise Usage(USAGE)
    if directory is None:
        raise Usage(USAGE)
    return Path(directory), limit, opcode


def run(argv: Sequence[str]) -> int:
    directory, limit, opcode = options(argv)
    files = sorted(directory.glob("*.json"))
    if opcode is not None:
        files = [path for path in files if path.stem == opcode]
    if not files:
        print(f"no cases found in {directory}")
        return 1

    checked = 0
    failed = 0
    broken: list[str] = []
    for path in files:
        cases = json.loads(path.read_text())
        if limit is not None:
            cases = cases[:limit]
        for case in cases:
            found = check(case)
            checked += 1
            if not found:
                continue
            failed += 1
            if path.stem not in broken:
                broken.append(path.stem)
            if failed <= REPORT_LIMIT:
                report(path.stem, case, found)

    print(f"{checked} cases, {failed} failed, {len(broken)} opcodes affected")
    if broken:
        print("affected: " + " ".join(broken[:40]))
    return 1 if failed else 0


def main(argv: Sequence[str]) -> int:
    try:
        return run(argv)
    except Usage as error:
        print(error)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
