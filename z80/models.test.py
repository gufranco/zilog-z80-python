import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import z80
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
        zilog, cmos = models.lookup("z80"), models.lookup("z84c00")

        self.assertEqual(
            (zilog.carry_rule == cmos.carry_rule, zilog.floating_output == cmos.floating_output),
            (True, False),
        )

    def test_and_the_nec_part_differs_only_in_where_the_carry_bits_come_from(self) -> None:
        zilog, nec = models.lookup("z80"), models.lookup("upd780c")

        self.assertEqual(
            (zilog.carry_rule == nec.carry_rule, zilog.floating_output == nec.floating_output),
            (False, True),
        )

    def test_every_model_says_what_it_is(self) -> None:
        for model in models.MODELS.values():
            self.assertTrue(model.summary.strip())

    def test_a_model_prints_as_something_a_person_can_read(self) -> None:
        self.assertIn("z80", repr(models.lookup("z80")))


class NameTest(unittest.TestCase):
    def test_a_model_is_found_by_its_own_name(self) -> None:
        self.assertEqual(models.lookup("z80").name, "z80")

    def test_case_does_not_matter(self) -> None:
        self.assertEqual(models.lookup("Z80").name, "z80")

    def test_neither_do_the_separators_people_write(self) -> None:
        self.assertEqual(models.lookup("Z84-C00").name, "z84c00")

    def test_an_alias_reaches_the_part_it_names(self) -> None:
        self.assertEqual(models.lookup("mostekmk3880").name, "z80")

    def test_a_part_with_its_own_behaviour_is_its_own_model(self) -> None:
        self.assertEqual(models.lookup("upd780c").name, "upd780c")

    def test_a_part_this_core_does_not_implement_is_refused(self) -> None:
        for name in ("z180", "ez80"):
            with self.assertRaises(errors.UnknownModelError):
                models.lookup(name)

    def test_a_name_no_part_answers_to_is_refused(self) -> None:
        with self.assertRaises(errors.UnknownModelError):
            models.lookup("6502")

    def test_and_the_refusal_lists_what_there_is(self) -> None:
        with self.assertRaises(errors.UnknownModelError) as caught:
            models.lookup("nothing")

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


class QuietStoreTest(unittest.TestCase):
    """`fill`, which is the one spelling across this family for a store of one byte.

    Not what a board hands over and not the default: a caller asking for zeroes
    is asking for something no machine does, so they have to say so. What it is
    for is a run that has to get through a few dozen instructions without meeting
    an opcode that stops the part, which is what every check of a cycle budget
    needs and what scrambled memory cannot give.
    """

    def test_a_fill_puts_that_byte_everywhere(self) -> None:
        part = z80.Cpu("z80", fill=0)

        self.assertEqual({part.memory.read8(address) for address in range(0x40)}, {0})

    def test_and_any_byte_works_rather_than_only_zero(self) -> None:
        part = z80.Cpu("z80", fill=0xAA)

        self.assertEqual({part.memory.read8(address) for address in range(0x40)}, {0xAA})

    def test_without_one_the_store_is_scrambled_rather_than_cleared(self) -> None:
        """The default has to stay the thing a machine actually hands over.

        Read address by address rather than off the store's own bytes, because
        the default store allocates nothing until it is asked and has no bytes
        to read.
        """
        part = z80.Cpu("z80")

        held = {part.memory.read8(address) for address in range(0x40)}

        self.assertNotEqual(held, {0})

    def test_and_a_store_handed_in_is_left_alone(self) -> None:
        """So `fill` cannot quietly replace memory a caller already built."""
        own = z80.Memory(fill=0xAA)

        part = z80.Cpu("z80", own, fill=0)

        self.assertIs(part.memory, own)
        self.assertEqual({part.memory.read8(address) for address in range(0x40)}, {0xAA})


class NamingNoneTest(unittest.TestCase):
    """That leaving the model out is refused, and refused usefully.

    A default here would be the one implicit thing in the whole call. It would
    also be worst on a package like this one, where the three parts differ in
    ways a caller can be caught by, so the refusal names all three rather than
    telling somebody they got it wrong.
    """

    def test_building_without_naming_a_model_is_refused(self) -> None:
        with self.assertRaises(errors.UnknownModelError):
            z80.Cpu()

    def test_and_the_refusal_names_every_model_there_is(self) -> None:
        with self.assertRaises(errors.UnknownModelError) as caught:
            z80.Cpu()

        missing = [name for name in z80.MODELS if name not in str(caught.exception)]

        self.assertEqual(missing, [])

    def test_and_says_it_will_not_choose_rather_than_only_that_it_cannot(self) -> None:
        with self.assertRaises(errors.UnknownModelError) as caught:
            z80.Cpu()

        self.assertIn("will not choose", str(caught.exception))

    def test_the_lookup_underneath_refuses_the_same_way(self) -> None:
        with self.assertRaises(errors.UnknownModelError):
            models.lookup(None)

    def test_a_model_that_is_named_is_built(self) -> None:
        held = z80.Cpu(sorted(z80.MODELS)[0])

        self.assertEqual(type(held).__name__, "Cpu")

    def test_nothing_named_describe_is_published(self) -> None:
        self.assertFalse(hasattr(z80, "describe"))

    def test_and_no_default_model_is_published_either(self) -> None:
        self.assertFalse(hasattr(z80, "DEFAULT_MODEL"))


if __name__ == "__main__":
    unittest.main()
