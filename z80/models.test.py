import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import z80
from conformance.bench import pins_of, ran
from z80 import (
    MODELS,
    Cpu,
    Model,
    Ports,
    SparseMemory,
    UnknownCarryRule,
    UnknownModelError,
)

CARRY_RULES = ("zilog", "nec")


def described(name: str) -> Model:
    return MODELS[Cpu(name).model]


def bare_output_from(name: str) -> int:
    space = SparseMemory(seed=1)
    space.write8(0x8000, 0xED)
    space.write8(0x8001, 0x71)
    ports = Ports(seed=1)
    cpu = Cpu(name, space, ports=ports)
    cpu.registers.pc = 0x8000
    cpu.registers.bc = 0x1234
    cpu.step()
    sent: int = ports.log[-1][1]
    return sent


def stored(part: Any) -> set[int]:
    return {part.memory.read8(address) for address in range(0x40)}


def refusal(case: unittest.TestCase, model: str | None) -> str:
    with case.assertRaises(UnknownModelError) as raised:
        Cpu(model)
    return str(raised.exception)


class CatalogueTest(unittest.TestCase):
    def test_the_family_covers_the_three_parts(self) -> None:
        # Arrange
        expected = {"z80", "z84c00", "upd780c"}

        # Act
        named = set(MODELS)

        # Assert
        self.assertEqual(named, expected)

    def test_every_model_names_a_carry_rule_somebody_measured(self) -> None:
        # Arrange
        models = MODELS.values()

        # Act
        rules = {model.carry_rule for model in models}

        # Assert
        self.assertLessEqual(rules, set(CARRY_RULES))

    def test_a_carry_rule_nobody_measured_is_refused(self) -> None:
        # Arrange
        rule = "guessed"

        # Act
        attempt = lambda: Model("invented", "a part nobody made", 0x00, carry_rule=rule)  # noqa: E731

        # Assert
        self.assertRaises(UnknownCarryRule, attempt)

    def test_every_model_says_whether_a_suite_stands_behind_it(self) -> None:
        # Arrange
        models = MODELS.values()

        # Act
        held = {model.name: model.verified for model in models}

        # Assert
        self.assertEqual(held, {"z80": True, "z84c00": False, "upd780c": False})

    def test_the_two_zilog_parts_differ_only_in_what_the_bare_output_sends(self) -> None:
        # Arrange
        names = ("z80", "z84c00")

        # Act
        zilog, cmos = (described(name) for name in names)

        # Assert
        self.assertEqual(
            (zilog.carry_rule == cmos.carry_rule, zilog.floating_output == cmos.floating_output),
            (True, False),
        )

    def test_and_the_nec_part_differs_only_in_where_the_carry_bits_come_from(self) -> None:
        # Arrange
        names = ("z80", "upd780c")

        # Act
        zilog, nec = (described(name) for name in names)

        # Assert
        self.assertEqual(
            (zilog.carry_rule == nec.carry_rule, zilog.floating_output == nec.floating_output),
            (False, True),
        )

    def test_every_model_says_what_it_is(self) -> None:
        # Arrange
        models = MODELS.values()

        # Act
        silent = [model.name for model in models if not model.summary.strip()]

        # Assert
        self.assertEqual(silent, [])

    def test_a_model_prints_as_something_a_person_can_read(self) -> None:
        # Arrange
        model = described("z80")

        # Act
        printed = repr(model)

        # Assert
        self.assertEqual(printed, "<Model z80, output with no source sends 0x00>")


class NameTest(unittest.TestCase):
    def test_a_model_is_found_by_its_own_name(self) -> None:
        # Arrange
        name = "z80"

        # Act
        found = described(name)

        # Assert
        self.assertEqual(found.name, "z80")

    def test_case_does_not_matter(self) -> None:
        # Arrange
        name = "Z80"

        # Act
        found = described(name)

        # Assert
        self.assertEqual(found.name, "z80")

    def test_neither_do_the_separators_people_write(self) -> None:
        # Arrange
        name = "Z84-C00"

        # Act
        found = described(name)

        # Assert
        self.assertEqual(found.name, "z84c00")

    def test_an_alias_reaches_the_part_it_names(self) -> None:
        # Arrange
        name = "mostekmk3880"

        # Act
        found = described(name)

        # Assert
        self.assertEqual(found.name, "z80")

    def test_a_part_with_its_own_behaviour_is_its_own_model(self) -> None:
        # Arrange
        name = "upd780c"

        # Act
        found = described(name)

        # Assert
        self.assertEqual(found.name, "upd780c")

    def test_a_part_this_core_does_not_implement_is_refused(self) -> None:
        # Arrange
        names = ("z180", "ez80")

        # Act
        refused = {name: refusal(self, name) for name in names}

        # Assert
        self.assertEqual(
            refused,
            {
                name: f"{name} is not a model this family covers; it has upd780c, z80, z84c00"
                for name in names
            },
        )

    def test_a_name_no_part_answers_to_is_refused(self) -> None:
        # Arrange
        name = "6502"

        # Act
        attempt = lambda: described(name)  # noqa: E731

        # Assert
        self.assertRaises(UnknownModelError, attempt)

    def test_and_the_refusal_lists_what_there_is(self) -> None:
        # Arrange
        name = "nothing"

        # Act
        said = refusal(self, name)

        # Assert
        self.assertEqual(
            said, "nothing is not a model this family covers; it has upd780c, z80, z84c00"
        )


class BuildTest(unittest.TestCase):
    def test_a_model_builds_a_machine_that_knows_which_one_it_is(self) -> None:
        # Arrange
        name = "z80"

        # Act
        cpu = Cpu(name, SparseMemory(), ports=Ports())

        # Assert
        self.assertEqual(cpu.model, "z80")

    def test_a_machine_it_builds_draws_the_pins_the_manual_draws(self) -> None:
        # Arrange
        cpu = ran((0x06, 0x42))

        # Act
        pins = pins_of(cpu, "read")

        # Assert
        self.assertEqual(pins, ["r-m-", "r-m-", "----"])

    def test_and_the_other_shape_reaches_it_like_any_other_option(self) -> None:
        # Arrange
        cpu = ran((0x06, 0x42), shape="recording")

        # Act
        pins = pins_of(cpu, "read")

        # Assert
        self.assertEqual(pins, ["----", "r-m-", "----"])

    def test_a_machine_carries_the_carry_rule_its_model_names(self) -> None:
        # Arrange
        setup = {"a": 0x00, "f": 0x28, "q": 0x00}

        # Act
        held = {name: ran((0x37,), setup, model=name).registers.f & 0x28 for name in MODELS}

        # Assert
        self.assertEqual(
            held,
            {name: 0x28 if MODELS[name].carry_rule == "zilog" else 0x00 for name in MODELS},
        )

    def test_the_two_rules_disagree_where_the_latch_is_what_decides(self) -> None:
        # Arrange
        setup = {"a": 0x00, "f": 0x28, "q": 0x00}

        # Act
        answers = {
            ran((0x37,), setup, model=name).registers.f & 0x28 for name in ("z80", "upd780c")
        }

        # Assert
        self.assertEqual(answers, {0x28, 0x00})

    def test_the_original_part_sends_zero_for_the_output_with_no_source(self) -> None:
        # Arrange
        name = "z80"

        # Act
        sent = bare_output_from(name)

        # Assert
        self.assertEqual(sent, 0x00)

    def test_the_later_part_sends_every_bit_instead(self) -> None:
        # Arrange
        name = "z84c00"

        # Act
        sent = bare_output_from(name)

        # Assert
        self.assertEqual(sent, 0xFF)


class QuietStoreTest(unittest.TestCase):
    def test_a_fill_puts_that_byte_everywhere(self) -> None:
        # Arrange
        fill = 0x00

        # Act
        part = z80.Cpu("z80", fill=fill)

        # Assert
        self.assertEqual(stored(part), {0x00})

    def test_and_any_byte_works_rather_than_only_zero(self) -> None:
        # Arrange
        fill = 0xAA

        # Act
        part = z80.Cpu("z80", fill=fill)

        # Assert
        self.assertEqual(stored(part), {0xAA})

    def test_without_one_the_store_is_scrambled_rather_than_cleared(self) -> None:
        # Arrange
        model = "z80"

        # Act
        part = z80.Cpu(model)

        # Assert
        self.assertGreater(len(stored(part)), 1)

    def test_and_a_store_handed_in_is_left_alone(self) -> None:
        # Arrange
        own = z80.Memory(fill=0xAA)

        # Act
        part: Any = z80.Cpu("z80", own, fill=0)

        # Assert
        self.assertEqual((part.memory is own, stored(part)), (True, {0xAA}))


class NamingNoneTest(unittest.TestCase):
    def test_building_without_naming_a_model_is_refused(self) -> None:
        # Arrange
        arguments: dict[str, Any] = {}

        # Act
        attempt = lambda: z80.Cpu(**arguments)  # noqa: E731

        # Assert
        self.assertRaises(UnknownModelError, attempt)

    def test_and_the_refusal_names_every_model_there_is(self) -> None:
        # Arrange
        model = None

        # Act
        said = refusal(self, model)

        # Assert
        self.assertEqual([name for name in z80.MODELS if name not in said], [])

    def test_and_says_it_will_not_choose_rather_than_only_that_it_cannot(self) -> None:
        # Arrange
        model = None

        # Act
        said = refusal(self, model)

        # Assert
        self.assertEqual(
            said,
            "no model was named, and this package will not choose one for you."
            " Name one of: upd780c, z80, z84c00",
        )

    def test_a_model_that_is_named_is_built(self) -> None:
        # Arrange
        name = sorted(z80.MODELS)[0]

        # Act
        held = z80.Cpu(name)

        # Assert
        self.assertEqual(type(held).__name__, "Cpu")

    def test_nothing_named_describe_is_published(self) -> None:
        # Arrange
        package = z80

        # Act
        published = hasattr(package, "describe")

        # Assert
        self.assertIs(published, False)

    def test_and_no_default_model_is_published_either(self) -> None:
        # Arrange
        package = z80

        # Act
        published = hasattr(package, "DEFAULT_MODEL")

        # Assert
        self.assertIs(published, False)


if __name__ == "__main__":
    unittest.main()
