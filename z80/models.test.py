import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from z80 import Cpu, Ports, SparseMemory, bus, errors, models
from z80.core import Cpu as Part


class CatalogueTest(unittest.TestCase):
    def test_the_family_covers_the_original_part(self) -> None:
        self.assertIn("z80", models.MODELS)

    def test_and_the_later_one_that_answers_differently(self) -> None:
        self.assertIn("z84c00", models.MODELS)

    def test_and_the_second_source_that_is_not_a_copy(self) -> None:
        self.assertIn("upd780c", models.MODELS)

    def test_every_model_names_a_carry_rule_somebody_measured(self) -> None:
        rules = {model.carry_rule for model in models.MODELS.values()}

        self.assertLessEqual(rules, set(models.CARRY_RULES))

    def test_a_carry_rule_nobody_measured_is_refused(self) -> None:
        with self.assertRaises(errors.UnknownCarryRule):
            models.Model("invented", "a part nobody made", 0x00, carry_rule="guessed")

    def test_every_model_says_whether_a_suite_stands_behind_it(self) -> None:
        held = {model.name: model.verified for model in models.MODELS.values()}

        self.assertEqual(held, {"z80": True, "z84c00": False, "upd780c": False})

    def test_the_two_zilog_parts_differ_only_in_what_the_bare_output_sends(self) -> None:
        zilog, cmos = models.describe("z80"), models.describe("z84c00")

        self.assertEqual(
            (zilog.carry_rule == cmos.carry_rule, zilog.floating_output == cmos.floating_output),
            (True, False),
        )

    def test_and_the_nec_part_differs_only_in_where_the_carry_bits_come_from(self) -> None:
        zilog, nec = models.describe("z80"), models.describe("upd780c")

        self.assertEqual(
            (zilog.carry_rule == nec.carry_rule, zilog.floating_output == nec.floating_output),
            (False, True),
        )

    def test_every_model_says_what_it_is(self) -> None:
        for model in models.MODELS.values():
            self.assertTrue(model.summary.strip())

    def test_a_model_prints_as_something_a_person_can_read(self) -> None:
        self.assertIn("z80", repr(models.describe("z80")))


class NameTest(unittest.TestCase):
    def test_a_model_is_found_by_its_own_name(self) -> None:
        self.assertEqual(models.describe("z80").name, "z80")

    def test_case_does_not_matter(self) -> None:
        self.assertEqual(models.describe("Z80").name, "z80")

    def test_neither_do_the_separators_people_write(self) -> None:
        self.assertEqual(models.describe("Z84-C00").name, "z84c00")

    def test_an_alias_reaches_the_part_it_names(self) -> None:
        self.assertEqual(models.describe("mostekmk3880").name, "z80")

    def test_a_part_with_its_own_behaviour_is_its_own_model(self) -> None:
        self.assertEqual(models.describe("upd780c").name, "upd780c")

    def test_a_part_this_core_does_not_implement_is_refused(self) -> None:
        for name in ("z180", "ez80"):
            with self.assertRaises(errors.UnknownModelError):
                models.describe(name)

    def test_a_name_no_part_answers_to_is_refused(self) -> None:
        with self.assertRaises(errors.UnknownModelError):
            models.describe("6502")

    def test_and_the_refusal_lists_what_there_is(self) -> None:
        with self.assertRaises(errors.UnknownModelError) as caught:
            models.describe("nothing")

        self.assertIn("z80", str(caught.exception))


class BuildTest(unittest.TestCase):
    def test_a_model_builds_a_machine_that_knows_which_one_it_is(self) -> None:
        cpu = Cpu("z80", SparseMemory(), ports=Ports())

        self.assertEqual(cpu.model, "z80")

    def test_a_machine_it_builds_draws_the_pins_the_manual_draws(self) -> None:
        cpu = Cpu("z80", SparseMemory(), ports=Ports())

        self.assertTrue(cpu.bus.follows_the_manual)

    def test_and_the_other_shape_reaches_it_like_any_other_option(self) -> None:
        cpu = Cpu("z80", SparseMemory(), shape=bus.RECORDING)

        self.assertFalse(cpu.bus.follows_the_manual)

    def test_a_machine_carries_the_carry_rule_its_model_names(self) -> None:
        held = {name: Cpu(name, SparseMemory()).carry_rule for name in models.MODELS}

        self.assertEqual(held, {"z80": "zilog", "z84c00": "zilog", "upd780c": "nec"})

    def test_the_two_rules_disagree_where_the_latch_is_what_decides(self) -> None:
        answers = set()
        for name in ("z80", "upd780c"):
            space = SparseMemory()
            space.write8(0x0100, 0x37)
            cpu = Cpu(name, space)
            cpu.registers.pc, cpu.registers.a, cpu.registers.f = 0x0100, 0x00, 0x28
            cpu.registers.q = 0
            cpu.step()
            answers.add(cpu.registers.f & 0x28)

        self.assertEqual(len(answers), 2)

    def test_the_original_part_sends_zero_for_the_output_with_no_source(self) -> None:
        cpu, ports = self.machine("z80")

        cpu.step()

        self.assertEqual(ports.log[-1][1], 0x00)

    def test_the_later_part_sends_every_bit_instead(self) -> None:
        cpu, ports = self.machine("z84c00")

        cpu.step()

        self.assertEqual(ports.log[-1][1], 0xFF)

    def machine(self, name: str) -> tuple[Part, Ports]:
        space = SparseMemory(seed=1)
        space.write8(0x8000, 0xED)
        space.write8(0x8001, 0x71)
        ports = Ports(seed=1)
        cpu = Cpu(name, space, ports=ports)
        cpu.registers.pc = 0x8000
        cpu.registers.bc = 0x1234
        return cpu, ports


if __name__ == "__main__":
    unittest.main()
