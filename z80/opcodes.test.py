import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from z80 import opcodes


def render(program: list[int], at: int = 0x8000) -> str:
    return opcodes.decode(bytes(program), 0, at).text


class SimpleTest(unittest.TestCase):
    def test_the_instruction_that_does_nothing_is_named(self) -> None:
        self.assertEqual(render([0x00]), "nop")

    def test_a_register_to_register_load_names_both(self) -> None:
        self.assertEqual(render([0x47]), "ld b,a")

    def test_a_load_through_the_working_pair_says_so(self) -> None:
        self.assertEqual(render([0x7E]), "ld a,(hl)")

    def test_an_immediate_load_shows_the_byte(self) -> None:
        self.assertEqual(render([0x3E, 0x42]), "ld a,$42")

    def test_a_wide_immediate_load_shows_the_word(self) -> None:
        self.assertEqual(render([0x21, 0x34, 0x12]), "ld hl,$1234")

    def test_arithmetic_against_a_register_names_it(self) -> None:
        self.assertEqual(render([0x80]), "add a,b")

    def test_arithmetic_against_a_byte_shows_it(self) -> None:
        self.assertEqual(render([0xC6, 0x10]), "add a,$10")

    def test_a_compare_is_not_written_as_a_subtract(self) -> None:
        self.assertEqual(render([0xFE, 0x10]), "cp $10")


class ControlTest(unittest.TestCase):
    def test_a_jump_shows_where(self) -> None:
        self.assertEqual(render([0xC3, 0x34, 0x12]), "jp $1234")

    def test_a_conditional_jump_shows_the_condition_first(self) -> None:
        self.assertEqual(render([0xC2, 0x34, 0x12]), "jp nz,$1234")

    def test_a_relative_jump_is_resolved_to_where_it_lands(self) -> None:
        self.assertEqual(render([0x18, 0x10]), "jr $8012")

    def test_a_backward_relative_jump_resolves_the_same_way(self) -> None:
        self.assertEqual(render([0x18, 0xFC]), "jr $7FFE")

    def test_the_counted_loop_is_named_for_what_it_counts(self) -> None:
        self.assertEqual(render([0x10, 0xFE]), "djnz $8000")

    def test_a_restart_shows_its_fixed_address(self) -> None:
        self.assertEqual(render([0xFF]), "rst $38")

    def test_a_call_shows_where(self) -> None:
        self.assertEqual(render([0xCD, 0x34, 0x12]), "call $1234")

    def test_a_conditional_return_names_the_condition(self) -> None:
        self.assertEqual(render([0xC8]), "ret z")


class PrefixTest(unittest.TestCase):
    def test_a_bit_test_names_the_bit_and_the_register(self) -> None:
        self.assertEqual(render([0xCB, 0x47]), "bit 0,a")

    def test_a_shift_names_the_register(self) -> None:
        self.assertEqual(render([0xCB, 0x00]), "rlc b")

    def test_a_bit_clear_is_distinct_from_a_bit_set(self) -> None:
        self.assertEqual(render([0xCB, 0x87]), "res 0,a")
        self.assertEqual(render([0xCB, 0xC7]), "set 0,a")

    def test_an_index_register_replaces_the_working_pair(self) -> None:
        self.assertEqual(render([0xDD, 0x21, 0x34, 0x12]), "ld ix,$1234")

    def test_and_brings_a_displacement_with_it(self) -> None:
        self.assertEqual(render([0xDD, 0x7E, 0x05]), "ld a,(ix+$05)")

    def test_a_negative_displacement_is_shown_as_one(self) -> None:
        self.assertEqual(render([0xDD, 0x7E, 0xFB]), "ld a,(ix-$05)")

    def test_the_other_index_register_is_named_correctly(self) -> None:
        self.assertEqual(render([0xFD, 0x7E, 0x05]), "ld a,(iy+$05)")

    def test_the_halves_of_an_index_register_have_their_own_names(self) -> None:
        self.assertEqual(render([0xDD, 0x44]), "ld b,ixh")

    def test_a_doubly_prefixed_bit_instruction_puts_the_displacement_first(self) -> None:
        self.assertEqual(render([0xDD, 0xCB, 0x05, 0x46]), "bit 0,(ix+$05)")

    def test_a_doubly_prefixed_shift_names_the_register_it_also_writes(self) -> None:
        self.assertEqual(render([0xDD, 0xCB, 0x05, 0x00]), "rlc (ix+$05),b")


class ExtendedTest(unittest.TestCase):
    def test_a_port_read_through_the_pair_is_named(self) -> None:
        self.assertEqual(render([0xED, 0x40]), "in b,(c)")

    def test_a_port_write_with_no_source_says_so(self) -> None:
        self.assertEqual(render([0xED, 0x71]), "out (c),0")

    def test_a_wide_subtract_with_carry_is_distinct_from_the_add(self) -> None:
        self.assertEqual(render([0xED, 0x42]), "sbc hl,bc")
        self.assertEqual(render([0xED, 0x4A]), "adc hl,bc")

    def test_the_block_move_is_named(self) -> None:
        self.assertEqual(render([0xED, 0xB0]), "ldir")

    def test_the_interrupt_mode_is_shown(self) -> None:
        self.assertEqual(render([0xED, 0x5E]), "im 2")

    def test_an_extended_opcode_that_names_nothing_is_reported_as_such(self) -> None:
        self.assertEqual(render([0xED, 0x00]), "db $ed,$00")


class LengthTest(unittest.TestCase):
    def test_an_instruction_reports_how_many_bytes_it_took(self) -> None:
        self.assertEqual(opcodes.decode(bytes([0x21, 0x34, 0x12]), 0, 0).size, 3)

    def test_a_prefixed_instruction_counts_its_prefix(self) -> None:
        self.assertEqual(opcodes.decode(bytes([0xDD, 0x7E, 0x05]), 0, 0).size, 3)

    def test_a_doubly_prefixed_instruction_counts_all_four(self) -> None:
        self.assertEqual(opcodes.decode(bytes([0xDD, 0xCB, 0x05, 0x46]), 0, 0).size, 4)

    def test_an_instruction_cut_short_by_the_end_of_the_data_is_refused(self) -> None:
        with self.assertRaises(opcodes.Truncated):
            opcodes.decode(bytes([0x21, 0x34]), 0, 0)

    def test_a_prefix_with_nothing_after_it_is_refused_too(self) -> None:
        with self.assertRaises(opcodes.Truncated):
            opcodes.decode(bytes([0xDD]), 0, 0)


class ListingTest(unittest.TestCase):
    def test_a_run_of_bytes_becomes_a_run_of_instructions(self) -> None:
        listing = opcodes.disassemble(bytes([0x00, 0x00, 0xC9]), 0x8000)

        self.assertEqual([entry.text for entry in listing], ["nop", "nop", "ret"])

    def test_each_instruction_knows_where_it_sat(self) -> None:
        listing = opcodes.disassemble(bytes([0x00, 0xC9]), 0x8000)

        self.assertEqual([entry.address for entry in listing], [0x8000, 0x8001])

    def test_a_trailing_byte_that_cannot_finish_is_shown_as_data(self) -> None:
        listing = opcodes.disassemble(bytes([0x00, 0x21]), 0x8000)

        self.assertEqual(listing[-1].text, "db $21")

    def test_and_the_listing_picks_up_again_from_the_byte_after_it(self) -> None:
        listing = opcodes.disassemble(bytes([0x00, 0x21, 0x34]), 0x8000)

        self.assertEqual([entry.text for entry in listing], ["nop", "db $21", "inc (hl)"])

    def test_an_empty_run_produces_an_empty_listing(self) -> None:
        self.assertEqual(opcodes.disassemble(b"", 0x8000), [])


if __name__ == "__main__":
    unittest.main()
