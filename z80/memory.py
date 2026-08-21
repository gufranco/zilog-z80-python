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

from __future__ import annotations

import random
from typing import Protocol


class PortBus(Protocol):
    """The little of a port space the core touches.

    Naming the surface rather than the class is what lets a conformance runner
    hand the core a scripted port that answers what a recorded case says it
    answered. Asking for the concrete class would make the core testable against
    nothing but itself.
    """

    def read(self, address: int) -> int: ...

    def write(self, address: int, value: int) -> None: ...


UNSET_SEED = 0x5A5A5A5A

ADDRESS_MASK = 0xFFFF


def _derive(seed: int, address: int) -> int:
    return random.Random((seed << 20) ^ address).randrange(0x100)


class SparseMemory:
    """Unclean everywhere without being allocated anywhere."""

    def __init__(self, seed: int = UNSET_SEED) -> None:
        self.seed = seed
        self.written: dict[int, int] = {}

    def read8(self, address: int) -> int:
        address &= ADDRESS_MASK
        if address in self.written:
            return self.written[address]
        return _derive(self.seed, address)

    def write8(self, address: int, value: int) -> None:
        self.written[address & ADDRESS_MASK] = value & 0xFF


class Ports:
    """The other sixteen bit space, and a record of what happened on it."""

    def __init__(self, seed: int = UNSET_SEED) -> None:
        self.seed = seed
        self.written: dict[int, int] = {}
        self.log: list[tuple[int, int, str]] = []

    def read(self, address: int) -> int:
        address &= ADDRESS_MASK
        value = self.written.get(address)
        if value is None:
            value = _derive(self.seed ^ 0x5555, address)
        self.log.append((address, value, "r"))
        return value

    def write(self, address: int, value: int) -> None:
        address &= ADDRESS_MASK
        value &= 0xFF
        self.written[address] = value
        self.log.append((address, value, "w"))
