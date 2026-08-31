"""Ask the die what the undocumented internal register holds.

Zilog has never named WZ in eleven revisions of the manual over forty years, so
no rung above a die reaches it. The netlist does: the file names `reg_w` and
`reg_z`, and `netlist.py` runs it a half cycle at a time. What this does is
execute one instruction and read the pair afterwards, which is the one question
`die-netlist-runs-here` says to put to the die rather than to a part.

**What this is not.** It is not a claim about a Z80 anybody owns. It is one die
photographed and read into a netlist, which is rung three: above any write-up,
below a logic capture of a real part. Every value here is the netlist's answer.

**The probe is calibrated in both directions.** `nop` and `ld a,n` touch nothing,
so the pair still reads the pattern the netlist powers up in, and a run that
reported a value for those would be reporting noise. `ld a,(nn)` is the case
every write-up agrees on, and the die gives the address plus one. A probe failing
the first is reading the wrong nets; one failing the second is reading at the
wrong instant.

**Why the power-up pattern matters.** Every net comes up at `0x55`. A register
that still reads `0x55` was never written, so no probe value may be `0x55` or a
run cannot tell a correct reading from an untouched net. That is not
hypothetical: the register mapping in `netlist.py` had D and H the wrong way
round and passed, because the only program exercising it wrote A, B and C.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conformance import netlist

HALT = bytes([0x76]) * 12
"""Padding, so the part stops itself rather than running into whatever follows."""

SETTLE = 340
"""Half cycles per probe, past the longest program here and past its halt."""

UNWRITTEN = 0x5555
"""What the pair reads when nothing has written it, both bytes at the power-up
pattern.
"""

PROBES: tuple[tuple[str, str, bytes], ...] = (
    ("nop", "control", bytes([0x00])),
    ("ld a,n", "control", bytes([0x3E, 0x7E])),
    ("ld a,(nn)", "reads", bytes([0x3A, 0x34, 0x12])),
    ("ld hl,(nn)", "reads", bytes([0x2A, 0x34, 0x12])),
    ("ld (nn),hl", "writes", bytes([0x21, 0x1A, 0x1B, 0x22, 0x34, 0x12])),
    ("ld (nn),a", "writes", bytes([0x3E, 0x9C, 0x32, 0x34, 0x12])),
    ("in a,(n)", "ports", bytes([0x3E, 0x9C, 0xDB, 0x56])),
    ("out (n),a", "ports", bytes([0xDB, 0x56, 0x3E, 0x9C, 0xD3, 0x56])),
    ("jp nn", "jumps", bytes([0xC3, 0x10, 0x00])),
)
"""One instruction each, with whatever it needs loaded first.

`out (n),a` reads a port before it writes one so the accumulator it stores is not
a byte this file spells, which keeps the probe honest about where the value in
the pair came from.
"""


Reading = Callable[[], list[dict[str, Any]]]


def run(program: bytes, where: Path | str | None = None) -> netlist.Simulation:
    """One program, to its halt, on a part that was reset first."""
    part = netlist.Simulation(where)
    part.reset()
    part.load(program + HALT)
    for _ in range(SETTLE):
        part.half_cycle()
    return part


def pair(part: netlist.Simulation) -> int:
    """The two nets together, high byte first, the way an address is written."""
    found = part.register("w") << 8 | part.register("z")
    assert isinstance(found, int)
    return found


def trace(program: bytes, half_cycles: int = 200) -> list[tuple[int, int]]:
    """Every half cycle at which the pair changed, and what it changed to.

    An end state says what a register holds and not how it got there. `ld (nn),a`
    is the case that needs the difference: the pair passes through the address
    and then the address plus one before the high byte goes to zero, so the zero
    is the instruction clearing it rather than never having loaded it.
    """
    part = netlist.Simulation()
    part.reset()
    part.load(program + HALT)
    found: list[tuple[int, int]] = []
    for at in range(half_cycles):
        part.half_cycle()
        value = pair(part)
        if not found or found[-1][1] != value:
            found.append((at, value))
    return found


def measure(probes: Sequence[tuple[str, str, bytes]] = PROBES) -> list[dict[str, Any]]:
    """What the die leaves in the pair after each probe."""
    found = []
    for name, group, program in probes:
        part = run(program)
        found.append(
            {
                "instruction": name,
                "group": group,
                "pair": f"{pair(part):#06x}",
                "written": pair(part) != UNWRITTEN,
                "a": f"{part.register('a'):#04x}",
            }
        )
    return found


def calibrated(found: Sequence[dict[str, Any]]) -> bool:
    """Whether the run is worth reading, decided before its results are.

    Both directions. Nothing may be reported for an instruction that touches the
    pair, and `ld a,(nn)` must give the address plus one, which is the one value
    every source agrees on.
    """
    controls = [one for one in found if one["group"] == "control"]
    read = next((one for one in found if one["instruction"] == "ld a,(nn)"), None)
    return (
        bool(controls)
        and not any(one["written"] for one in controls)
        and read is not None
        and read["pair"] == "0x1235"
    )


def recorded(where: Path | str | None = None) -> dict[str, Any]:
    """The record this writes, read back."""
    path = Path(where) if where is not None else Path(__file__).resolve().parent / "wz.json"
    held = json.loads(path.read_text())
    assert isinstance(held, dict), f"{path} does not hold an object"
    return held


def main(argv: Sequence[str] = (), read: Reading = measure) -> int:
    out = Path(argv[0]) if argv else Path(__file__).resolve().parent / "wz.json"
    try:
        found = read()
    except netlist.Missing as raised:
        print(f"REFUSED {raised}")
        return 1

    if not calibrated(found):
        print("  the probe is not calibrated; nothing here is worth recording")
        return 1

    held = {
        "note": (
            "What the die leaves in the undocumented WZ pair after one instruction."
            " Zilog names the register nowhere, so nothing above a die answers this."
            " Read off the Visual 6502 netlist, which is rung three: above any"
            " write-up and below a capture of a real part."
        ),
        "rung": 3,
        "unwritten": f"{UNWRITTEN:#06x}",
        "calibration": (
            "nop and ld a,n must leave the pair unwritten, and ld a,(nn) must give"
            " the address plus one. A run failing the first is reading the wrong"
            " nets; one failing the second is reading at the wrong instant."
        ),
        "probes": found,
        "clearedHighByte": (
            "ld (nn),a and out (n),a end with the high byte at zero. The trace shows"
            " the pair passing through the address and then the address plus one"
            " first, so the byte is cleared rather than never loaded. ld (nn),hl,"
            " which is the same kind of store, keeps it."
        ),
    }
    Path(out).write_text(json.dumps(held, indent=2) + "\n")
    print(f"  {len(found)} probes, calibrated, written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
