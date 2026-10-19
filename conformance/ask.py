from __future__ import annotations

import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import die, netlist  # noqa: E402

RECORD = Path(__file__).resolve().parent / "die.json"

ADD_HL_BC = bytes([0x09])

HALTS = bytes([die.HALT]) * 4

NONMASKABLE = 0x0066

MODE_ONE = 0x0038

MODE_TWO = 0x5040

TABLE = bytes([0x00, 0x40, 0x50])

TABLE_AT = 0x0020

ODD_VECTOR = 0x21

RESTART_VECTOR = 0xFF

RELEASED_AT = 40

PULSE_AT = 5

BUS_STATES = 24

BUS_HALVES = 60

BUS_WINDOW = 11

HOLDS = (1, 3)

DATA_AT = 0x0030

USAGE = "usage: ask.py [output] [--sweep]"

Asking = Callable[[], list[dict[str, Any]]]

Sweeping = Callable[[], dict[str, Any]]

BLOCK_CASES = (
    ("ini", 0xA2, 0x80, 0xF0, 0x02),
    ("ini without a carry", 0xA2, 0x10, 0x05, 0x02),
    ("ind", 0xAA, 0x80, 0xF0, 0x02),
    ("outi", 0xA3, 0x90, 0x00, 0x03),
    ("outd", 0xAB, 0x01, 0x00, 0x03),
)

PREFIXED = (
    ("dd 37", 0xDD, 0x37),
    ("dd 3f", 0xDD, 0x3F),
    ("fd 37", 0xFD, 0x37),
    ("fd 3f", 0xFD, 0x3F),
)

PLACED = (
    ("ex (sp),hl", bytes([0xE3])),
    ("ex (sp),ix", bytes([0xDD, 0xE3])),
    ("ex (sp),iy", bytes([0xFD, 0xE3])),
    ("rrd", bytes([0xED, 0x67])),
    ("rld", bytes([0xED, 0x6F])),
    ("ld (ix+d),n", bytes([0xDD, 0x36, 0x02, 0x9C])),
    ("ld (iy+d),n", bytes([0xFD, 0x36, 0x02, 0x9C])),
)


class Answering:
    __slots__ = ("value",)

    def __init__(self, value: int) -> None:
        self.value = value

    def read(self, _address: int) -> int:
        return self.value

    def write(self, _address: int, _value: int) -> None:
        return None


def answer(question: str, divergence: str, theirs: Any, mine: Any) -> dict[str, Any]:
    return {
        "question": question,
        "divergence": divergence,
        "die": theirs,
        "model": mine,
        "agrees": theirs == mine,
    }


def stepped(program: bytes, steps: int, value: int | None = None) -> Any:
    cpu = die.part(program)
    cpu.ports = None if value is None else Answering(value)
    for _ in range(steps):
        cpu.step()
    return cpu


def fetches(cycles: Sequence[die.Cycle]) -> list[int | None]:
    return [one.address for one in cycles if one.kind == "fetch"]


def model_fetches(cpu: Any) -> list[int]:
    return [cpu.bus.log[at][0] for at, kind in cpu.bus.cycles if kind == "fetch"]


def refresh_address() -> dict[str, Any]:
    program = bytes([0x3E, 0x9C, 0xED, 0x47, 0x3E, 0xF0, 0xED, 0x4F, 0x00]) + die.TAIL
    states = die.bench(program).states
    nop = next(one for one in die.die_cycles(states) if one.address == 0x0008)
    theirs = next(one.refresh for one in states[nop.start :] if one.refresh is not None)
    mine = stepped(program, 5).bus.log[3][0]
    return answer("refresh-address", "recording-refresh-on-address-pins", theirs, mine)


def halt_fetch_address() -> dict[str, Any]:
    program = bytes([0x00, die.HALT]) + die.TAIL
    theirs = fetches(die.die_cycles(die.bench(program).states))[2:4]
    cpu = stepped(program, 2)
    mine = []
    for _ in range(2):
        cpu.step()
        mine.extend(model_fetches(cpu))
    return answer("halt-fetch-address", "halt-fetch-address-unstated", theirs, mine)


def die_response(program: bytes, line: str, vector: int | None, to: int) -> dict[str, Any]:
    events = {0: ((die.ACTIVE, line),), RELEASED_AT: ((die.RELEASED, line),)}
    made = die.bench(program, events, vector)
    cycles = die.die_cycles(made.states)
    landed = next(at for at, one in enumerate(cycles) if one.kind == "fetch" and one.address == to)
    began = landed - (5 if to == MODE_TWO else 3)
    return shape(
        cycles[began].length,
        cycles[landed].start - cycles[began].start,
        made.register("w") << 8 | made.register("z"),
        [one.address for one in cycles[began:landed] if one.kind == "read"],
    )


def shape(first: int, total: int, wz: int, reads: Sequence[int | None]) -> dict[str, Any]:
    return {
        "firstCycleStates": first,
        "responseStates": total,
        "wz": wz,
        "pointer": reads[0] if reads else None,
    }


def model_response(program: bytes, steps: int, vector: int | None) -> dict[str, Any]:
    cpu = stepped(program, steps)
    if vector is None:
        cpu.nmi()
    else:
        cpu.irq(vector)
    starts = [at for at, _kind in cpu.bus.cycles]
    reads = [cpu.bus.log[at][0] for at, kind in cpu.bus.cycles if kind == "read"]
    return shape(starts[1] - starts[0], cpu.bus.states, cpu.registers.wz, reads)


def mode_one_response() -> dict[str, Any]:
    program = bytes([0xED, 0x56, 0xFB, 0x00]) + die.TAIL
    theirs = die_response(program, "_int", RESTART_VECTOR, MODE_ONE)
    mine = model_response(program, 3, RESTART_VECTOR)
    return answer("mode-one-response", "interrupt-acknowledge-unchecked", theirs, mine)


def mode_zero_response() -> dict[str, Any]:
    program = bytes([0xED, 0x46, 0xFB, 0x00]) + die.TAIL
    theirs = die_response(program, "_int", RESTART_VECTOR, MODE_ONE)
    mine = model_response(program, 3, RESTART_VECTOR)
    return answer("mode-zero-response", "acknowledge-internal-state-placement", theirs, mine)


def mode_two_response() -> dict[str, Any]:
    head = bytes([0xED, 0x5E, 0xFB, 0x00])
    program = head + bytes(TABLE_AT - len(head)) + TABLE + die.TAIL
    theirs = die_response(program, "_int", ODD_VECTOR, MODE_TWO)
    mine = model_response(program, 3, ODD_VECTOR)
    return answer("mode-two-response", "mode-two-vector-low-bit", theirs, mine)


def nonmaskable_response() -> dict[str, Any]:
    program = bytes(4) + die.TAIL
    theirs = die_response(program, "_nmi", None, NONMASKABLE)
    mine = model_response(program, 1, None)
    return answer("nonmaskable-response", "wz-after-an-interrupt-response", theirs, mine)


def nonmaskable_short_pulse() -> dict[str, Any]:
    program = ADD_HL_BC + die.TAIL
    events = {PULSE_AT: ((die.ACTIVE, "_nmi"),), PULSE_AT + 1: ((die.RELEASED, "_nmi"),)}
    theirs = NONMASKABLE in fetches(die.die_cycles(die.bench(program, events).states))
    cpu = die.part(program)
    seen = 0

    def each() -> None:
        nonlocal seen
        seen += 1
        cpu.nmi_line = seen == PULSE_AT

    cpu.on_cycle = each
    found: list[int] = []
    for _ in range(3):
        cpu.step()
        found.extend(model_fetches(cpu))
    return answer(
        "nonmaskable-short-pulse", "nonmaskable-short-pulse-unstated", theirs, NONMASKABLE in found
    )


def block_flags(op: int, value: int, low: int, high: int) -> tuple[int, int]:
    head = bytes([0xA7, 0x01, low, high, 0x21, DATA_AT, 0x00, 0xED, op]) + HALTS
    program = head + bytes(DATA_AT - len(head)) + bytes([value])
    made = die.bench(program, ports={(high << 8) | low: value, ((high - 1) << 8) | low: value})
    return made.register("f"), stepped(program, 4, value).registers.f


def block_transfer_flags() -> dict[str, Any]:
    found = {name: block_flags(op, value, low, high) for name, op, value, low, high in BLOCK_CASES}
    theirs = {name: pair[0] for name, pair in found.items()}
    mine = {name: pair[1] for name, pair in found.items()}
    return answer(
        "block-transfer-flags", "block-transfer-flags-the-manual-gets-wrong", theirs, mine
    )


def prefixed_flags(prefix: int, op: int) -> tuple[int, int]:
    program = bytes([0x3E, 0x00, 0xFE, 0x28, prefix, op]) + HALTS
    return die.bench(program).register("f"), stepped(program, 3).registers.f


def prefixed_carry_flags() -> dict[str, Any]:
    found = {name: prefixed_flags(prefix, op) for name, prefix, op in PREFIXED}
    theirs = {name: pair[0] for name, pair in found.items()}
    mine = {name: pair[1] for name, pair in found.items()}
    return answer(
        "prefixed-carry-flags", "generator-head-disagrees-with-the-pinned-corpus", theirs, mine
    )


def die_grants(asserted: int, held: int) -> list[int]:
    events = {asserted: ((die.ACTIVE, "_busrq"),), asserted + held: ((die.RELEASED, "_busrq"),)}
    states = die.bench(ADD_HL_BC + die.TAIL, events, halves=BUS_HALVES).states[:BUS_STATES]
    return [at for at, one in enumerate(states) if one.busak]


def model_grants(asserted: int, held: int) -> list[int]:
    cpu = die.part(ADD_HL_BC + die.TAIL)
    seen = 0
    granted: list[int] = []

    def each() -> None:
        nonlocal seen
        granted.extend([seen] if cpu.busack else [])
        seen += 1
        cpu.busreq_line = asserted <= seen < asserted + held

    cpu.busreq_line = asserted == 0
    cpu.on_cycle = each
    while seen < BUS_STATES:
        cpu.step()
    return [at for at in granted if at < BUS_STATES]


def bus_request() -> dict[str, Any]:
    asked = [(at, held) for held in HOLDS for at in range(BUS_WINDOW)]
    theirs = {f"{at}+{held}": die_grants(at, held) for at, held in asked}
    mine = {f"{at}+{held}": model_grants(at, held) for at, held in asked}
    return answer("bus-request", "bus-request-and-acknowledge", theirs, mine)


def cycles_of(program: bytes) -> tuple[list[list[Any]], list[list[Any]]]:
    mine = die.model_cycles(program + die.TAIL)
    theirs = die.die_cycles(die.bench(program + die.TAIL).states)[: len(mine)]
    return [list(one) for one in theirs], [list(one) for one in mine]


def placement() -> dict[str, Any]:
    found = {name: cycles_of(program) for name, program in PLACED}
    theirs = {name: pair[0] for name, pair in found.items()}
    mine = {name: pair[1] for name, pair in found.items()}
    return answer("placement", "generator-head-disagrees-with-the-pinned-corpus", theirs, mine)


def block_input_cycles() -> dict[str, Any]:
    theirs, mine = cycles_of(bytes([0xED, 0xA2]))
    lengths = ([one[3] for one in theirs], [one[3] for one in mine])
    return answer("block-input-machine-cycles", "block-input-breakdown-order", *lengths)


QUESTIONS: dict[str, Callable[[], dict[str, Any]]] = {
    "refresh-address": refresh_address,
    "halt-fetch-address": halt_fetch_address,
    "mode-one-response": mode_one_response,
    "mode-zero-response": mode_zero_response,
    "mode-two-response": mode_two_response,
    "nonmaskable-response": nonmaskable_response,
    "nonmaskable-short-pulse": nonmaskable_short_pulse,
    "block-transfer-flags": block_transfer_flags,
    "prefixed-carry-flags": prefixed_carry_flags,
    "bus-request": bus_request,
    "placement": placement,
    "block-input-machine-cycles": block_input_cycles,
}


def asked() -> list[dict[str, Any]]:
    return [question() for question in QUESTIONS.values()]


def sweep(listing: Callable[[], list[tuple[str, bytes]]] = die.catalogue) -> dict[str, Any]:
    return die.compare(listing())


def recorded(where: Path | str | None = None) -> dict[str, Any]:
    held = json.loads(Path(where or RECORD).read_text())
    assert isinstance(held, dict), "the die record does not hold an object"
    return held


def written(answers: list[dict[str, Any]], swept: dict[str, Any]) -> dict[str, Any]:
    return {
        "note": (
            "What the Visual 6502 netlist of the die answers to each question below,"
            " beside what this package does. Rung three: above a recording, below a"
            " capture of a real part. Every answer is the netlist's, never the part's."
        ),
        "rung": 3,
        "netlist": netlist.identity()["commit"],
        "answers": answers,
        "sweep": swept,
    }


def main(
    argv: Sequence[str] = (),
    asking: Asking = asked,
    sweeping: Sweeping = sweep,
) -> int:
    options = [one for one in argv if one.startswith("--")]
    if any(one != "--sweep" for one in options):
        print(USAGE)
        return 2
    paths = [one for one in argv if not one.startswith("--")]
    out = Path(paths[0]) if paths else RECORD
    try:
        answers = asking()
    except netlist.Missing as raised:
        print(f"REFUSED {raised}")
        return 1
    swept = sweeping() if options else recorded()["sweep"]
    out.write_text(json.dumps(written(answers, swept), indent=2) + "\n")
    print(f"  {len(answers)} answers, {swept['compared']} opcode forms swept, written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
