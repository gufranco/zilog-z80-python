from __future__ import annotations

import hashlib
import json
import os
import sys
import zipfile
from collections.abc import Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, override

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from z80 import Cpu, Memory  # noqa: E402

RECORD = Path(__file__).resolve().parent / "testroms.json"

PLACES = "TEST_CARTRIDGES"

KEPT = Path(__file__).resolve().parent.parent / "external" / "Master EverDrive"

DATA_PORT = 0xFD

NO_DEVICE = 0xFF

ADDRESS_MASK = 0xFFFF

NEWLINE = "\n"

PRINTED = {0x0A: NEWLINE, 0x0D: NEWLINE}

PRINTABLE = range(0x20, 0x7F)

LIMIT = 40_000_000_000

PASSED = "OK"

JUMPS_TO_ITSELF = (bytes([0x18, 0xFE]), bytes([0xC3]))

NOTHING_TO_RUN = 2

USAGE_ERROR = 3

USAGE = "usage: exercisers.py [--jobs N] [--write] [image, folder or zip ...]"


Host = tuple[int | None, dict[int, int]]


class Unfinished(Exception): ...


class DebugPort:
    __slots__ = ("answers", "text")

    def __init__(self, answers: dict[int, int] | None = None) -> None:
        self.text: list[str] = []
        self.answers = answers or {}

    def read(self, address: int) -> int:
        return self.answers.get(address & 0xFF, NO_DEVICE)

    def write(self, address: int, value: int) -> None:
        if address & 0xFF == DATA_PORT:
            self.put(value)

    def put(self, value: int) -> None:
        self.text.append(PRINTED.get(value, chr(value) if value in PRINTABLE else " "))


class Cartridge(Memory):
    __slots__ = ("rom_end",)

    def __init__(self, image: bytes) -> None:
        super().__init__(image=image)
        self.rom_end = len(image)

    @override
    def write8(self, address: int, value: int) -> None:
        if address & ADDRESS_MASK >= self.rom_end:
            super().write8(address, value)


def record(where: Path | str | None = None) -> dict[str, Any]:
    held = json.loads(Path(where or RECORD).read_text())
    assert isinstance(held, dict), "the record does not hold an object"
    return held


def entry(name: str, where: Path | str | None = None) -> dict[str, Any]:
    found = [one for one in record(where)["cartridges"] if one["id"] == name]
    assert found, f"{name} is not in the record"
    return dict(found[0])


def runnable(held: dict[str, Any]) -> list[dict[str, Any]]:
    return [one for one in held["cartridges"] if one["outcome"] == "run" and "testTable" in one]


def candidates(place: Path) -> Iterator[bytes]:
    if place.is_dir():
        for path in sorted(place.rglob("*")):
            yield from candidates(path)
    elif zipfile.is_zipfile(place):
        with zipfile.ZipFile(place) as archive:
            for member in archive.namelist():
                yield archive.read(member)
    elif place.is_file():
        yield place.read_bytes()


def images(places: Sequence[Path], wanted: set[str]) -> dict[str, bytes]:
    found: dict[str, bytes] = {}
    for place in places:
        for data in candidates(place):
            digest = hashlib.sha256(data).hexdigest()
            if digest in wanted:
                found[digest] = data
    return found


def settled(space: Memory, at: int) -> bool:
    here = bytes(space.read8(at + offset) for offset in range(3))
    return here[:2] == JUMPS_TO_ITSELF[0] or (
        here[:1] == JUMPS_TO_ITSELF[1] and here[1] | here[2] << 8 == at
    )


def printed(image: bytes, limit: int = LIMIT, host: Host | None = None) -> list[str]:
    print_at, answers = host or (None, {})
    space = Cartridge(image)
    port = DebugPort(answers)
    cpu = Cpu("z80", space, ports=port)
    cpu.reset()
    for _ in range(limit):
        if settled(space, cpu.registers.pc):
            return [line for line in "".join(port.text).split(NEWLINE) if line.strip()]
        if cpu.registers.pc == print_at:
            port.put(cpu.registers.a)
        cpu.step()
    raise Unfinished(f"still running after {limit} instructions: {''.join(port.text)!r}")


def pointers(image: bytes, table: int) -> list[int]:
    found = []
    at = table
    while image[at] | image[at + 1]:
        found.append(image[at] | image[at + 1] << 8)
        at += 2
    return found


def flag_masks(image: bytes, table: int) -> list[int]:
    return sorted({image[pointer] for pointer in pointers(image, table)})


def host_of(one: dict[str, Any]) -> Host:
    answers = {int(port, 16): value for port, value in one.get("portAnswers", {}).items()}
    return one.get("printAt"), answers


def verdict(job: tuple[bytes, Host | None]) -> list[str]:
    image, host = job
    return printed(image, host=host)[1:-1]


def verdicts(work: Sequence[tuple[bytes, Host | None]], jobs: int = 1) -> list[list[str]]:
    if jobs <= 1:
        return list(map(verdict, work))
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(verdict, work))


def options(argv: Sequence[str]) -> tuple[int, bool, list[Path]] | None:
    jobs, write, places = 1, False, []
    words = list(argv)
    while words:
        word = words.pop(0)
        if word == "--write":
            write = True
        elif word == "--jobs" and words and words[0].isdigit():
            jobs = int(words.pop(0))
        elif word.startswith("--"):
            return None
        else:
            places.append(Path(word))
    return jobs, write, places


def places_from(given: list[Path], kept: Path) -> list[Path]:
    if given:
        return given
    named = os.environ.get(PLACES, "")
    return [Path(one) for one in named.split(os.pathsep) if one] or [kept]


def judged(one: dict[str, Any], lines: list[str]) -> bool:
    print(f"{one['id']}: {len(lines)} tests")
    for line in lines:
        print(f"  {line}")
    passed = all(line.endswith(PASSED) for line in lines)
    return passed and lines == one.get("verdict")


def main(argv: Sequence[str], where: Path | str | None = None, kept: Path = KEPT) -> int:
    parsed = options(argv)
    if parsed is None:
        print(USAGE)
        return USAGE_ERROR
    jobs, write, given = parsed
    held = record(where)
    wanted = runnable(held)
    found = images(places_from(given, kept), {one["sha256"] for one in wanted})
    if not found:
        print(f"SKIPPED none of the {len(wanted)} pinned images is on this machine")
        return NOTHING_TO_RUN
    present = [one for one in wanted if one["sha256"] in found]
    for one in wanted:
        if one not in present:
            print(f"SKIPPED {one['id']}: not on this machine")
    work = [(found[one["sha256"]], host_of(one)) for one in present]
    good = True
    for one, lines in zip(present, verdicts(work, jobs), strict=True):
        masks = flag_masks(found[one["sha256"]], one["testTable"])
        print(f"{one['id']}: flag masks {[f'{mask:02X}h' for mask in masks]}")
        good = judged(one, lines) and masks == one.get("flagMasks") and good
        one["verdict"] = lines
        one["flagMasks"] = masks
    if write:
        Path(where or RECORD).write_text(json.dumps(held, indent=2) + "\n")
    return 0 if good else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
