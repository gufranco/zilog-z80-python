from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from z80 import Cpu, Memory  # noqa: E402

RECORD = Path(__file__).resolve().parent / "z80test.json"

USAGE = "usage: z80test.py <tape>"

LOAD_AT = 0x8000

PRINT = 0x0010

OPEN_CHANNEL = 0x1601

RETURN = 0xC9

STACK = 0x7FF0

SYSTEM_VARIABLES = 0x5C3A

EVEN_PORT = 0xBF

ODD_PORT = 0xFF

DATA_BLOCK = 0xFF

NEWLINE = 0x0D

PRINTABLE = range(0x20, 0x7F)

LIMIT = 1_000_000_000

PASSED = "Result: all tests passed."

RETURNED = 0x0000


class Refused(Exception): ...


class Unfinished(Exception): ...


class Host:
    __slots__ = ()

    def read(self, address: int) -> int:
        return ODD_PORT if address & 1 else EVEN_PORT

    def write(self, _address: int, _value: int) -> None:
        return None


def identity(where: Path | str | None = None) -> dict[str, Any]:
    held = json.loads(Path(where or RECORD).read_text())
    assert isinstance(held, dict), "the suite record does not hold an object"
    return held


def check(path: Path, held: dict[str, Any]) -> str:
    if not path.is_file():
        raise Refused(f"{path.name} is not there")
    found = hashlib.sha256(path.read_bytes()).hexdigest()
    names = [name for name, digest in held["taps"].items() if digest == found]
    if not names:
        raise Refused(f"{path.name} is no tape of the pinned release: {found}")
    return str(names[0])


def blocks(data: bytes) -> list[bytes]:
    found = []
    at = 0
    while at + 2 <= len(data):
        length = data[at] | data[at + 1] << 8
        found.append(data[at + 2 : at + 2 + length])
        at += 2 + length
    return found


def code(data: bytes) -> bytes:
    held = [one for one in blocks(data) if one and one[0] == DATA_BLOCK]
    return held[-1][1:-1] if held else b""


def loaded(program: bytes) -> Any:
    space = Memory(fill=0x00)
    for offset, byte in enumerate(program):
        space.write8(LOAD_AT + offset, byte)
    space.write8(OPEN_CHANNEL, RETURN)
    space.write8(PRINT, RETURN)
    cpu = Cpu("z80", space, ports=Host())
    cpu.reset()
    cpu.registers.sp = STACK
    cpu.registers.pc = LOAD_AT
    cpu.registers.iy = SYSTEM_VARIABLES
    return cpu


def character(value: int) -> str:
    if value == NEWLINE:
        return "\n"
    return chr(value) if value in PRINTABLE else " "


def run(program: bytes, limit: int = LIMIT) -> list[str]:
    cpu = loaded(program)
    text: list[str] = []
    for _ in range(limit):
        if cpu.registers.pc == RETURNED:
            return "".join(text).split("\n")
        if cpu.registers.pc == PRINT:
            text.append(character(cpu.registers.a))
        cpu.step()
    raise Unfinished(f"still running after {limit} instructions")


def main(argv: Sequence[str], record: Path | str | None = None) -> int:
    if len(argv) != 1:
        print(USAGE)
        return 2
    path = Path(argv[0])
    try:
        name = check(path, identity(record))
    except Refused as raised:
        print(f"REFUSED {raised}")
        return 1
    lines = run(code(path.read_bytes()))
    for line in lines:
        print(line)
    print(f"  {name}: {len(lines)} lines")
    return 0 if PASSED in lines else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
