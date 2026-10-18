import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.bench import FLAG, ran

OR_A = (0xB7,)

SCF = (0x37,)

CPL = (0x2F,)

SBC_HL_DE = (0xED, 0x52)

HIDDEN = FLAG["x"] | FLAG["y"]


def flags_after(program: tuple[int, ...], **setup: int) -> int:
    held: int = ran(program, {"f": 0x00, **setup}).registers.f
    return held


def even(value: int) -> bool:
    return bin(value).count("1") % 2 == 0


class BitTest(unittest.TestCase):
    def test_the_two_undocumented_bits_are_the_ones_nobody_named(self) -> None:
        # Arrange
        result = 0x28

        # Act
        found = flags_after(OR_A, a=result)

        # Assert
        self.assertEqual(found, 0x08 | 0x20 | 0x04)

    def test_the_documented_bits_are_where_the_datasheet_puts_them(self) -> None:
        # Arrange
        runs = {
            "carry": (SCF, {"a": 0x00}),
            "half carry and negate": (CPL, {"a": 0x00}),
            "sign": (OR_A, {"a": 0x80}),
            "zero and parity": (OR_A, {"a": 0x00}),
        }

        # Act
        found = {name: flags_after(program, **setup) for name, (program, setup) in runs.items()}

        # Assert
        self.assertEqual(
            found,
            {
                "carry": 0x01,
                "half carry and negate": 0x10 | 0x02 | 0x08 | 0x20,
                "sign": 0x80,
                "zero and parity": 0x40 | 0x04,
            },
        )

    def test_the_eight_bits_account_for_the_whole_register(self) -> None:
        # Arrange
        runs = ((SCF, 0x00), (CPL, 0x00), (OR_A, 0x80), (OR_A, 0x00), (OR_A, 0x28))

        # Act
        every = 0
        for program, accumulator in runs:
            every |= flags_after(program, a=accumulator)

        # Assert
        self.assertEqual(every, 0xFF)


class UndocumentedTest(unittest.TestCase):
    def test_the_hidden_bits_are_copied_from_the_result(self) -> None:
        # Arrange
        result = 0xFF

        # Act
        found = flags_after(OR_A, a=result) & HIDDEN

        # Assert
        self.assertEqual(found, 0x28)

    def test_a_result_with_neither_bit_sets_neither(self) -> None:
        # Arrange
        result = 0xD7

        # Act
        found = flags_after(OR_A, a=result) & HIDDEN

        # Assert
        self.assertEqual(found, 0)

    def test_each_bit_comes_from_its_own_position_in_the_result(self) -> None:
        # Arrange
        results = (0x08, 0x20)

        # Act
        found = [flags_after(OR_A, a=result) & HIDDEN for result in results]

        # Assert
        self.assertEqual(found, [0x08, 0x20])


class ParityTest(unittest.TestCase):
    def test_an_even_number_of_set_bits_is_even_parity(self) -> None:
        # Arrange
        result = 0x03

        # Act
        found = flags_after(OR_A, a=result) & FLAG["pv"]

        # Assert
        self.assertEqual(found, 0x04)

    def test_an_odd_number_is_not(self) -> None:
        # Arrange
        result = 0x07

        # Act
        found = flags_after(OR_A, a=result) & FLAG["pv"]

        # Assert
        self.assertEqual(found, 0)

    def test_no_bits_at_all_counts_as_even(self) -> None:
        # Arrange
        result = 0x00

        # Act
        found = flags_after(OR_A, a=result) & FLAG["pv"]

        # Assert
        self.assertEqual(found, 0x04)

    def test_every_result_agrees_with_counting_its_bits(self) -> None:
        # Arrange
        results = range(256)

        # Act
        found = {value: bool(flags_after(OR_A, a=value) & FLAG["pv"]) for value in results}

        # Assert
        self.assertEqual(found, {value: even(value) for value in results})


class SignZeroTest(unittest.TestCase):
    def test_a_result_with_the_top_bit_set_is_negative(self) -> None:
        # Arrange
        result = 0x80

        # Act
        found = flags_after(OR_A, a=result) & FLAG["s"]

        # Assert
        self.assertEqual(found, 0x80)

    def test_a_result_of_zero_says_so(self) -> None:
        # Arrange
        result = 0x00

        # Act
        found = flags_after(OR_A, a=result) & FLAG["z"]

        # Assert
        self.assertEqual(found, 0x40)

    def test_a_result_that_is_neither_says_neither(self) -> None:
        # Arrange
        result = 0x01

        # Act
        found = flags_after(OR_A, a=result) & (FLAG["s"] | FLAG["z"])

        # Assert
        self.assertEqual(found, 0)

    def test_it_carries_the_hidden_bits_too(self) -> None:
        # Arrange
        result = 0x28

        # Act
        found = flags_after(OR_A, a=result) & HIDDEN

        # Assert
        self.assertEqual(found, 0x28)


class WideSignZeroTest(unittest.TestCase):
    def test_a_sixteen_bit_result_takes_its_sign_from_the_high_byte(self) -> None:
        # Arrange
        result = 0x8000

        # Act
        found = flags_after(SBC_HL_DE, hl=result, de=0x0000) & FLAG["s"]

        # Assert
        self.assertEqual(found, 0x80)

    def test_and_its_hidden_bits_from_the_high_byte(self) -> None:
        # Arrange
        result = 0x2800

        # Act
        found = flags_after(SBC_HL_DE, hl=result, de=0x0000) & HIDDEN

        # Assert
        self.assertEqual(found, 0x28)

    def test_zero_is_decided_by_the_whole_sixteen_bits(self) -> None:
        # Arrange
        results = (0x0000, 0x0001)

        # Act
        found = [flags_after(SBC_HL_DE, hl=result, de=0x0000) & FLAG["z"] for result in results]

        # Assert
        self.assertEqual(found, [0x40, 0])


if __name__ == "__main__":
    unittest.main()
