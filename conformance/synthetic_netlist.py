from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import override

from conformance import netlist

NAMES: list[tuple[str, int]] = [
    ("vss", 1),
    ("vcc", 2),
    ("clk", 3),
    ("_reset", 4),
    ("_busrq", 5),
    ("_int", 6),
    ("_nmi", 7),
    ("_wait", 8),
    ("_rfsh", 9),
    ("_m1", 10),
    ("_mreq", 11),
    ("_rd", 12),
    ("_wr", 13),
    ("_iorq", 14),
    ("t2", 15),
    ("t3", 16),
    ("out", 17),
    ("ring", 18),
    ("quiet", 19),
]
NAMES += [(f"ab{i}", 20 + i) for i in range(16)]
NAMES += [(f"db{i}", 40 + i) for i in range(8)]
for _base, _at in (("a", 50), ("bb", 60), ("cc", 70), ("pcl", 80), ("pch", 90)):
    NAMES += [(f"reg_{_base}{i}", _at + i) for i in range(8)]

TRANSISTORS: list[tuple[int, int, int]] = [(3, 17, 1), (2, 19, 2), (15, 17, 19)]

PULLED_UP: tuple[int, ...] = (17,)


def transistor_line(gate: int, first: int, second: int, pullup: str = "false") -> str:
    return f"['t0',{gate},{first},{second},[1,2,3,4],[1,1,1,1,5],{pullup},]"


def segment_line(number: int, mark: str) -> str:
    return f"[{number},'{mark}',0,1,2,3,4,5,6,7,8]"


def build(
    where: Path,
    names: list[tuple[str, int]] | None = None,
    transistors: list[tuple[int, int, int]] | None = None,
    pulled_up: tuple[int, ...] = PULLED_UP,
    pullup_entries: int = netlist.TRANSISTORS_THAT_ARE_PULLUPS,
    extra_names: str = "",
    extra_transistors: str = "",
    extra_segments: str = "",
) -> Path:
    chosen = NAMES if names is None else names
    body = "\n".join(f"{name}: {number}," for name, number in chosen)
    (where / "nodenames.js").write_text(
        "// a synthetic netlist\nvar nodenames = {\n" + body + "\n" + extra_names + "\n}\n"
    )
    wanted = TRANSISTORS if transistors is None else transistors
    lines = [transistor_line(gate, first, second) for gate, first, second in wanted]
    lines += [transistor_line(1, 1, 1, "true") for _ in range(pullup_entries)]
    (where / "transdefs.js").write_text(
        "var transdefs = [\nskipped\n" + "\n".join(lines) + "\n" + extra_transistors + "\n]\n"
    )
    segments = [segment_line(number, "+") for number in pulled_up]
    segments += [segment_line(200, "-")]
    (where / "segdefs.js").write_text(
        "var segdefs = [\nskipped\n" + "\n".join(segments) + "\n" + extra_segments + "\n]\n"
    )
    stamp(where)
    return where


def stamp(where: Path) -> Path:
    manifest = where / "netlist.manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "algorithm": {"licence": "MIT"},
                "netlist": [
                    {
                        "file": name,
                        "bytes": (where / name).stat().st_size,
                        "sha256": hashlib.sha256((where / name).read_bytes()).hexdigest(),
                        "retrievedFrom": f"https://example.invalid/{name}",
                    }
                    for name in netlist.FILES
                ],
            }
        )
    )
    return manifest


class Fixture(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.hold = tempfile.TemporaryDirectory()
        self.addCleanup(self.hold.cleanup)
        self.where = build(Path(self.hold.name))

    def parsed(self) -> netlist.Netlist:
        return netlist.Netlist(self.where, self.where / "netlist.manifest.json")

    def part(self) -> netlist.Simulation:
        return netlist.Simulation(self.where, self.where / "netlist.manifest.json")
