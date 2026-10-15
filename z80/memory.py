from __future__ import annotations

import random
from collections.abc import Sequence
from typing import Protocol


class PortBus(Protocol):
    def read(self, address: int) -> int: ...

    def write(self, address: int, value: int) -> None: ...


UNSET_SEED = 0x5A5A5A5A

ADDRESS_MASK = 0xFFFF


def _derive(seed: int, address: int) -> int:
    return random.Random((seed << 20) ^ address).randrange(0x100)


class SparseMemory:
    __slots__ = (
        "seed",
        "written",
    )

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


class Memory:
    __slots__ = ("data",)

    def __init__(
        self,
        size: int = 0x10000,
        image: Sequence[int] | None = None,
        seed: int = UNSET_SEED,
        fill: int | None = None,
    ) -> None:
        if fill is None:
            self.data = bytearray(_derive(seed, address) for address in range(size))
        else:
            self.data = bytearray([fill & 0xFF]) * size
        if image is not None:
            self.data[: len(image)] = image

    def read8(self, address: int) -> int:
        return self.data[address & ADDRESS_MASK]

    def write8(self, address: int, value: int) -> None:
        self.data[address & ADDRESS_MASK] = value & 0xFF


class Ports:
    __slots__ = (
        "log",
        "seed",
        "written",
    )

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
