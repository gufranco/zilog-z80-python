import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.bench import FLAG, row, spent


class OperationTimingTest(unittest.TestCase):
    def test_an_arithmetic_register_operation_costs_what_page_145_says(self) -> None:
        # Arrange
        program = (0x80,)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(145)["tStates"])

    def test_an_arithmetic_immediate_costs_what_page_147_says(self) -> None:
        # Arrange
        program = (0xC6, 0x00)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(147)["tStates"])

    def test_arithmetic_through_the_pair_costs_what_page_148_says(self) -> None:
        # Arrange
        program = (0x86,)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(148)["tStates"])

    def test_indexed_arithmetic_costs_what_page_149_says(self) -> None:
        # Arrange
        program = (0xDD, 0x86, 0x01)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(149)["tStates"])

    def test_incrementing_a_register_costs_what_page_165_says(self) -> None:
        # Arrange
        program = (0x04,)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(165)["tStates"])

    def test_incrementing_through_the_pair_costs_what_page_167_says(self) -> None:
        # Arrange
        program = (0x34,)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(167)["tStates"])

    def test_incrementing_through_an_index_costs_what_page_168_says(self) -> None:
        # Arrange
        program = (0xDD, 0x34, 0x01)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(168)["tStates"])

    def test_the_decimal_adjust_costs_what_page_174_says(self) -> None:
        # Arrange
        program = (0x27,)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(174)["tStates"])

    def test_complementing_the_accumulator_costs_what_page_175_says(self) -> None:
        # Arrange
        program = (0x2F,)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(175)["tStates"])

    def test_negating_it_costs_what_page_176_says(self) -> None:
        # Arrange
        program = (0xED, 0x44)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(176)["tStates"])

    def test_the_no_operation_costs_what_page_180_says(self) -> None:
        # Arrange
        program = (0x00,)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(180)["tStates"])

    def test_disabling_interrupts_costs_what_page_182_says(self) -> None:
        # Arrange
        program = (0xF3,)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(182)["tStates"])

    def test_a_wide_add_costs_what_page_188_says(self) -> None:
        # Arrange
        program = (0x09,)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(188)["tStates"])

    def test_a_wide_add_with_carry_costs_what_page_190_says(self) -> None:
        # Arrange
        program = (0xED, 0x4A)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(190)["tStates"])

    def test_an_indexed_wide_add_costs_what_page_194_says(self) -> None:
        # Arrange
        program = (0xDD, 0x09)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(194)["tStates"])

    def test_incrementing_a_pair_costs_what_page_198_says(self) -> None:
        # Arrange
        program = (0x03,)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(198)["tStates"])

    def test_incrementing_an_index_costs_what_page_199_says(self) -> None:
        # Arrange
        program = (0xDD, 0x23)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(199)["tStates"])

    def test_rotating_the_accumulator_costs_what_page_205_says(self) -> None:
        # Arrange
        program = (0x07,)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(205)["tStates"])

    def test_rotating_a_register_costs_what_page_213_says(self) -> None:
        # Arrange
        program = (0xCB, 0x00)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(213)["tStates"])

    def test_the_nibble_rotate_costs_what_page_238_says(self) -> None:
        # Arrange
        program = (0xED, 0x6F)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(238)["tStates"])

    def test_an_unconditional_jump_costs_what_page_262_says(self) -> None:
        # Arrange
        program = (0xC3, 0x00, 0x20)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(262)["tStates"])

    def test_a_jump_through_the_pair_costs_what_page_275_says(self) -> None:
        # Arrange
        program = (0xE9,)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(275)["tStates"])

    def test_an_unconditional_call_costs_what_page_281_says(self) -> None:
        # Arrange
        program = (0xCD, 0x00, 0x20)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(281)["tStates"])

    def test_a_return_costs_what_page_285_says(self) -> None:
        # Arrange
        program = (0xC9,)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(285)["tStates"])

    def test_a_restart_costs_what_page_293_says(self) -> None:
        # Arrange
        program = (0xC7,)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(293)["tStates"])

    def test_an_immediate_input_costs_what_page_295_says(self) -> None:
        # Arrange
        program = (0xDB, 0x00)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(295)["tStates"])

    def test_a_register_input_costs_what_page_296_says(self) -> None:
        # Arrange
        program = (0xED, 0x40)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(296)["tStates"])

    def test_an_immediate_output_costs_what_page_306_says(self) -> None:
        # Arrange
        program = (0xD3, 0x00)

        # Act
        states = spent(program)

        # Assert
        self.assertEqual(states, row(306)["tStates"])


class ConditionalTimingTest(unittest.TestCase):
    def test_a_relative_jump_taken_costs_more_than_one_not_taken(self) -> None:
        # Arrange
        program = (0x20, 0x02)

        # Act
        taken, passed = spent(program, {"f": 0x00}), spent(program, {"f": FLAG["z"]})

        # Assert
        self.assertEqual(taken - passed, 5)

    def test_a_conditional_call_taken_costs_more_than_one_not_taken(self) -> None:
        # Arrange
        program = (0xC4, 0x00, 0x20)

        # Act
        taken, passed = spent(program, {"f": 0x00}), spent(program, {"f": FLAG["z"]})

        # Assert
        self.assertEqual(taken - passed, 7)

    def test_a_conditional_return_taken_costs_more_than_one_not_taken(self) -> None:
        # Arrange
        program = (0xC0,)

        # Act
        taken, passed = spent(program, {"f": 0x00}), spent(program, {"f": FLAG["z"]})

        # Assert
        self.assertEqual(taken - passed, 6)

    def test_a_decrementing_branch_taken_costs_more_than_one_not_taken(self) -> None:
        # Arrange
        program = (0x10, 0x02)

        # Act
        taken, passed = spent(program, {"b": 5}), spent(program, {"b": 1})

        # Assert
        self.assertEqual(taken - passed, 5)

    def test_a_repeating_block_move_costs_more_while_it_repeats(self) -> None:
        # Arrange
        program = (0xED, 0xB0)

        # Act
        repeating, last = spent(program, {"bc": 4}), spent(program, {"bc": 1})

        # Assert
        self.assertEqual(repeating - last, 5)


if __name__ == "__main__":
    unittest.main()
