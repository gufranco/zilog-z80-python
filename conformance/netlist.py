from __future__ import annotations

import hashlib
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent / "docs" / "independent" / "visual6502"

MANIFEST = Path(__file__).resolve().parent / "netlist.manifest.json"

FILES = ("nodenames.js", "segdefs.js", "transdefs.js")

USAGE = "usage: netlist.py [--half-cycles N]"

MAX_NETS = 4000
MAX_TRANS = 10000

GROUND = 1
POWER = 2

SETTLE_LIMIT = 100

RESET_HALF_CYCLES = 31

TRANSISTORS_THAT_ARE_PULLUPS = 32

MAIN_REGISTERS = {"b": "bb", "c": "cc", "d": "hh", "e": "ll", "h": "dd", "l": "ee"}

SAMPLE = bytes([0x3E, 0x42, 0x06, 0x99, 0x0E, 0x17, 0x04, 0x00])

DEFAULT_HALF_CYCLES = 130

_NAME = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(\d+)\s*,", re.M)


class Missing(Exception): ...


def identity(manifest: Path | str | None = None) -> dict[str, Any]:
    with Path(manifest or MANIFEST).open() as handle:
        held: dict[str, Any] = json.load(handle)
    return held


def check(path: Path, entry: dict[str, Any]) -> None:
    if not path.is_file():
        raise Missing(f"{path.name} is not in {path.parent}. Take it from {entry['retrievedFrom']}")
    size = path.stat().st_size
    if size != entry["bytes"]:
        raise Missing(f"{path.name} is {size} bytes, not {entry['bytes']}")
    found = hashlib.sha256(path.read_bytes()).hexdigest()
    if found != entry["sha256"]:
        raise Missing(f"{path.name} is a different file: {found}")


class Netlist:
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
