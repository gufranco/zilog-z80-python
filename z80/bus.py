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

Edges, and the rule that turns them into columns
------------------------------------------------

The pin columns below are not written out by hand. ``EDGES`` holds where each
control pin goes active and inactive, in T states from the start of the machine
cycle, measured off Figures 5, 6, 7 and 9 of the pinned document rendered at 200
dpi and snapped to the clock, which moves in half T states. Everything else is
derived from that table, so a column and the measurement behind it cannot drift
apart.

A four character string per T state cannot express those edges directly, because
they land between states. The rule here is to read the pins at the clock edge
that ends each T state: a pin belongs to state ``n`` when it went active before
that instant and had not yet gone inactive. That names a real instant, and it is
insensitive to the slew every edge in a drawing carries, which a rule asking
whether a pin was asserted at any point during a state is not.

Reading them at the other obvious instant, or over the whole state, gives a
different answer on the state each strobe is released in, and
``conformance/divergences.json`` records what that reading gives and why this one
was chosen instead. The choice is a modelling decision rather than a fact about
the part, which is why it is named rather than assumed.

``RECORDING`` is not derived from the edges at all. It is one strobe per
transfer, which is what the pinned corpus contains and what its generator
describes as a deliberate simplification that "simplifies emulator development
and speeds up execution at no cost to accuracy". ``conformance/cycles.py``
selects it so that the recording still checks this core cycle for cycle.
"""

from __future__ import annotations

from typing import override

READ = "r"

WRITE = "w"

MEMORY = "m"

PORT = "i"

PIN_ORDER = (READ, WRITE, MEMORY, PORT)
"""The order the corpus writes the four control pins in."""

IDLE = "----"
"""No control pin asserted, which is what an internal cycle looks like."""

MEMORY_READ = "r-m-"

MEMORY_WRITE = "-wm-"

MEMORY_REQUEST = "--m-"
"""Memory request without read, which is what a refresh state asserts."""

PORT_READ = "r--i"

PORT_WRITE = "-w-i"

PORT_REQUEST = "---i"
"""Port request without read, which is what an interrupt acknowledge asserts."""

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
"""Each machine cycle, as its length and the interval each pin is active over.

Measured off the manual's figures and snapped to the clock. The fetch carries two
memory request entries because it asserts it twice, once for the opcode and once
for the refresh, with the read strobe absent from the second: "To prevent data
from different memory segments from being gated onto the data bus, an RD signal
is not generated during this refresh period."
"""


def columns(cycle: str) -> tuple[str, ...]:
    """The pins of one machine cycle, read at the clock edge ending each state."""
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
"""Every machine cycle's pins, derived once rather than on each cycle spent.

The derivation above is what makes the columns a consequence of the measurements.
Running it per machine cycle would make the default shape pay for that on every
instruction of every program, which is the one shape a caller gets without asking.
"""

FETCH_STATES = EDGES[FETCH][0]

MEMORY_STATES = EDGES[READ_CYCLE][0]

PORT_STATES = EDGES[PORT_READ_CYCLE][0]

ACKNOWLEDGE_STATES = EDGES[ACKNOWLEDGE][0]

ADDRESS_MASK = 0xFFFF

MANUAL = "manual"
"""The manual's measured edges, read at the clock edge ending each T state."""

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

    __slots__ = ("address", "cycles", "log", "recording", "shape", "states")

    def __init__(self, recording: bool = False, shape: str = MANUAL) -> None:
        if shape not in SHAPES:
            raise UnknownShape(f"{shape} is not a pin shape; there are {', '.join(SHAPES)}")
        self.recording = recording
        self.shape = shape
        self.log: list[tuple[int | None, int | None, str]] = []
        self.cycles: list[tuple[int, str]] = []
        self.states = 0
        self.address = 0

    @property
    def follows_the_manual(self) -> bool:
        """Whether this bus is drawing the edges the manual's figures carry."""
        return self.shape == MANUAL

    def clear(self) -> None:
        """Start a fresh instruction, keeping the address the last one left."""
        self.log.clear()
        self.cycles.clear()
        self.states = 0

    def mark(self, address: int | None, value: int | None, pins: str) -> None:
        """One T state, which is the only way anything reaches the log."""
        self.states += 1
        if address is not None:
            self.address = address & ADDRESS_MASK
        if self.recording:
            self.log.append((None if address is None else address & ADDRESS_MASK, value, pins))

    def spend(
        self,
        cycle: str,
        addresses: tuple[int, ...],
        values: tuple[int | None, ...],
        recorded: tuple[str, ...],
    ) -> None:
        """One machine cycle, in whichever shape this bus was asked for.

        The addresses are the same either way. The pins are not, because they
        depend on how a waveform becomes a column, and on a cycle that drives the
        data bus the values are not either: the recording shows the data only
        while its strobe is down, where the figures show it held across the whole
        cycle. That is why the caller passes the values rather than this deriving
        them, and why the two write methods are the only ones that pass two sets.

        A recording bus also notes where each machine cycle began and which kind
        it was, so that a reader of the transcript does not have to infer the
        boundaries from the pins. Inferring them works until two cycle kinds draw
        the same first columns, and then it stops working silently.
        """
        if self.recording:
            self.cycles.append((self.states, cycle))
        pins = COLUMNS[cycle] if self.follows_the_manual else recorded
        for address, value, held in zip(addresses, values, pins, strict=True):
            self.mark(address, value, held)

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
        self.spend(
            FETCH,
            (counter, counter, refresh, refresh),
            (None, None, value, None),
            (IDLE, MEMORY_READ, IDLE, IDLE),
        )

    def read(self, address: int, value: int) -> None:
        """A read outside a fetch, whose strobes outlast a fetch's by half a state.

        The manual's prose says memory request and read "are used the same way as
        in a fetch cycle", but Figure 6 does not draw them that way: they are
        released on the falling clock edge of T3 rather than on the rising edge,
        because there is no refresh address waiting for the bus. Prose elsewhere
        in the same document agrees with the figure and not with the summary.
        """
        self.spend(
            READ_CYCLE,
            (address, address, address),
            (None, None, value),
            (IDLE, MEMORY_READ, IDLE),
        )

    def write(self, address: int, value: int) -> None:
        """A write, whose value is on the bus before a read's has arrived.

        On a read the part is waiting for memory and latches at the end. On a
        write it is driving, so the data is already out when the write strobe
        falls, and Figure 6 holds it there across the whole cycle. A model that
        treated the two symmetrically would disagree on every store.

        The manual separates the two strobes rather than running them together:
        memory request goes active "when the address bus is stable", half a clock
        into T1, and the write strobe only once "the data on the data bus is
        stable", a full T state later.
        """
        manual = self.follows_the_manual
        self.spend(
            WRITE_CYCLE,
            (address, address, address),
            (value, value, value) if manual else (None, value, None),
            (IDLE, MEMORY_WRITE, IDLE),
        )

    def port_read(self, address: int, value: int) -> None:
        """A port read, whose strobes start a whole T state later than memory's.

        Figure 7 puts the port request and read edges on the rising edge of T2
        rather than half a clock into T1, so a port cycle leaves its first state
        bare where a memory cycle does not. The automatically inserted wait state
        sits inside the strobe rather than before it.
        """
        self.spend(
            PORT_READ_CYCLE,
            (address, address, address, address),
            (None, None, None, value),
            (IDLE, IDLE, PORT_READ, IDLE),
        )

    def port_write(self, address: int, value: int) -> None:
        """A port write, which drives its data from a state before its strobe.

        Figure 7 puts the data on the bus half a clock into T1 and holds it past
        the end of T3, so every state of the cycle carries it, while the strobe
        covers only the last three. The recording shows the data on the strobed
        state alone, which is the same simplification it makes for a memory write.
        """
        manual = self.follows_the_manual
        self.spend(
            PORT_WRITE_CYCLE,
            (address, address, address, address),
            (value, value, value, value) if manual else (None, None, value, None),
            (IDLE, IDLE, PORT_WRITE, IDLE),
        )

    def acknowledge(self, counter: int, refresh: int, value: int) -> None:
        """The special fetch that answers an interrupt.

        It is an M1 cycle with the port request asserted "instead of the normal
        MREQ", and with two wait states added so a daisy chain has time to settle.
        Figure 9 puts the port request half a clock into the first wait state and
        releases it on the rising edge of T3. Refresh follows as it does in an
        ordinary fetch, which is why the last states look the same.

        No read strobe appears anywhere in the figure. A device answering an
        acknowledge is told by the port request and the machine cycle pin
        together, not by a read.

        These are the six states the figure draws. The cycle the manual costs is
        seven, because six would make the printed mode 2 total eighteen against a
        printed nineteen, so the M1 underneath the two waits is the five state
        kind a restart already has. The figure stops before drawing that state and
        never says where in the cycle it falls, so it is spent by the response,
        which is where a restart spends its own.
        """
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
