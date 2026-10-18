import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.bench import (
    acknowledged,
    cycle_lengths,
    entries_of,
    loaded,
    pins_of,
    ran,
    shaped,
)
from z80 import Cpu, UnknownShape

NOP = (0x00,)

LOAD_IMMEDIATE = (0x06, 0x42)

LOAD_THROUGH_HL = (0x7E,)

STORE_THROUGH_HL = (0x77,)

INPUT_IMMEDIATE = (0xDB, 0x34)

OUTPUT_IMMEDIATE = (0xD3, 0x34)

INCREMENT_PAIR = (0x03,)

INCREMENT_THROUGH_HL = (0x34,)

LOAD_INDEXED = (0xDD, 0x7E, 0x01)

PINS = "rwmi"


def every_run() -> list[Any]:
    return [
        shaped(NOP, "manual"),
        shaped(LOAD_IMMEDIATE, "manual"),
        shaped(STORE_THROUGH_HL, "manual", {"hl": 0x2000}),
        shaped(INPUT_IMMEDIATE, "manual"),
        shaped(OUTPUT_IMMEDIATE, "manual"),
        acknowledged("manual"),
    ]


class ShapeTest(unittest.TestCase):
    def test_a_part_follows_the_manual_unless_told_otherwise(self) -> None:
        # Arrange
        cpu = ran(LOAD_IMMEDIATE)

        # Act
        pins = pins_of(cpu, "read")

        # Assert
        self.assertEqual(pins, ["r-m-", "r-m-", "----"])

    def test_the_recorded_shape_has_to_be_asked_for(self) -> None:
        # Arrange
        cpu = ran(LOAD_IMMEDIATE, shape="recording")

        # Act
        pins = pins_of(cpu, "read")

        # Assert
        self.assertEqual(pins, ["----", "r-m-", "----"])

    def test_a_shape_that_is_neither_is_refused_rather_than_guessed(self) -> None:
        # Arrange
        shape = "invented"

        # Act
        attempt = lambda: Cpu("z80", shape=shape)  # noqa: E731

        # Assert
        self.assertRaises(UnknownShape, attempt)

    def test_and_the_refusal_names_the_two_shapes_there_are(self) -> None:
        # Arrange
        shape = "invented"

        # Act
        with self.assertRaises(UnknownShape) as raised:
            Cpu("z80", shape=shape)

        # Assert
        self.assertEqual(
            str(raised.exception), "invented is not a pin shape; there are manual, recording"
        )


class EdgeTest(unittest.TestCase):
    def test_every_machine_cycle_kind_the_part_runs_is_one_of_six(self) -> None:
        # Arrange
        runs = every_run()

        # Act
        kinds = {kind for cpu in runs for _, kind in cpu.bus.cycles}

        # Assert
        self.assertEqual(kinds, {"fetch", "read", "write", "portRead", "portWrite", "acknowledge"})

    def test_every_column_is_as_wide_as_the_pins_there_are(self) -> None:
        # Arrange
        runs = every_run()

        # Act
        widths = {len(pins) for cpu in runs for _, _, pins in cpu.bus.log}

        # Assert
        self.assertEqual(widths, {4})

    def test_the_pins_are_written_in_the_order_the_corpus_writes_them(self) -> None:
        # Arrange
        runs = every_run()

        # Act
        astray = [
            pins
            for cpu in runs
            for _, _, pins in cpu.bus.log
            if any(held not in (PINS[place], "-") for place, held in enumerate(pins))
        ]

        # Assert
        self.assertEqual(astray, [])

    def test_a_strobe_belongs_to_the_state_whose_end_it_is_still_active_at(self) -> None:
        # Arrange
        cpu = shaped(NOP, "manual")

        # Act
        pins = pins_of(cpu, "fetch")

        # Assert
        self.assertEqual(pins[:2], ["r-m-", "r-m-"])

    def test_and_not_to_one_it_merely_overlaps(self) -> None:
        # Arrange
        cpu = shaped(NOP, "manual")

        # Act
        pins = pins_of(cpu, "fetch")

        # Assert
        self.assertEqual(pins[2], "--m-")

    def test_a_port_cycle_leaves_its_first_state_bare_and_a_memory_one_does_not(self) -> None:
        # Arrange
        cpu = shaped(INPUT_IMMEDIATE, "manual")

        # Act
        first = (pins_of(cpu, "portRead")[0], pins_of(cpu, "read")[0])

        # Assert
        self.assertEqual(first, ("----", "r-m-"))


class CountingTest(unittest.TestCase):
    def test_a_part_that_has_run_nothing_has_spent_nothing(self) -> None:
        # Arrange
        model = "z80"

        # Act
        cpu = Cpu(model)

        # Assert
        self.assertEqual(cpu.bus.states, 0)

    def test_an_opcode_fetch_costs_the_four_the_manual_gives_it(self) -> None:
        # Arrange
        cpu = ran(NOP)

        # Act
        lengths = cycle_lengths(cpu)

        # Assert
        self.assertEqual(lengths, [4])

    def test_a_memory_access_costs_three(self) -> None:
        # Arrange
        cpu = ran(LOAD_IMMEDIATE)

        # Act
        lengths = cycle_lengths(cpu)

        # Assert
        self.assertEqual(lengths, [4, 3])

    def test_a_port_access_costs_four_because_of_the_automatic_wait(self) -> None:
        # Arrange
        cpu = ran(INPUT_IMMEDIATE)

        # Act
        lengths = cycle_lengths(cpu)

        # Assert
        self.assertEqual(lengths, [4, 3, 4])

    def test_the_shape_changes_no_count(self) -> None:
        # Arrange
        shapes = ("manual", "recording")

        # Act
        found = {shape: shaped(INPUT_IMMEDIATE, shape).bus.states for shape in shapes}

        # Assert
        self.assertEqual(found, dict.fromkeys(shapes, 11))

    def test_counting_happens_without_recording(self) -> None:
        # Arrange
        program = LOAD_IMMEDIATE

        # Act
        cpu = ran(program, recording=False)

        # Assert
        self.assertEqual((cpu.bus.states, cpu.bus.log, cpu.bus.cycles), (7, [], []))

    def test_each_instruction_starts_counting_from_nothing(self) -> None:
        # Arrange
        cpu = loaded((*LOAD_IMMEDIATE, *NOP))
        cpu.step()

        # Act
        cpu.step()

        # Assert
        self.assertEqual((cpu.bus.states, len(cpu.bus.log), cpu.bus.cycles), (4, 4, [(0, "fetch")]))


class IdleTest(unittest.TestCase):
    def test_an_internal_cycle_asserts_no_pin_and_drives_no_value(self) -> None:
        # Arrange
        cpu = shaped(INCREMENT_PAIR, "manual")

        # Act
        internal = [(value, pins) for _, value, pins in cpu.bus.log[4:]]

        # Assert
        self.assertEqual(internal, [(None, "----")] * 2)

    def test_after_a_fetch_it_holds_the_refresh_address(self) -> None:
        # Arrange
        cpu = shaped(INCREMENT_PAIR, "manual")

        # Act
        addresses = [address for address, _, _ in cpu.bus.log[4:]]

        # Assert
        self.assertEqual(addresses, [0x5678] * 2)

    def test_after_a_read_it_holds_the_address_that_read_left(self) -> None:
        # Arrange
        cpu = shaped(INCREMENT_THROUGH_HL, "manual", {"hl": 0x2000})

        # Act
        internal = cpu.bus.log[7]

        # Assert
        self.assertEqual(internal, (0x2000, None, "----"))


class AddressTest(unittest.TestCase):
    def test_an_address_past_sixteen_bits_is_carried_round(self) -> None:
        # Arrange
        cpu = shaped(LOAD_INDEXED, "manual", {"ix": 0xFFFF})

        # Act
        addresses = {address for address, _, _ in entries_of(cpu, "read")[-3:]}

        # Assert
        self.assertEqual(addresses, {0x0000})


class ReprTest(unittest.TestCase):
    def test_a_bus_prints_what_it_has_spent_and_recorded(self) -> None:
        # Arrange
        cpu = ran(LOAD_IMMEDIATE)

        # Act
        printed = repr(cpu.bus)

        # Assert
        self.assertEqual(printed, "<Bus 7 T states, 7 recorded, manual>")

    def test_and_which_shape_it_is_drawing(self) -> None:
        # Arrange
        cpu = ran(LOAD_IMMEDIATE, shape="recording", recording=False)

        # Act
        printed = repr(cpu.bus)

        # Assert
        self.assertEqual(printed, "<Bus 7 T states, 0 recorded, recording>")


if __name__ == "__main__":
    unittest.main()
