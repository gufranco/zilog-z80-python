import contextlib
import sys
import unittest
from pathlib import Path
from typing import ClassVar

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from z80 import registers


class PairTest(unittest.TestCase):
    def test_a_pair_reads_as_its_two_halves(self) -> None:
        file = registers.Registers()
        file.b, file.c = 0x12, 0x34

        self.assertEqual(file.bc, 0x1234)

    def test_writing_a_pair_writes_both_halves(self) -> None:
        file = registers.Registers()

        file.de = 0x1234

        self.assertEqual((file.d, file.e), (0x12, 0x34))

    def test_every_pair_the_processor_has_is_addressable_both_ways(self) -> None:
        file = registers.Registers()

        for pair, (high, low) in registers.PAIRS.items():
            setattr(file, pair, 0xABCD)

            self.assertEqual(getattr(file, high), 0xAB, pair)
            self.assertEqual(getattr(file, low), 0xCD, pair)

    def test_a_pair_wraps_at_sixteen_bits(self) -> None:
        file = registers.Registers()

        file.hl = 0x1FFFF

        self.assertEqual(file.hl, 0xFFFF)

    def test_a_half_wraps_at_eight(self) -> None:
        file = registers.Registers()

        file.a = 0x1FF

        self.assertEqual(file.a, 0xFF)


class ShadowTest(unittest.TestCase):
    def test_exchanging_the_main_set_swaps_three_pairs_and_not_the_accumulator(self) -> None:
        file = registers.Registers()
        file.bc, file.de, file.hl, file.af = 0x1111, 0x2222, 0x3333, 0x4444
        file.bc_, file.de_, file.hl_, file.af_ = 0xAAAA, 0xBBBB, 0xCCCC, 0xDDDD

        file.exchange_set()

        self.assertEqual((file.bc, file.de, file.hl), (0xAAAA, 0xBBBB, 0xCCCC))
        self.assertEqual(file.af, 0x4444)

    def test_exchanging_the_accumulator_swaps_only_that_pair(self) -> None:
        file = registers.Registers()
        file.af, file.af_ = 0x1234, 0xABCD
        file.bc = 0x1111

        file.exchange_accumulator()

        self.assertEqual((file.af, file.af_), (0xABCD, 0x1234))
        self.assertEqual(file.bc, 0x1111)

    def test_exchanging_twice_puts_everything_back(self) -> None:
        file = registers.Registers()
        file.bc, file.de, file.hl = 0x1111, 0x2222, 0x3333
        file.bc_, file.de_, file.hl_ = 0xAAAA, 0xBBBB, 0xCCCC

        file.exchange_set()
        file.exchange_set()

        self.assertEqual((file.bc, file.de, file.hl), (0x1111, 0x2222, 0x3333))


class RefreshTest(unittest.TestCase):
    def test_the_refresh_counter_advances_in_its_low_seven_bits(self) -> None:
        file = registers.Registers()
        file.r = 0x7F

        file.tick_refresh()

        self.assertEqual(file.r, 0x00)

    def test_the_top_bit_of_the_refresh_counter_is_left_alone(self) -> None:
        file = registers.Registers()
        file.r = 0xFF

        file.tick_refresh()

        self.assertEqual(file.r, 0x80)

    def test_it_advances_by_one_the_rest_of_the_time(self) -> None:
        file = registers.Registers()
        file.r = 0x40

        file.tick_refresh()

        self.assertEqual(file.r, 0x41)


class UncleanTest(unittest.TestCase):
    def test_two_files_seeded_differently_hold_different_things(self) -> None:
        first = registers.Registers(seed=1)
        second = registers.Registers(seed=2)

        self.assertNotEqual((first.a, first.bc, first.ix), (second.a, second.bc, second.ix))

    def test_the_same_seed_gives_the_same_unclean_file(self) -> None:
        first = registers.Registers(seed=7)
        second = registers.Registers(seed=7)

        self.assertEqual((first.a, first.bc, first.ix), (second.a, second.bc, second.ix))

    def test_a_reset_defines_only_what_a_reset_defines(self) -> None:
        file = registers.Registers(seed=3)

        file.reset()

        self.assertEqual(file.pc, 0x0000)
        self.assertEqual(file.i, 0x00)
        self.assertEqual(file.r, 0x00)
        self.assertEqual(file.im, 0)
        self.assertFalse(file.iff1)
        self.assertFalse(file.iff2)


class ReadingTest(unittest.TestCase):
    def test_a_register_file_prints_as_the_three_values_a_reader_wants_first(self) -> None:
        file = registers.Registers(seed=1)
        file.pc = 0x1234
        file.af = 0x5678
        file.hl = 0x9ABC

        self.assertEqual(repr(file), "<Registers pc=1234 af=5678 hl=9ABC>")


def narrower(held: object, names: tuple[str, ...], mask: int) -> list[str]:
    """Every register that kept more than its own width after an oversized write."""
    found = []
    for name in names:
        with contextlib.suppress(AttributeError):
            setattr(held, name, mask << 1 | 1)
        value = getattr(held, name)
        if value != mask:
            found.append(f"{name} kept {value:#x}")
    return found


class WidthTest(unittest.TestCase):
    """That every register masks to its own width, and to no other.

    The twenty-nine properties are written out rather than generated, which buys
    the throughput of a C descriptor and risks one of them masking to the wrong
    width. This is the answer to that risk, and it is a better one than a factory
    was: it holds whether they were typed or generated, and it names the register
    that is wrong rather than failing somewhere downstream.
    """

    BYTES: ClassVar[tuple[str, ...]] = (
        "a",
        "f",
        "b",
        "c",
        "d",
        "e",
        "h",
        "l",
        "w",
        "z",
        "ixh",
        "ixl",
        "iyh",
        "iyl",
        "i",
        "r",
    )

    WORDS: ClassVar[tuple[str, ...]] = (
        "af_",
        "bc_",
        "de_",
        "hl_",
        "pc",
        "sp",
        "af",
        "bc",
        "de",
        "hl",
        "wz",
        "ix",
        "iy",
    )

    def test_every_eight_bit_register_keeps_eight_bits(self) -> None:
        self.assertEqual(narrower(registers.Registers(), self.BYTES, 0xFF), [])

    def test_every_sixteen_bit_register_keeps_sixteen(self) -> None:
        self.assertEqual(narrower(registers.Registers(), self.WORDS, 0xFFFF), [])

    def test_the_reader_names_a_register_that_keeps_too_much(self) -> None:
        """A check nothing has been seen to fail is a check nobody knows."""

        class Wider:
            eight = 0x1FF

        self.assertEqual(narrower(Wider(), ("eight",), 0xFF), ["eight kept 0x1ff"])

    def test_the_two_lists_cover_every_register_the_class_has(self) -> None:
        """A register left out of both lists is one this check never reaches."""
        held = {
            name for name, value in vars(registers.Registers).items() if isinstance(value, property)
        }

        self.assertEqual(held, set(self.BYTES) | set(self.WORDS))

    def test_a_name_the_part_does_not_have_cannot_be_written(self) -> None:
        """The slots are the point: a wrong spelling fails instead of going nowhere."""
        held = registers.Registers()

        with self.assertRaises(AttributeError):
            held.irq_disable = False  # type: ignore[attr-defined]


if __name__ == "__main__":
    unittest.main()
