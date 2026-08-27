"""That the switch-level run is the reference's, and that it runs the part.

The netlist itself is not carried, so every check here is driven against a
synthetic one built in the fixture: three files in the published formats
describing a circuit small enough to reason about by hand. That is not a
convenience. A check that only runs when a two megabyte file happens to be on the
machine is a check that reports success by being skipped.

The real netlist is used when it is present, and only for the things a synthetic
circuit cannot show: that the part fetches, executes, comes to rest on every edge,
and lands on register values nothing else would produce.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import ClassVar, override

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import netlist  # noqa: E402

NAMES: list[tuple[str, int]] = [
    ("vss", 1),
    ("vcc", 2),
    ("clk", 3),
    ("_reset", 4),
    ("_busrq", 5),
    ("_int", 6),
    ("_nmi", 7),
    ("_wait", 8),
    ("_rfsh", 9),
    ("_m1", 10),
    ("_mreq", 11),
    ("_rd", 12),
    ("_wr", 13),
    ("_iorq", 14),
    ("t2", 15),
    ("t3", 16),
    ("out", 17),
    ("ring", 18),
    ("quiet", 19),
]
NAMES += [(f"ab{i}", 20 + i) for i in range(16)]
NAMES += [(f"db{i}", 40 + i) for i in range(8)]
for _base, _at in (("a", 50), ("bb", 60), ("cc", 70), ("pcl", 80), ("pch", 90)):
    NAMES += [(f"reg_{_base}{i}", _at + i) for i in range(8)]

TRANSISTORS: list[tuple[int, int, int]] = [(3, 17, 1), (2, 19, 2), (15, 17, 19)]

PULLED_UP: tuple[int, ...] = (17,)


def transistor_line(gate: int, first: int, second: int, pullup: str = "false") -> str:
    return f"['t0',{gate},{first},{second},[1,2,3,4],[1,1,1,1,5],{pullup},]"


def segment_line(number: int, mark: str) -> str:
    return f"[{number},'{mark}',0,1,2,3,4,5,6,7,8]"


def build(
    where: Path,
    names: list[tuple[str, int]] | None = None,
    transistors: list[tuple[int, int, int]] | None = None,
    pulled_up: tuple[int, ...] = PULLED_UP,
    pullup_entries: int = netlist.TRANSISTORS_THAT_ARE_PULLUPS,
    extra_names: str = "",
    extra_transistors: str = "",
    extra_segments: str = "",
) -> Path:
    chosen = NAMES if names is None else names
    body = "\n".join(f"{name}: {number}," for name, number in chosen)
    (where / "nodenames.js").write_text(
        "// a synthetic netlist\nvar nodenames = {\n" + body + "\n" + extra_names + "\n}\n"
    )
    wanted = TRANSISTORS if transistors is None else transistors
    lines = [transistor_line(gate, first, second) for gate, first, second in wanted]
    lines += [transistor_line(1, 1, 1, "true") for _ in range(pullup_entries)]
    (where / "transdefs.js").write_text(
        "var transdefs = [\nskipped\n" + "\n".join(lines) + "\n" + extra_transistors + "\n]\n"
    )
    segments = [segment_line(number, "+") for number in pulled_up]
    segments += [segment_line(200, "-")]
    (where / "segdefs.js").write_text(
        "var segdefs = [\nskipped\n" + "\n".join(segments) + "\n" + extra_segments + "\n]\n"
    )
    stamp(where)
    return where


def stamp(where: Path) -> Path:
    """An identity file for the synthetic netlist, so the real check runs on it.

    The digests are taken from the files that were just written, which would be
    circular if the point were to prove the files right. It is not: the point is
    that the loader refuses a file the identity does not name, and a synthetic
    identity exercises that exactly as a real one does.
    """
    manifest = where / "netlist.json"
    manifest.write_text(
        json.dumps(
            {
                "algorithm": {"licence": "MIT"},
                "files": [
                    {
                        "file": name,
                        "bytes": (where / name).stat().st_size,
                        "sha256": hashlib.sha256((where / name).read_bytes()).hexdigest(),
                        "retrievedFrom": f"https://example.invalid/{name}",
                    }
                    for name in netlist.FILES
                ],
            }
        )
    )
    return manifest


class Fixture(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.hold = tempfile.TemporaryDirectory()
        self.addCleanup(self.hold.cleanup)
        self.where = build(Path(self.hold.name))

    def parsed(self) -> netlist.Netlist:
        return netlist.Netlist(self.where, self.where / "netlist.json")

    def part(self) -> netlist.Simulation:
        return netlist.Simulation(self.where, self.where / "netlist.json")


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

    def test_the_identity_carried_here_names_the_three_files(self) -> None:
        held = netlist.identity()

        self.assertEqual([one["file"] for one in held["files"]], list(netlist.FILES))

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
        part = self.part()
        queued: list[int] = []

        part._queue(netlist.GROUND, queued)

        self.assertEqual(queued, [])

    def test_a_net_is_queued_once_however_many_times_it_is_reached(self) -> None:
        part = self.part()
        queued: list[int] = []

        part._queue(17, queued)
        part._queue(17, queued)

        self.assertEqual(queued, [17])

    def test_resolving_a_rail_does_nothing(self) -> None:
        part = self.part()
        before = bytes(part.state)

        part._resolve(netlist.POWER, [])

        self.assertEqual(bytes(part.state), before)

    def test_a_group_seeded_on_a_rail_is_just_that_rail(self) -> None:
        """The walk stops at a rail rather than crossing it.

        Nothing reaches this through a normal propagation, because resolution
        refuses a rail before it ever collects a group. It is reached here so the
        rule is stated for every case rather than for the ones that come up.
        """
        part = self.part()

        part._collect(netlist.GROUND)

        self.assertEqual(part._group, [netlist.GROUND])

    def test_a_net_reached_through_the_far_end_of_a_transistor_joins_the_group(self) -> None:
        part = self.part()
        part.on[2] = 1

        part._regroup(19)

        self.assertIn(17, part._group)

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


class ClockTest(Fixture):
    def quiet(self) -> netlist.Simulation:
        part = self.part()
        part.pullup[17] = 0
        part.drive(1, "clk")
        return part

    def arrange(self, part: netlist.Simulation, **levels: int) -> None:
        for name, level in levels.items():
            part.state[part.number(name)] = level

    def test_a_refresh_cycle_is_left_alone(self) -> None:
        part = self.quiet()
        self.arrange(part, clk=0, _rfsh=0)
        part.memory[0] = 0x5A

        part.half_cycle()

        self.assertEqual(part.data(), 0)

    def test_an_instruction_read_answers_from_memory(self) -> None:
        part = self.quiet()
        self.arrange(part, clk=0, _rfsh=1, _m1=0, _mreq=0, _rd=0, _wr=1, _iorq=1, t2=1, t3=0)
        part.memory[0] = 0x5A

        part.half_cycle()

        self.assertEqual(part.data(), 0x5A)

    def test_a_data_read_answers_from_memory(self) -> None:
        part = self.quiet()
        self.arrange(part, clk=0, _rfsh=1, _m1=1, _mreq=0, _rd=0, _wr=1, _iorq=1, t2=0, t3=1)
        part.memory[0] = 0x3C

        part.half_cycle()

        self.assertEqual(part.data(), 0x3C)

    def test_a_data_write_lands_in_memory(self) -> None:
        part = self.quiet()
        self.arrange(part, clk=0, _rfsh=1, _m1=1, _mreq=0, _rd=1, _wr=0, _iorq=1, t2=0, t3=1)
        self.arrange(part, db0=1, db1=1)

        part.half_cycle()

        self.assertEqual(part.memory[0], 0x03)

    def test_a_port_read_answers_from_the_ports(self) -> None:
        part = self.quiet()
        self.arrange(part, clk=0, _rfsh=1, _m1=1, _mreq=1, _rd=0, _wr=1, _iorq=0, t2=0, t3=1)
        part.ports[0] = 0x77

        part.half_cycle()

        self.assertEqual(part.data(), 0x77)

    def test_a_port_write_lands_in_the_ports(self) -> None:
        part = self.quiet()
        self.arrange(part, clk=0, _rfsh=1, _m1=1, _mreq=1, _rd=1, _wr=0, _iorq=0, t2=0, t3=1)
        self.arrange(part, db2=1)

        part.half_cycle()

        self.assertEqual(part.ports[0], 0x04)

    def test_a_cycle_matching_nothing_touches_neither_memory_nor_ports(self) -> None:
        part = self.quiet()
        self.arrange(part, clk=0, _rfsh=1, _m1=1, _mreq=1, _rd=1, _wr=1, _iorq=1, t2=0, t3=0)

        part.half_cycle()

        self.assertEqual((part.memory[0], part.ports[0]), (0, 0))

    def test_the_clock_turns_over_on_every_half_cycle(self) -> None:
        part = self.quiet()

        part.half_cycle()

        self.assertEqual((part.read("clk"), part.half_cycles), (0, 1))

    def test_a_reset_hands_the_part_back(self) -> None:
        part = self.quiet()

        self.assertIs(part.reset(), part)

    def test_a_reset_starts_the_count_at_the_half_cycles_it_holds_for(self) -> None:
        part = self.quiet()

        part.reset()

        self.assertEqual(part.half_cycles, netlist.RESET_HALF_CYCLES)

    def test_a_program_loads_where_it_is_asked_to(self) -> None:
        part = self.quiet()

        part.load(b"\x11\x22", at=4)

        self.assertEqual(bytes(part.memory[4:6]), b"\x11\x22")

    def test_the_program_counter_reads_high_byte_first(self) -> None:
        part = self.quiet()
        self.arrange(part, reg_pch0=1, reg_pcl1=1)

        self.assertEqual(part.pc(), 0x0102)

    def test_the_address_bus_reads_sixteen_nets(self) -> None:
        part = self.quiet()
        self.arrange(part, ab15=1, ab0=1)

        self.assertEqual(part.address(), 0x8001)

    def test_a_main_register_is_read_under_the_name_an_instruction_uses(self) -> None:
        part = self.quiet()
        self.arrange(part, reg_bb0=1, reg_bb3=1)

        self.assertEqual(part.register("b"), 0x09)

    def test_a_register_with_no_shadow_is_read_under_its_own_name(self) -> None:
        part = self.quiet()
        self.arrange(part, reg_a7=1)

        self.assertEqual(part.register("a"), 0x80)


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
            code = netlist.main([], self.where, self.where / "netlist.json")

        self.assertEqual((code, "REFUSED" in held.getvalue()), (1, True))

    def test_a_run_that_never_settles_is_reported_as_a_failure(self) -> None:
        build(self.where, transistors=[(18, 18, 1)], pulled_up=(18,))
        held = io.StringIO()

        with redirect_stdout(held):
            code = netlist.main(["--half-cycles", "2"], self.where, self.where / "netlist.json")

        self.assertEqual(code, 1)


PRESENT = all((netlist.ROOT / name).is_file() for name in netlist.FILES)


@unittest.skipUnless(PRESENT, "the Visual 6502 netlist is not on this machine")
class AgainstTheDieTest(unittest.TestCase):
    """The things a synthetic circuit cannot show: that it runs the part."""

    part: ClassVar[netlist.Simulation]

    @classmethod
    @override
    def setUpClass(cls) -> None:
        cls.part = netlist.Simulation()
        cls.part.reset()
        cls.part.load(netlist.SAMPLE)
        for _ in range(netlist.DEFAULT_HALF_CYCLES):
            cls.part.half_cycle()

    def test_the_netlist_is_the_one_that_was_read(self) -> None:
        self.assertEqual((self.part.transistors, self.part.pullups), (6781, 2059))

    def test_every_propagation_comes_to_rest(self) -> None:
        self.assertEqual(self.part.unsettled, 0)

    def test_it_executes_the_load_it_was_given(self) -> None:
        self.assertEqual(self.part.register("a"), 0x42)

    def test_it_executes_the_increment_after_the_load(self) -> None:
        self.assertEqual(self.part.register("b"), 0x9A)

    def test_it_carries_on_past_the_program(self) -> None:
        self.assertEqual((self.part.register("c"), self.part.pc()), (0x17, 0x0011))


@unittest.skipUnless(PRESENT, "the Visual 6502 netlist is not on this machine")
class MeasuredRatherThanTakenTest(unittest.TestCase):
    """The two things this package established for itself, driven against the die.

    Both look like details and neither is. The first decides whether the netlist
    ever comes to rest; the second decides whether a register read means anything.
    """

    def test_the_single_letter_names_hold_the_shadow_set_rather_than_the_main_one(self) -> None:
        """`LD B,0x99` then `INC B` puts 0x9A somewhere, and not under `reg_b`."""
        part = netlist.Simulation()
        part.reset()
        part.load(netlist.SAMPLE)
        for _ in range(netlist.DEFAULT_HALF_CYCLES):
            part.half_cycle()

        self.assertNotEqual(part.bus("reg_b", 8), 0x9A)

    def test_loading_the_pullup_entries_stops_the_netlist_ever_resting(self) -> None:
        """The one thing that changes is whether those 32 entries are loaded.

        They are written with their gate tied to power, so each one joins a net
        to the power rail and never opens. Loaded, they fight whatever pulls
        those nets down and the netlist never comes to rest.
        """
        held = (netlist.ROOT / "transdefs.js").read_text().splitlines()
        flagged = [line for line in held if line.rstrip().endswith("true,],")]
        with tempfile.TemporaryDirectory() as hold:
            spare = Path(hold) / "transdefs.js"
            spare.write_text("\n".join(line.replace("true,", "false,") for line in flagged) + "\n")
            part = netlist.Simulation()
            part._read_transistors(spare)

        part.reset()
        part.load(netlist.SAMPLE)
        for _ in range(netlist.DEFAULT_HALF_CYCLES):
            part.half_cycle()

        self.assertEqual(
            (len(flagged), part.unsettled > 0), (netlist.TRANSISTORS_THAT_ARE_PULLUPS, True)
        )


if __name__ == "__main__":
    unittest.main()
