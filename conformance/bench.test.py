import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance import bench


class FlagTest(unittest.TestCase):
    def test_each_flag_is_the_bit_table_21_gives_it(self) -> None:
        # Arrange
        expected = {
            "c": 0x01,
            "n": 0x02,
            "pv": 0x04,
            "x": 0x08,
            "h": 0x10,
            "y": 0x20,
            "z": 0x40,
            "s": 0x80,
        }

        # Act
        found = dict(bench.FLAG)

        # Assert
        self.assertEqual(found, expected)


class LoadedTest(unittest.TestCase):
    def test_a_loaded_part_is_poised_on_the_first_byte_of_its_program(self) -> None:
        # Arrange
        program = (0x3E, 0x42)

        # Act
        cpu = bench.loaded(program, {"b": 0x07})

        # Assert
        self.assertEqual(
            (cpu.registers.pc, cpu.registers.sp, cpu.registers.b, cpu.memory.read8(0x0101)),
            (0x0100, 0x8000, 0x07, 0x42),
        )

    def test_a_part_loaded_without_recording_keeps_no_log(self) -> None:
        # Arrange
        program = (0x00,)

        # Act
        cpu = bench.ran(program, recording=False)

        # Assert
        self.assertEqual((cpu.bus.states, cpu.bus.log), (4, []))

    def test_and_it_is_the_model_it_was_asked_for(self) -> None:
        # Arrange
        model = "z84c00"

        # Act
        cpu = bench.loaded((0x00,), model=model)

        # Assert
        self.assertEqual(cpu.model, model)


class RanTest(unittest.TestCase):
    def test_a_run_executes_one_instruction(self) -> None:
        # Arrange
        program = (0x3E, 0x42)

        # Act
        cpu = bench.ran(program)

        # Assert
        self.assertEqual((cpu.registers.a, cpu.registers.pc), (0x42, 0x0102))

    def test_a_no_operation_spends_the_four_states_page_180_prints(self) -> None:
        # Arrange
        program = (0x00,)

        # Act
        states = bench.spent(program)

        # Assert
        self.assertEqual(states, 4)


class CycleTest(unittest.TestCase):
    def test_an_immediate_load_is_a_fetch_then_a_read(self) -> None:
        # Arrange
        cpu = bench.ran((0x06, 0x42))

        # Act
        lengths = bench.cycle_lengths(cpu)

        # Assert
        self.assertEqual(lengths, [4, 3])

    def test_and_every_state_is_named_after_its_cycle(self) -> None:
        # Arrange
        cpu = bench.ran((0x06, 0x42))

        # Act
        names = bench.cycle_names(cpu)

        # Assert
        self.assertEqual(names, ["fetch"] * 4 + ["read"] * 3)

    def test_the_states_of_one_kind_of_cycle_are_picked_out(self) -> None:
        # Arrange
        cpu = bench.ran((0x06, 0x42))

        # Act
        entries = bench.entries_of(cpu, "read")

        # Assert
        self.assertEqual(
            entries, [(0x0101, None, "r-m-"), (0x0101, None, "r-m-"), (0x0101, 0x42, "----")]
        )

    def test_the_pins_of_one_kind_of_cycle_are_picked_out(self) -> None:
        # Arrange
        cpu = bench.ran((0x06, 0x42))

        # Act
        pins = bench.pins_of(cpu, "read")

        # Assert
        self.assertEqual(pins, ["r-m-", "r-m-", "----"])


class ShapedTest(unittest.TestCase):
    def test_a_shaped_run_carries_the_refresh_address_it_was_given(self) -> None:
        # Arrange
        program = (0x00,)

        # Act
        cpu = bench.shaped(program, "recording")

        # Assert
        self.assertEqual(
            [(address, pins) for address, _, pins in cpu.bus.log[1:]],
            [(0x0100, "r-m-"), (0x5678, "----"), (0x5678, "----")],
        )

    def test_an_acknowledged_part_has_restarted_where_mode_one_goes(self) -> None:
        # Arrange
        shape = "manual"

        # Act
        cpu = bench.acknowledged(shape)

        # Assert
        self.assertEqual((cpu.registers.pc, cpu.bus.cycles[0]), (0x0038, (0, "acknowledge")))


class RowTest(unittest.TestCase):
    def test_a_row_is_found_by_the_page_it_was_printed_on(self) -> None:
        # Arrange
        page = 72

        # Act
        found = bench.row(page)

        # Assert
        self.assertEqual((found["tStates"], found["machineCycles"]), (7, [4, 3]))


if __name__ == "__main__":
    unittest.main()
