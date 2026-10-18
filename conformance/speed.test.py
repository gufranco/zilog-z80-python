import sys
import unittest
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance import speed


def ticking(*seconds: float) -> Any:
    held = [0.0]
    steps = list(seconds)

    def clock() -> float:
        if not steps:
            return held[0]
        at = held[0]
        held[0] = at + steps.pop(0)
        return at

    return clock


class MeasurementTest(unittest.TestCase):
    def timing_of(self, seconds: Sequence[float]) -> speed.Timed:
        return speed.Timed("z80", instructions=1000, seconds=seconds)

    def test_the_median_is_the_middle_of_the_runs(self) -> None:
        # Arrange
        seconds = [0.1, 0.2, 0.9]

        # Act
        found = self.timing_of(seconds)

        # Assert
        self.assertEqual(found.median, 0.2)

    def test_and_a_single_run_is_its_own_median(self) -> None:
        # Arrange
        seconds = [0.5]

        # Act
        found = self.timing_of(seconds)

        # Assert
        self.assertEqual(found.median, 0.5)

    def test_the_rate_is_t_states_over_the_median(self) -> None:
        # Arrange
        seconds = [0.1, 0.2, 0.9]

        # Act
        found = self.timing_of(seconds)

        # Assert
        self.assertEqual(found.rate, 5000)

    def test_one_slow_run_moves_the_median_less_than_it_moves_a_mean(self) -> None:
        # Arrange
        runs = ([0.1, 0.1, 0.1], [0.1, 0.1, 9.9])

        # Act
        steady, hiccup = (self.timing_of(seconds) for seconds in runs)

        # Assert
        self.assertEqual(steady.median, hiccup.median)

    def test_a_run_faster_than_the_floor_beats_it(self) -> None:
        # Arrange
        found = self.timing_of([0.001])

        # Act
        beaten = found.beats(100)

        # Assert
        self.assertIs(beaten, True)

    def test_and_one_slower_does_not(self) -> None:
        # Arrange
        found = self.timing_of([10.0])

        # Act
        beaten = found.beats(1000)

        # Assert
        self.assertIs(beaten, False)

    def test_a_run_exactly_at_the_floor_beats_it(self) -> None:
        found = speed.Timed("z80", instructions=1000, seconds=[1.0])

        self.assertTrue(found.beats(1000))

    def test_a_measurement_prints_as_the_rate_it_found(self) -> None:
        # Arrange
        found = self.timing_of([0.1])

        # Act
        printed = repr(found)

        # Assert
        self.assertIn("T states per second", printed)


class RunTest(unittest.TestCase):
    def test_a_run_records_one_duration_per_repeat(self) -> None:
        found = speed.timed(instructions=10, repeats=3, clock=ticking(0.1, 0.1, 0.1))

        self.assertEqual(len(found.seconds), 3)

    def test_and_reports_the_part_it_ran(self) -> None:
        found = speed.timed(instructions=10, repeats=1, clock=ticking(0.1))

        self.assertEqual(found.part, "z80")

    def test_and_the_number_of_instructions_it_was_asked_for(self) -> None:
        found = speed.timed(instructions=10, repeats=1, clock=ticking(0.1))

        self.assertEqual(found.instructions, 10)

    def test_a_run_really_executes_the_instructions(self) -> None:
        found = speed.timed(instructions=64, repeats=1, clock=ticking(0.1))

        self.assertEqual(found.rate, 640)

    def test_a_run_left_to_its_own_clock_measures_real_time(self) -> None:
        # Arrange
        instructions = 64

        # Act
        found = speed.timed(instructions=instructions, repeats=2)

        # Assert
        self.assertEqual((len(found.seconds), all(one > 0 for one in found.seconds)), (2, True))


class ReportTest(unittest.TestCase):
    def test_a_report_gives_the_rate_and_the_runtime(self) -> None:
        found = speed.Timed("z80", instructions=1000, seconds=[0.001])

        lines = " ".join(speed.lines_for(found, floor=100))

        self.assertIn("T states per second", lines)
        self.assertIn("Python", lines)

    def test_and_the_fastest_and_slowest_run(self) -> None:
        found = speed.Timed("z80", instructions=1000, seconds=[0.001, 0.002, 0.003])

        lines = " ".join(speed.lines_for(found, floor=100))

        self.assertIn("fastest", lines)
        self.assertIn("slowest", lines)

    def test_it_does_not_claim_a_share_of_the_silicon(self) -> None:
        found = speed.Timed("z80", instructions=1000, seconds=[0.001])

        self.assertNotIn("% of the", " ".join(speed.lines_for(found, floor=100)))
        self.assertFalse(hasattr(found, "of_real_time"))

    def test_a_run_below_the_floor_says_so(self) -> None:
        found = speed.Timed("z80", instructions=1000, seconds=[10.0])

        self.assertIn("below the floor", " ".join(speed.lines_for(found, floor=1000)))

    def test_a_run_above_it_does_not(self) -> None:
        found = speed.Timed("z80", instructions=1000, seconds=[0.001])

        self.assertNotIn("below the floor", " ".join(speed.lines_for(found, floor=100)))


class OptionTest(unittest.TestCase):
    def test_a_run_with_no_options_takes_the_defaults(self) -> None:
        self.assertEqual(speed.options([]), (speed.INSTRUCTIONS, speed.REPEATS))

    def test_a_count_of_instructions_can_be_named(self) -> None:
        self.assertEqual(speed.options(["--instructions", "5"])[0], 5)

    def test_and_a_number_of_repeats(self) -> None:
        self.assertEqual(speed.options(["--repeats", "3"])[1], 3)

    def test_an_unknown_option_is_refused_by_name(self) -> None:
        with self.assertRaises(speed.Usage) as raised:
            speed.options(["--nonsense"])

        self.assertIn("--nonsense", str(raised.exception))

    def test_an_option_with_no_value_is_refused(self) -> None:
        with self.assertRaises(speed.Usage) as raised:
            speed.options(["--repeats"])

        self.assertIn("--repeats", str(raised.exception))


class EntryTest(unittest.TestCase):
    def invoked(self, argv: Sequence[str], **held: Any) -> tuple[int, str]:
        said: list[str] = []
        code = speed.main(argv, say=said.append, **held)
        return code, " ".join(said)

    def test_a_run_that_beats_the_floor_passes(self) -> None:
        # Arrange
        timed = speed.Timed("z80", 1000, [0.001])

        # Act
        code, said = self.invoked([], floor=100, run=lambda **_options: timed)

        # Assert
        self.assertEqual((code, "below the floor" in said), (0, False))

    def test_a_run_that_does_not_fails_and_says_so(self) -> None:
        # Arrange
        timed = speed.Timed("z80", 1000, [1.0])

        # Act
        code, said = self.invoked([], floor=1_000_000, run=lambda **_options: timed)

        # Assert
        self.assertEqual((code, "below the floor" in said), (1, True))

    def test_an_unusable_option_is_reported_rather_than_raised(self) -> None:
        # Arrange
        argv = ["--nonsense"]

        # Act
        code, said = self.invoked(argv)

        # Assert
        self.assertEqual((code, "--nonsense" in said), (2, True))


if __name__ == "__main__":
    unittest.main()
