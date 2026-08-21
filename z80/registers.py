"""The register file, including the two the datasheet does not name.

The visible part is ordinary: seven eight bit registers and an accumulator, four
sixteen bit pairs made from them, two index registers, a stack pointer and a
program counter. There is a second copy of the main set that instructions swap in
and out wholesale, which is not the same as saving them.

Two more registers exist that no programmer ever names and every accurate model
needs.

`WZ` is where the processor keeps an address it is in the middle of building. It
is invisible until an instruction leaves a value in it that a later instruction
copies into the flags, at which point two bits of the flag register report what
was in a register the programmer cannot see. It has been called MEMPTR for that
reason.

`Q` records whether the instruction just executed touched the flags at all. Two
instructions read it, and get a different answer depending on what ran before
them, which is why an emulator that omits it fails those two and nothing else.

Both are in the conformance suite's initial and final state, so a model without
them cannot pass, and a model that carries them is right for reasons its author
can point at.

Nothing starts clean. Everything except what a reset defines holds arbitrary but
reproducible values, because that is what a real part holds.
"""

from __future__ import annotations

import random
from typing import Any, override

UNSET_SEED = 0x5A5A5A5A

PAIRS = {
    "af": ("a", "f"),
    "bc": ("b", "c"),
    "de": ("d", "e"),
    "hl": ("h", "l"),
    "wz": ("w", "z"),
    "ix": ("ixh", "ixl"),
    "iy": ("iyh", "iyl"),
}

EIGHT_BIT = (
    "a",
    "f",
    "b",
    "c",
    "d",
    "e",
    "h",
    "l",
    "w",
    "z",
    "ixh",
    "ixl",
    "iyh",
    "iyl",
    "i",
    "r",
)

SHADOWS = ("af_", "bc_", "de_", "hl_")

REFRESH_MASK = 0x7F


def _pair_property(high: str, low: str) -> property:
    def read(self: Any) -> int:
        return int((getattr(self, high) << 8) | getattr(self, low))

    def write(self: Any, value: int) -> None:
        value &= 0xFFFF
        setattr(self, high, value >> 8)
        setattr(self, low, value & 0xFF)

    return property(read, write)


def _byte_property(name: str) -> property:
    store = f"_{name}"

    def read(self: Any) -> int:
        return int(getattr(self, store))

    def write(self: Any, value: int) -> None:
        setattr(self, store, value & 0xFF)

    return property(read, write)


def _word_property(name: str) -> property:
    store = f"_{name}"

    def read(self: Any) -> int:
        return int(getattr(self, store))

    def write(self: Any, value: int) -> None:
        setattr(self, store, value & 0xFFFF)

    return property(read, write)


class Registers:
    """One Z80's registers, the hidden ones included."""

    im: int
    iff1: bool
    iff2: bool
    q: int
    p: int
    ei: int
    a: int
    f: int
    b: int
    c: int
    d: int
    e: int
    h: int
    l: int  # noqa: E741 -- the part has a register called L
    w: int
    z: int
    ixh: int
    ixl: int
    iyh: int
    iyl: int
    i: int
    r: int
    af_: int
    bc_: int
    de_: int
    hl_: int
    pc: int
    sp: int
    af: int
    bc: int
    de: int
    hl: int
    wz: int
    ix: int
    iy: int
    """Every register, declared for the checker and attached below as a property.

    The eight bit registers, the shadows and the pairs are all built by the same
    three factories rather than written out, because writing twenty-nine nearly
    identical properties by hand is how one of them ends up masking to the wrong
    width. A bare annotation creates no class attribute at runtime, so these say
    what the type is without getting in the way of the properties that follow.
    """

    def __init__(self, seed: int = UNSET_SEED) -> None:
        generator = random.Random(seed)
        for name in EIGHT_BIT:
            setattr(self, f"_{name}", generator.randrange(0x100))
        for name in SHADOWS:
            setattr(self, f"_{name}", generator.randrange(0x10000))
        self._pc = generator.randrange(0x10000)
        self._sp = generator.randrange(0x10000)
        self.im = generator.randrange(3)
        self.iff1 = bool(generator.randrange(2))
        self.iff2 = bool(generator.randrange(2))
        self.q = 0
        self.p = 0
        self.ei = 0

    def reset(self) -> Registers:
        """What a reset defines, and nothing else.

        The program counter, the interrupt vector and refresh registers, the
        interrupt mode and both enable latches. The rest keeps what it held.
        """
        self.pc = 0x0000
        self.i = 0x00
        self.r = 0x00
        self.im = 0
        self.iff1 = False
        self.iff2 = False
        self.q = 0
        self.p = 0
        self.ei = 0
        return self

    def exchange_set(self) -> None:
        """Swap the main three pairs with their shadows, leaving the accumulator."""
        self.bc, self.bc_ = self.bc_, self.bc
        self.de, self.de_ = self.de_, self.de
        self.hl, self.hl_ = self.hl_, self.hl

    def exchange_accumulator(self) -> None:
        """Swap the accumulator and flags with their shadow, and nothing else."""
        self.af, self.af_ = self.af_, self.af

    def tick_refresh(self) -> None:
        """Advance the refresh counter the way the processor does.

        Only the low seven bits count. The top bit is whatever was last written
        to it and stays there, which is why software that reads the register as a
        source of changing numbers gets a value that never crosses that bit.
        """
        self.r = (self.r & 0x80) | ((self.r + 1) & REFRESH_MASK)

    @override
    def __repr__(self) -> str:
        return f"<Registers pc={self.pc:04X} af={self.af:04X} hl={self.hl:04X}>"


for _name in EIGHT_BIT:
    setattr(Registers, _name, _byte_property(_name))

for _name in (*SHADOWS, "pc", "sp"):
    setattr(Registers, _name, _word_property(_name))

for _pair, (_high, _low) in PAIRS.items():
    setattr(Registers, _pair, _pair_property(_high, _low))
