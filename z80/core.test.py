import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from z80 import Ports, SparseMemory, core, flags
from z80.core import Cpu


def machine(program: list[int], at: int = 0x8000, **fields: Any) -> tuple[Cpu, SparseMemory]:
    space = SparseMemory(seed=1)
    for offset, value in enumerate(program):
        space.write8(at + offset, value)
    cpu = core.Cpu(space, Ports(seed=1), reset=False)
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
        cpu, _ = machine([0xC6, 0x01], a=0xFF)

        cpu.step()

        self.assertEqual(cpu.registers.a, 0x00)
        self.assertTrue(cpu.registers.f & flags.C)
        self.assertTrue(cpu.registers.f & flags.Z)

    def test_an_add_sets_the_half_carry_from_the_low_nibble(self) -> None:
        cpu, _ = machine([0xC6, 0x01], a=0x0F)

        cpu.step()

        self.assertTrue(cpu.registers.f & flags.H)

    def test_an_add_reports_overflow_when_the_sign_is_wrong(self) -> None:
        cpu, _ = machine([0xC6, 0x01], a=0x7F)

        cpu.step()

        self.assertTrue(cpu.registers.f & flags.PV)

    def test_an_add_clears_the_subtract_flag(self) -> None:
        cpu, _ = machine([0xC6, 0x01], a=0x00, f=flags.N)

        cpu.step()

        self.assertFalse(cpu.registers.f & flags.N)

    def test_a_subtract_sets_it(self) -> None:
        cpu, _ = machine([0xD6, 0x01], a=0x02)

        cpu.step()

        self.assertTrue(cpu.registers.f & flags.N)

    def test_a_compare_takes_its_hidden_bits_from_the_operand(self) -> None:
        cpu, _ = machine([0xFE, 0x28], a=0xFF)

        cpu.step()

        self.assertEqual(cpu.registers.f & (flags.X | flags.Y), flags.X | flags.Y)

    def test_a_subtract_takes_them_from_the_result(self) -> None:
        cpu, _ = machine([0xD6, 0xD7], a=0xFF)

        cpu.step()

        self.assertEqual(cpu.registers.f & (flags.X | flags.Y), flags.X | flags.Y)


class LogicTest(unittest.TestCase):
    def test_an_and_sets_the_half_carry_and_clears_the_carry(self) -> None:
        cpu, _ = machine([0xE6, 0x0F], a=0xFF)

        cpu.step()

        self.assertEqual(cpu.registers.a, 0x0F)
        self.assertTrue(cpu.registers.f & flags.H)
        self.assertFalse(cpu.registers.f & flags.C)

    def test_an_or_clears_both(self) -> None:
        cpu, _ = machine([0xF6, 0x0F], a=0xF0)

        cpu.step()

        self.assertEqual(cpu.registers.a, 0xFF)
        self.assertFalse(cpu.registers.f & flags.H)

    def test_a_logical_operation_reports_parity_rather_than_overflow(self) -> None:
        cpu, _ = machine([0xE6, 0x03], a=0xFF)

        cpu.step()

        self.assertTrue(cpu.registers.f & flags.PV)


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
        cpu, _ = machine([0xC2, 0x34, 0x12], f=flags.Z)

        cpu.step()

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
        cpu = core.Cpu(SparseMemory(seed=1), Ports(seed=1))

        self.assertEqual(cpu.registers.pc, 0x0000)

    def test_a_reset_leaves_the_working_registers_holding_what_they_held(self) -> None:
        first = core.Cpu(SparseMemory(), Ports(), seed=1)
        second = core.Cpu(SparseMemory(), Ports(), seed=2)

        self.assertNotEqual(first.registers.hl, second.registers.hl)


class LimitTest(unittest.TestCase):
    def test_a_run_that_never_ends_is_stopped_rather_than_hanging(self) -> None:
        cpu, _ = machine([0xC3, 0x00, 0x80])
        cpu.step_limit = 50

        with self.assertRaises(core.StepLimit):
            cpu.run_until(lambda _: False)

    def test_an_offered_interrupt_counts_against_the_same_limit(self) -> None:
        cpu, _ = machine([0x00])
        cpu.registers.sp, cpu.registers.iff1, cpu.registers.im = 0x8000, True, 1
        cpu.step_limit = 0

        with self.assertRaises(core.StepLimit):
            cpu.interrupt(0xFF)

    def test_and_so_does_the_nonmaskable_line(self) -> None:
        cpu, _ = machine([0x00])
        cpu.registers.sp = 0x8000
        cpu.step_limit = 0

        with self.assertRaises(core.StepLimit):
            cpu.nonmaskable()


if __name__ == "__main__":
    unittest.main()
