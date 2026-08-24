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

The default compares against the pinned corpus, whose pin encoding strobes each
line for a single T state. Passing ``--shape manual`` compares against a corpus
regenerated with the generator's full memory cycle flag on, which strobes them
the way the manual's figures do. The two corpora are not interchangeable, and
neither is a directory the other runs against.

Usage:
    python3 -m conformance.cycles <suite-directory> [--limit N] [--opcode NAME]
        [--shape manual|recording]
"""

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
    """What one case reported: where it differed, and how much went unchecked.

    The second half is not decoration. A manual shape run against a regenerated
    corpus skips the states that corpus draws idle whatever it was told, and a
    result that reported only the differences would read as a clean run of
    everything.
    """

    differences: list[Difference]
    skipped: int


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


OPENED_IDLE = (bus.FETCH, bus.READ_CYCLE)
"""The cycle kinds the generator opens with an idle column whatever it is told.

Its opcode fetch routine writes that column without consulting the flag that
widens every other strobe, and the fourth byte of an indexed bit instruction goes
through the same routine even though it does not refresh. A corpus regenerated
with the flag on is therefore right everywhere except the first state of those.
"""


def opening_states(cpu_cycles: Sequence[tuple[int, str]]) -> set[int]:
    """Which T states open a cycle the generator draws with an idle first column.

    Taken from the bus rather than inferred from the pins, because two cycle
    kinds can draw the same opening columns and an inference that works today
    stops working quietly. Skipping these states is a claim about the generator,
    and the count is printed so a run that skipped something never reads as a run
    that checked it.
    """
    return {start for start, kind in cpu_cycles if kind in OPENED_IDLE}


def check(case: Case, shape: str = bus.RECORDING) -> Comparison:
    """One case run with the bus recording, compared state for state."""
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
