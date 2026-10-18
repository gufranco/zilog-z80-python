import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.bench import (
    START,
    acknowledged,
    entries_of,
    loaded,
    pins_of,
    shaped,
)
from z80 import Ports

NOP = (0x00,)

LOAD_IMMEDIATE = (0x06, 0x42)

LOAD_THROUGH_HL = (0x7E,)

STORE_THROUGH_HL = (0x77,)

INPUT_IMMEDIATE = (0xDB, 0x34)

OUTPUT_IMMEDIATE = (0xD3, 0x34)

INPUT_THROUGH_C = (0xED, 0x78)


def read_from(shape: str) -> Any:
    cpu = loaded(LOAD_THROUGH_HL, {"hl": 0x2000}, shape=shape)
    cpu.memory.write8(0x2000, 0x42)
    cpu.step()
    return cpu


def port_with(value: int) -> Ports:
    ports = Ports()
    ports.write(0x1234, value)
    return ports


class FetchTest(unittest.TestCase):
    def test_the_counter_is_on_the_bus_for_the_first_two_states(self) -> None:
        # Arrange
        cpu = shaped(NOP, "manual")

        # Act
        addresses = [address for address, _, _ in entries_of(cpu, "fetch")]

        # Assert
        self.assertEqual(addresses[:2], [START, START])

    def test_and_the_refresh_address_for_the_last_two(self) -> None:
        # Arrange
        cpu = shaped(NOP, "manual")

        # Act
        addresses = [address for address, _, _ in entries_of(cpu, "fetch")]

        # Assert
        self.assertEqual(addresses[2:], [0x5678, 0x5678])

    def test_memory_request_continues_through_refresh_but_read_does_not(self) -> None:
        # Arrange
        cpu = shaped(NOP, "manual")

        # Act
        pins = pins_of(cpu, "fetch")

        # Assert
        self.assertEqual(pins[2:], ["--m-", "----"])

    def test_the_opcode_appears_on_the_third(self) -> None:
        # Arrange
        cpu = shaped(NOP, "manual")

        # Act
        values = [value for _, value, _ in entries_of(cpu, "fetch")]

        # Assert
        self.assertEqual(values, [None, None, 0x00, None])

    def test_the_recorded_shape_strobes_for_one_state_only(self) -> None:
        # Arrange
        cpu = shaped(NOP, "recording")

        # Act
        pins = pins_of(cpu, "fetch")

        # Assert
        self.assertEqual(pins, ["----", "r-m-", "----", "----"])

    def test_and_puts_the_same_addresses_and_value_where_the_manual_does(self) -> None:
        # Arrange
        shapes = ("manual", "recording")

        # Act
        found = {shape: [entry[:2] for entry in shaped(NOP, shape).bus.log] for shape in shapes}

        # Assert
        self.assertEqual(found["manual"], found["recording"])


class MemoryTest(unittest.TestCase):
    def test_a_read_holds_one_address_throughout(self) -> None:
        # Arrange
        cpu = read_from("manual")

        # Act
        addresses = {address for address, _, _ in entries_of(cpu, "read")}

        # Assert
        self.assertEqual(addresses, {0x2000})

    def test_a_read_latches_its_value_at_the_end(self) -> None:
        # Arrange
        cpu = read_from("manual")

        # Act
        values = [value for _, value, _ in entries_of(cpu, "read")]

        # Assert
        self.assertEqual(values, [None, None, 0x42])

    def test_a_write_asserts_memory_request_before_the_write_strobe(self) -> None:
        # Arrange
        cpu = shaped(STORE_THROUGH_HL, "manual", {"hl": 0x2000, "a": 0x42})

        # Act
        pins = pins_of(cpu, "write")

        # Assert
        self.assertEqual(pins, ["--m-", "-wm-", "----"])

    def test_a_write_drives_its_value_from_the_start_because_the_part_is_driving(self) -> None:
        # Arrange
        cpu = shaped(STORE_THROUGH_HL, "manual", {"hl": 0x2000, "a": 0x42})

        # Act
        values = [value for _, value, _ in entries_of(cpu, "write")]

        # Assert
        self.assertEqual(values, [0x42, 0x42, 0x42])

    def test_the_recorded_shape_reads_with_a_single_state_strobe(self) -> None:
        # Arrange
        cpu = read_from("recording")

        # Act
        pins = pins_of(cpu, "read")

        # Assert
        self.assertEqual(pins, ["----", "r-m-", "----"])

    def test_and_writes_with_one_too(self) -> None:
        # Arrange
        cpu = shaped(STORE_THROUGH_HL, "recording", {"hl": 0x2000, "a": 0x42})

        # Act
        pins = pins_of(cpu, "write")

        # Assert
        self.assertEqual(pins, ["----", "-wm-", "----"])

    def test_and_shows_the_written_value_only_while_the_strobe_is_down(self) -> None:
        # Arrange
        cpu = shaped(STORE_THROUGH_HL, "recording", {"hl": 0x2000, "a": 0x42})

        # Act
        values = [value for _, value, _ in entries_of(cpu, "write")]

        # Assert
        self.assertEqual(values, [None, 0x42, None])

    def test_a_read_and_a_write_never_assert_the_same_pins(self) -> None:
        # Arrange
        reading = read_from("manual")
        writing = shaped(STORE_THROUGH_HL, "manual", {"hl": 0x2000, "a": 0x42})

        # Act
        strobed = (
            {pins for pins in pins_of(reading, "read") if "r" in pins},
            {pins for pins in pins_of(writing, "write") if "w" in pins},
        )

        # Assert
        self.assertEqual(strobed, ({"r-m-"}, {"-wm-"}))


class PortTest(unittest.TestCase):
    def test_a_port_read_asserts_read_and_the_port_request(self) -> None:
        # Arrange
        cpu = shaped(INPUT_IMMEDIATE, "manual", {"a": 0x12}, ports=port_with(0x42))

        # Act
        pins = pins_of(cpu, "portRead")

        # Assert
        self.assertEqual(pins[2], "r--i")

    def test_a_port_write_asserts_write_and_the_port_request(self) -> None:
        # Arrange
        cpu = shaped(OUTPUT_IMMEDIATE, "manual", {"a": 0x12})

        # Act
        pins = pins_of(cpu, "portWrite")

        # Assert
        self.assertEqual(pins[2], "-w-i")

    def test_the_request_falls_a_whole_state_later_than_a_memory_one(self) -> None:
        # Arrange
        cpu = shaped(INPUT_IMMEDIATE, "manual", {"a": 0x12}, ports=port_with(0x42))

        # Act
        pins = pins_of(cpu, "portRead")

        # Assert
        self.assertEqual(pins, ["----", "r--i", "r--i", "----"])

    def test_a_port_read_latches_its_value_at_the_end(self) -> None:
        # Arrange
        cpu = shaped(INPUT_IMMEDIATE, "manual", {"a": 0x12}, ports=port_with(0x42))

        # Act
        values = [value for _, value, _ in entries_of(cpu, "portRead")]

        # Assert
        self.assertEqual(values, [None, None, None, 0x42])

    def test_a_port_write_drives_its_value_from_the_first_state(self) -> None:
        # Arrange
        cpu = shaped(OUTPUT_IMMEDIATE, "manual", {"a": 0x12})

        # Act
        values = [value for _, value, _ in entries_of(cpu, "portWrite")]

        # Assert
        self.assertEqual(values, [0x12] * 4)

    def test_and_strobes_the_three_states_after_the_address_settles(self) -> None:
        # Arrange
        cpu = shaped(OUTPUT_IMMEDIATE, "manual", {"a": 0x12})

        # Act
        pins = pins_of(cpu, "portWrite")

        # Assert
        self.assertEqual(pins, ["----", "-w-i", "-w-i", "----"])

    def test_a_port_uses_all_sixteen_address_lines(self) -> None:
        # Arrange
        cpu = shaped(INPUT_THROUGH_C, "manual", {"bc": 0xABCD})

        # Act
        addresses = {address for address, _, _ in entries_of(cpu, "portRead")}

        # Assert
        self.assertEqual(addresses, {0xABCD})

    def test_the_recorded_shape_strobes_the_wait_state_alone(self) -> None:
        # Arrange
        cpu = shaped(INPUT_IMMEDIATE, "recording", {"a": 0x12}, ports=port_with(0x42))

        # Act
        pins = pins_of(cpu, "portRead")

        # Assert
        self.assertEqual(pins, ["----", "----", "r--i", "----"])

    def test_and_writes_the_same_way(self) -> None:
        # Arrange
        cpu = shaped(OUTPUT_IMMEDIATE, "recording", {"a": 0x12})

        # Act
        pins = pins_of(cpu, "portWrite")

        # Assert
        self.assertEqual(pins, ["----", "----", "-w-i", "----"])


class AcknowledgeTest(unittest.TestCase):
    def test_it_draws_the_six_states_the_figure_draws(self) -> None:
        # Arrange
        cpu = acknowledged("manual")

        # Act
        drawn = [pins for _, _, pins in cpu.bus.log[:6]]

        # Assert
        self.assertEqual(drawn, ["----", "----", "---i", "---i", "--m-", "----"])

    def test_the_state_the_figure_does_not_draw_follows_it_with_no_pin(self) -> None:
        # Arrange
        cpu = acknowledged("manual")

        # Act
        following = (cpu.bus.cycles[1][0], cpu.bus.log[6][2])

        # Assert
        self.assertEqual(following, (7, "----"))

    def test_it_never_asserts_the_read_strobe(self) -> None:
        # Arrange
        cpu = acknowledged("manual")

        # Act
        reads = [pins.count("r") for _, _, pins in cpu.bus.log[:6]]

        # Assert
        self.assertEqual(reads, [0] * 6)

    def test_the_refresh_address_reaches_the_bus_for_the_last_two(self) -> None:
        # Arrange
        cpu = acknowledged("manual")

        # Act
        addresses = [address for address, _, _ in cpu.bus.log[4:6]]

        # Assert
        self.assertEqual(addresses, [0x5678] * 2)

    def test_the_vector_arrives_on_the_second_wait_state(self) -> None:
        # Arrange
        cpu = acknowledged("manual")

        # Act
        values = [value for _, value, _ in cpu.bus.log[:6]]

        # Assert
        self.assertEqual(values, [None, None, None, 0xFF, None, None])

    def test_the_recorded_shape_strobes_that_one_state_alone(self) -> None:
        # Arrange
        cpu = acknowledged("recording")

        # Act
        drawn = [pins for _, _, pins in cpu.bus.log[:6]]

        # Assert
        self.assertEqual(drawn, ["----"] * 3 + ["---i"] + ["----"] * 2)

    def test_and_costs_the_same_either_way(self) -> None:
        # Arrange
        shapes = ("manual", "recording")

        # Act
        found = {shape: acknowledged(shape).bus.states for shape in shapes}

        # Assert
        self.assertEqual(found["manual"], found["recording"])


if __name__ == "__main__":
    unittest.main()
