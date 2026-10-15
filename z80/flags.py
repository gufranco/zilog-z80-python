from __future__ import annotations

C = 0x01
N = 0x02
PV = 0x04
X = 0x08
H = 0x10
Y = 0x20
Z = 0x40
S = 0x80

UNDOCUMENTED = X | Y

PARITY = tuple(PV if bin(value).count("1") % 2 == 0 else 0 for value in range(256))


def undocumented(value: int) -> int:
    return value & UNDOCUMENTED


def parity(value: int) -> int:
    return PARITY[value & 0xFF]


def sign_zero(value: int) -> int:
    value &= 0xFF
    return (S if value & 0x80 else 0) | (Z if value == 0 else 0) | undocumented(value)


def sign_zero16(value: int) -> int:
    value &= 0xFFFF
    high = value >> 8
    return (S if high & 0x80 else 0) | (Z if value == 0 else 0) | undocumented(high)
