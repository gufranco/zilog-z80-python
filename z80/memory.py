"""Memory and ports, neither of which starts cleared.

A byte nobody has written holds whatever the hardware powered up with, so reading
one is reading something undefined. Filling it with zeroes would make that read
look deliberate, and a program that depends on it would appear to work. So an
address that has never been written derives its value from the address itself:
arbitrary, not zero, and the same every time it is asked.

Ports are a separate sixteen bit space, not part of memory, and the whole sixteen
bits address them. Software that treats only the low eight as significant works
until something answers on the top half. Every transaction is recorded in order,
because a conformance suite that names which port was touched and with what needs
that answered rather than inferred.
"""

import random

UNSET_SEED = 0x5A5A5A5A

ADDRESS_MASK = 0xFFFF


def _derive(seed, address):
    return random.Random((seed << 20) ^ address).randrange(0x100)


class SparseMemory:
    """Unclean everywhere without being allocated anywhere."""

    def __init__(self, seed=UNSET_SEED):
        self.seed = seed
        self.written = {}

    def read8(self, address):
        address &= ADDRESS_MASK
        if address in self.written:
            return self.written[address]
        return _derive(self.seed, address)

    def write8(self, address, value):
        self.written[address & ADDRESS_MASK] = value & 0xFF


class Ports:
    """The other sixteen bit space, and a record of what happened on it."""

    def __init__(self, seed=UNSET_SEED):
        self.seed = seed
        self.written = {}
        self.log = []

    def read(self, address):
        address &= ADDRESS_MASK
        value = self.written.get(address)
        if value is None:
            value = _derive(self.seed ^ 0x5555, address)
        self.log.append((address, value, "r"))
        return value

    def write(self, address, value):
        address &= ADDRESS_MASK
        value &= 0xFF
        self.written[address] = value
        self.log.append((address, value, "w"))
