from __future__ import annotations

import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conformance import netlist

HALT = bytes([0x76]) * 12

SETTLE = 340

UNWRITTEN = 0x5555

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


Reading = Callable[[], list[dict[str, Any]]]


def run(program: bytes, where: Path | str | None = None) -> netlist.Simulation:
    part = netlist.Simulation(where)
    part.reset()
    part.load(program + HALT)
    for _ in range(SETTLE):
        part.half_cycle()
    return part


def pair(part: netlist.Simulation) -> int:
    found = part.register("w") << 8 | part.register("z")
    assert isinstance(found, int)
    return found


def trace(program: bytes, half_cycles: int = 200) -> list[tuple[int, int]]:
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
    controls = [one for one in found if one["group"] == "control"]
    read = next((one for one in found if one["instruction"] == "ld a,(nn)"), None)
    return (
        bool(controls)
        and not any(one["written"] for one in controls)
        and read is not None
        and read["pair"] == "0x1235"
    )


def recorded(where: Path | str | None = None) -> dict[str, Any]:
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
