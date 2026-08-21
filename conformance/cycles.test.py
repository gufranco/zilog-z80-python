import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import cycles

from z80 import bus

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


WIDE: dict[str, Any] = {
    "name": "00 0000",
    "initial": NOP["initial"],
    "final": NOP["final"],
    "cycles": [
        [0x4DDF, None, "----"],
        [0x4DDF, None, "r-m-"],
        [0xA610, 0x00, "--m-"],
        [0xA610, None, "----"],
    ],
}
"""The same case as the corpus draws it with the full memory cycle flag on.

Its first state is idle where the manual's shape strobes, which is the state the
generator writes without consulting that flag and the one the runner skips.
"""


class ShapeTest(unittest.TestCase):
    """The manual shape, against a corpus drawn the way that shape draws."""

    def test_the_recorded_shape_is_what_a_run_gets_without_asking(self) -> None:
        self.assertEqual(cycles.options(["somewhere"])[3], bus.RECORDING)

    def test_the_manual_shape_can_be_asked_for(self) -> None:
        self.assertEqual(cycles.options(["somewhere", "--shape", "manual"])[3], bus.MANUAL)

    def test_a_shape_that_is_neither_is_refused(self) -> None:
        with self.assertRaises(cycles.Usage):
            cycles.options(["somewhere", "--shape", "invented"])

    def test_a_shape_with_nothing_after_it_is_refused(self) -> None:
        with self.assertRaises(cycles.Usage):
            cycles.options(["somewhere", "--shape"])

    def test_a_widened_case_is_reproduced_in_the_manual_shape(self) -> None:
        self.assertEqual(cycles.check(WIDE, bus.MANUAL).differences, [])

    def test_and_the_state_that_went_unchecked_is_counted(self) -> None:
        self.assertEqual(cycles.check(WIDE, bus.MANUAL).skipped, 1)

    def test_the_recorded_shape_counts_no_skips_because_it_makes_none(self) -> None:
        self.assertEqual(cycles.check(NOP).skipped, 0)

    def test_the_same_widened_case_fails_against_the_recorded_shape(self) -> None:
        self.assertNotEqual(cycles.check(WIDE).differences, [])

    def test_a_run_in_the_manual_shape_passes_against_a_widened_suite(self) -> None:
        self.assertEqual(cycles.run([str(suite_of([WIDE])), "--shape", "manual"]), 0)

    def test_and_fails_against_it_in_the_recorded_shape(self) -> None:
        self.assertEqual(cycles.run([str(suite_of([WIDE]))]), 1)

    def test_a_difference_outside_an_opening_state_is_still_reported(self) -> None:
        wrong = dict(WIDE)
        wrong["cycles"] = [*WIDE["cycles"][:3], [0xA610, None, "r-m-"]]

        self.assertNotEqual(cycles.check(wrong, bus.MANUAL).differences, [])

    def test_the_opening_states_come_from_the_bus_rather_than_the_pins(self) -> None:
        line = bus.Bus(recording=True)
        line.read(0x2000, 0x42)
        line.fetch(0x1234, 0x5678, 0xAB)

        self.assertEqual(cycles.opening_states(line.cycles), {0, 3})

    def test_a_cycle_the_generator_draws_in_full_is_not_skipped(self) -> None:
        line = bus.Bus(recording=True)
        line.port_read(0x8000, 0x42)

        self.assertEqual(cycles.opening_states(line.cycles), set())


class ComparisonTest(unittest.TestCase):
    def test_a_case_the_model_reproduces_reports_nothing(self) -> None:
        self.assertEqual(cycles.check(NOP).differences, [])

    def test_a_case_with_a_changed_address_is_reported(self) -> None:
        wrong = json.loads(json.dumps(NOP))
        wrong["cycles"][0][0] = 0x0000

        self.assertNotEqual(cycles.check(wrong).differences, [])

    def test_a_case_with_a_changed_pin_string_is_reported(self) -> None:
        wrong = json.loads(json.dumps(NOP))
        wrong["cycles"][1][2] = "----"

        self.assertNotEqual(cycles.check(wrong).differences, [])

    def test_a_case_with_a_changed_value_is_reported(self) -> None:
        wrong = json.loads(json.dumps(NOP))
        wrong["cycles"][2][1] = 0xFF

        self.assertNotEqual(cycles.check(wrong).differences, [])

    def test_a_case_with_a_missing_state_is_reported(self) -> None:
        wrong = json.loads(json.dumps(NOP))
        del wrong["cycles"][-1]

        self.assertNotEqual(cycles.check(wrong).differences, [])

    def test_a_report_names_the_state_that_differed(self) -> None:
        wrong = json.loads(json.dumps(NOP))
        wrong["cycles"][2][1] = 0xFF

        self.assertEqual(cycles.check(wrong).differences[0][0], 2)

    def test_a_comparison_carries_both_readings(self) -> None:
        wrong = json.loads(json.dumps(NOP))
        wrong["cycles"][2][1] = 0xFF

        _index, expected, actual = cycles.check(wrong).differences[0]

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

        self.assertGreater(len(cycles.check(long).differences), cycles.STATE_LIMIT)

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


def opcodes_that_disagree(directory: Path, sample: int) -> list[str]:
    """Which opcode files in a directory this core does not reproduce.

    A named function rather than a body inside the suite-gated test, because a
    body that only runs where the suite is present is a body that goes unmeasured
    on every machine and every job where it is not, and an unmeasured sweep is
    the one part of a gate nobody would notice breaking.
    """
    return [
        path.stem
        for path in sorted(directory.glob("*.json"))
        if any(cycles.check(case).differences for case in json.loads(path.read_text())[:sample])
    ]


class SweepTest(unittest.TestCase):
    """The sweep the gate runs, on a suite small enough to build here."""

    def test_a_suite_the_model_reproduces_names_nothing(self) -> None:
        self.assertEqual(opcodes_that_disagree(suite_of([NOP, NOP]), 2), [])

    def test_a_suite_it_does_not_names_the_opcode(self) -> None:
        wrong = json.loads(json.dumps(NOP))
        wrong["cycles"][2][1] = 0xFF

        self.assertEqual(opcodes_that_disagree(suite_of([wrong]), 2), ["00"])

    def test_only_the_sample_is_read(self) -> None:
        wrong = json.loads(json.dumps(NOP))
        wrong["cycles"][2][1] = 0xFF

        self.assertEqual(opcodes_that_disagree(suite_of([NOP, wrong]), 1), [])


@unittest.skipUnless(HAS_SUITE, "the conformance suite is not on this machine")
class AgainstSuiteTest(unittest.TestCase):
    """The gate proper, on a sample. The full sweep is a workflow job, not a test."""

    def test_every_opcode_reproduces_its_recorded_bus_activity(self) -> None:
        self.assertEqual(opcodes_that_disagree(SUITE, 2), [])


if __name__ == "__main__":
    unittest.main()
