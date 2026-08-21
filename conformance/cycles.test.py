import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import cycles

SUITE = Path.home() / ".cache" / "conformance-suites" / "z80" / "v1"

HAS_SUITE = SUITE.is_dir()

NOP: dict[str, Any] = {
    "name": "00 0000",
    "initial": {"pc": 0x4DDF, "i": 0xA6, "r": 0x10, "ram": [[0x4DDF, 0x00]]},
    "final": {"pc": 0x4DE0, "r": 0x11, "ram": [[0x4DDF, 0x00]]},
    "cycles": [
        [0x4DDF, None, "----"],
        [0x4DDF, None, "r-m-"],
        [0xA610, 0x00, "----"],
        [0xA610, None, "----"],
    ],
}


def suite_of(cases: list[dict[str, Any]]) -> Path:
    where = Path(tempfile.mkdtemp())
    (where / "00.json").write_text(json.dumps(cases))
    return where


class ComparisonTest(unittest.TestCase):
    def test_a_case_the_model_reproduces_reports_nothing(self) -> None:
        self.assertEqual(cycles.check(NOP), [])

    def test_a_case_with_a_changed_address_is_reported(self) -> None:
        wrong = json.loads(json.dumps(NOP))
        wrong["cycles"][0][0] = 0x0000

        self.assertNotEqual(cycles.check(wrong), [])

    def test_a_case_with_a_changed_pin_string_is_reported(self) -> None:
        wrong = json.loads(json.dumps(NOP))
        wrong["cycles"][1][2] = "----"

        self.assertNotEqual(cycles.check(wrong), [])

    def test_a_case_with_a_changed_value_is_reported(self) -> None:
        wrong = json.loads(json.dumps(NOP))
        wrong["cycles"][2][1] = 0xFF

        self.assertNotEqual(cycles.check(wrong), [])

    def test_a_case_with_a_missing_state_is_reported(self) -> None:
        wrong = json.loads(json.dumps(NOP))
        del wrong["cycles"][-1]

        self.assertNotEqual(cycles.check(wrong), [])

    def test_a_report_names_the_state_that_differed(self) -> None:
        wrong = json.loads(json.dumps(NOP))
        wrong["cycles"][2][1] = 0xFF

        self.assertEqual(cycles.check(wrong)[0][0], 2)

    def test_a_comparison_carries_both_readings(self) -> None:
        wrong = json.loads(json.dumps(NOP))
        wrong["cycles"][2][1] = 0xFF

        _index, expected, actual = cycles.check(wrong)[0]

        self.assertNotEqual(expected, actual)


class DifferenceTest(unittest.TestCase):
    def test_two_identical_transcripts_report_nothing(self) -> None:
        self.assertEqual(cycles.differences([[1, None, "----"]], [[1, None, "----"]]), [])

    def test_a_transcript_that_stops_early_is_reported_rather_than_ignored(self) -> None:
        found = cycles.differences([[1, None, "----"], [2, None, "----"]], [[1, None, "----"]])

        self.assertEqual(found[0][0], 1)

    def test_and_one_that_runs_long(self) -> None:
        found = cycles.differences([[1, None, "----"]], [[1, None, "----"], [2, None, "----"]])

        self.assertEqual(found[0][0], 1)


class OptionTest(unittest.TestCase):
    def test_a_directory_is_required(self) -> None:
        with self.assertRaises(cycles.Usage):
            cycles.options([])

    def test_the_directory_is_read_off_the_command_line(self) -> None:
        self.assertEqual(cycles.options(["somewhere"])[0], Path("somewhere"))

    def test_the_number_of_cases_can_be_limited(self) -> None:
        self.assertEqual(cycles.options(["somewhere", "--limit", "5"])[1], 5)

    def test_one_opcode_can_be_named(self) -> None:
        self.assertEqual(cycles.options(["somewhere", "--opcode", "ed b0"])[2], "ed b0")

    def test_an_option_with_no_value_is_refused(self) -> None:
        with self.assertRaises(cycles.Usage):
            cycles.options(["somewhere", "--limit"])

    def test_an_option_the_runner_does_not_know_is_refused(self) -> None:
        with self.assertRaises(cycles.Usage):
            cycles.options(["somewhere", "elsewhere", "again"])


class RunTest(unittest.TestCase):
    def test_a_suite_the_model_reproduces_passes(self) -> None:
        self.assertEqual(cycles.run([str(suite_of([NOP]))]), 0)

    def test_a_suite_it_does_not_fails(self) -> None:
        wrong = json.loads(json.dumps(NOP))
        wrong["cycles"][2][1] = 0xFF

        self.assertEqual(cycles.run([str(suite_of([wrong]))]), 1)

    def test_a_directory_with_no_cases_is_reported_rather_than_passing(self) -> None:
        self.assertEqual(cycles.run([str(Path(tempfile.mkdtemp()))]), 1)

    def test_naming_an_opcode_nobody_has_is_reported_rather_than_passing(self) -> None:
        self.assertEqual(cycles.run([str(suite_of([NOP])), "--opcode", "zz"]), 1)

    def test_a_limit_shortens_the_run(self) -> None:
        self.assertEqual(cycles.run([str(suite_of([NOP, NOP])), "--limit", "1"]), 0)


class ReportingTest(unittest.TestCase):
    """What a run says when it finds something, which is the half nobody reads."""

    def wrong_case(self, at: int = 2) -> dict[str, Any]:
        wrong: dict[str, Any] = json.loads(json.dumps(NOP))
        wrong["cycles"][at][1] = 0xFF
        return wrong

    def test_a_run_stops_naming_cases_after_the_first_handful(self) -> None:
        many = [self.wrong_case() for _ in range(cycles.REPORT_LIMIT + 5)]

        self.assertEqual(cycles.run([str(suite_of(many))]), 1)

    def test_an_opcode_is_counted_once_however_many_of_its_cases_fail(self) -> None:
        many = [self.wrong_case(), self.wrong_case()]

        self.assertEqual(cycles.run([str(suite_of(many))]), 1)

    def test_a_report_shows_at_most_a_handful_of_states(self) -> None:
        long = json.loads(json.dumps(NOP))
        long["cycles"] = [[0, None, "----"]] * (cycles.STATE_LIMIT + 4)

        self.assertGreater(len(cycles.check(long)), cycles.STATE_LIMIT)

    def test_a_directory_holding_an_opcode_by_name_is_run_alone(self) -> None:
        self.assertEqual(cycles.run([str(suite_of([NOP])), "--opcode", "00"]), 0)

    def test_a_stray_second_directory_is_refused(self) -> None:
        with self.assertRaises(cycles.Usage):
            cycles.options(["one", "two"])

    def test_options_naming_no_directory_at_all_are_refused(self) -> None:
        with self.assertRaises(cycles.Usage):
            cycles.options(["--limit", "5"])


class EntryTest(unittest.TestCase):
    def test_a_run_with_no_directory_says_so(self) -> None:
        self.assertEqual(cycles.main([]), 2)

    def test_a_usable_run_reports_success(self) -> None:
        self.assertEqual(cycles.main([str(suite_of([NOP]))]), 0)


@unittest.skipUnless(HAS_SUITE, "the conformance suite is not on this machine")
class AgainstSuiteTest(unittest.TestCase):
    """The gate proper, on a sample. The full sweep is a workflow job, not a test."""

    def test_every_opcode_reproduces_its_recorded_bus_activity(self) -> None:
        failed = [
            path.stem
            for path in sorted(SUITE.glob("*.json"))
            if any(cycles.check(case) for case in json.loads(path.read_text())[:2])
        ]

        self.assertEqual(failed, [])


if __name__ == "__main__":
    unittest.main()
