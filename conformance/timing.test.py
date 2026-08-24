"""That every timing the manual prints is reproduced by running the instruction.

The manual's tables are a transcription, so nothing in them is checked by the
conformance corpus: that corpus is a recording of another model, and this file is
the only place the core is held to Zilog for all 217 rows rather than for the
handful a hand-written case names.
"""

import contextlib
import io
import sys
import unittest
from pathlib import Path
from typing import override

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import timing  # noqa: E402

SURVEYED = timing.survey()

KNOWN = timing.catalogue()


class ExpansionTest(unittest.TestCase):
    def test_a_family_becomes_one_instruction_per_register(self) -> None:
        found = timing.spellings("SBC A, r")

        self.assertEqual(found[0], "sbc a,b")

    def test_and_covers_all_seven_of_them(self) -> None:
        found = timing.spellings("SBC A, r")

        self.assertEqual(len(found), 7)

    def test_a_row_with_no_operand_is_just_the_mnemonic(self) -> None:
        self.assertEqual(timing.spellings("NOP"), ["nop"])

    def test_the_bit_the_res_page_omits_is_put_back(self) -> None:
        found = timing.spellings("RES r")

        self.assertEqual(found[0], "res 0,b")

    def test_and_a_page_that_prints_the_bit_is_left_alone(self) -> None:
        found = timing.spellings("SET b, r")

        self.assertEqual(found[0], "set 0,b")

    def test_the_one_row_the_manual_writes_without_a_comma_still_parses(self) -> None:
        head, pieces = timing.operands("IN r (C)")

        self.assertEqual((head, pieces), ("in", ["r", "(C)"]))

    def test_the_mark_on_the_alternate_register_file_is_matched(self) -> None:
        found = timing.spellings(f"EX AF, AF{timing.PRIME}")

        self.assertEqual(found, ["ex af,af'"])


class RelativeTest(unittest.TestCase):
    def test_an_ordinary_instruction_is_not_a_relative_jump(self) -> None:
        self.assertIsNone(timing.relative("LD r, r'"))

    def test_an_unconditional_relative_jump_names_no_condition(self) -> None:
        self.assertEqual(timing.relative("JR e"), ("jr", None))

    def test_a_conditional_one_names_its_condition(self) -> None:
        self.assertEqual(timing.relative("JR NC, e"), ("jr", "nc"))

    def test_and_it_reaches_only_instructions_carrying_that_condition(self) -> None:
        found = timing.encodings_for("JR NC, e", KNOWN)

        self.assertEqual(found, [(0x30, timing.OPERAND)])


class CatalogueTest(unittest.TestCase):
    def test_the_disassembler_names_every_documented_mnemonic(self) -> None:
        self.assertIn("ld b,c", KNOWN)

    def test_a_byte_that_decodes_to_nothing_is_left_out(self) -> None:
        named = [text for text in KNOWN if text.startswith("db")]

        self.assertEqual(named, [])

    def test_an_indexed_form_carries_its_prefix_and_displacement(self) -> None:
        self.assertEqual(KNOWN["ld b,(ix+$01)"], (0xDD, 0x46, timing.OPERAND))


class SpendTest(unittest.TestCase):
    def test_a_register_load_costs_one_fetch(self) -> None:
        self.assertEqual(timing.spend((0x41,), {}), 4)

    def test_a_setup_reaches_the_registers_before_the_step(self) -> None:
        taken = timing.spend((0x38, 0x02), {"f": 0xFF})
        missed = timing.spend((0x38, 0x02), {"f": 0x00})

        self.assertEqual((taken, missed), (12, 7))

    def test_an_output_costs_its_cycle_with_no_device_attached(self) -> None:
        self.assertEqual(timing.spend((0xED, 0x41), {}), 12)


class SurveyTest(unittest.TestCase):
    def test_every_printed_row_is_surveyed(self) -> None:
        self.assertEqual(len(SURVEYED), len(timing.rows()))

    def test_every_printed_row_reaches_an_instruction_that_can_be_run(self) -> None:
        unreached = [one.instruction for one in SURVEYED if not one.measured]

        self.assertEqual(unreached, [])

    def test_and_a_run_spends_what_the_manual_prints(self) -> None:
        wrong = [
            f"page {one.page} {one.instruction}: printed {one.printed}, measured {list(one.measured)}"
            for one in SURVEYED
            if not one.agrees
        ]

        self.assertEqual(wrong, [])

    def test_the_whole_documented_instruction_set_is_covered(self) -> None:
        self.assertEqual(len(SURVEYED), 217)


class ReportTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.clean = timing.Row(71, "LD r, r'", 4, (4,))
        self.broken = timing.Row(99, "LD dd, nn", 10, (7,))

    def test_a_clean_survey_still_says_how_much_it_checked(self) -> None:
        said = timing.report([self.clean])

        self.assertIn("1 printed rows, 1 reproduced by a run", said)

    def test_a_disagreement_is_named_with_both_figures(self) -> None:
        said = timing.report([self.broken])

        self.assertIn("printed 10, measured [7]", said)

    def test_a_row_reaching_nothing_is_counted_apart(self) -> None:
        said = timing.report([timing.Row(1, "NOSUCH", 4, ())])

        self.assertIn("1 reaching no instruction at all", said)

    def test_a_row_that_agrees_says_so(self) -> None:
        self.assertTrue(self.clean.agrees)

    def test_and_one_that_does_not(self) -> None:
        self.assertFalse(self.broken.agrees)


class EntryPointTest(unittest.TestCase):
    def test_a_survey_that_agrees_reports_nothing_to_fix(self) -> None:
        printed = io.StringIO()

        with contextlib.redirect_stdout(printed):
            status = timing.main([{"manualPage": 71, "instruction": "NOP", "tStates": 4}])

        self.assertEqual((status, "0 not" in printed.getvalue()), (0, True))

    def test_a_survey_that_does_not_asks_for_a_person(self) -> None:
        printed = io.StringIO()

        with contextlib.redirect_stdout(printed):
            status = timing.main([{"manualPage": 71, "instruction": "NOP", "tStates": 99}])

        self.assertEqual((status, "1 not" in printed.getvalue()), (1, True))


if __name__ == "__main__":
    unittest.main()
