"""Hold the core to the recorded bus activity, one T state at a time.

``singlestep.py`` compares the state an instruction leaves behind. This compares
what the part did while producing it: the address, the value, and which of the
four control pins were asserted, in order, for every T state.

The difference is not academic. A core can spend the right number of cycles doing
the wrong thing, and no comparison of registers and memory will show it. Holding
this core to the recorded bus found a push that wrote the low half of the pair
first where the part writes the high half, which touches the same two addresses
in the opposite order and leaves identical final state.

The recording is rung two here and Zilog's manual is rung one, but they answer
different questions. The manual gives the shape of each machine cycle and how
many T states an instruction spends; it never says where within a long machine
cycle the bus falls idle. That ordering is what this compares, and only the
recording has it. ``conformance/divergences.json`` records the two places where
the recording's encoding departs from the manual on purpose.

Usage:
    python3 conformance/cycles.py <suite-directory> [--limit N] [--opcode NAME]
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from singlestep import ScriptedPorts, Usage, machine_for

__all__ = ["ScriptedPorts", "Usage", "check", "differences", "main", "options", "run"]

USAGE = "usage: cycles.py <suite-directory> [--limit N] [--opcode NAME]"

REPORT_LIMIT = 20

STATE_LIMIT = 8

Case = dict[str, Any]

State = list[Any]

Difference = tuple[int, State | None, State | None]


def differences(expected: Sequence[State], actual: Sequence[State]) -> list[Difference]:
    """Where the two transcripts stop agreeing, by T state.

    The comparison runs past the end of the shorter one so that a transcript
    which stops early is a finding rather than a silence.
    """
    found: list[Difference] = []
    for index in range(max(len(expected), len(actual))):
        theirs = expected[index] if index < len(expected) else None
        ours = actual[index] if index < len(actual) else None
        if theirs != ours:
            found.append((index, theirs, ours))
    return found


def check(case: Case) -> list[Difference]:
    """One case run with the bus recording, compared state for state."""
    cpu = machine_for(case["initial"], ScriptedPorts(case.get("ports", [])), recording=True)
    cpu.step()
    recorded = [list(entry) for entry in case.get("cycles", [])]
    return differences(recorded, [list(entry) for entry in cpu.bus.log])


def report(name: str, case: Case, found: Sequence[Difference]) -> None:
    print(f"FAIL {name} {case['name']}")
    for index, expected, actual in found[:STATE_LIMIT]:
        print(f"  T{index}: recorded {expected}, model {actual}")


def options(argv: Sequence[str]) -> tuple[Path, int | None, str | None]:
    if not argv:
        raise Usage(USAGE)
    directory: str | None = None
    limit: int | None = None
    opcode: str | None = None
    rest = list(argv)
    while rest:
        item = rest.pop(0)
        if item in ("--limit", "--opcode"):
            if not rest:
                raise Usage(USAGE)
            value = rest.pop(0)
            if item == "--limit":
                limit = int(value)
            else:
                opcode = value
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
    states = 0
    failed = 0
    broken: list[str] = []
    for path in files:
        cases = json.loads(path.read_text())
        if limit is not None:
            cases = cases[:limit]
        for case in cases:
            found = check(case)
            checked += 1
            states += len(case.get("cycles", []))
            if not found:
                continue
            failed += 1
            if path.stem not in broken:
                broken.append(path.stem)
            if failed <= REPORT_LIMIT:
                report(path.stem, case, found)

    print(
        f"{checked} cases, {states} T states compared, {failed} failed, {len(broken)} opcodes affected"
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
