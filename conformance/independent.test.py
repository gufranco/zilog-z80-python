import json
import sys
import unittest
from collections.abc import Sequence
from pathlib import Path
from typing import Any, override

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from z80 import flags, memory, models  # noqa: E402

HELD = json.loads((Path(__file__).resolve().parent / "independent.json").read_text())

START = 0x0100


def run(program: Sequence[int], **setup: int) -> Any:
    """One instruction, assembled where nothing else is, and stepped."""
    space = memory.SparseMemory()
    for offset, byte in enumerate(program):
        space.write8(START + offset, byte)
    cpu = models.describe("z80").build(space, reset=True)
    cpu.registers.pc = START
    for name, value in setup.items():
        setattr(cpu.registers, name, value)
    cpu.step()
    return cpu


class RecordTest(unittest.TestCase):
    def test_everything_here_says_it_settles_nothing_on_its_own(self) -> None:
        self.assertIn("settles nothing on its own", HELD["note"])

    def test_and_says_which_rung_it_sits_on(self) -> None:
        self.assertTrue(HELD["authority"].startswith("Rung 3"))

    def test_every_section_names_where_it_came_from(self) -> None:
        missing = [
            name
            for name, section in HELD.items()
            if isinstance(section, dict) and not section.get("source")
        ]

        self.assertEqual(missing, [])


class AddressRegisterTest(unittest.TestCase):
    """The register the corpus fixes, checked against a table nobody derived from it."""

    @override
    def setUp(self) -> None:
        self.rules = HELD["internalAddressRegister"]["rules"]

    def test_the_table_covers_every_kind_of_instruction_that_touches_it(self) -> None:
        self.assertEqual(len(self.rules), 20)

    def test_a_load_through_a_pair_leaves_the_address_after_the_one_it_read(self) -> None:
        self.assertEqual(run((0x0A,), bc=0x1234).registers.wz, 0x1235)

    def test_and_so_does_the_other_pair(self) -> None:
        self.assertEqual(run((0x1A,), de=0x1234).registers.wz, 0x1235)

    def test_an_extended_load_leaves_the_address_after_the_one_it_read(self) -> None:
        self.assertEqual(run((0x3A, 0x34, 0x12)).registers.wz, 0x1235)

    def test_a_store_through_a_pair_puts_the_accumulator_in_the_high_half(self) -> None:
        self.assertEqual(run((0x02,), bc=0x12FF, a=0x77).registers.wz, 0x7700)

    def test_and_the_low_half_wraps_inside_itself(self) -> None:
        self.assertEqual(run((0x12,), de=0x1234, a=0x77).registers.wz, 0x7735)

    def test_an_extended_store_does_the_same(self) -> None:
        self.assertEqual(run((0x32, 0x34, 0x12), a=0x77).registers.wz, 0x7735)

    def test_a_sixteen_bit_load_leaves_the_address_after_its_own(self) -> None:
        self.assertEqual(run((0x2A, 0x34, 0x12)).registers.wz, 0x1235)

    def test_and_a_sixteen_bit_store(self) -> None:
        self.assertEqual(run((0x22, 0x34, 0x12), hl=0x9999).registers.wz, 0x1235)

    def test_a_pair_addition_uses_the_pair_as_it_was(self) -> None:
        self.assertEqual(run((0x19,), hl=0x1234, de=0x0001).registers.wz, 0x1235)

    def test_a_digit_rotate_uses_the_pointer_plus_one(self) -> None:
        self.assertEqual(run((0xED, 0x6F), hl=0x1234).registers.wz, 0x1235)

    def test_a_jump_leaves_where_it_jumped_to(self) -> None:
        self.assertEqual(run((0xC3, 0x34, 0x12)).registers.wz, 0x1234)

    def test_a_relative_jump_leaves_where_it_jumped_to(self) -> None:
        self.assertEqual(run((0x18, 0x05)).registers.wz, START + 7)

    def test_an_input_by_immediate_puts_the_accumulator_above_it(self) -> None:
        self.assertEqual(run((0xDB, 0x34), a=0x12).registers.wz, 0x1235)

    def test_an_input_through_the_pair_uses_the_pair_plus_one(self) -> None:
        self.assertEqual(run((0xED, 0x40), bc=0x1234).registers.wz, 0x1235)

    def test_and_so_does_an_output(self) -> None:
        self.assertEqual(run((0xED, 0x41), bc=0x1234).registers.wz, 0x1235)

    def test_a_block_input_uses_the_pair_as_it_was(self) -> None:
        self.assertEqual(run((0xED, 0xA2), bc=0x1234, hl=0x2000).registers.wz, 0x1235)

    def test_and_counts_the_other_way_when_it_steps_back(self) -> None:
        self.assertEqual(run((0xED, 0xAA), bc=0x1234, hl=0x2000).registers.wz, 0x1233)

    def test_a_block_output_uses_the_pair_as_it_leaves_it(self) -> None:
        self.assertEqual(run((0xED, 0xA3), bc=0x1234, hl=0x2000).registers.wz, 0x1135)

    def test_and_a_block_output_that_steps_back(self) -> None:
        self.assertEqual(run((0xED, 0xAB), bc=0x1234, hl=0x2000).registers.wz, 0x1133)

    def test_a_restart_leaves_where_it_restarted_to(self) -> None:
        self.assertEqual(run((0xCF,), sp=0x8000).registers.wz, 0x0008)


class InterruptAcceptanceTest(unittest.TestCase):
    def taken(self, program: Sequence[int], **setup: int) -> bool:
        cpu = run(program, **setup)
        return bool(cpu.interrupt(0xFF))

    def test_an_enable_holds_the_next_boundary(self) -> None:
        self.assertFalse(self.taken((0xFB,), sp=0x8000, im=1))

    def test_a_return_from_interrupt_holds_it_when_the_two_disagreed(self) -> None:
        space = memory.SparseMemory()
        space.write8(START, 0xED)
        space.write8(START + 1, 0x45)
        cpu = models.describe("z80").build(space, reset=True)
        cpu.registers.pc, cpu.registers.sp = START, 0x8000
        cpu.registers.iff1, cpu.registers.iff2, cpu.registers.im = False, True, 1
        cpu.step()

        self.assertFalse(cpu.interrupt(0xFF))

    def test_and_does_not_when_they_agreed(self) -> None:
        space = memory.SparseMemory()
        space.write8(START, 0xED)
        space.write8(START + 1, 0x45)
        cpu = models.describe("z80").build(space, reset=True)
        cpu.registers.pc, cpu.registers.sp = START, 0x8000
        cpu.registers.iff1, cpu.registers.iff2, cpu.registers.im = True, True, 1
        cpu.step()

        self.assertTrue(cpu.interrupt(0xFF))

    def test_the_record_names_the_rule_the_manual_does_not_carry(self) -> None:
        rules = HELD["interruptAcceptance"]["rules"]

        self.assertEqual([rule["alsoInTheManual"] for rule in rules], [True, False])


class ModeZeroTest(unittest.TestCase):
    def machine(self, model: str = "z80") -> Any:
        space = memory.SparseMemory()
        space.write8(START, 0x00)
        cpu = models.describe(model).build(space, reset=True)
        cpu.registers.pc, cpu.registers.sp = START, 0x8000
        cpu.registers.iff1, cpu.registers.im = True, 0
        return cpu

    def test_an_operand_byte_leaves_the_counter_where_it_was(self) -> None:
        cpu = self.machine()

        cpu.interrupt(0x3E)

        self.assertEqual(cpu.registers.pc, START)

    def test_a_jump_still_reaches_where_it_was_told_to(self) -> None:
        space = memory.SparseMemory()
        space.write8(START, 0x00)
        space.write8(START + 1, 0x34)
        space.write8(START + 2, 0x12)
        cpu = models.describe("z80").build(space, reset=True)
        cpu.registers.pc, cpu.registers.sp = START, 0x8000
        cpu.registers.iff1, cpu.registers.im = True, 0

        cpu.interrupt(0xC3)

        self.assertNotEqual(cpu.registers.pc, START)

    def test_a_single_byte_response_leaves_the_counter_alone_too(self) -> None:
        cpu = self.machine()

        cpu.interrupt(0x00)

        self.assertEqual(cpu.registers.pc, START)

    def test_the_record_quotes_the_source_rather_than_paraphrasing_it(self) -> None:
        self.assertIn("pre-interrupt state", HELD["modeZeroResponse"]["quote"])


class ModeTwoVectorTest(unittest.TestCase):
    def landed(self, vector: int) -> int:
        space = memory.SparseMemory()
        space.write8(START, 0x00)
        for address, value in ((0x00FE, 0x11), (0x00FF, 0x22), (0x0100, 0x33)):
            space.write8(address, value)
        cpu = models.describe("z80").build(space, reset=True)
        cpu.registers.pc, cpu.registers.sp = START, 0x8000
        cpu.registers.i, cpu.registers.iff1, cpu.registers.im = 0x00, True, 2
        cpu.interrupt(vector)
        return int(cpu.registers.pc)

    def test_an_odd_vector_is_used_whole(self) -> None:
        self.assertEqual(self.landed(0xFF), 0x3322)

    def test_an_even_one_reads_the_entry_it_names(self) -> None:
        self.assertEqual(self.landed(0xFE), 0x2211)

    def test_the_two_differ_which_is_what_the_manual_denies(self) -> None:
        self.assertNotEqual(self.landed(0xFF), self.landed(0xFE))

    def test_the_record_quotes_the_test_that_found_it(self) -> None:
        self.assertIn("I have tested this", HELD["modeTwoVector"]["quote"])


class ResponseCostTest(unittest.TestCase):
    """What each response spends, against a source that is not the manual's arithmetic."""

    def spent(self, mode: int, vector: int = 0xFF, nonmaskable: bool = False) -> int:
        cpu = models.describe("z80").build(memory.SparseMemory(), reset=True)
        cpu.registers.sp, cpu.registers.pc = 0x8000, START
        cpu.registers.iff1, cpu.registers.im = True, mode
        if nonmaskable:
            cpu.nonmaskable()
        else:
            cpu.interrupt(vector)
        return len(cpu.bus)

    def test_the_nonmaskable_line_costs_what_young_reports(self) -> None:
        self.assertEqual(self.spent(1, nonmaskable=True), HELD["responseCost"]["nonmaskable"])

    def test_mode_one_costs_what_young_reports(self) -> None:
        self.assertEqual(self.spent(1), HELD["responseCost"]["modeOne"])

    def test_mode_two_costs_what_young_reports(self) -> None:
        self.assertEqual(self.spent(2), HELD["responseCost"]["modeTwo"])

    def test_a_mode_zero_restart_costs_what_young_reports(self) -> None:
        self.assertEqual(self.spent(0, vector=0xC7), HELD["responseCost"]["modeZeroRestart"])

    def test_the_acknowledge_cycle_is_the_seven_both_sources_give(self) -> None:
        held = HELD["responseCost"]

        self.assertEqual(held["modeOne"] - held["acknowledgeCycle"], 6)


class CarryRuleTest(unittest.TestCase):
    """The two carry flag rules, on the two kinds of part that are not disputed."""

    def carried(self, model: str, latch: int, f: int, a: int) -> int:
        space = memory.SparseMemory()
        space.write8(START, 0x37)
        cpu = models.describe(model).build(space, reset=True)
        cpu.registers.pc, cpu.registers.a, cpu.registers.f = START, a, f
        cpu.registers.q = latch
        cpu.step()
        return cpu.registers.f & (flags.X | flags.Y)

    def test_a_zilog_part_combines_the_accumulator_with_the_flags_when_the_latch_is_clear(
        self,
    ) -> None:
        self.assertEqual(self.carried("z80", 0, 0x28, 0x00), 0x28)

    def test_and_takes_the_accumulator_alone_when_it_is_not(self) -> None:
        self.assertEqual(self.carried("z80", 0x28, 0x28, 0x00), 0x00)

    def test_the_nec_part_takes_the_accumulator_alone_either_way(self) -> None:
        held = {self.carried("upd780c", latch, 0x28, 0x00) for latch in (0, 0x28)}

        self.assertEqual(held, {0x00})


if __name__ == "__main__":
    unittest.main()
