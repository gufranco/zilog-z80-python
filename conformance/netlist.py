"""Run the part as a net of transistors, so the model can be asked about the die.

Every other check in this package holds the model to a document or to a recording.
Both stop at the package boundary: a document says what the part does and a
recording says what one part did, and neither says what is inside. A switch-level
run of the netlist answers a third kind of question, which is the one most of the
open questions in this repository turn out to be.

The resolver, the group walk, the propagation loop and the file readers follow
`chipsim.js` and `wires.js` from the Visual 6502 project, which are MIT licensed.
This is a Python implementation rather than a translation, and what it is faithful
to is their behaviour, because a resolver that settles differently is a different
chip. The notice they require is in `THIRD-PARTY-NOTICES.md`.

The three files it reads are not carried here. `netlist.manifest.json` names them, says
where they come from and records what each one hashes to, and a load refuses
anything that is not what was read.

Two things had to be established here rather than taken from anyone, and both were
measured. They are in `TRANSISTORS_THAT_ARE_PULLUPS` and `MAIN_REGISTERS`.

Authority rung 3. Below a manufacturer document and below a recording taken off a
real part, because a netlist is an extraction and an extraction can be wrong.
Nothing in this package is held to what it says; it is used to ask questions, and
an answer it gives is recorded as coming from it.

Usage:
    python3 -m conformance.netlist [--half-cycles N]
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent / "docs" / "independent" / "visual6502"
"""Where the three files land, which is the folder git ignores.

Same reasoning as `conformance.documents`: the record lives beside the code and
the files it identifies do not live in the repository at all.
"""

MANIFEST = Path(__file__).resolve().parent / "netlist.manifest.json"

FILES = ("nodenames.js", "segdefs.js", "transdefs.js")

USAGE = "usage: netlist.py [--half-cycles N]"

MAX_NETS = 4000
MAX_TRANS = 10000
"""Bounds this netlist states, carried so the arrays can be flat lists rather than
dictionaries. A netlist needing more is not this one, and the load says so rather
than growing silently.
"""

GROUND = 1
POWER = 2
"""The two nets whose numbers the format fixes. Checked on load rather than
trusted, because every rule below is written in terms of them.
"""

SETTLE_LIMIT = 100
"""Rounds before a propagation is called unsettled, which is the reference's own
limiter. Reaching it is recorded rather than raised: a netlist that will not rest
is a finding about the run, and stopping mid-edge would hide it.
"""

RESET_HALF_CYCLES = 31
"""Half cycles reset is held low for, which is what the reference's own Z80 setup
does before releasing it.
"""

TRANSISTORS_THAT_ARE_PULLUPS = 32
"""Entries in the transistor file that are pull-ups rather than transistors.

Each carries a flag saying so, and loading them anyway is not a small inaccuracy.
It is the difference between a netlist that comes to rest and one that never
does. Measured on 2026-08-27 over a run of 130 half cycles: loading them leaves
36 propagations hitting the limiter and no register reaches a correct value,
skipping them leaves none.

The count is checked rather than assumed, because a file where a different number
of entries carry that flag is a different file.
"""

MAIN_REGISTERS = {"b": "bb", "c": "cc", "d": "dd", "e": "ee", "h": "hh", "l": "ll"}
"""Where the main register set actually lives, against the names the file gives.

The doubled names hold the registers an instruction writes and the single-letter
ones hold the shadow set, which is the opposite of what the names suggest. So it
was measured rather than read: `LD r,n` was executed for each of A, B, C, D, E, H
and L across all eight bit positions, and the nets that followed the loaded value
were recorded. A is the exception and is under its own name.

The authority for this is Zilog's definition of `LD r,n` together with the
netlist, never anybody's naming file.
"""

SAMPLE = bytes([0x3E, 0x42, 0x06, 0x99, 0x0E, 0x17, 0x04, 0x00])
"""Load, load, load, increment. Chosen so the registers afterwards hold values
that only executing it produces, rather than values a part doing nothing would
also show.
"""

DEFAULT_HALF_CYCLES = 130

_NAME = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(\d+)\s*,", re.M)


class Missing(Exception):
    """The netlist is not on this machine, or is not the netlist that was read."""


def identity(manifest: Path | str | None = None) -> dict[str, Any]:
    with Path(manifest or MANIFEST).open() as handle:
        held: dict[str, Any] = json.load(handle)
    return held


def check(path: Path, entry: dict[str, Any]) -> None:
    """That one file is the one the manifest names, by size and then by digest.

    Size first because it is one call and it rejects almost every wrong file, and
    the digest because size alone rejects nothing that was edited in place. A
    refusal names where the file comes from, since a reader holding the wrong one
    needs the address more than the reason.
    """
    if not path.is_file():
        raise Missing(f"{path.name} is not in {path.parent}. Take it from {entry['retrievedFrom']}")
    size = path.stat().st_size
    if size != entry["bytes"]:
        raise Missing(f"{path.name} is {size} bytes, not {entry['bytes']}")
    found = hashlib.sha256(path.read_bytes()).hexdigest()
    if found != entry["sha256"]:
        raise Missing(f"{path.name} is a different file: {found}")


class Netlist:
    """The three files, parsed into nets and transistors.

    Kept apart from the run below because parsing is where a netlist is rejected
    and running is where it is used, and a fault in the first should never be
    reported as a fault in the second.
    """

    def __init__(self, where: Path | str | None = None, manifest: Path | str | None = None) -> None:
        root = Path(where or ROOT)
        self.identity = identity(manifest)
        for entry in self.identity["netlist"]:
            check(root / str(entry["file"]), entry)

        self.names: dict[str, int] = {}
        self.state = bytearray(MAX_NETS)
        self.pullup = bytearray(MAX_NETS)
        self.pulldown = bytearray(MAX_NETS)

        self.gates: list[list[int]] = [[] for _ in range(MAX_NETS)]
        self.channels: list[list[int]] = [[] for _ in range(MAX_NETS)]

        self.on = bytearray(MAX_TRANS)
        self.gate_of = [0] * MAX_TRANS
        self.first_of = [0] * MAX_TRANS
        self.second_of = [0] * MAX_TRANS

        self.transistors = 0
        self.skipped_pullups = 0
        self.pullups = 0

        self._read_names(root / "nodenames.js")
        self._check_fixed_nets()
        self._read_pullups(root / "segdefs.js")
        self._read_transistors(root / "transdefs.js")
        self._check_pullup_entries()

    def _check_fixed_nets(self) -> None:
        for name, wanted in (("vss", GROUND), ("vcc", POWER)):
            found = self.names.get(name)
            if found != wanted:
                raise Missing(f"{name} is net {found}, and every rule here assumes {wanted}")

    def _check_pullup_entries(self) -> None:
        if self.skipped_pullups != TRANSISTORS_THAT_ARE_PULLUPS:
            raise Missing(
                f"{self.skipped_pullups} entries are marked pull-ups, not"
                f" {TRANSISTORS_THAT_ARE_PULLUPS}, so this is a different file"
            )

    def _read_names(self, path: Path) -> None:
        for name, number in _NAME.findall(path.read_text()):
            wanted = int(number)
            if wanted >= MAX_NETS:
                raise Missing(f"net {wanted} is past the {MAX_NETS} this netlist was read at")
            self.names[name] = wanted

    def _read_pullups(self, path: Path) -> None:
        """A pull-up is a property of a net here rather than a transistor of its own.

        It is one of the three things the resolver weighs, and it is weighed
        inside the joined set rather than ahead of it, which is why a net can be
        pulled up and still read low.
        """
        for raw in path.read_text().splitlines():
            if not raw.startswith("["):
                continue
            fields = raw[1:].split(",")
            if len(fields) <= 4:
                continue
            number = int(fields[0])
            if number >= MAX_NETS:
                raise Missing(f"net {number} is past the {MAX_NETS} this netlist was read at")
            self.pullup[number] = 1 if "+" in fields[1] else 0
        self.pullups = sum(self.pullup)

    def _read_transistors(self, path: Path) -> None:
        """Gate, then the two channel connections, then a flag marking a pull-up.

        The two channel connections are ordered rather than symmetric. A
        transistor tied to a rail carries that connection second, because closing
        one queues only the first end and opening one queues both, and queueing a
        rail is work that decides nothing.
        """
        for raw in path.read_text().splitlines():
            if not raw.startswith("["):
                continue
            flat = raw.replace("[", " ").replace("]", " ")
            fields = [one for one in flat.split(",") if one.strip()]
            if len(fields) < 4:
                continue
            if fields[-1].strip() == "true":
                self.skipped_pullups += 1
                continue
            if self.transistors >= MAX_TRANS:
                raise Missing(f"more than the {MAX_TRANS} transistors this was read at")
            gate = int(fields[1])
            first = int(fields[2])
            second = int(fields[3])
            if first == GROUND:
                first, second = second, GROUND
            if first == POWER:
                first, second = second, POWER
            number = self.transistors
            self.gate_of[number] = gate
            self.first_of[number] = first
            self.second_of[number] = second
            self.gates[gate].append(number)
            self.channels[first].append(number)
            self.channels[second].append(number)
            self.transistors += 1

    def number(self, name: str) -> int:
        return self.names.get(name, 0)

    def read(self, name: str) -> int:
        return self.state[self.number(name)]

    def bus(self, name: str, width: int) -> int:
        value = 0
        for i in range(width - 1, -1, -1):
            value = (value << 1) | (1 if self.read(f"{name}{i}") else 0)
        return value


class Simulation(Netlist):
    """The netlist, driven a half cycle at a time, with memory and ports attached."""

    def __init__(self, where: Path | str | None = None, manifest: Path | str | None = None) -> None:
        super().__init__(where, manifest)
        self._group: list[int] = []
        self._grouped = bytearray(MAX_NETS)
        self._queued = bytearray(MAX_NETS)
        self.half_cycles = 0
        self.unsettled = 0
        self.memory = bytearray(0x10000)
        self.ports = bytearray(0x10000)
        self.state[GROUND] = 0
        self.state[POWER] = 1

    def connected(self) -> list[int]:
        return [
            n
            for n in range(MAX_NETS)
            if n not in (GROUND, POWER) and (self.gates[n] or self.channels[n])
        ]

    def _collect(self, start: int) -> None:
        """Every net joined to this one through transistors that are closed.

        The walk stops at a rail rather than crossing it, so a group holds the
        rails it touches and everything joined between them.
        """
        group = self._group
        seen = self._grouped
        stack = [start]
        while stack:
            n = stack.pop()
            if seen[n]:
                continue
            seen[n] = 1
            group.append(n)
            if n in (GROUND, POWER):
                continue
            joined: list[int] = []
            for t in self.channels[n]:
                if not self.on[t]:
                    continue
                joined.append(self.second_of[t] if self.first_of[t] == n else self.first_of[t])
            stack.extend(reversed(joined))

    def _regroup(self, n: int) -> None:
        for one in self._group:
            self._grouped[one] = 0
        self._group = []
        self._collect(n)

    def _value(self) -> int:
        """What the joined set settles to.

        Ground beats power, power beats everything else, and failing both the set
        is decided by the first net in it that says anything: pulled up, pulled
        down, or already high. A set where nothing says anything settles low.
        """
        if self._grouped[GROUND]:
            return 0
        if self._grouped[POWER]:
            return 1
        for n in self._group:
            if self.pullup[n]:
                return 1
            if self.pulldown[n]:
                return 0
            if self.state[n]:
                return 1
        return 0

    def _queue(self, n: int, into: list[int]) -> None:
        if n in (GROUND, POWER):
            return
        if self._queued[n]:
            return
        self._queued[n] = 1
        into.append(n)

    def _resolve(self, n: int, into: list[int]) -> None:
        if n in (GROUND, POWER):
            return
        self._regroup(n)
        level = self._value()
        for one in self._group:
            if self.state[one] == level:
                continue
            self.state[one] = level
            if level:
                for t in self.gates[one]:
                    if not self.on[t]:
                        self.on[t] = 1
                        self._queue(self.first_of[t], into)
            else:
                for t in self.gates[one]:
                    if self.on[t]:
                        self.on[t] = 0
                        self._queue(self.first_of[t], into)
                        self._queue(self.second_of[t], into)

    def settle(self, seeds: Sequence[int]) -> None:
        """Propagate until nothing changes, or record that it never did.

        Every net queued in a round is resolved, including one an earlier group in
        the same round already set. Skipping those is the obvious optimisation and
        it is wrong: a transistor that closed earlier in the round changes which
        nets the later one is joined to, so the group is not the group that was
        already resolved.
        """
        pending = list(seeds)
        for _ in range(SETTLE_LIMIT):
            if not pending:
                return
            following: list[int] = []
            for n in pending:
                self._queued[n] = 0
            for n in pending:
                self._resolve(n, following)
            pending = following
        self.unsettled += 1

    def drive(self, level: int, name: str) -> None:
        n = self.number(name)
        self.pullup[n] = level
        self.pulldown[n] = 0 if level else 1
        self.settle([n])

    def put(self, value: int) -> None:
        for i in range(8):
            self.drive(1 if value & (1 << i) else 0, f"db{i}")

    def half_cycle(self) -> None:
        """One clock edge, with the pins serviced just before the rise.

        Which machine cycle the part is in is decided from the control pins the
        way Zilog's manual defines them rather than from any other implementation.
        An opcode fetch drives MREQ and RD low with M1 low, a memory read does the
        same one T state later with M1 high, a write drives WR in place of RD, and
        the two port cycles drive IORQ in place of MREQ. A refresh cycle is left
        alone, because the address on the bus during refresh is not one anybody is
        asking about.
        """
        clock = self.read("clk")
        if not clock and self.read("_rfsh"):
            m1 = bool(self.read("_m1"))
            mreq = bool(self.read("_mreq"))
            rd = bool(self.read("_rd"))
            wr = bool(self.read("_wr"))
            iorq = bool(self.read("_iorq"))
            t2 = bool(self.read("t2"))
            t3 = bool(self.read("t3"))
            if not mreq and not rd and wr and iorq and ((not m1 and t2) or (m1 and t3)):
                self.put(self.memory[self.address()])
            elif m1 and not mreq and rd and not wr and iorq and t3:
                self.memory[self.address()] = self.data()
            elif m1 and mreq and not rd and wr and not iorq and t3:
                self.put(self.ports[self.address()])
            elif m1 and mreq and rd and not wr and not iorq and t3:
                self.ports[self.address()] = self.data()
        self.drive(0 if clock else 1, "clk")
        self.half_cycles += 1

    def reset(self) -> Simulation:
        """Hold reset low across the documented number of half cycles, then release.

        Everything is settled once from every connected net before the first edge,
        because a transistor that has never been resolved is open, and a netlist
        where every transistor is open is not a state the part powers up in.
        """
        for t in range(self.transistors):
            self.on[t] = 0
        self.drive(0, "_reset")
        self.drive(1, "clk")
        self.drive(1, "_busrq")
        self.drive(1, "_int")
        self.drive(1, "_nmi")
        self.drive(1, "_wait")
        self.settle(self.connected())
        self.half_cycles = 0
        for _ in range(RESET_HALF_CYCLES):
            self.half_cycle()
        self.drive(1, "_reset")
        return self

    def address(self) -> int:
        return self.bus("ab", 16)

    def data(self) -> int:
        return self.bus("db", 8)

    def register(self, name: str) -> int:
        """One eight-bit register, under the name an instruction would call it.

        MAIN_REGISTERS is applied here rather than at every call site, so a caller
        asks for `b` and gets what `LD B,n` writes.
        """
        return self.bus(f"reg_{MAIN_REGISTERS.get(name, name)}", 8)

    def pc(self) -> int:
        return (self.register("pch") << 8) | self.register("pcl")

    def load(self, program: bytes, at: int = 0) -> Simulation:
        self.memory[at : at + len(program)] = program
        return self


def options(argv: Sequence[str]) -> int:
    half_cycles = DEFAULT_HALF_CYCLES
    rest = list(argv)
    while rest:
        item = rest.pop(0)
        if item != "--half-cycles":
            raise SystemExit(USAGE)
        if not rest:
            raise SystemExit(USAGE)
        half_cycles = int(rest.pop(0))
    return half_cycles


def main(
    argv: Sequence[str],
    where: Path | str | None = None,
    manifest: Path | str | None = None,
) -> int:
    half_cycles = options(argv)
    try:
        part = Simulation(where, manifest)
    except Missing as raised:
        print(f"REFUSED {raised}")
        return 1
    print(f"transistors {part.transistors}, pulled-up nets {part.pullups}")
    part.reset().load(SAMPLE)
    for _ in range(half_cycles):
        part.half_cycle()
    print(
        f"after {part.half_cycles} half cycles:"
        f" pc {part.pc():04X}"
        f" a {part.register('a'):02X}"
        f" b {part.register('b'):02X}"
        f" c {part.register('c'):02X}"
    )
    print(f"unsettled propagations {part.unsettled}")
    return 1 if part.unsettled else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
