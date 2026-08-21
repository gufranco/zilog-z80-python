"""What the part does with its pins, one T state at a time.

A core that spends the right number of cycles doing the wrong thing passes every
count and every state comparison. What makes a cycle claim checkable is the
sequence: the address, the value, which of the four control pins are asserted,
in order. This module is where that sequence is produced, and it is the only
place in the package that knows the shape of a machine cycle.

The shapes come from the Timing chapter of Zilog's own user manual, pinned in
``conformance/hardware.json``:

- An opcode fetch is four T states. The program counter is on the address bus
  for the first two, and the refresh address for the last two, because "During
  T3 and T4, the lower seven bits of the address bus contain a memory refresh
  address and the RFSH signal becomes active".
- A memory read or write other than an opcode fetch is three, because those
  cycles "are generally three clock periods long unless wait states are
  requested by memory through the WAIT signal".
- An input or output cycle is four, because "During I/O operations, a single
  wait state is automatically inserted". That wait is not requested by the
  device and cannot be declined, which is why an I/O access costs one more T
  state than a memory access.

An internal cycle drives no control pin and holds whatever address was last on
the bus, rather than inventing one. A model that drove a plausible address
through a cycle the part spends thinking would be reporting a bus transaction
that never happened.

Two details of the pin encoding belong to the recording rather than to Zilog,
and ``conformance/divergences.json`` records both. The recording asserts read
and memory-request for a single T state where the manual has them span two, and
it puts the refresh value on the address pins during a fetch. Both are choices
its generator documents.
"""

from __future__ import annotations

from typing import override

IDLE = "----"
"""No control pin asserted, which is what an internal cycle looks like."""

MEMORY_READ = "r-m-"

MEMORY_WRITE = "-wm-"

PORT_READ = "r--i"

PORT_WRITE = "-w-i"

FETCH_STATES = 4

MEMORY_STATES = 3

PORT_STATES = 4

ADDRESS_MASK = 0xFFFF


class Bus:
    """The T states an instruction spends, and optionally what was on the pins.

    Counting is always on, because a cycle count nobody can read is not a claim.
    Recording is not, because holding a tuple per T state across a suite of a
    million cases costs more than the comparison it feeds, and most callers want
    only the count.
    """

    __slots__ = ("address", "log", "recording", "states")

    def __init__(self, recording: bool = False) -> None:
        self.recording = recording
        self.log: list[tuple[int | None, int | None, str]] = []
        self.states = 0
        self.address = 0

    def clear(self) -> None:
        """Start a fresh instruction, keeping the address the last one left."""
        self.log.clear()
        self.states = 0

    def mark(self, address: int | None, value: int | None, pins: str) -> None:
        """One T state, which is the only way anything reaches the log."""
        self.states += 1
        if address is not None:
            self.address = address & ADDRESS_MASK
        if self.recording:
            self.log.append((None if address is None else address & ADDRESS_MASK, value, pins))

    def idle(self, count: int = 1) -> None:
        """Internal cycles, holding the address the last access left on the bus."""
        for _ in range(count):
            self.mark(self.address, None, IDLE)

    def fetch(self, counter: int, refresh: int, value: int) -> None:
        """An opcode fetch: the counter for two T states, then the refresh address.

        The refresh address is the interrupt vector register above the refresh
        counter as it stood when the fetch began, before the increment the fetch
        performs. Reading it after the increment is wrong by one on every
        instruction and by more on a prefixed one.
        """
        self.mark(counter, None, IDLE)
        self.mark(counter, None, MEMORY_READ)
        self.mark(refresh, value, IDLE)
        self.mark(refresh, None, IDLE)

    def read(self, address: int, value: int) -> None:
        self.mark(address, None, IDLE)
        self.mark(address, None, MEMORY_READ)
        self.mark(address, value, IDLE)

    def write(self, address: int, value: int) -> None:
        """A write, whose value appears a T state earlier than a read's.

        On a read the part is waiting for memory and latches at the end. On a
        write it is driving, so the data is already out when the write strobe
        falls. A model that treated the two symmetrically would disagree on the
        middle T state of every store.
        """
        self.mark(address, None, IDLE)
        self.mark(address, value, MEMORY_WRITE)
        self.mark(address, None, IDLE)

    def port_read(self, address: int, value: int) -> None:
        self.mark(address, None, IDLE)
        self.mark(address, None, IDLE)
        self.mark(address, None, PORT_READ)
        self.mark(address, value, IDLE)

    def port_write(self, address: int, value: int) -> None:
        self.mark(address, None, IDLE)
        self.mark(address, None, IDLE)
        self.mark(address, value, PORT_WRITE)
        self.mark(address, None, IDLE)

    def __len__(self) -> int:
        return self.states

    @override
    def __repr__(self) -> str:
        return f"<Bus {self.states} T states, {len(self.log)} recorded>"
