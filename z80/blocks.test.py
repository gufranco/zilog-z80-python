import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from z80 import Ports, SparseMemory, core, flags


def machine(program, at=0x8000, **fields):
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


class MoveTest(unittest.TestCase):
    def test_a_move_copies_one_byte_between_the_two_pointers(self):
        cpu, space = machine([0xED, 0xA0], hl=0x1000, de=0x2000, bc=0x0005)
        space.write8(0x1000, 0x42)

        cpu.step()

        self.assertEqual(space.read8(0x2000), 0x42)

    def test_a_move_advances_both_pointers_and_counts_down(self):
        cpu, _ = machine([0xED, 0xA0], hl=0x1000, de=0x2000, bc=0x0005)

        cpu.step()

        self.assertEqual(
            (cpu.registers.hl, cpu.registers.de, cpu.registers.bc), (0x1001, 0x2001, 4)
        )

    def test_a_backward_move_retreats_both_pointers(self):
        cpu, _ = machine([0xED, 0xA8], hl=0x1000, de=0x2000, bc=0x0005)

        cpu.step()

        self.assertEqual((cpu.registers.hl, cpu.registers.de), (0x0FFF, 0x1FFF))

    def test_a_move_reports_whether_any_count_remains(self):
        cpu, _ = machine([0xED, 0xA0], hl=0x1000, de=0x2000, bc=0x0001)

        cpu.step()

        self.assertFalse(cpu.registers.f & flags.PV)

    def test_a_move_takes_its_hidden_bits_from_the_byte_plus_the_accumulator(self):
        cpu, space = machine([0xED, 0xA0], hl=0x1000, de=0x2000, bc=0x0002, a=0x00)
        space.write8(0x1000, 0x0A)

        cpu.step()

        self.assertEqual(cpu.registers.f & flags.X, flags.X)
        self.assertEqual(cpu.registers.f & flags.Y, flags.Y)

    def test_a_repeating_move_stays_on_the_same_instruction_until_it_is_done(self):
        cpu, _ = machine([0xED, 0xB0], hl=0x1000, de=0x2000, bc=0x0002)

        cpu.step()

        self.assertEqual(cpu.registers.pc, 0x8000)

    def test_a_repeating_move_moves_on_when_the_count_reaches_zero(self):
        cpu, _ = machine([0xED, 0xB0], hl=0x1000, de=0x2000, bc=0x0001)

        cpu.step()

        self.assertEqual(cpu.registers.pc, 0x8002)

    def test_a_repeating_move_run_to_completion_copies_the_whole_block(self):
        cpu, space = machine([0xED, 0xB0], hl=0x1000, de=0x2000, bc=0x0004)
        for offset in range(4):
            space.write8(0x1000 + offset, 0x10 + offset)

        cpu.run_until(lambda machine: machine.registers.pc == 0x8002)

        self.assertEqual([space.read8(0x2000 + at) for at in range(4)], [0x10, 0x11, 0x12, 0x13])


class CompareTest(unittest.TestCase):
    def test_a_compare_reports_a_match_without_disturbing_the_accumulator(self):
        cpu, space = machine([0xED, 0xA1], hl=0x1000, bc=0x0005, a=0x42)
        space.write8(0x1000, 0x42)

        cpu.step()

        self.assertTrue(cpu.registers.f & flags.Z)
        self.assertEqual(cpu.registers.a, 0x42)

    def test_a_compare_advances_the_pointer_and_counts_down(self):
        cpu, _ = machine([0xED, 0xA1], hl=0x1000, bc=0x0005)

        cpu.step()

        self.assertEqual((cpu.registers.hl, cpu.registers.bc), (0x1001, 4))

    def test_a_compare_never_touches_the_carry(self):
        cpu, _ = machine([0xED, 0xA1], hl=0x1000, bc=0x0005, a=0x00, f=flags.C)

        cpu.step()

        self.assertTrue(cpu.registers.f & flags.C)

    def test_a_repeating_compare_stops_on_a_match(self):
        cpu, space = machine([0xED, 0xB1], hl=0x1000, bc=0x0004, a=0x42)
        space.write8(0x1000, 0x42)

        cpu.step()

        self.assertEqual(cpu.registers.pc, 0x8002)

    def test_a_repeating_compare_keeps_looking_while_the_count_holds(self):
        cpu, space = machine([0xED, 0xB1], hl=0x1000, bc=0x0004, a=0x42)
        space.write8(0x1000, 0x00)

        cpu.step()

        self.assertEqual(cpu.registers.pc, 0x8000)

    def test_a_repeating_compare_gives_up_when_the_count_runs_out(self):
        cpu, space = machine([0xED, 0xB1], hl=0x1000, bc=0x0001, a=0x42)
        space.write8(0x1000, 0x00)

        cpu.step()

        self.assertEqual(cpu.registers.pc, 0x8002)


class InputTest(unittest.TestCase):
    def test_an_input_stores_what_the_port_answered(self):
        cpu, space = machine([0xED, 0xA2], hl=0x1000, bc=0x0234)
        cpu.ports.write(0x0234, 0x42)

        cpu.step()

        self.assertEqual(space.read8(0x1000), 0x42)

    def test_an_input_counts_down_the_high_half_of_the_pair(self):
        cpu, _ = machine([0xED, 0xA2], hl=0x1000, bc=0x0534)

        cpu.step()

        self.assertEqual(cpu.registers.b, 0x04)

    def test_an_input_advances_the_pointer(self):
        cpu, _ = machine([0xED, 0xA2], hl=0x1000, bc=0x0534)

        cpu.step()

        self.assertEqual(cpu.registers.hl, 0x1001)

    def test_a_backward_input_retreats_it(self):
        cpu, _ = machine([0xED, 0xAA], hl=0x1000, bc=0x0534)

        cpu.step()

        self.assertEqual(cpu.registers.hl, 0x0FFF)

    def test_a_repeating_input_stops_when_the_counter_empties(self):
        cpu, _ = machine([0xED, 0xB2], hl=0x1000, bc=0x0134)

        cpu.step()

        self.assertEqual(cpu.registers.pc, 0x8002)


class OutputTest(unittest.TestCase):
    def test_an_output_sends_the_byte_the_pointer_names(self):
        cpu, space = machine([0xED, 0xA3], hl=0x1000, bc=0x0534)
        space.write8(0x1000, 0x42)

        cpu.step()

        self.assertIn((0x0434, 0x42, "w"), cpu.ports.log)

    def test_an_output_counts_down_before_it_names_the_port(self):
        cpu, _ = machine([0xED, 0xA3], hl=0x1000, bc=0x0534)

        cpu.step()

        self.assertEqual(cpu.ports.log[-1][0] >> 8, 0x04)

    def test_a_repeating_output_keeps_going_while_the_counter_holds(self):
        cpu, _ = machine([0xED, 0xB3], hl=0x1000, bc=0x0534)

        cpu.step()

        self.assertEqual(cpu.registers.pc, 0x8000)

    def test_a_repeating_output_run_to_completion_sends_every_byte(self):
        cpu, space = machine([0xED, 0xB3], hl=0x1000, bc=0x0334)
        for offset in range(3):
            space.write8(0x1000 + offset, 0x10 + offset)

        cpu.run_until(lambda machine: machine.registers.pc == 0x8002)

        self.assertEqual([entry[1] for entry in cpu.ports.log], [0x10, 0x11, 0x12])


class UndefinedTest(unittest.TestCase):
    def test_an_extended_opcode_in_the_block_range_that_names_nothing_does_nothing(self):
        cpu, _ = machine([0xED, 0xA4], hl=0x1000, bc=0x0005)

        cpu.step()

        self.assertEqual((cpu.registers.hl, cpu.registers.bc), (0x1000, 0x0005))

    def test_and_leaves_the_program_counter_after_it(self):
        cpu, _ = machine([0xED, 0xA4])

        cpu.step()

        self.assertEqual(cpu.registers.pc, 0x8002)


if __name__ == "__main__":
    unittest.main()
