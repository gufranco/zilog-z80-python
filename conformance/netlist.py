"""Run the part as a net of transistors, so the model can be asked about the die.

Every other check in this package holds the model to a document or to a recording.
Both stop at the package boundary: a document says what the part does and a
recording says what one part did, and neither says what is inside. A switch-level
run of the netlist answers a third kind of question, which is the one most of the
open questions in this repository turn out to be.

What this reads is not carried here. The netlist is Z80Explorer's, extracted from
die photographs of a real part and published under Creative Commons BY-NC-SA 4.0,
so the repository carries its identity and this program, never the files.
`netlist.json` names all four, where they come from and what they hash to, and a
load refuses anything that is not what was read.

This is an independent implementation in Python rather than a translation of the
reference's C++. What it is faithful to is the reference's behaviour, because a
resolver that settles differently is a different chip, and the file formats, which
are the ones the Visual 6502 team defined. Read against Z80Explorer at commit
867ad38a013862d1de6b0fb33fd77594823f40c3.

Authority rung 3, die simulation. Below a manufacturer document and below the part
itself, above a recording taken from somebody else's model.

Usage:
    python3 -m conformance.netlist [--half-cycles N]
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent / "docs" / "independent" / "z80explorer"
"""Where the four files land, which is the folder git ignores.

Same reasoning as `conformance.documents`: the record lives beside the code and
the files it identifies do not live in the repository at all.
"""

MANIFEST = Path(__file__).resolve().parent / "netlist.json"

FILES = ("nodenames.js", "netnames.js", "transdefs.js", "segdefs.js")

USAGE = "usage: netlist.py [--half-cycles N]"

MAX_NETS = 4000
MAX_TRANS = 10000
"""Bounds the reference states for this netlist, carried so the arrays can be flat
lists rather than dictionaries. A netlist needing more is not this one, and the
load says so rather than growing silently.
"""

GROUND = 1
POWER = 2
CLOCK = 3
"""The three nets whose numbers the format fixes. Checked on load rather than
trusted, because every rule below is written in terms of them.
"""

SETTLE_LIMIT = 100
"""Rounds before a propagation is called unsettled, which is the reference's own
limiter. Reaching it is recorded rather than raised: a netlist that will not rest
is a finding about the run, and stopping mid-edge would hide it.
"""

RESET_HALF_CYCLES = 8
"""Half cycles the reference holds reset low for before releasing it."""

FLOATING = ("_mreq", "_iorq", "_rd", "_wr", "dbus0", "ubus0", "vbus0")
"""Nets read for their high-impedance state rather than for a level.

A net nothing is driving has no level, and reading its last one as though it were
current is how a bus that has been released reads as though it were still held.
"""

DEFAULT_HALF_CYCLES = 130

SAMPLE = bytes([0x3E, 0x42, 0x06, 0x99, 0x0E, 0x17, 0x04, 0x00])
"""Load, load, load, increment. Chosen so the registers afterwards hold values
that only executing it produces, rather than values a part doing nothing would
also show.
"""


class Missing(Exception):
    """The netlist is not on this machine, or is not the netlist that was read."""


def identity(manifest: Path | str | None = None) -> dict[str, Any]:
    with Path(manifest or MANIFEST).open() as handle:
        held: dict[str, Any] = json.load(handle)
    return held


def check(path: Path, entry: dict[str, Any]) -> None:
    """That one file is the one the manifest names, by size and then by digest.

    Size first because it is one call and it rejects almost every wrong file,
    and the digest because size alone rejects nothing that was edited in place.
    A refusal names where the file comes from, since a reader who has the wrong
    one needs the address more than the reason.
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
    """The four files, parsed into nets and transistors.

    Kept apart from the run below because parsing is where a netlist is rejected
    and running is where it is used, and a fault in the first should never be
    reported as a fault in the second.
    """

    def __init__(self, where: Path | str | None = None, manifest: Path | str | None = None) -> None:
        root = Path(where or ROOT)
        self.identity = identity(manifest)
        for entry in self.identity["files"]:
            check(root / str(entry["file"]), entry)

        self.names: dict[str, int] = {}
        self.named: list[str] = [""] * MAX_NETS
        self.buses: dict[str, tuple[int, ...]] = {}

        self.state = bytearray(MAX_NETS)
        self.floats = bytearray(MAX_NETS)
        self.high = bytearray(MAX_NETS)
        self.low = bytearray(MAX_NETS)
        self.pulled_up = bytearray(MAX_NETS)

        self.gates: list[list[int]] = [[] for _ in range(MAX_NETS)]
        self.channels: list[list[int]] = [[] for _ in range(MAX_NETS)]

        self.on = bytearray(MAX_TRANS)
        self.gate_of = [0] * MAX_TRANS
        self.first_of = [0] * MAX_TRANS
        self.second_of = [0] * MAX_TRANS

        self.transistors = 0
        self.skipped_pullups = 0
        self.pullups = 0

        self._read_names(root / "nodenames.js", custom=False)
        self._read_names(root / "netnames.js", custom=True)
        self._check_fixed_nets()
        self._read_transistors(root / "transdefs.js")
        self._read_pullups(root / "segdefs.js")

    def _check_fixed_nets(self) -> None:
        for name, wanted in (("vss", GROUND), ("vcc", POWER), ("clk", CLOCK)):
            found = self.names.get(name)
            if found != wanted:
                raise Missing(f"{name} is net {found}, and every rule here assumes {wanted}")

    def _read_names(self, path: Path, custom: bool) -> None:
        """One name per line, with the custom file overriding and adding buses.

        An override deletes the old name rather than shadowing it. A name left
        pointing at a net nobody uses is worse than an absent name, because it
        answers.
        """
        for raw in path.read_text().splitlines():
            comment = raw.find("/")
            line = raw[:comment].strip() if comment != -1 else raw.strip()
            if ":" not in line:
                continue
            line = line[:-1] if line.endswith(",") else line
            head, _, tail = line.partition(":")
            name = head.strip()
            body = tail.strip()
            if custom and body.startswith("["):
                members = [one.strip() for one in body.strip("[] ").split(",") if one.strip()]
                if len(members) > 1:
                    self.buses[name] = tuple(int(one) for one in members)
                    continue
                body = members[0]
            if not body.isdigit():
                continue
            number = int(body)
            if number >= MAX_NETS:
                raise Missing(f"net {number} is past the {MAX_NETS} this netlist was read at")
            if custom:
                if name in self.names:
                    self.named[self.names[name]] = ""
                    del self.names[name]
            elif name in self.names or self.named[number]:
                continue
            self.named[number] = name
            self.names[name] = number

    def _read_transistors(self, path: Path) -> None:
        """Gate, then the two channel connections, then a flag marking a pull-up.

        The two channel connections are ordered rather than symmetric. A
        transistor tied to a rail or to the clock carries that connection second,
        because closing one queues both of its ends and opening one queues only
        the first, and queueing a rail is work that decides nothing.
        """
        for raw in path.read_text().splitlines():
            if not raw.startswith("["):
                continue
            flat = raw.replace("[", " ").replace("]", " ")[:-2]
            fields = [one for one in flat.split(",") if one.strip()]
            if len(fields) != 14 or len(fields[0]) <= 2:
                continue
            if fields[13].strip() == "true":
                self.skipped_pullups += 1
                continue
            number = int(fields[0].strip().strip("'")[1:])
            if number >= MAX_TRANS:
                raise Missing(f"transistor {number} is past the {MAX_TRANS} this was read at")
            gate = int(fields[1])
            first = int(fields[2])
            second = int(fields[3])
            if first <= CLOCK:
                first, second = second, first
            self.gate_of[number] = gate
            self.first_of[number] = first
            self.second_of[number] = second
            self.gates[gate].append(number)
            self.channels[first].append(number)
            self.channels[second].append(number)
            self.transistors += 1

    def _read_pullups(self, path: Path) -> None:
        """A pull-up is a property of a net here rather than a transistor of its own.

        It sets the net high on load and it stays that way until something drives
        it, so it resolves as a pull and not as a rail. That distinction is the
        whole of why a net can be pulled up and still read low.
        """
        for raw in path.read_text().splitlines():
            if not raw.startswith("["):
                continue
            fields = raw[2:-2].split(",")
            if len(fields) <= 4:
                continue
            number = int(fields[0])
            if number >= MAX_NETS:
                raise Missing(f"net {number} is past the {MAX_NETS} this netlist was read at")
            up = 1 if "+" in fields[1] else 0
            self.pulled_up[number] = up
            self.high[number] = up
        self.pullups = sum(self.pulled_up)

    def number(self, name: str) -> int:
        return self.names.get(name, 0)

    def read(self, name: str) -> int:
        """A net's level, or 2 when it floats and nothing is driving it."""
        n = self.number(name)
        if self.floats[n]:
            for t in self.channels[n]:
                if self.on[t]:
                    return 1 if self.state[n] else 0
            return 1 if self.pulled_up[n] else 2
        return 1 if self.state[n] else 0

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
        for name in FLOATING:
            self.floats[self.number(name)] = 1
        for i in range(16):
            self.floats[self.number(f"ab{i}")] = 1

    def connected(self) -> list[int]:
        return [
            n
            for n in range(MAX_NETS)
            if n not in (GROUND, POWER) and (self.gates[n] or self.channels[n])
        ]

    def _collect(self, start: int) -> None:
        """Every net joined to this one through transistors that are closed.

        A rail found on the way is moved to the front, and the last one found
        stays there, which is what makes `_value` able to decide on the front of
        the group alone.

        Whether that ordering matters was measured rather than assumed. Groups
        reaching both rails at once are common, 2,098 of 167,115 resolutions
        across a short run, and the front differs from a plain "is a rail
        present" test on 82 of them. Deciding those 82 the other way runs the
        part to the same registers, so the ordering is faithful to the reference
        without being load-bearing on this netlist. It is kept because a rule
        that happens not to matter here is not a rule that is known not to
        matter.
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
                if len(group) > 1:
                    group[0], group[-1] = group[-1], group[0]
                continue
            joined: list[int] = []
            for t in self.channels[n]:
                if not self.on[t]:
                    continue
                other = self.second_of[t] if self.first_of[t] == n else self.first_of[t]
                joined.append(other)
            stack.extend(reversed(joined))

    def _regroup(self, n: int) -> None:
        for one in self._group:
            self._grouped[one] = 0
        self._group = []
        self._collect(n)

    def _value(self) -> int:
        """What the joined set settles to.

        Three rules in order, and the order is the whole of it. A rail at the
        front decides outright. Failing that, anything being pulled decides, high
        before low. Failing that, nothing is driving the set at all and it keeps
        the level of whichever net has the most gates hanging off it, which is the
        reference's stand-in for the largest capacitance.
        """
        group = self._group
        if group[0] == GROUND:
            return 0
        if group[0] == POWER:
            return 1
        for n in group:
            if self.high[n]:
                return 1
            if self.low[n]:
                return 0
        level = 0
        weight = 0
        for n in group:
            count = len(self.gates[n])
            if count > weight:
                weight = count
                level = self.state[n]
        return level

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
        if self.high[n] == level:
            return
        self.high[n] = level
        self.low[n] = 0 if level else 1
        self.settle([n])

    def put(self, value: int) -> None:
        for i in range(8):
            self.drive(1 if value & (1 << i) else 0, f"db{i}")

    def half_cycle(self) -> None:
        """One clock edge, with the pins serviced just before the rise.

        The part drives its address and its control lines through the low half and
        samples the data bus on the rise, so anything answering it has to have
        answered by then. A refresh cycle is left alone: the address on the bus
        during refresh is not one anybody is asking about.
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
        """Hold reset low across eight half cycles, then release it.

        Everything is settled once from every connected net before the first edge,
        because a transistor that has never been resolved is open, and a netlist
        where every transistor is open is not a state the part powers up in.
        """
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
        return self.bus(f"reg_{name}", 8)

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
