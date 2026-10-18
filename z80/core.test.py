import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.bench import FLAG, RECORD
from z80 import Cpu, Ports, RunLimit, SparseMemory

RESET = RECORD["facts"]["reset"]

RESET_COST = RESET["minimumClockCycles"] + RESET["afterThePinReleases"]["states"]


def machine(program: list[int], at: int = 0x8000, **fields: Any) -> tuple[Any, SparseMemory]:
    space = SparseMemory(seed=1)
    for offset, value in enumerate(program):
        space.write8(at + offset, value)
    cpu = Cpu("z80", space, ports=Ports(seed=1))
    cpu.registers.pc = at
    cpu.registers.sp = 0xFFFE
    cpu.registers.af = 0x0000
    cpu.registers.bc = cpu.registers.de = cpu.registers.hl = 0x0000
    cpu.registers.ix = cpu.registers.iy = 0x0000
    cpu.registers.i = cpu.registers.r = 0x00
    for name, value in fields.items():
        setattr(cpu.registers, name, value)
    return cpu, space


class LoadTest(unittest.TestCase):
    def test_an_immediate_load_puts_the_byte_in_the_register(self) -> None:
        cpu, _ = machine([0x3E, 0x42])

        cpu.step()

        self.assertEqual(cpu.registers.a, 0x42)

    def test_a_register_to_register_load_copies_it(self) -> None:
        cpu, _ = machine([0x47], a=0x42)

        cpu.step()

        self.assertEqual(cpu.registers.b, 0x42)

    def test_a_load_through_a_pair_reads_where_it_points(self) -> None:
        cpu, space = machine([0x7E], hl=0x1234)
        space.write8(0x1234, 0x42)

        cpu.step()

        self.assertEqual(cpu.registers.a, 0x42)

    def test_a_store_through_a_pair_writes_where_it_points(self) -> None:
        cpu, space = machine([0x77], hl=0x1234, a=0x42)

        cpu.step()

        self.assertEqual(space.read8(0x1234), 0x42)

    def test_a_wide_immediate_load_takes_two_bytes_low_first(self) -> None:
        cpu, _ = machine([0x21, 0x34, 0x12])

        cpu.step()

        self.assertEqual(cpu.registers.hl, 0x1234)

    def test_a_load_that_names_the_memory_at_hl_is_not_a_register(self) -> None:
        cpu, space = machine([0x36, 0x42], hl=0x1234)

        cpu.step()

        self.assertEqual(space.read8(0x1234), 0x42)


class ArithmeticTest(unittest.TestCase):
    def test_an_add_sets_carry_when_it_leaves_the_byte(self) -> None:
        # Arrange
        cpu, _ = machine([0xC6, 0x01], a=0xFF)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.registers.a, 0x00)
        self.assertEqual(cpu.registers.f & FLAG["c"], FLAG["c"])
        self.assertEqual(cpu.registers.f & FLAG["z"], FLAG["z"])

    def test_an_add_sets_the_half_carry_from_the_low_nibble(self) -> None:
        # Arrange
        cpu, _ = machine([0xC6, 0x01], a=0x0F)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.registers.f & FLAG["h"], FLAG["h"])

    def test_an_add_reports_overflow_when_the_sign_is_wrong(self) -> None:
        # Arrange
        cpu, _ = machine([0xC6, 0x01], a=0x7F)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.registers.f & FLAG["pv"], FLAG["pv"])

    def test_an_add_clears_the_subtract_flag(self) -> None:
        # Arrange
        cpu, _ = machine([0xC6, 0x01], a=0x00, f=FLAG["n"])

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.registers.f & FLAG["n"], 0)

    def test_a_subtract_sets_it(self) -> None:
        # Arrange
        cpu, _ = machine([0xD6, 0x01], a=0x02)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.registers.f & FLAG["n"], FLAG["n"])

    def test_a_compare_takes_its_hidden_bits_from_the_operand(self) -> None:
        # Arrange
        cpu, _ = machine([0xFE, 0x28], a=0xFF)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.registers.f & (FLAG["x"] | FLAG["y"]), FLAG["x"] | FLAG["y"])

    def test_a_subtract_takes_them_from_the_result(self) -> None:
        # Arrange
        cpu, _ = machine([0xD6, 0xD7], a=0xFF)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.registers.f & (FLAG["x"] | FLAG["y"]), FLAG["x"] | FLAG["y"])


class LogicTest(unittest.TestCase):
    def test_an_and_sets_the_half_carry_and_clears_the_carry(self) -> None:
        # Arrange
        cpu, _ = machine([0xE6, 0x0F], a=0xFF)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.registers.a, 0x0F)
        self.assertEqual(cpu.registers.f & FLAG["h"], FLAG["h"])
        self.assertEqual(cpu.registers.f & FLAG["c"], 0)

    def test_an_or_clears_both(self) -> None:
        # Arrange
        cpu, _ = machine([0xF6, 0x0F], a=0xF0)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.registers.a, 0xFF)
        self.assertEqual(cpu.registers.f & FLAG["h"], 0)

    def test_a_logical_operation_reports_parity_rather_than_overflow(self) -> None:
        # Arrange
        cpu, _ = machine([0xE6, 0x03], a=0xFF)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.registers.f & FLAG["pv"], FLAG["pv"])


class ExchangeTest(unittest.TestCase):
    def test_the_main_set_can_be_swapped_wholesale(self) -> None:
        cpu, _ = machine([0xD9], bc=0x1111, bc_=0xAAAA)

        cpu.step()

        self.assertEqual((cpu.registers.bc, cpu.registers.bc_), (0xAAAA, 0x1111))

    def test_the_accumulator_has_its_own_swap(self) -> None:
        cpu, _ = machine([0x08], af=0x1234, af_=0xABCD)

        cpu.step()

        self.assertEqual(cpu.registers.af, 0xABCD)

    def test_the_two_working_pairs_can_be_swapped_with_each_other(self) -> None:
        cpu, _ = machine([0xEB], de=0x1111, hl=0x2222)

        cpu.step()

        self.assertEqual((cpu.registers.de, cpu.registers.hl), (0x2222, 0x1111))


class ControlTest(unittest.TestCase):
    def test_a_jump_goes_where_it_says(self) -> None:
        cpu, _ = machine([0xC3, 0x34, 0x12])

        cpu.step()

        self.assertEqual(cpu.registers.pc, 0x1234)

    def test_a_call_pushes_the_address_after_it(self) -> None:
        cpu, space = machine([0xCD, 0x34, 0x12])

        cpu.step()

        self.assertEqual(cpu.registers.pc, 0x1234)
        self.assertEqual(space.read8(0xFFFD), 0x80)
        self.assertEqual(space.read8(0xFFFC), 0x03)

    def test_a_return_goes_back_to_it(self) -> None:
        cpu, space = machine([0xC9], sp=0xFFFC)
        space.write8(0xFFFC, 0x03)
        space.write8(0xFFFD, 0x80)

        cpu.step()

        self.assertEqual(cpu.registers.pc, 0x8003)

    def test_a_relative_jump_counts_from_the_instruction_after_it(self) -> None:
        cpu, _ = machine([0x18, 0x10])

        cpu.step()

        self.assertEqual(cpu.registers.pc, 0x8012)

    def test_a_relative_jump_backwards_is_signed(self) -> None:
        cpu, _ = machine([0x18, 0xFC])

        cpu.step()

        self.assertEqual(cpu.registers.pc, 0x7FFE)

    def test_a_conditional_jump_not_taken_costs_only_its_operand(self) -> None:
        # Arrange
        cpu, _ = machine([0xC2, 0x34, 0x12], f=FLAG["z"])

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.registers.pc, 0x8003)

    def test_a_restart_goes_to_its_fixed_address(self) -> None:
        cpu, _ = machine([0xFF])

        cpu.step()

        self.assertEqual(cpu.registers.pc, 0x0038)


class RefreshTest(unittest.TestCase):
    def test_every_instruction_advances_the_refresh_counter(self) -> None:
        cpu, _ = machine([0x00], r=0x00)

        cpu.step()

        self.assertEqual(cpu.registers.r, 0x01)

    def test_a_prefixed_instruction_advances_it_twice(self) -> None:
        cpu, _ = machine([0xCB, 0x00], r=0x00)

        cpu.step()

        self.assertEqual(cpu.registers.r, 0x02)


class ResetTest(unittest.TestCase):
    def test_a_reset_puts_the_program_counter_at_the_bottom(self) -> None:
        # Arrange
        cpu = Cpu("z80", SparseMemory(seed=1), ports=Ports(seed=1))

        # Act
        cpu.reset()

        # Assert
        self.assertEqual(cpu.registers.pc, 0x0000)

    def test_a_reset_leaves_the_working_registers_holding_what_they_held(self) -> None:
        # Arrange
        parts = [Cpu("z80", SparseMemory(), ports=Ports(), seed=seed) for seed in (1, 2)]

        # Act
        held = [part.reset().registers.hl for part in parts]

        # Assert
        self.assertNotEqual(held[0], held[1])


class ClockTest(unittest.TestCase):
    def test_a_step_reports_the_t_states_that_instruction_took(self) -> None:
        cpu, _ = machine([0x00])

        states = cpu.step()

        self.assertEqual(states, 4)

    def test_the_tally_adds_up_across_instructions(self) -> None:
        cpu, _ = machine([0x00, 0x00, 0x00])

        cpu.step()
        cpu.step()
        cpu.step()

        self.assertEqual(cpu.cycles, 12)

    def test_a_budget_runs_whole_instructions_and_reports_what_was_spent(self) -> None:
        cpu, _ = machine([0x00] * 8)

        spent = cpu.run_for(10)

        self.assertEqual(spent, 12)

    def test_the_tally_survives_a_reset_because_a_clock_does_not_rewind(self) -> None:
        # Arrange
        cpu, _ = machine([0x00])
        cpu.step()

        # Act
        cpu.reset()

        # Assert
        self.assertEqual(cpu.cycles, 4 + RESET_COST)

    def test_a_reset_costs_the_pin_hold_and_the_two_that_follow_it(self) -> None:
        cpu, _ = machine([0x00])
        before = cpu.cycles

        cpu.reset()

        self.assertEqual(cpu.cycles - before, 5)

    def test_and_those_two_are_spent_after_the_pin_releases(self) -> None:
        # Arrange
        cpu, _ = machine([0x00])
        before = cpu.cycles

        # Act
        cpu.reset()

        # Assert
        self.assertEqual(cpu.cycles - before, RESET_COST)

    def test_a_bounded_run_gives_up_rather_than_hanging(self) -> None:
        # Arrange
        cpu, _ = machine([0xC3, 0x00, 0x80])

        # Act
        attempt = lambda: cpu.run_until(lambda _: False, limit=50)  # noqa: E731

        # Assert
        self.assertRaises(RunLimit, attempt)

    def test_a_bounded_run_that_reaches_its_condition_does_not_raise(self) -> None:
        cpu, _ = machine([0x00, 0x00])
        target = cpu.registers.pc + 2

        cpu.run_until(lambda part: part.registers.pc == target, limit=50)

        self.assertEqual(cpu.registers.pc, target)


if __name__ == "__main__":
    unittest.main()
