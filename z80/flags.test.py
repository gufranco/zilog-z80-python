import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from z80 import flags


class BitTest(unittest.TestCase):
    def test_the_two_undocumented_bits_are_the_ones_nobody_named(self):
        self.assertEqual(flags.X, 0x08)
        self.assertEqual(flags.Y, 0x20)

    def test_the_documented_bits_are_where_the_datasheet_puts_them(self):
        self.assertEqual(flags.C, 0x01)
        self.assertEqual(flags.N, 0x02)
        self.assertEqual(flags.PV, 0x04)
        self.assertEqual(flags.H, 0x10)
        self.assertEqual(flags.Z, 0x40)
        self.assertEqual(flags.S, 0x80)

    def test_the_eight_bits_account_for_the_whole_register(self):
        every = flags.C | flags.N | flags.PV | flags.X | flags.H | flags.Y | flags.Z | flags.S

        self.assertEqual(every, 0xFF)


class UndocumentedTest(unittest.TestCase):
    def test_the_hidden_bits_are_copied_from_the_result(self):
        self.assertEqual(flags.undocumented(0xFF), flags.X | flags.Y)

    def test_a_result_with_neither_bit_sets_neither(self):
        self.assertEqual(flags.undocumented(0x00), 0)

    def test_each_bit_comes_from_its_own_position_in_the_result(self):
        self.assertEqual(flags.undocumented(0x08), flags.X)
        self.assertEqual(flags.undocumented(0x20), flags.Y)


class ParityTest(unittest.TestCase):
    def test_an_even_number_of_set_bits_is_even_parity(self):
        self.assertEqual(flags.parity(0x03), flags.PV)

    def test_an_odd_number_is_not(self):
        self.assertEqual(flags.parity(0x07), 0)

    def test_no_bits_at_all_counts_as_even(self):
        self.assertEqual(flags.parity(0x00), flags.PV)

    def test_the_table_agrees_with_counting_the_bits(self):
        for value in range(256):
            expected = flags.PV if bin(value).count("1") % 2 == 0 else 0

            self.assertEqual(flags.parity(value), expected, f"{value:02X}")


class SignZeroTest(unittest.TestCase):
    def test_a_result_with_the_top_bit_set_is_negative(self):
        self.assertTrue(flags.sign_zero(0x80) & flags.S)

    def test_a_result_of_zero_says_so(self):
        self.assertTrue(flags.sign_zero(0x00) & flags.Z)

    def test_a_result_that_is_neither_says_neither(self):
        self.assertEqual(flags.sign_zero(0x01) & (flags.S | flags.Z), 0)

    def test_it_carries_the_hidden_bits_too(self):
        self.assertEqual(flags.sign_zero(0x28) & (flags.X | flags.Y), flags.X | flags.Y)


class WideSignZeroTest(unittest.TestCase):
    def test_a_sixteen_bit_result_takes_its_sign_from_the_high_byte(self):
        self.assertTrue(flags.sign_zero16(0x8000) & flags.S)

    def test_and_its_hidden_bits_from_the_high_byte(self):
        self.assertEqual(flags.sign_zero16(0x2800) & (flags.X | flags.Y), flags.X | flags.Y)

    def test_zero_is_decided_by_the_whole_sixteen_bits(self):
        self.assertTrue(flags.sign_zero16(0x0000) & flags.Z)
        self.assertFalse(flags.sign_zero16(0x0001) & flags.Z)


if __name__ == "__main__":
    unittest.main()
