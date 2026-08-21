import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from z80 import Ports, SparseMemory, bus, models
from z80.core import Cpu


class CatalogueTest(unittest.TestCase):
    def test_the_family_covers_the_original_part(self) -> None:
        self.assertIn("z80", models.MODELS)

    def test_and_the_later_one_that_answers_differently(self) -> None:
        self.assertIn("z84c00", models.MODELS)

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
        self.assertEqual(models.describe("upd780c").name, "z80")

    def test_a_name_no_part_answers_to_is_refused(self) -> None:
        with self.assertRaises(models.UnknownModelError):
            models.describe("6502")

    def test_and_the_refusal_lists_what_there_is(self) -> None:
        with self.assertRaises(models.UnknownModelError) as caught:
            models.describe("nothing")

        self.assertIn("z80", str(caught.exception))


class BuildTest(unittest.TestCase):
    def test_a_model_builds_a_machine_that_knows_which_one_it_is(self) -> None:
        cpu = models.describe("z80").build(SparseMemory(), ports=Ports())

        self.assertEqual(cpu.model, "z80")

    def test_a_machine_it_builds_draws_the_pins_the_manual_draws(self) -> None:
        cpu = models.describe("z80").build(SparseMemory(), ports=Ports())

        self.assertTrue(cpu.bus.follows_the_manual)

    def test_and_the_other_shape_reaches_it_like_any_other_option(self) -> None:
        cpu = models.describe("z80").build(SparseMemory(), shape=bus.RECORDING)

        self.assertFalse(cpu.bus.follows_the_manual)

    def test_the_original_part_sends_zero_for_the_output_with_no_source(self) -> None:
        cpu, ports = self.machine("z80")

        cpu.step()

        self.assertEqual(ports.log[-1][1], 0x00)

    def test_the_later_part_sends_every_bit_instead(self) -> None:
        cpu, ports = self.machine("z84c00")

        cpu.step()

        self.assertEqual(ports.log[-1][1], 0xFF)

    def machine(self, name: str) -> tuple[Cpu, Ports]:
        space = SparseMemory(seed=1)
        space.write8(0x8000, 0xED)
        space.write8(0x8001, 0x71)
        ports = Ports(seed=1)
        cpu = models.describe(name).build(space, ports=ports, reset=False)
        cpu.registers.pc = 0x8000
        cpu.registers.bc = 0x1234
        return cpu, ports


if __name__ == "__main__":
    unittest.main()
