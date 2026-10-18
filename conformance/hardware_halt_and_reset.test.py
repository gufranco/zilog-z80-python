import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.bench import FACTS, STACK, loaded, spent
from z80 import Cpu, SparseMemory

SHAPES = FACTS["machineCycleShapes"]

RESPONSE = FACTS["interruptResponse"]

HALT = (0x76,)


def halted() -> Any:
    cpu = loaded(HALT)
    cpu.step()
    return cpu


def raised_in(cpu: Any, line: str, states: frozenset[int]) -> None:
    seen = [0]

    def hook() -> None:
        seen[0] += 1
        setattr(cpu, line, seen[0] + 1 in states)

    setattr(cpu, line, 1 in states)
    cpu.on_cycle = hook


def powered(seed: int = 0x5A5A5A5A) -> Any:
    return Cpu("z80", SparseMemory(seed=seed), seed=seed)


def reset_from(first: int, nmi_line: bool) -> Any:
    space = SparseMemory()
    space.write8(first, 0x00)
    cpu = Cpu("z80", space, recording=True)
    cpu.nmi_line = nmi_line
    cpu.reset()
    cpu.registers.sp = STACK
    return cpu


class HaltTest(unittest.TestCase):
    def test_a_halted_step_costs_a_whole_fetch(self) -> None:
        # Arrange
        cpu = halted()

        # Act
        states = cpu.step()

        # Assert
        self.assertEqual(states, FACTS["halt"]["tStatesPerCycle"])

    def test_and_that_is_the_length_of_an_ordinary_one(self) -> None:
        # Arrange
        cpu = halted()

        # Act
        states = cpu.step()

        # Assert
        self.assertEqual(states, spent((0x00,)))

    def test_it_draws_the_pins_of_a_fetch_because_that_is_what_it_is(self) -> None:
        # Arrange
        cpu = halted()

        # Act
        cpu.step()

        # Assert
        self.assertEqual(
            [entry[2] for entry in cpu.bus.log], SHAPES["figureEdges"]["opcodeFetch"]["columns"]
        )

    def test_the_counter_does_not_advance(self) -> None:
        # Arrange
        cpu = halted()
        before = cpu.registers.pc

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.registers.pc, before)

    def test_the_refresh_counter_does(self) -> None:
        # Arrange
        cpu = halted()
        before = cpu.registers.r

        # Act
        cpu.step()

        # Assert
        self.assertNotEqual(cpu.registers.r, before)

    def test_an_accepted_interrupt_leaves_the_halt_state(self) -> None:
        # Arrange
        cpu = halted()
        cpu.registers.iff1, cpu.registers.im = True, 1

        # Act
        cpu.irq(0xFF)

        # Assert
        self.assertEqual(cpu.held(), False)

    def test_and_so_does_the_nonmaskable_line(self) -> None:
        # Arrange
        cpu = halted()

        # Act
        cpu.nmi()

        # Assert
        self.assertEqual(cpu.held(), False)

    def test_a_halted_cycle_is_a_fetch_whose_data_is_ignored(self) -> None:
        # Arrange
        cpu = halted()
        cpu.memory.write8(cpu.registers.pc, 0x3C)
        before = (cpu.registers.pc, cpu.registers.a)

        # Act
        spent_now = cpu.step()

        # Assert
        self.assertEqual(
            (spent_now, [name for _, name in cpu.bus.cycles], (cpu.registers.pc, cpu.registers.a)),
            (FACTS["halt"]["tStatesPerCycle"], ["fetch"], before),
        )

    def test_the_halt_state_repeats_its_fetch_every_cycle(self) -> None:
        # Arrange
        cpu = halted()
        before = cpu.registers.pc
        cycles = 3 * FACTS["halt"]["tStatesPerCycle"]

        # Act
        spent_now = cpu.run_for(cycles)

        # Assert
        self.assertEqual((spent_now, cpu.held(), cpu.registers.pc), (cycles, True, before))

    def test_an_interrupt_sampled_in_the_printed_state_ends_the_halt(self) -> None:
        # Arrange
        cpu = halted()
        cpu.registers.iff1, cpu.registers.im = True, 1
        raised_in(cpu, "irq_line", frozenset({FACTS["halt"]["sampledInState"]}))

        # Act
        cpu.step()

        # Assert
        self.assertEqual((cpu.held(), cpu.registers.pc), (False, RESPONSE["mode1"]["restartsAt"]))


class ResetTest(unittest.TestCase):
    def test_reset_clears_what_the_manual_says_it_clears(self) -> None:
        # Arrange
        cpu = powered()

        # Act
        cpu.reset()

        # Assert
        cleared = {name: getattr(cpu.registers, name) for name in FACTS["reset"]["clears"]}
        self.assertEqual(cleared, dict.fromkeys(FACTS["reset"]["clears"], 0))

    def test_and_leaves_the_interrupt_mode_where_the_manual_says(self) -> None:
        # Arrange
        cpu = powered()
        cpu.registers.im = 2

        # Act
        cpu.reset()

        # Assert
        self.assertEqual(cpu.registers.im, FACTS["reset"]["interruptMode"])

    def test_and_clears_the_interrupt_enable(self) -> None:
        # Arrange
        cpu = powered()
        cpu.registers.iff1 = cpu.registers.iff2 = True

        # Act
        cpu.reset()

        # Assert
        self.assertEqual((cpu.registers.iff1, cpu.registers.iff2), (False, False))

    def test_it_does_not_clear_a_register_the_manual_does_not_name(self) -> None:
        # Arrange
        cpu = powered(seed=7)

        # Act
        cpu.reset()

        # Assert
        held = (cpu.registers.a, cpu.registers.bc, cpu.registers.de, cpu.registers.hl)
        self.assertNotEqual(held, (0, 0, 0, 0))


class PrintedFactTest(unittest.TestCase):
    def test_a_reset_spends_the_pin_time_and_the_two_states_after_it(self) -> None:
        # Arrange
        cpu = powered()
        before = cpu.cycles

        # Act
        cpu.reset()

        # Assert
        self.assertEqual(
            cpu.cycles - before,
            FACTS["reset"]["minimumClockCycles"] + FACTS["reset"]["afterThePinReleases"]["states"],
        )

    def test_the_first_fetch_after_a_reset_is_from_the_printed_address(self) -> None:
        # Arrange
        cpu = reset_from(0x0000, nmi_line=False)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.bus.log[0][0], FACTS["reset"]["afterThePinReleases"]["firstFetchFrom"])

    def test_a_reset_clears_the_interrupt_enable_as_the_manual_says(self) -> None:
        # Arrange
        cpu = powered()
        cpu.registers.iff1 = cpu.registers.iff2 = True
        cleared = FACTS["reset"]["clearsInterruptEnable"]

        # Act
        cpu.reset()

        # Assert
        self.assertEqual((cpu.registers.iff1, cpu.registers.iff2), (not cleared, not cleared))

    def test_a_nonmaskable_line_held_through_reset_is_not_detected(self) -> None:
        # Arrange
        printed = FACTS["nonmaskableDuringReset"]
        start = FACTS["reset"]["afterThePinReleases"]["firstFetchFrom"]
        cpu = reset_from(start, nmi_line=True)

        # Act
        cpu.step()

        # Assert
        self.assertEqual((cpu.registers.pc, cpu.registers.sp), (start + 1, STACK), printed["quote"])

    def test_a_nonmaskable_line_lowered_after_reset_is_processed(self) -> None:
        # Arrange
        printed = FACTS["nonmaskableDuringReset"]
        cpu = reset_from(FACTS["reset"]["afterThePinReleases"]["firstFetchFrom"], nmi_line=False)
        cpu.nmi_line = True

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.registers.pc, FACTS["interruptModes"]["nmiVector"], printed["quote"])


if __name__ == "__main__":
    unittest.main()
