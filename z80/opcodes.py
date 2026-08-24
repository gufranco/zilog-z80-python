"""Naming what the core executes, from the same decomposition the core uses.

A disassembler built from a table of several hundred rows is a second description
of the instruction set, and two descriptions drift. This one walks the opcode the
way the part walks it, so an instruction the core executes and an instruction this
names cannot disagree about which one it is.

The output is the conventional assembler syntax, lower case, with hexadecimal
written the way the assemblers of the period wrote it. Relative jumps are resolved
to the address they reach rather than left as the offset the byte holds, because
an offset is not something a reader can follow.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import override

from .errors import Truncated

REGISTERS = ("b", "c", "d", "e", "h", "l", "(hl)", "a")

PAIRS_SP = ("bc", "de", "hl", "sp")
PAIRS_AF = ("bc", "de", "hl", "af")

CONDITIONS = ("nz", "z", "nc", "c", "po", "pe", "p", "m")

ARITHMETIC = ("add a,", "adc a,", "sub ", "sbc a,", "and ", "xor ", "or ", "cp ")

SHIFTS = ("rlc", "rrc", "rl", "rr", "sla", "sra", "sll", "srl")

ACCUMULATOR = ("rlca", "rrca", "rla", "rra", "daa", "cpl", "scf", "ccf")

BLOCKS = (
    ("ldi", "cpi", "ini", "outi"),
    ("ldd", "cpd", "ind", "outd"),
    ("ldir", "cpir", "inir", "otir"),
    ("lddr", "cpdr", "indr", "otdr"),
)

INTERRUPT_MODES = (0, 0, 1, 2, 0, 0, 1, 2)

INDEX_PREFIX = {0xDD: "ix", 0xFD: "iy"}


class Instruction:
    """One decoded instruction: where it sat, how long it was, and what it says."""

    __slots__ = (
        "address",
        "raw",
        "size",
        "text",
    )

    def __init__(self, address: int, size: int, text: str, raw: Sequence[int]) -> None:
        self.address = address
        self.size = size
        self.text = text
        self.raw = raw

    @override
    def __repr__(self) -> str:
        return f"<{self.address:04X} {self.text}>"


class Reader:
    """A cursor over the bytes, which refuses to read past the end rather than guess."""

    __slots__ = (
        "data",
        "offset",
        "start",
    )

    def __init__(self, data: Sequence[int], offset: int) -> None:
        self.data = data
        self.start = offset
        self.offset = offset

    def byte(self) -> int:
        if self.offset >= len(self.data):
            raise Truncated(f"instruction at {self.start} runs past the end of the data")
        value = self.data[self.offset]
        self.offset += 1
        return value

    def word(self) -> int:
        low = self.byte()
        return low | (self.byte() << 8)

    def signed(self) -> int:
        value = self.byte()
        return value - 0x100 if value & 0x80 else value

    @property
    def size(self) -> int:
        return self.offset - self.start


def byte_text(value: int) -> str:
    return f"${value:02X}"


def word_text(value: int) -> str:
    return f"${value:04X}"


def displacement_text(value: int) -> str:
    sign = "-" if value < 0 else "+"
    return f"{sign}${abs(value):02X}"


def register_text(index: int, prefix: str | None, displacement: int) -> str:
    """One register operand, which an index prefix can change into a memory reference."""
    name = REGISTERS[index]
    if prefix is None:
        return name
    if name == "(hl)":
        return f"({prefix}{displacement_text(displacement)})"
    if name == "h":
        return f"{prefix}h"
    if name == "l":
        return f"{prefix}l"
    return name


def pair_text(name: str, prefix: str | None) -> str:
    return prefix if name == "hl" and prefix is not None else name


def decode(data: Sequence[int], offset: int = 0, address: int = 0) -> Instruction:
    """The instruction at that offset, named as an assembler would name it."""
    reader = Reader(data, offset)
    prefix = None
    opcode = reader.byte()
    while opcode in INDEX_PREFIX:
        prefix = INDEX_PREFIX[opcode]
        opcode = reader.byte()

    if opcode == 0xCB:
        text = decode_bit(reader, prefix)
    elif opcode == 0xED:
        text = decode_extended(reader)
    else:
        text = decode_plain(reader, opcode, prefix, address)

    size = reader.size
    return Instruction(address, size, text, bytes(data[offset : offset + size]))


def decode_plain(reader: Reader, opcode: int, prefix: str | None, address: int) -> str:
    x = opcode >> 6
    y = (opcode >> 3) & 0x07
    z = opcode & 0x07
    p = y >> 1
    q = y & 1

    if x == 1:
        if y == 6 and z == 6:
            return "halt"
        displacement = reader.signed() if (y == 6 or z == 6) and prefix is not None else 0
        source = register_text(z, None if y == 6 else prefix, displacement)
        target = register_text(y, None if z == 6 else prefix, displacement)
        return f"ld {target},{source}"

    if x == 2:
        displacement = reader.signed() if z == 6 and prefix is not None else 0
        return f"{ARITHMETIC[y]}{register_text(z, prefix, displacement)}".strip()

    if x == 0:
        return decode_group0(reader, y, z, p, q, prefix, address)
    return decode_group3(reader, y, z, p, q, prefix)


def decode_group0(
    reader: Reader, y: int, z: int, p: int, q: int, prefix: str | None, address: int
) -> str:
    if z == 0:
        return decode_group0_control(reader, y, address)
    if z == 1:
        name = pair_text(PAIRS_SP[p], prefix)
        if q == 0:
            return f"ld {name},{word_text(reader.word())}"
        return f"add {pair_text('hl', prefix)},{name}"
    if z == 2:
        return decode_group0_indirect(reader, p, q, prefix)
    if z == 3:
        name = pair_text(PAIRS_SP[p], prefix)
        return f"{'inc' if q == 0 else 'dec'} {name}"
    if z in (4, 5):
        displacement = reader.signed() if y == 6 and prefix is not None else 0
        return f"{'inc' if z == 4 else 'dec'} {register_text(y, prefix, displacement)}"
    if z == 6:
        displacement = reader.signed() if y == 6 and prefix is not None else 0
        return f"ld {register_text(y, prefix, displacement)},{byte_text(reader.byte())}"
    return ACCUMULATOR[y]


def decode_group0_control(reader: Reader, y: int, address: int) -> str:
    if y == 0:
        return "nop"
    if y == 1:
        return "ex af,af'"
    offset = reader.signed()
    target = word_text((address + reader.size + offset) & 0xFFFF)
    if y == 2:
        return f"djnz {target}"
    if y == 3:
        return f"jr {target}"
    return f"jr {CONDITIONS[y - 4]},{target}"


def decode_group0_indirect(reader: Reader, p: int, q: int, prefix: str | None) -> str:
    if p == 0:
        return "ld a,(bc)" if q else "ld (bc),a"
    if p == 1:
        return "ld a,(de)" if q else "ld (de),a"
    where = f"({word_text(reader.word())})"
    if p == 3:
        return f"ld a,{where}" if q else f"ld {where},a"
    name = pair_text("hl", prefix)
    return f"ld {name},{where}" if q else f"ld {where},{name}"


def decode_group3(reader: Reader, y: int, z: int, p: int, q: int, prefix: str | None) -> str:
    if z == 0:
        return f"ret {CONDITIONS[y]}"
    if z == 1:
        if q == 0:
            return f"pop {pair_text(PAIRS_AF[p], prefix)}"
        return (
            "ret",
            "exx",
            f"jp ({pair_text('hl', prefix)})",
            f"ld sp,{pair_text('hl', prefix)}",
        )[p]
    if z == 2:
        return f"jp {CONDITIONS[y]},{word_text(reader.word())}"
    if z == 3:
        return decode_group3_misc(reader, y, prefix)
    if z == 4:
        return f"call {CONDITIONS[y]},{word_text(reader.word())}"
    if z == 5:
        if q == 0:
            return f"push {pair_text(PAIRS_AF[p], prefix)}"
        return f"call {word_text(reader.word())}"
    if z == 6:
        return f"{ARITHMETIC[y]}{byte_text(reader.byte())}".strip()
    return f"rst ${y * 8:02X}"


def decode_group3_misc(reader: Reader, y: int, prefix: str | None) -> str:
    if y == 0:
        return f"jp {word_text(reader.word())}"
    if y == 2:
        return f"out ({byte_text(reader.byte())}),a"
    if y == 3:
        return f"in a,({byte_text(reader.byte())})"
    if y == 4:
        return f"ex (sp),{pair_text('hl', prefix)}"
    if y == 5:
        return "ex de,hl"
    return "di" if y == 6 else "ei"


def decode_bit(reader: Reader, prefix: str | None) -> str:
    displacement = reader.signed() if prefix is not None else 0
    opcode = reader.byte()
    x = opcode >> 6
    y = (opcode >> 3) & 0x07
    z = opcode & 0x07
    target = register_text(6 if prefix is not None else z, prefix, displacement)

    if x == 1:
        return f"bit {y},{target}"
    name = SHIFTS[y] if x == 0 else ("res" if x == 2 else "set")
    operand = target if x == 0 else f"{y},{target}"
    if prefix is not None and z != 6:
        return f"{name} {operand},{REGISTERS[z]}"
    return f"{name} {operand}"


def decode_extended(reader: Reader) -> str:
    opcode = reader.byte()
    x = opcode >> 6
    y = (opcode >> 3) & 0x07
    z = opcode & 0x07
    p = y >> 1
    q = y & 1

    if x == 2:
        if y >= 4 and z <= 3:
            return BLOCKS[y - 4][z]
        return f"db $ed,{byte_text(opcode)}"
    if x != 1:
        return f"db $ed,{byte_text(opcode)}"
    if z == 0:
        return "in f,(c)" if y == 6 else f"in {REGISTERS[y]},(c)"
    if z == 1:
        return "out (c),0" if y == 6 else f"out (c),{REGISTERS[y]}"
    if z == 2:
        return f"{'sbc' if q == 0 else 'adc'} hl,{PAIRS_SP[p]}"
    if z == 3:
        where = f"({word_text(reader.word())})"
        return f"ld {PAIRS_SP[p]},{where}" if q else f"ld {where},{PAIRS_SP[p]}"
    if z == 4:
        return "neg"
    if z == 5:
        return "reti" if y == 1 else "retn"
    if z == 6:
        return f"im {INTERRUPT_MODES[y]}"
    return ("ld i,a", "ld r,a", "ld a,i", "ld a,r", "rrd", "rld", "nop", "nop")[y]


def disassemble(data: Sequence[int], address: int = 0) -> list[Instruction]:
    """Every instruction in a run of bytes, with a trailing fragment shown as data."""
    listing: list[Instruction] = []
    offset = 0
    while offset < len(data):
        try:
            found = decode(data, offset, (address + offset) & 0xFFFF)
        except Truncated:
            found = Instruction(
                (address + offset) & 0xFFFF,
                1,
                f"db {byte_text(data[offset])}",
                data[offset : offset + 1],
            )
        listing.append(found)
        offset += found.size
    return listing
