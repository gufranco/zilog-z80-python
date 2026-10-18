from __future__ import annotations

from collections.abc import Callable
from typing import override

from .errors import UnknownShape

READ = "r"

WRITE = "w"

MEMORY = "m"

PORT = "i"

PIN_ORDER = (READ, WRITE, MEMORY, PORT)

IDLE = "----"

MEMORY_READ = "r-m-"

MEMORY_WRITE = "-wm-"

MEMORY_REQUEST = "--m-"

PORT_READ = "r--i"

PORT_WRITE = "-w-i"

PORT_REQUEST = "---i"

FETCH = "fetch"

READ_CYCLE = "read"

WRITE_CYCLE = "write"

PORT_READ_CYCLE = "portRead"

PORT_WRITE_CYCLE = "portWrite"

ACKNOWLEDGE = "acknowledge"

EDGES: dict[str, tuple[int, tuple[tuple[str, float, float], ...]]] = {
    FETCH: (4, ((READ, 0.5, 2.0), (MEMORY, 0.5, 2.0), (MEMORY, 2.5, 3.5))),
    READ_CYCLE: (3, ((READ, 0.5, 2.5), (MEMORY, 0.5, 2.5))),
    WRITE_CYCLE: (3, ((MEMORY, 0.5, 2.5), (WRITE, 1.5, 2.5))),
    PORT_READ_CYCLE: (4, ((READ, 1.0, 3.5), (PORT, 1.0, 3.5))),
    PORT_WRITE_CYCLE: (4, ((WRITE, 1.0, 3.5), (PORT, 1.0, 3.5))),
    ACKNOWLEDGE: (6, ((PORT, 2.5, 4.0), (MEMORY, 4.5, 5.5))),
}


def columns(cycle: str) -> tuple[str, ...]:
    states, edges = EDGES[cycle]
    return tuple(
        "".join(
            pin
            if any(pin == name and start < state + 1 <= end for name, start, end in edges)
            else "-"
            for pin in PIN_ORDER
        )
        for state in range(states)
    )


COLUMNS: dict[str, tuple[str, ...]] = {name: columns(name) for name in EDGES}

FETCH_STATES = EDGES[FETCH][0]

MEMORY_STATES = EDGES[READ_CYCLE][0]

PORT_STATES = EDGES[PORT_READ_CYCLE][0]

ACKNOWLEDGE_STATES = EDGES[ACKNOWLEDGE][0]

ADDRESS_MASK = 0xFFFF

SAMPLE_WAIT_AFTER = 1

MANUAL = "manual"

RECORDING = "recording"

SHAPES = (MANUAL, RECORDING)


class Bus:
    __slots__ = (
        "address",
        "cycles",
        "log",
        "on_state",
        "recording",
        "shape",
        "states",
        "waiting",
    )

    def __init__(
        self,
        on_state: Callable[[], None],
        waiting: Callable[[], bool],
        recording: bool = False,
        shape: str = MANUAL,
    ) -> None:
        if shape not in SHAPES:
            raise UnknownShape(f"{shape} is not a pin shape; there are {', '.join(SHAPES)}")
        self.waiting = waiting

        self.on_state = on_state
        self.recording = recording
        self.shape = shape
        self.log: list[tuple[int, int | None, str]] = []
        self.cycles: list[tuple[int, str]] = []
        self.states = 0
        self.address = 0

    @property
    def follows_the_manual(self) -> bool:
        return self.shape == MANUAL

    def clear(self) -> None:
        self.log.clear()
        self.cycles.clear()
        self.states = 0

    def mark(self, address: int, value: int | None, pins: str) -> None:
        self.states += 1
        self.address = address & ADDRESS_MASK
        if self.recording:
            self.log.append((self.address, value, pins))
        self.on_state()

    def spend(
        self,
        cycle: str,
        addresses: tuple[int, ...],
        values: tuple[int | None, ...],
        recorded: tuple[str, ...],
    ) -> None:
        if self.recording:
            self.cycles.append((self.states, cycle))
        pins = COLUMNS[cycle] if self.follows_the_manual else recorded
        for index, (address, value, held) in enumerate(zip(addresses, values, pins, strict=True)):
            self.mark(address, value, held)
            if index == SAMPLE_WAIT_AFTER:
                while self.waiting():
                    self.mark(address, None, held)

    def idle(self, count: int = 1) -> None:
        for _ in range(count):
            self.mark(self.address, None, IDLE)

    def fetch(self, counter: int, refresh: int, value: int) -> None:
        self.spend(
            FETCH,
            (counter, counter, refresh, refresh),
            (None, None, value, None),
            (IDLE, MEMORY_READ, IDLE, IDLE),
        )

    def read(self, address: int, value: int) -> None:
        self.spend(
            READ_CYCLE,
            (address, address, address),
            (None, None, value),
            (IDLE, MEMORY_READ, IDLE),
        )

    def write(self, address: int, value: int) -> None:
        manual = self.follows_the_manual
        self.spend(
            WRITE_CYCLE,
            (address, address, address),
            (value, value, value) if manual else (None, value, None),
            (IDLE, MEMORY_WRITE, IDLE),
        )

    def port_read(self, address: int, value: int) -> None:
        self.spend(
            PORT_READ_CYCLE,
            (address, address, address, address),
            (None, None, None, value),
            (IDLE, IDLE, PORT_READ, IDLE),
        )

    def port_write(self, address: int, value: int) -> None:
        manual = self.follows_the_manual
        self.spend(
            PORT_WRITE_CYCLE,
            (address, address, address, address),
            (value, value, value, value) if manual else (None, None, value, None),
            (IDLE, IDLE, PORT_WRITE, IDLE),
        )

    def acknowledge(self, counter: int, refresh: int, value: int) -> None:
        self.spend(
            ACKNOWLEDGE,
            (counter, counter, counter, counter, refresh, refresh),
            (None, None, None, value, None, None),
            (IDLE, IDLE, IDLE, PORT_REQUEST, IDLE, IDLE),
        )

    def __len__(self) -> int:
        return self.states

    @override
    def __repr__(self) -> str:
        return f"<Bus {self.states} T states, {len(self.log)} recorded, {self.shape}>"
