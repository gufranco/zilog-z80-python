"""The flag register, including the two bits the datasheet leaves blank.

Six of the eight bits are documented: carry, add-or-subtract, parity or overflow,
half carry, zero and sign. The other two have no names and no stated meaning, and
they are not spare. Almost every instruction copies bits three and five of its own
result into them, so software can read them, and software did.

Where they come from is the interesting part. For most instructions it is the
result. For a compare it is the operand rather than the result, because the
result is discarded and never reaches the register. For two instructions it is an
internal register the programmer cannot name. Getting any of those wrong produces
a core that runs every program correctly until one of them looks.

Parity is a table rather than a count. It is consulted on nearly every logical
operation, and counting the bits of a byte two hundred and fifty six different
ways is the sort of arithmetic worth doing once.
"""

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


def undocumented(value):
    """Bits three and five of a result, which is where the hidden flags come from."""
    return value & UNDOCUMENTED


def parity(value):
    """The parity flag for a byte, even parity setting it."""
    return PARITY[value & 0xFF]


def sign_zero(value):
    """Sign, zero and the two hidden bits, all taken from one byte."""
    value &= 0xFF
    return (S if value & 0x80 else 0) | (Z if value == 0 else 0) | undocumented(value)


def sign_zero16(value):
    """The same for a sixteen bit result, whose hidden bits come from its top half."""
    value &= 0xFFFF
    high = value >> 8
    return (S if high & 0x80 else 0) | (Z if value == 0 else 0) | undocumented(high)
