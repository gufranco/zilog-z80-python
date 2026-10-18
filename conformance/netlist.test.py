from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import netlist  # noqa: E402
from conformance.synthetic_netlist import (  # noqa: E402
    NAMES,
    Fixture,
    build,
    segment_line,
    transistor_line,
)


class IdentityTest(Fixture):
    def test_a_missing_file_names_itself_and_where_it_comes_from(self) -> None:
        (self.where / "transdefs.js").unlink()

        with self.assertRaises(netlist.Missing) as raised:
            self.parsed()

        self.assertIn("https://example.invalid/transdefs.js", str(raised.exception))

    def test_a_file_of_the_wrong_size_is_refused_before_it_is_hashed(self) -> None:
        (self.where / "transdefs.js").write_text("var transdefs = [\n]\n")

        with self.assertRaises(netlist.Missing) as raised:
            self.parsed()

        self.assertIn("bytes", str(raised.exception))

    def test_a_file_edited_without_changing_its_size_is_refused(self) -> None:
        held = (self.where / "segdefs.js").read_text()
        (self.where / "segdefs.js").write_text(held.replace("'+'", "'-'", 1))

        with self.assertRaises(netlist.Missing) as raised:
            self.parsed()

        self.assertIn("a different file", str(raised.exception))

    def test_every_entry_publishes_the_whole_digest_ladder(self) -> None:
        held = netlist.identity()

        missing = [
            (one["file"], key)
            for one in held["netlist"]
            for key in ("bytes", "crc32", "md5", "sha1", "sha256")
            if key not in one
        ]

        self.assertEqual(missing, [])

    def test_and_says_which_of_them_decides(self) -> None:
        held = netlist.identity()

        self.assertIn("sha256 decides", held["decides"])

    def test_the_published_digests_agree_with_each_other(self) -> None:
        held = netlist.identity()

        wrong = [
            one["file"]
            for one in held["netlist"]
            if len(str(one["sha256"])) != 64 or len(str(one["sha1"])) != 40
        ]

        self.assertEqual(wrong, [])

    def test_the_identity_carried_here_names_the_three_files(self) -> None:
        held = netlist.identity()

        self.assertEqual([one["file"] for one in held["netlist"]], list(netlist.FILES))

    def test_the_identity_carried_here_names_the_licence_the_resolver_follows(self) -> None:
        held = netlist.identity()

        self.assertEqual(held["algorithm"]["licence"], "MIT")


class LoadingTest(Fixture):
    def test_the_transistors_and_the_pullups_are_the_ones_written(self) -> None:
        held = self.parsed()

        self.assertEqual((held.transistors, held.pullups), (3, 1))

    def test_the_entries_that_are_pullups_are_counted_and_not_loaded(self) -> None:
        held = self.parsed()

        self.assertEqual(held.skipped_pullups, netlist.TRANSISTORS_THAT_ARE_PULLUPS)

    def test_a_file_with_a_different_number_of_pullup_entries_is_refused(self) -> None:
        build(self.where, pullup_entries=netlist.TRANSISTORS_THAT_ARE_PULLUPS - 1)

        with self.assertRaises(netlist.Missing) as raised:
            self.parsed()

        self.assertIn("different file", str(raised.exception))

    def test_the_two_fixed_nets_are_checked_rather_than_trusted(self) -> None:
        moved = [(name, 5 if name == "vss" else number) for name, number in NAMES]
        build(self.where, names=moved)

        with self.assertRaises(netlist.Missing) as raised:
            self.parsed()

        self.assertIn("vss", str(raised.exception))

    def test_a_ground_connection_is_moved_to_the_second_place(self) -> None:
        build(self.where, transistors=[(3, 1, 17)])

        held = self.parsed()

        self.assertEqual((held.first_of[0], held.second_of[0]), (17, netlist.GROUND))

    def test_a_power_connection_is_moved_to_the_second_place(self) -> None:
        build(self.where, transistors=[(3, 2, 17)])

        held = self.parsed()

        self.assertEqual((held.first_of[0], held.second_of[0]), (17, netlist.POWER))

    def test_a_net_past_the_bound_this_was_read_at_is_refused(self) -> None:
        build(self.where, extra_names="beyond: 99999,")

        with self.assertRaises(netlist.Missing) as raised:
            self.parsed()

        self.assertIn("99999", str(raised.exception))

    def test_a_pulled_up_net_past_the_bound_is_refused(self) -> None:
        build(self.where, extra_segments=segment_line(99999, "+"))

        with self.assertRaises(netlist.Missing) as raised:
            self.parsed()

        self.assertIn("99999", str(raised.exception))

    def test_more_transistors_than_this_was_read_at_is_refused(self) -> None:
        crowd = "\n".join(transistor_line(3, 17, 1) for _ in range(netlist.MAX_TRANS))
        build(self.where, extra_transistors=crowd)

        with self.assertRaises(netlist.Missing) as raised:
            self.parsed()

        self.assertIn(str(netlist.MAX_TRANS), str(raised.exception))

    def test_lines_that_are_not_entries_are_passed_over(self) -> None:
        build(
            self.where,
            extra_transistors="not an entry\n['t8',1,2]",
            extra_segments="not an entry\n[5,'-']",
        )

        held = self.parsed()

        self.assertEqual(held.transistors, 3)

    def test_an_unknown_name_is_net_zero_rather_than_an_error(self) -> None:
        held = self.parsed()

        self.assertEqual(held.number("nothing_is_called_this"), 0)

    def test_a_bus_reads_least_significant_net_first(self) -> None:
        held = self.parsed()
        held.state[40] = 1
        held.state[42] = 1

        self.assertEqual(held.bus("db", 8), 0x05)


class ResolutionTest(Fixture):
    def test_a_group_that_reaches_ground_settles_low(self) -> None:
        part = self.part()
        part.state[17] = 1
        part.on[0] = 1

        part.settle([17])

        self.assertEqual(part.state[17], 0)

    def test_a_group_that_reaches_power_settles_high(self) -> None:
        part = self.part()
        part.on[1] = 1
        part.state[19] = 0

        part.settle([19])

        self.assertEqual(part.state[19], 1)

    def test_a_net_being_pulled_up_settles_high(self) -> None:
        part = self.part()
        part.state[17] = 0

        part.settle([17])

        self.assertEqual(part.state[17], 1)

    def test_a_net_being_pulled_down_settles_low(self) -> None:
        part = self.part()
        part.pullup[17] = 0
        part.pulldown[17] = 1
        part.state[17] = 1

        part.settle([17])

        self.assertEqual(part.state[17], 0)

    def test_a_group_nothing_drives_keeps_a_level_one_of_its_nets_already_held(self) -> None:
        part = self.part()
        part.pullup[17] = 0
        part.state[17] = 0
        part.state[19] = 1
        part.on[2] = 1

        part.settle([17])

        self.assertEqual(part.state[17], 1)

    def test_a_group_where_nothing_says_anything_settles_low(self) -> None:
        part = self.part()
        part.pullup[17] = 0
        part.state[17] = 0
        part.state[19] = 1

        part.settle([17])

        self.assertEqual(part.state[17], 0)

    def test_a_ring_that_never_rests_is_recorded_rather_than_raised(self) -> None:
        build(self.where, transistors=[(18, 18, 1)], pulled_up=(18,))
        part = self.part()

        part.settle([18])

        self.assertEqual(part.unsettled, 1)

    def test_the_rails_are_never_queued_for_resolution(self) -> None:
        # Arrange
        part = self.part()
        queued: list[int] = []

        # Act
        part.enqueue(netlist.GROUND, queued)

        # Assert
        self.assertEqual(queued, [])

    def test_a_net_is_queued_once_however_many_times_it_is_reached(self) -> None:
        # Arrange
        part = self.part()
        queued: list[int] = []

        # Act
        part.enqueue(17, queued)
        part.enqueue(17, queued)

        # Assert
        self.assertEqual(queued, [17])

    def test_resolving_a_rail_does_nothing(self) -> None:
        # Arrange
        part = self.part()
        before = bytes(part.state)

        # Act
        part.resolve(netlist.POWER, [])

        # Assert
        self.assertEqual(bytes(part.state), before)

    def test_a_group_seeded_on_a_rail_is_just_that_rail(self) -> None:
        # Arrange
        part = self.part()

        # Act
        part.collect_group(netlist.GROUND)

        # Assert
        self.assertEqual(part.group, [netlist.GROUND])

    def test_a_net_reached_through_the_far_end_of_a_transistor_joins_the_group(self) -> None:
        # Arrange
        part = self.part()
        part.on[2] = 1

        # Act
        part.regroup(19)

        # Assert
        self.assertIn(17, part.group)

    def test_a_net_going_low_leaves_an_already_open_transistor_alone(self) -> None:
        part = self.part()
        part.pullup[19] = 0
        part.pulldown[19] = 1
        part.state[19] = 1
        part.on[1] = 0

        part.settle([19])

        self.assertEqual((part.state[19], part.on[1]), (0, 0))

    def test_the_connected_nets_leave_out_the_rails(self) -> None:
        part = self.part()

        found = part.connected()

        self.assertNotIn(netlist.GROUND, found)


class CommandLineTest(Fixture):
    def test_no_arguments_asks_for_the_default_run(self) -> None:
        found = netlist.options([])

        self.assertEqual(found, netlist.DEFAULT_HALF_CYCLES)

    def test_a_run_length_is_taken_from_the_arguments(self) -> None:
        found = netlist.options(["--half-cycles", "12"])

        self.assertEqual(found, 12)

    def test_a_run_length_with_no_number_is_refused(self) -> None:
        with self.assertRaises(SystemExit):
            netlist.options(["--half-cycles"])

    def test_an_argument_nobody_defined_is_refused(self) -> None:
        with self.assertRaises(SystemExit):
            netlist.options(["--wat"])

    def test_a_netlist_that_is_not_here_is_reported_rather_than_raised(self) -> None:
        (self.where / "segdefs.js").unlink()
        held = io.StringIO()

        with redirect_stdout(held):
            code = netlist.main([], self.where, self.where / "netlist.manifest.json")

        self.assertEqual((code, "REFUSED" in held.getvalue()), (1, True))

    def test_a_run_that_never_settles_is_reported_as_a_failure(self) -> None:
        build(self.where, transistors=[(18, 18, 1)], pulled_up=(18,))
        held = io.StringIO()

        with redirect_stdout(held):
            code = netlist.main(
                ["--half-cycles", "2"], self.where, self.where / "netlist.manifest.json"
            )

        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
