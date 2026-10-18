from __future__ import annotations

import functools
import hashlib
import sys
import threading
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import z80  # noqa: E402


class ClockTest(unittest.TestCase):
    def part(self) -> Any:
        self.memory = z80.Memory(image=bytes([0x3E, 0x42, 0x00, 0x00, 0x00, 0x00]))
        cpu = z80.Cpu("z80", self.memory, recording=True)
        cpu.reset()
        cpu.registers.pc = 0x0000
        return cpu

    def test_a_tick_spends_exactly_one_cycle(self) -> None:
        cpu = self.part()
        before = cpu.cycles

        with z80.Clock(cpu) as clock:
            clock.tick()

        self.assertEqual((clock.cycles, cpu.cycles - before), (1, 1))

    def test_a_budget_stops_between_cycles_rather_than_overshooting(self) -> None:
        cpu = self.part()

        with z80.Clock(cpu) as clock:
            spent = clock.run_for(7)

        self.assertEqual(spent, 7)

    def test_the_part_is_suspended_part_way_through_an_instruction(self) -> None:
        cpu = self.part()

        with z80.Clock(cpu) as clock:
            clock.tick()
            self.memory.write8(0x0001, 0x99)
            clock.run_for(6)

        self.assertIn(0x99, [value for _, value, _ in cpu.bus.log])

    def test_a_halted_part_keeps_costing_cycles_under_a_clock(self) -> None:
        space = z80.Memory(image=bytes([0x76]))
        cpu = z80.Cpu("z80", space)
        cpu.reset()
        cpu.registers.pc = 0x0000

        with z80.Clock(cpu) as clock:
            clock.run_for(12)

        self.assertEqual((clock.cycles, cpu.held()), (12, True))

    def test_a_clock_can_be_iterated(self) -> None:
        cpu = self.part()

        with z80.Clock(cpu) as clock:
            spent = [total for total, _ in zip(clock, range(4), strict=False)]

        self.assertEqual(spent, [1, 2, 3, 4])

    def test_iteration_ends_when_the_clock_is_closed(self) -> None:
        clock = z80.Clock(self.part())
        clock.close()

        self.assertEqual(list(clock), [])

    def test_a_closed_clock_refuses_to_tick(self) -> None:
        clock = z80.Clock(self.part())
        clock.close()

        with self.assertRaises(z80.ClockClosed):
            clock.tick()

    def test_closing_twice_is_not_an_error(self) -> None:
        clock = z80.Clock(self.part())
        clock.close()

        clock.close()

        self.assertTrue(clock.closed)

    def test_closing_gives_the_part_its_hook_back(self) -> None:
        cpu = self.part()
        watched: list[int] = []
        cpu.on_cycle = lambda: watched.append(1)

        with z80.Clock(cpu) as clock:
            clock.tick()
        cpu.step()

        self.assertEqual((clock.cycles, bool(watched)), (1, True))

    def test_a_failure_inside_the_part_reaches_the_driver(self) -> None:
        cpu = self.part()
        clock = z80.Clock(cpu)
        self.addCleanup(clock.close)

        def explode() -> None:
            raise RuntimeError("a device said no")

        clock.tick()
        cpu.on_cycle = explode

        with self.assertRaises(RuntimeError):
            clock.run_for(8)

    def test_and_the_clock_refuses_to_go_on_afterwards(self) -> None:
        cpu = self.part()
        clock = z80.Clock(cpu)
        self.addCleanup(clock.close)

        def explode() -> None:
            raise RuntimeError("a device said no")

        clock.tick()
        cpu.on_cycle = explode
        with self.assertRaises(RuntimeError):
            clock.run_for(8)

        with self.assertRaises(z80.ClockClosed):
            clock.tick()


PROGRAM = bytes([0x3E, 0x42, 0x47, 0x21, 0x34, 0x12, 0x77, 0x23, 0x00, 0x18, 0xF5])


def a_part() -> Any:
    cpu = z80.Cpu("z80", z80.Memory(image=PROGRAM, fill=0x00))
    return cpu.reset()


def where(cpu: Any) -> tuple[int, int, int, int, int]:
    held = cpu.registers
    return cpu.steps, cpu.cycles, held.pc, held.a, held.hl


class ClosedAtABoundaryTest(unittest.TestCase):
    def test_a_closed_clock_leaves_the_part_where_step_leaves_it(self) -> None:
        # Arrange
        stepped, ticked = a_part(), a_part()
        states = [stepped.step() for _ in range(8)]

        # Act
        with z80.Clock(ticked) as clock:
            clock.run_for(sum(states))

        # Assert
        self.assertEqual(where(ticked), where(stepped))

    def test_and_where_run_for_leaves_it(self) -> None:
        # Arrange
        budgeted, ticked = a_part(), a_part()
        spent = budgeted.run_for(21)

        # Act
        with z80.Clock(ticked) as clock:
            clock.run_for(spent)

        # Assert
        self.assertEqual(where(ticked), where(budgeted))

    def test_a_clock_closed_inside_an_instruction_spends_nothing_more(self) -> None:
        # Arrange
        cpu = a_part()
        cycles, accumulator = cpu.cycles, cpu.registers.a

        # Act
        with z80.Clock(cpu) as clock:
            clock.run_for(5)

        # Assert
        self.assertEqual(
            (cpu.cycles - cycles, cpu.bus.states, cpu.registers.a), (5, 5, accumulator)
        )


def ticked_open(budget: int) -> tuple[int, int, int, int, int]:
    cpu = a_part()
    clock = z80.Clock(cpu)
    try:
        clock.run_for(budget)
        return where(cpu)
    finally:
        clock.close()


class OpenAtABoundaryTest(unittest.TestCase):
    def test_an_open_clock_shows_the_part_where_step_leaves_it(self) -> None:
        # Arrange
        stepped = a_part()
        states = [stepped.step() for _ in range(8)]

        # Act
        found = ticked_open(sum(states))

        # Assert
        self.assertEqual(found, where(stepped))

    def test_including_the_load_its_first_instruction_ends_on(self) -> None:
        # Arrange
        stepped = a_part()
        states = stepped.step()

        # Act
        found = ticked_open(states)

        # Assert
        self.assertEqual(found, where(stepped))


class Watched:
    __slots__ = ("base", "inner", "parts", "paused", "seen")

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.parts: list[Any] = []
        self.paused = 0
        self.base = 0
        self.seen: list[tuple[int, int]] = []

    def noted(self, address: int) -> int:
        for part in self.parts:
            self.seen.append((self.paused, self.base + part.bus.states))
        return address

    def read8(self, address: int) -> int:
        return int(self.inner.read8(self.noted(address)))

    def write8(self, address: int, value: int) -> None:
        self.inner.write8(self.noted(address), value)

    def pause(self) -> None:
        self.paused += 1


def watched_run(instructions: int) -> list[tuple[int, int]]:
    memory = Watched(z80.Memory(image=PROGRAM, fill=0x00))
    cpu = z80.Cpu("z80", memory)
    cpu.reset()
    memory.parts.append(cpu)
    cpu.on_cycle = memory.pause
    for _ in range(instructions):
        memory.base = memory.paused
        cpu.step()
    return memory.seen


class EveryAccessStaysOnItsOwnStateTest(unittest.TestCase):
    def test_no_access_is_made_before_the_state_ahead_of_it_has_paused(self) -> None:
        # Arrange
        instructions = 8

        # Act
        seen = watched_run(instructions)

        # Assert
        self.assertEqual([paused for paused, _ in seen], [due for _, due in seen])


PATIENCE_SECONDS = 10.0

LAST_TWO_STATES = 2

REGISTERS = ("a", "f", "bc", "de", "hl", "pc", "sp", "i", "r", "iff1", "iff2", "im")


def within(call: Callable[[], Any]) -> tuple[str, Any]:
    outcome: list[tuple[str, Any]] = []

    def attempt() -> None:
        outcome.append(("returned", call()))

    worker = threading.Thread(target=attempt, daemon=True)
    worker.start()
    worker.join(PATIENCE_SECONDS)
    return outcome[0] if outcome else ("still running", None)


def refusal(line: str) -> str:
    return (
        f"{line}() was called inside an instruction; tick the clock to the instruction "
        f"boundary, or set {line}_line, which the part samples when the instruction completes"
    )


def an_interruptible_part() -> Any:
    cpu = a_part()
    cpu.registers.iff1 = True
    cpu.registers.iff2 = True
    cpu.registers.im = 1
    return cpu


def observed(cpu: Any) -> tuple[Any, ...]:
    held = cpu.registers
    return (
        tuple(getattr(held, name, None) for name in REGISTERS),
        cpu.steps,
        cpu.cycles,
        cpu.held(),
        hashlib.sha256(bytes(cpu.memory.read8(address) for address in range(0x10000))).hexdigest(),
    )


def attempted(call: Callable[[], Any]) -> tuple[str, str]:
    try:
        call()
    except z80.InsideInstruction as refused:
        return "refused", str(refused)
    return "taken", ""


def stepped_through(instructions: int) -> tuple[Any, ...]:
    cpu = an_interruptible_part()
    for _ in range(instructions):
        cpu.step()
    return observed(cpu)


def first_instruction_states() -> int:
    return int(an_interruptible_part().step())


def offered_between_steps(line: str) -> tuple[Any, ...]:
    cpu = an_interruptible_part()
    cpu.step()
    outcome = attempted(getattr(cpu, line))
    cpu.step()
    return outcome, observed(cpu)


def offered_to_a_paused_clock(cpu: Any, line: str, ticks: int, afterwards: int) -> Any:
    clock = z80.Clock(cpu)
    try:
        clock.run_for(ticks)
        outcome = attempted(getattr(cpu, line))
        clock.run_for(afterwards)
        return outcome, observed(cpu)
    finally:
        clock.close()


def offered_at_a_boundary(line: str) -> Any:
    reference = an_interruptible_part()
    reference.step()
    getattr(reference, line)()
    afterwards = reference.step()
    cpu = an_interruptible_part()
    return offered_to_a_paused_clock(cpu, line, first_instruction_states(), afterwards)


def offered_inside_an_instruction(line: str) -> Any:
    first = first_instruction_states()
    cpu = an_interruptible_part()
    reference = an_interruptible_part()
    reference.step()
    rest = reference.step() - 1
    return offered_to_a_paused_clock(cpu, line, first + 1, rest)


def entered_through_the_line() -> tuple[int, tuple[Any, ...]]:
    cpu = an_interruptible_part()
    cpu.irq_line = True
    before = cpu.cycles
    cpu.step()
    return cpu.cycles - before, observed(cpu)


def offered_inside_an_entry_the_line_began() -> Any:
    spent, _ = entered_through_the_line()
    cpu = an_interruptible_part()
    cpu.irq_line = True
    return offered_to_a_paused_clock(cpu, "irq", spent - LAST_TWO_STATES, LAST_TWO_STATES)


class AnInterruptOfferedToAPausedClockTest(unittest.TestCase):
    def test_an_irq_at_an_instruction_boundary_is_taken_as_between_steps(self) -> None:
        # Arrange
        expected = offered_between_steps("irq")

        # Act
        found = within(functools.partial(offered_at_a_boundary, "irq"))

        # Assert
        self.assertEqual(found, ("returned", expected))

    def test_an_irq_inside_an_instruction_is_refused_and_leaves_no_trace(self) -> None:
        # Arrange
        expected = (("refused", refusal("irq")), stepped_through(2))

        # Act
        found = within(functools.partial(offered_inside_an_instruction, "irq"))

        # Assert
        self.assertEqual(found, ("returned", expected))

    def test_an_nmi_at_an_instruction_boundary_is_taken_as_between_steps(self) -> None:
        # Arrange
        expected = offered_between_steps("nmi")

        # Act
        found = within(functools.partial(offered_at_a_boundary, "nmi"))

        # Assert
        self.assertEqual(found, ("returned", expected))

    def test_an_nmi_inside_an_instruction_is_refused_and_leaves_no_trace(self) -> None:
        # Arrange
        expected = (("refused", refusal("nmi")), stepped_through(2))

        # Act
        found = within(functools.partial(offered_inside_an_instruction, "nmi"))

        # Assert
        self.assertEqual(found, ("returned", expected))

    def test_an_irq_inside_an_entry_the_line_began_is_refused_and_leaves_no_trace(self) -> None:
        # Arrange
        expected = (("refused", refusal("irq")), entered_through_the_line()[1])

        # Act
        found = within(offered_inside_an_entry_the_line_began)

        # Assert
        self.assertEqual(found, ("returned", expected))


if __name__ == "__main__":
    unittest.main()
