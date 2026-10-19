from __future__ import annotations

import json
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from itertools import pairwise
from pathlib import Path
from typing import Any, NamedTuple, override

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import netlist, timing  # noqa: E402
from z80 import Cpu, Memory  # noqa: E402

RECORD = Path(__file__).resolve().parent / "die.json"

POWER_UP = 0x5555

PAIRS = ("af", "bc", "de", "hl", "ix", "iy", "sp", "wz", "af_", "bc_", "de_", "hl_")

HALT = 0x76

HALVES = 160

ACTIVE = 0

RELEASED = 1

INTERNAL = "internal"

BUS_AVAILABLE = "busAvailable"

KINDS = ("acknowledge", "fetch", "read", "write", "portRead", "portWrite")

TAIL = bytes(12)

Events = Mapping[int, tuple[tuple[int, str], ...]]


@dataclass(frozen=True, slots=True)
class State:
    first: bool
    kinds: frozenset[str] = frozenset()
    address: int | None = None
    refresh: int | None = None
    busak: bool = False


class Cycle(NamedTuple):
    start: int
    kind: str
    address: int | None
    length: int


def strobed(level: Callable[[str], bool]) -> str | None:
    m1, mreq, iorq = level("_m1"), level("_mreq"), level("_iorq")
    rd, wr = level("_rd"), level("_wr")
    if m1 and iorq:
        return "acknowledge"
    if mreq and rd:
        return "fetch" if m1 else "read"
    if mreq and wr:
        return "write"
    if iorq and rd:
        return "portRead"
    if iorq and wr:
        return "portWrite"
    return None


class Bench(netlist.Simulation):
    def __init__(self, where: Path | str | None = None) -> None:
        super().__init__(where)
        self.vector: int | None = None
        self.events: Events = {}
        self.at = -1
        self.running = False
        self.states: list[State] = []

    @override
    def half_cycle(self) -> None:
        if self.vector is not None and not self.read("clk") and self.answering():
            self.put(self.vector)
        super().half_cycle()
        if self.running:
            self.observe()

    def answering(self) -> bool:
        return not self.read("_m1") and not self.read("_iorq")

    def observe(self) -> None:
        if not self.read("clk") and (self.states or self.read("t1")):
            self.at += 1
            self.states.append(State(first=bool(self.read("t1"))))
            for level, name in self.events.get(self.at, ()):
                self.drive(level, name)
        if self.states:
            self.states[-1] = self.seen(self.states[-1])

    def seen(self, state: State) -> State:
        kind = strobed(lambda name: not self.read(name))
        found = state
        if kind is not None:
            address = self.address() if state.address is None else state.address
            found = replace(found, kinds=found.kinds | {kind}, address=address)
        if not self.read("_rfsh") and not self.read("_mreq"):
            found = replace(found, refresh=self.address())
        return replace(found, busak=found.busak or not self.read("_busak"))


def bench(
    program: bytes,
    events: Events | None = None,
    vector: int | None = None,
    halves: int = HALVES,
    ports: dict[int, int] | None = None,
) -> Bench:
    made = Bench()
    made.reset()
    made.load(program)
    for address, value in (ports or {}).items():
        made.ports[address] = value
    made.vector = vector
    made.events = events or {}
    made.running = True
    for _ in range(halves):
        made.half_cycle()
    return made


def kind_of(states: Sequence[State]) -> tuple[str, int | None]:
    for kind in KINDS:
        for state in states:
            if kind in state.kinds:
                return kind, state.address
    return INTERNAL, None


def die_cycles(states: Sequence[State]) -> list[Cycle]:
    starts = [at for at, state in enumerate(states) if state.first]
    found = []
    for start, end in pairwise(starts):
        kind, address = kind_of(states[start:end])
        found.append(Cycle(start, kind, address, end - start))
    return found


def part(program: bytes) -> Any:
    space = Memory(fill=0x00)
    for at, byte in enumerate(program):
        space.write8(at, byte)
    cpu = Cpu("z80", space, recording=True)
    cpu.reset()
    for name in PAIRS:
        setattr(cpu.registers, name, POWER_UP)
    return cpu


def boundaries(log: Sequence[tuple[int | None, int | None, str]]) -> tuple[list[int], list[int]]:
    ends: list[int] = []
    held_at: list[int] = []
    held = 0
    for address, _value, _pins in log:
        held_at.append(held)
        if address is None:
            ends.extend([] if ends and ends[-1] == held else [held])
            continue
        held += 1
    return ends, held_at


def model_cycles(program: bytes) -> list[Cycle]:
    cpu = part(program)

    def each() -> None:
        cpu.busreq_line = not cpu.busack

    cpu.busreq_line = True
    cpu.on_cycle = each
    cpu.step()
    ends, held_at = boundaries(cpu.bus.log)
    kinds = {
        held_at[at]: (kind, cpu.bus.log[at][0])
        for at, kind in cpu.bus.cycles
        if kind != BUS_AVAILABLE
    }
    found = []
    for start, end in pairwise([0, *ends]):
        kind, address = kinds.get(start, (INTERNAL, None))
        found.append(Cycle(start, kind, address, end - start))
    return found


def compare(
    names: Iterable[tuple[str, bytes]],
    modelled: Callable[[bytes], list[Cycle]] = model_cycles,
) -> dict[str, Any]:
    differing = []
    compared = 0
    for name, program in names:
        mine = modelled(program + TAIL)
        theirs = die_cycles(bench(program + TAIL).states)
        compared += 1
        if theirs[: len(mine)] != mine:
            differing.append(name)
    return {"compared": compared, "differing": differing}


def catalogue() -> list[tuple[str, bytes]]:
    found = timing.catalogue().items()
    return [(text, bytes(raw)) for text, raw in sorted(found) if raw != (HALT,)]


def recorded(where: Path | str | None = None) -> dict[str, Any]:
    held = json.loads(Path(where or RECORD).read_text())
    assert isinstance(held, dict), "the die record does not hold an object"
    return held
