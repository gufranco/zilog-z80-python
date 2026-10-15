from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.singlestep import ScriptedPorts, Usage, machine_for
from z80 import bus

__all__ = [
    "Comparison",
    "ScriptedPorts",
    "Usage",
    "check",
    "differences",
    "main",
    "opening_states",
    "options",
    "run",
]

USAGE = "usage: python3 -m conformance.cycles <suite-directory> [--limit N] [--opcode NAME] [--shape manual|recording]"

REPORT_LIMIT = 20

STATE_LIMIT = 8

Case = dict[str, Any]

State = list[Any]

Difference = tuple[int, State | None, State | None]


class Comparison(NamedTuple):
    differences: list[Difference]
    skipped: int


def differences(expected: Sequence[State], actual: Sequence[State]) -> list[Difference]:
    found: list[Difference] = []
    for index in range(max(len(expected), len(actual))):
        theirs = expected[index] if index < len(expected) else None
        ours = actual[index] if index < len(actual) else None
        if theirs != ours:
            found.append((index, theirs, ours))
    return found


OPENED_IDLE = (bus.FETCH, bus.READ_CYCLE)


def opening_states(cpu_cycles: Sequence[tuple[int, str]]) -> set[int]:
    return {start for start, kind in cpu_cycles if kind in OPENED_IDLE}


def check(case: Case, shape: str = bus.RECORDING) -> Comparison:
    cpu = machine_for(
        case["initial"], ScriptedPorts(case.get("ports", [])), recording=True, shape=shape
    )
    cpu.step()
    ours = [list(entry) for entry in cpu.bus.log]
    recorded = [list(entry) for entry in case.get("cycles", [])]
    found = differences(recorded, ours)
    if shape != bus.MANUAL:
        return Comparison(found, 0)
    allowed = opening_states(cpu.bus.cycles)
    return Comparison([entry for entry in found if entry[0] not in allowed], len(allowed))


def report(name: str, case: Case, found: Sequence[Difference]) -> None:
    print(f"FAIL {name} {case['name']}")
    for index, expected, actual in found[:STATE_LIMIT]:
        print(f"  T{index}: recorded {expected}, model {actual}")


def options(argv: Sequence[str]) -> tuple[Path, int | None, str | None, str]:
    if not argv:
        raise Usage(USAGE)
    directory: str | None = None
    limit: int | None = None
    opcode: str | None = None
    shape: str = bus.RECORDING
    rest = list(argv)
    while rest:
        item = rest.pop(0)
        if item in ("--limit", "--opcode", "--shape"):
            if not rest:
                raise Usage(USAGE)
            value = rest.pop(0)
            if item == "--limit":
                limit = int(value)
            elif item == "--opcode":
                opcode = value
            elif value not in bus.SHAPES:
                raise Usage(USAGE)
            else:
                shape = value
        elif directory is None:
            directory = item
        else:
            raise Usage(USAGE)
    if directory is None:
        raise Usage(USAGE)
    return Path(directory), limit, opcode, shape


def run(argv: Sequence[str]) -> int:
    directory, limit, opcode, shape = options(argv)
    files = sorted(directory.glob("*.json"))
    if opcode is not None:
        files = [path for path in files if path.stem == opcode]
    if not files:
        print(f"no cases found in {directory}")
        return 1

    checked = 0
    states = 0
    failed = 0
    skipped = 0
    broken: list[str] = []
    for path in files:
        cases = json.loads(path.read_text())
        if limit is not None:
            cases = cases[:limit]
        for case in cases:
            found, allowed = check(case, shape)
            checked += 1
            skipped += allowed
            states += len(case.get("cycles", []))
            if not found:
                continue
            failed += 1
            if path.stem not in broken:
                broken.append(path.stem)
            if failed <= REPORT_LIMIT:
                report(path.stem, case, found)

    print(
        f"{checked} cases, {states} T states compared, {failed} failed, "
        f"{len(broken)} opcodes affected, {skipped} opening states skipped, "
        f"shape {shape}"
    )
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
