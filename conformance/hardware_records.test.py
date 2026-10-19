import json
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

from conformance.bench import pins_of, ran  # noqa: E402

DIVERGENCES = json.loads((ROOT / "conformance" / "divergences.json").read_text())

SUITES = json.loads((ROOT / "conformance" / "suites.json").read_text())

SUITE = SUITES["suites"][0]

GENERATOR = SUITE["generator"]

ENTRIES = DIVERGENCES["divergences"]

SHAPES = ("manual", "recording")

REFRESH = {"i": 0x56, "r": 0x78}

MOVED_ON = "generator-head-disagrees-with-the-pinned-corpus"


def entry_named(name: str) -> dict[str, Any]:
    found: dict[str, Any] = next(entry for entry in ENTRIES if entry["id"] == name)
    return found


def named_entries() -> set[str]:
    return {entry["id"] for entry in ENTRIES}


class SuiteRecordTest(unittest.TestCase):
    def test_the_corpus_is_pinned_by_commit(self) -> None:
        # Arrange
        suite = SUITE

        # Act
        commit = suite["commit"]

        # Assert
        self.assertEqual(len(commit), 40)

    def test_and_so_is_the_generator_that_produced_it(self) -> None:
        # Arrange
        generator = GENERATOR

        # Act
        commit = generator["commit"]

        # Assert
        self.assertEqual(len(commit), 40)

    def test_the_generator_names_every_file_it_has_to_be_given(self) -> None:
        # Arrange
        generator = GENERATOR

        # Act
        required = generator["requires"]

        # Assert
        self.assertEqual(len(required), 3)

    def test_the_flag_that_would_widen_the_strobes_is_recorded_as_off(self) -> None:
        # Arrange
        flags = GENERATOR["flags"]

        # Act
        widened = flags["Z80_DO_FULL_MEMCYCLES"]

        # Assert
        self.assertIs(widened, False)

    def test_which_is_why_the_recorded_shape_strobes_one_state(self) -> None:
        # Arrange
        cpu = ran((0x06, 0x42), shape="recording")

        # Act
        pins = pins_of(cpu, "read")

        # Assert
        self.assertEqual(pins.count("r-m-"), 1)

    def test_the_flag_that_puts_refresh_on_the_address_pins_is_recorded_as_on(self) -> None:
        # Arrange
        flags = GENERATOR["flags"]

        # Act
        refreshing = flags["Z80_DO_MEM_REFRESHES"]

        # Assert
        self.assertIs(refreshing, True)

    def test_which_is_why_both_shapes_carry_a_refresh_address(self) -> None:
        # Arrange
        program = (0x00,)

        # Act
        found = {ran(program, REFRESH, shape=shape).bus.log[2][0] for shape in SHAPES}

        # Assert
        self.assertEqual(found, {0x5678})

    def test_the_entries_the_generator_emits_and_the_corpus_omits_are_named(self) -> None:
        # Arrange
        generator = GENERATOR

        # Act
        excluded = generator["excludedFromPublication"]

        # Assert
        self.assertEqual(len(excluded), 2)

    def test_the_second_oracle_is_recorded_with_the_flags_that_build_it(self) -> None:
        # Arrange
        run = GENERATOR["fullMemoryCycleRun"]

        # Act
        widened = run["flags"]["Z80_DO_FULL_MEMCYCLES"]

        # Assert
        self.assertIs(widened, True)

    def test_and_with_what_it_reported_rather_than_only_that_it_was_run(self) -> None:
        # Arrange
        measured = GENERATOR["fullMemoryCycleRun"]["measured"]

        # Act
        every_case = len(measured["opcodesAffected"]) * SUITE["tests_per_opcode"]

        # Assert
        self.assertEqual(measured["failed"], every_case)

    def test_every_opcode_it_reported_is_one_the_generator_already_moved_on(self) -> None:
        # Arrange
        listed = " ".join(entry_named(MOVED_ON)["referenceDoes"]["detail"])
        affected = GENERATOR["fullMemoryCycleRun"]["measured"]["opcodesAffected"]

        # Act
        missing = [name for name in affected if name not in listed]

        # Assert
        self.assertEqual(missing, [])

    def test_the_states_it_skips_are_named_and_counted(self) -> None:
        # Arrange
        run = GENERATOR["fullMemoryCycleRun"]

        # Act
        allowance = set(run["allowance"])

        # Assert
        self.assertEqual(allowance, {"what", "why", "counted"})

    def test_the_command_that_rebuilds_the_corpus_exists(self) -> None:
        # Arrange
        named = GENERATOR["howToRun"].split()[1]

        # Act
        present = (ROOT / named).is_file()

        # Assert
        self.assertIs(present, True)

    def test_and_so_does_the_one_that_compares_against_it(self) -> None:
        # Arrange
        named = GENERATOR["fullMemoryCycleRun"]["howToCompare"].split()[1]

        # Act
        present = (ROOT / named).is_file()

        # Assert
        self.assertIs(present, True)


class DivergenceTest(unittest.TestCase):
    def test_no_two_entries_share_an_id(self) -> None:
        # Arrange
        names = [entry["id"] for entry in ENTRIES]

        # Act
        distinct = set(names)

        # Assert
        self.assertEqual(len(names), len(distinct))

    def test_every_entry_says_which_side_the_package_follows(self) -> None:
        # Arrange
        entries = ENTRIES

        # Act
        missing = [entry["id"] for entry in entries if not entry.get("packageFollows")]

        # Assert
        self.assertEqual(missing, [])

    def test_every_open_entry_says_what_would_settle_it(self) -> None:
        # Arrange
        entries = ENTRIES

        # Act
        missing = [
            entry["id"]
            for entry in entries
            if entry["status"] == "open" and not entry.get("wouldSettleIt")
        ]

        # Assert
        self.assertEqual(missing, [])

    def test_every_closed_entry_says_what_would_reopen_it(self) -> None:
        # Arrange
        entries = ENTRIES

        # Act
        missing = [
            entry["id"]
            for entry in entries
            if entry["status"] == "closed" and not entry.get("wouldReopenIt")
        ]

        # Assert
        self.assertEqual(missing, [])

    def test_the_two_places_the_recording_departs_from_the_manual_are_both_written_up(
        self,
    ) -> None:
        # Arrange
        expected = {"recording-single-state-strobe", "recording-refresh-on-address-pins"}

        # Act
        named = named_entries()

        # Assert
        self.assertLessEqual(expected, named)

    def test_each_of_those_quotes_the_generator_admitting_it(self) -> None:
        # Arrange
        entries = ENTRIES

        # Act
        admitted = [
            entry["id"]
            for entry in entries
            if entry["id"].startswith("recording-")
            and "generatorSaysSoItself" in entry["referenceDoes"]
        ]

        # Assert
        self.assertEqual(len(admitted), 2)

    def test_every_timing_chapter_cycle_is_modelled_or_written_up(self) -> None:
        # Arrange
        expected = {
            "wait-states-requested-by-a-device",
            "bus-request-and-acknowledge",
            "power-down-is-a-stopped-clock",
        }

        # Act
        named = named_entries()

        # Assert
        self.assertLessEqual(expected, named)

    def test_and_each_of_those_says_what_would_bring_it_into_scope(self) -> None:
        # Arrange
        entries = ENTRIES

        # Act
        missing = [
            entry["id"]
            for entry in entries
            if entry["severity"] == "outOfScope" and not entry.get("wouldReopenIt")
        ]

        # Assert
        self.assertEqual(missing, [])

    def test_the_places_the_manual_is_silent_are_each_written_up(self) -> None:
        # Arrange
        expected = {
            "undocumented-flag-bits",
            "internal-register-wz",
            "undocumented-opcodes",
            "internal-cycle-placement",
            "acknowledge-internal-state-placement",
            "halt-fetch-address-unstated",
        }

        # Act
        named = named_entries()

        # Assert
        self.assertLessEqual(expected, named)

    def test_the_generator_moving_away_from_the_pinned_corpus_is_written_up(self) -> None:
        # Arrange
        name = MOVED_ON

        # Act
        found = entry_named(name)

        # Assert
        self.assertEqual(len(found["referenceDoes"]["detail"]), 4)

    def test_and_that_entry_names_what_would_reopen_it_because_a_bump_would(self) -> None:
        # Arrange
        name = MOVED_ON

        # Act
        found = entry_named(name)

        # Assert
        self.assertGreater(len(str(found["wouldReopenIt"]).strip()), 0)


if __name__ == "__main__":
    unittest.main()
