import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.bench import row, spent


class LoadTimingTest(unittest.TestCase):
    def test_a_register_to_register_load_costs_what_page_71_says(self) -> None:
        # Arrange
        program = (0x41,)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(71)["tStates"])

    def test_an_immediate_load_costs_what_page_72_says(self) -> None:
        # Arrange
        program = (0x06, 0x00)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(72)["tStates"])

    def test_a_load_through_the_pair_costs_what_page_74_says(self) -> None:
        # Arrange
        program = (0x46,)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(74)["tStates"])

    def test_an_indexed_load_costs_what_page_75_says(self) -> None:
        # Arrange
        program = (0xDD, 0x46, 0x01)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(75)["tStates"])

    def test_a_store_through_the_pair_costs_what_page_79_says(self) -> None:
        # Arrange
        program = (0x70,)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(79)["tStates"])

    def test_an_indexed_store_costs_what_page_81_says(self) -> None:
        # Arrange
        program = (0xDD, 0x70, 0x01)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(81)["tStates"])

    def test_an_immediate_store_through_the_pair_costs_what_page_85_says(self) -> None:
        # Arrange
        program = (0x36, 0x00)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(85)["tStates"])

    def test_an_indexed_immediate_store_costs_what_page_86_says(self) -> None:
        # Arrange
        program = (0xDD, 0x36, 0x01, 0x00)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(86)["tStates"])

    def test_a_load_through_a_pair_costs_what_page_88_says(self) -> None:
        # Arrange
        program = (0x0A,)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(88)["tStates"])

    def test_an_extended_load_costs_what_page_90_says(self) -> None:
        # Arrange
        program = (0x3A, 0x00, 0x20)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(90)["tStates"])

    def test_reading_the_interrupt_register_costs_what_page_94_says(self) -> None:
        # Arrange
        program = (0xED, 0x57)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(94)["tStates"])

    def test_writing_it_costs_what_page_96_says(self) -> None:
        # Arrange
        program = (0xED, 0x47)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(96)["tStates"])

    def test_a_wide_immediate_load_costs_what_page_99_says(self) -> None:
        # Arrange
        program = (0x01, 0x00, 0x20)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(99)["tStates"])

    def test_an_indexed_wide_immediate_load_costs_what_page_100_says(self) -> None:
        # Arrange
        program = (0xDD, 0x21, 0x00, 0x20)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(100)["tStates"])

    def test_a_wide_extended_load_costs_what_page_102_says(self) -> None:
        # Arrange
        program = (0x2A, 0x00, 0x20)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(102)["tStates"])

    def test_the_extended_form_of_it_costs_what_page_103_says(self) -> None:
        # Arrange
        program = (0xED, 0x4B, 0x00, 0x20)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(103)["tStates"])

    def test_a_wide_extended_store_costs_what_page_107_says(self) -> None:
        # Arrange
        program = (0x22, 0x00, 0x20)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(107)["tStates"])

    def test_loading_the_stack_pointer_costs_what_page_112_says(self) -> None:
        # Arrange
        program = (0xF9,)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(112)["tStates"])

    def test_a_push_costs_what_page_115_says(self) -> None:
        # Arrange
        program = (0xC5,)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(115)["tStates"])

    def test_an_indexed_push_costs_what_page_117_says(self) -> None:
        # Arrange
        program = (0xDD, 0xE5)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(117)["tStates"])

    def test_a_pop_costs_what_page_119_says(self) -> None:
        # Arrange
        program = (0xC1,)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(119)["tStates"])

    def test_exchanging_the_pairs_costs_what_page_124_says(self) -> None:
        # Arrange
        program = (0xEB,)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(124)["tStates"])

    def test_exchanging_the_shadow_set_costs_what_page_126_says(self) -> None:
        # Arrange
        program = (0xD9,)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(126)["tStates"])

    def test_exchanging_through_the_stack_costs_what_page_127_says(self) -> None:
        # Arrange
        program = (0xE3,)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(127)["tStates"])

    def test_a_block_move_costs_what_page_130_says(self) -> None:
        # Arrange
        program = (0xED, 0xA0)

        # Act
        states = spent(program, {"bc": 1})

        # Assert
        self.assertEqual(states, row(130)["tStates"])

    def test_a_block_compare_costs_what_page_138_says(self) -> None:
        # Arrange
        program = (0xED, 0xA1)

        # Act
        states = spent(program, {"bc": 1})

        # Assert
        self.assertEqual(states, row(138)["tStates"])


if __name__ == "__main__":
    unittest.main()
