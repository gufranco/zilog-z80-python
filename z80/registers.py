from __future__ import annotations

import random
from typing import override

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


class Registers:
    __slots__ = (
        "_a",
        "_af_",
        "_b",
        "_bc_",
        "_c",
        "_d",
        "_de_",
        "_e",
        "_f",
        "_h",
        "_hl_",
        "_i",
        "_ixh",
        "_ixl",
        "_iyh",
        "_iyl",
        "_l",
        "_pc",
        "_r",
        "_sp",
        "_w",
        "_z",
        "ei",
        "iff1",
        "iff2",
        "im",
        "p",
        "q",
    )

    im: int
    iff1: bool
    iff2: bool
    q: int
    p: int
    ei: int

    @property
    def a(self) -> int:
        return self._a

    @a.setter
    def a(self, value: int) -> None:
        self._a = value & 0xFF

    @property
    def f(self) -> int:
        return self._f

    @f.setter
    def f(self, value: int) -> None:
        self._f = value & 0xFF

    @property
    def b(self) -> int:
        return self._b

    @b.setter
    def b(self, value: int) -> None:
        self._b = value & 0xFF

    @property
    def c(self) -> int:
        return self._c

    @c.setter
    def c(self, value: int) -> None:
        self._c = value & 0xFF

    @property
    def d(self) -> int:
        return self._d

    @d.setter
    def d(self, value: int) -> None:
        self._d = value & 0xFF

    @property
    def e(self) -> int:
        return self._e

    @e.setter
    def e(self, value: int) -> None:
        self._e = value & 0xFF

    @property
    def h(self) -> int:
        return self._h

    @h.setter
    def h(self, value: int) -> None:
        self._h = value & 0xFF

    @property
    def l(self) -> int:  # noqa: E743 -- the part has a register called L
        return self._l

    @l.setter
    def l(self, value: int) -> None:  # noqa: E743 -- the part has a register called L
        self._l = value & 0xFF

    @property
    def w(self) -> int:
        return self._w

    @w.setter
    def w(self, value: int) -> None:
        self._w = value & 0xFF

    @property
    def z(self) -> int:
        return self._z

    @z.setter
    def z(self, value: int) -> None:
        self._z = value & 0xFF

    @property
    def ixh(self) -> int:
        return self._ixh

    @ixh.setter
    def ixh(self, value: int) -> None:
        self._ixh = value & 0xFF

    @property
    def ixl(self) -> int:
        return self._ixl

    @ixl.setter
    def ixl(self, value: int) -> None:
        self._ixl = value & 0xFF

    @property
    def iyh(self) -> int:
        return self._iyh

    @iyh.setter
    def iyh(self, value: int) -> None:
        self._iyh = value & 0xFF

    @property
    def iyl(self) -> int:
        return self._iyl

    @iyl.setter
    def iyl(self, value: int) -> None:
        self._iyl = value & 0xFF

    @property
    def i(self) -> int:
        return self._i

    @i.setter
    def i(self, value: int) -> None:
        self._i = value & 0xFF

    @property
    def r(self) -> int:
        return self._r

    @r.setter
    def r(self, value: int) -> None:
        self._r = value & 0xFF

    @property
    def af_(self) -> int:
        return self._af_

    @af_.setter
    def af_(self, value: int) -> None:
        self._af_ = value & 0xFFFF

    @property
    def bc_(self) -> int:
        return self._bc_

    @bc_.setter
    def bc_(self, value: int) -> None:
        self._bc_ = value & 0xFFFF

    @property
    def de_(self) -> int:
        return self._de_

    @de_.setter
    def de_(self, value: int) -> None:
        self._de_ = value & 0xFFFF

    @property
    def hl_(self) -> int:
        return self._hl_

    @hl_.setter
    def hl_(self, value: int) -> None:
        self._hl_ = value & 0xFFFF

    @property
    def pc(self) -> int:
        return self._pc

    @pc.setter
    def pc(self, value: int) -> None:
        self._pc = value & 0xFFFF

    @property
    def sp(self) -> int:
        return self._sp

    @sp.setter
    def sp(self, value: int) -> None:
        self._sp = value & 0xFFFF

    @property
    def af(self) -> int:
        return (self.a << 8) | self.f

    @af.setter
    def af(self, value: int) -> None:
        value &= 0xFFFF
        self.a = value >> 8
        self.f = value & 0xFF

    @property
    def bc(self) -> int:
        return (self.b << 8) | self.c

    @bc.setter
    def bc(self, value: int) -> None:
        value &= 0xFFFF
        self.b = value >> 8
        self.c = value & 0xFF

    @property
    def de(self) -> int:
        return (self.d << 8) | self.e

    @de.setter
    def de(self, value: int) -> None:
        value &= 0xFFFF
        self.d = value >> 8
        self.e = value & 0xFF

    @property
    def hl(self) -> int:
        return (self.h << 8) | self.l

    @hl.setter
    def hl(self, value: int) -> None:
        value &= 0xFFFF
        self.h = value >> 8
        self.l = value & 0xFF

    @property
    def wz(self) -> int:
        return (self.w << 8) | self.z

    @wz.setter
    def wz(self, value: int) -> None:
        value &= 0xFFFF
        self.w = value >> 8
        self.z = value & 0xFF

    @property
    def ix(self) -> int:
        return (self.ixh << 8) | self.ixl

    @ix.setter
    def ix(self, value: int) -> None:
        value &= 0xFFFF
        self.ixh = value >> 8
        self.ixl = value & 0xFF

    @property
    def iy(self) -> int:
        return (self.iyh << 8) | self.iyl

    @iy.setter
    def iy(self, value: int) -> None:
        value &= 0xFFFF
        self.iyh = value >> 8
        self.iyl = value & 0xFF

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
        self.bc, self.bc_ = self.bc_, self.bc
        self.de, self.de_ = self.de_, self.de
        self.hl, self.hl_ = self.hl_, self.hl

    def exchange_accumulator(self) -> None:
        self.af, self.af_ = self.af_, self.af

    def tick_refresh(self) -> None:
        self.r = (self.r & 0x80) | ((self.r + 1) & REFRESH_MASK)

    @override
    def __repr__(self) -> str:
        return f"<Registers pc={self.pc:04X} af={self.af:04X} hl={self.hl:04X}>"
