"""What the part does with its pins, one T state at a time.

A core that spends the right number of cycles doing the wrong thing passes every
count and every state comparison. What makes a cycle claim checkable is the
sequence: the address, the value, which of the four control pins are asserted,
in order. This module is where that sequence is produced, and it is the only
place in the package that knows the shape of a machine cycle.

The lengths come from the Timing chapter of Zilog's own user manual, pinned in
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
- An interrupt acknowledge draws six, because it is a special M1 cycle to which
  "Two wait states are automatically added". The manual's own response totals
  make the cycle seven, so a five state M1 sits under those two waits, and the
  state the figure does not draw is spent by the response rather than here, in
  the same place a restart already spends the fifth state of its own M1.

An internal cycle drives no control pin and holds whatever address was last on
the bus, rather than inventing one. A model that drove a plausible address
through a cycle the part spends thinking would be reporting a bus transaction
that never happened.

Why there are two shapes rather than one
----------------------------------------

A four character string per T state cannot express what the manual draws. Every
edge in Figures 5, 6, 7 and 9 falls on a clock edge, which is a half T state
boundary, so a per-state model has to choose a rule for turning a waveform into
a column. There is no rule the manual states, and the choice is a modelling
decision rather than a fact about the part. Pretending otherwise is how a
convention becomes a citation.

``MANUAL`` is coverage: a pin appears in every T state the figure shows it
asserted for any part of. The edges were measured off the figures as rendered
from the pinned document, and they are recorded in ``conformance/hardware.json``
under ``figureEdges`` so a reader can apply a different rule without going back
to the PDF.

``RECORDING`` is one strobe per transfer, which is what the pinned corpus
contains and what its generator describes as a deliberate simplification that
"simplifies emulator development and speeds up execution at no cost to
accuracy". ``conformance/cycles.py`` selects it so that the recording still
checks this core cycle for cycle.

Keeping both here, rather than transforming one into the other after the fact,
means the difference is stated once, in the module that owns it, instead of
being spread across a runner that would have to guess which T state was which.
"""

from __future__ import annotations

from typing import override

IDLE = "----"
"""No control pin asserted, which is what an internal cycle looks like."""

MEMORY_READ = "r-m-"

MEMORY_WRITE = "-wm-"

MEMORY_REQUEST = "--m-"
"""Memory request without read, which is what the refresh states assert."""

PORT_READ = "r--i"

PORT_WRITE = "-w-i"

PORT_REQUEST = "---i"
"""Port request without read, which is what an interrupt acknowledge asserts."""

FETCH_STATES = 4

MEMORY_STATES = 3

PORT_STATES = 4

ACKNOWLEDGE_STATES = 6

ADDRESS_MASK = 0xFFFF

MANUAL = "manual"
"""Coverage of the manual's figures, a pin in every state it is asserted in."""

RECORDING = "recording"
"""One strobe per transfer, which is what the pinned corpus contains."""

SHAPES = (MANUAL, RECORDING)


class UnknownShape(Exception):
    """A bus asked for a pin shape that is neither documented nor recorded."""


class Bus:
    """The T states an instruction spends, and optionally what was on the pins.

    Counting is always on, because a cycle count nobody can read is not a claim.
    Recording is not, because holding a tuple per T state across a suite of a
    million cases costs more than the comparison it feeds, and most callers want
    only the count.
    """

    __slots__ = ("address", "log", "recording", "shape", "states")

    def __init__(self, recording: bool = False, shape: str = MANUAL) -> None:
        if shape not in SHAPES:
            raise UnknownShape(f"{shape} is not a pin shape; there are {', '.join(SHAPES)}")
        self.recording = recording
        self.shape = shape
        self.log: list[tuple[int | None, int | None, str]] = []
        self.states = 0
        self.address = 0

    @property
    def follows_the_manual(self) -> bool:
        """Whether this bus is drawing a pin in every state it is asserted in."""
        return self.shape == MANUAL

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

        Read and memory request fall together half a clock into T1 and are
        released on the rising edge of T3, so under coverage they hold T1 and T2.
        Memory request falls a second time for the refresh, half a clock into T3
        and released half a clock into T4, so those two states carry a request
        with no read. That is the manual's own reason: "To prevent data from
        different memory segments from being gated onto the data bus, an RD
        signal is not generated during this refresh period."
        """
        if self.follows_the_manual:
            self.mark(counter, None, MEMORY_READ)
            self.mark(counter, None, MEMORY_READ)
            self.mark(refresh, value, MEMORY_REQUEST)
            self.mark(refresh, None, MEMORY_REQUEST)
            return
        self.mark(counter, None, IDLE)
        self.mark(counter, None, MEMORY_READ)
        self.mark(refresh, value, IDLE)
        self.mark(refresh, None, IDLE)

    def read(self, address: int, value: int) -> None:
        """A read outside a fetch, whose strobes outlast a fetch's by half a state.

        The manual's prose says memory request and read "are used the same way as
        in a fetch cycle", but Figure 6 does not draw them that way: they are
        released half a clock into T3 rather than on its rising edge, because
        there is no refresh address waiting for the bus. Under coverage that puts
        a strobe on all three states.
        """
        if self.follows_the_manual:
            self.mark(address, None, MEMORY_READ)
            self.mark(address, None, MEMORY_READ)
            self.mark(address, value, MEMORY_READ)
            return
        self.mark(address, None, IDLE)
        self.mark(address, None, MEMORY_READ)
        self.mark(address, value, IDLE)

    def write(self, address: int, value: int) -> None:
        """A write, whose value appears a T state earlier than a read's.

        On a read the part is waiting for memory and latches at the end. On a
        write it is driving, so the data is already out when the write strobe
        falls. A model that treated the two symmetrically would disagree on the
        middle T state of every store.

        The manual separates the two strobes rather than running them together:
        memory request goes active "when the address bus is stable", half a clock
        into T1, and the write strobe only once "the data on the data bus is
        stable", a full T state later. Both are released half a clock into T3,
        which is the manual saying the write "goes inactive one-half T state
        before the address and data bus contents are changed".
        """
        if self.follows_the_manual:
            self.mark(address, value, MEMORY_REQUEST)
            self.mark(address, value, MEMORY_WRITE)
            self.mark(address, value, MEMORY_WRITE)
            return
        self.mark(address, None, IDLE)
        self.mark(address, value, MEMORY_WRITE)
        self.mark(address, None, IDLE)

    def port_read(self, address: int, value: int) -> None:
        """A port read, whose strobes start a whole T state later than memory's.

        Figure 7 puts the port request and read edges on the rising edge of T2
        rather than half a clock into T1, and releases them half a clock into T3.
        Under coverage that leaves T1 bare and strobes the other three, which is
        the automatic wait state sitting inside the strobe rather than before it.
        """
        if self.follows_the_manual:
            self.mark(address, None, IDLE)
            self.mark(address, None, PORT_READ)
            self.mark(address, None, PORT_READ)
            self.mark(address, value, PORT_READ)
            return
        self.mark(address, None, IDLE)
        self.mark(address, None, IDLE)
        self.mark(address, None, PORT_READ)
        self.mark(address, value, IDLE)

    def port_write(self, address: int, value: int) -> None:
        if self.follows_the_manual:
            self.mark(address, value, IDLE)
            self.mark(address, value, PORT_WRITE)
            self.mark(address, value, PORT_WRITE)
            self.mark(address, value, PORT_WRITE)
            return
        self.mark(address, None, IDLE)
        self.mark(address, None, IDLE)
        self.mark(address, value, PORT_WRITE)
        self.mark(address, None, IDLE)

    def acknowledge(self, counter: int, refresh: int, value: int) -> None:
        """The special fetch that answers an interrupt, seven T states long.

        It is an M1 cycle with the port request asserted "instead of the normal
        MREQ", and with two wait states added so a daisy chain has time to settle.
        Figure 9 puts the port request half a clock into the first wait state and
        releases it on the rising edge of T3, so under coverage it covers the two
        wait states and nothing else. Refresh follows exactly as it does in an
        ordinary fetch, which is why the next two states look the same.

        No read strobe appears anywhere in the figure. A device answering an
        acknowledge is told by the port request and the machine cycle pin
        together, not by a read.

        These are the six states Figure 9 draws. The cycle the manual costs is
        seven, because six would make the printed mode 2 total eighteen against a
        printed nineteen, so the M1 underneath the two waits is the five state
        kind a restart already has. The figure stops before drawing that state and
        never says where in the cycle it falls, so it is spent by the response,
        which is where a restart spends its own.
        """
        if self.follows_the_manual:
            self.mark(counter, None, IDLE)
            self.mark(counter, None, IDLE)
            self.mark(counter, None, PORT_REQUEST)
            self.mark(counter, value, PORT_REQUEST)
            self.mark(refresh, None, MEMORY_REQUEST)
            self.mark(refresh, None, MEMORY_REQUEST)
            return
        self.mark(counter, None, IDLE)
        self.mark(counter, None, IDLE)
        self.mark(counter, None, IDLE)
        self.mark(counter, value, PORT_REQUEST)
        self.mark(refresh, None, IDLE)
        self.mark(refresh, None, IDLE)

    def __len__(self) -> int:
        return self.states

    @override
    def __repr__(self) -> str:
        return f"<Bus {self.states} T states, {len(self.log)} recorded, {self.shape}>"
