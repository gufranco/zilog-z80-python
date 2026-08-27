"""That the switch-level run is the reference's, and that it runs the part.

The netlist itself is not carried, so every check here is driven against a
synthetic one built in the fixture: four files in the published formats
describing a circuit small enough to reason about by hand. That is not a
convenience. A check that only runs when a two megabyte file happens to be on
the machine is a check that reports success by being skipped.

The real netlist is used when it is present, and only for the one thing a
synthetic circuit cannot show: that the part fetches, executes and lands on a
register value nothing else would produce.
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

NAMES = [
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
NAMES += [(f"reg_a{i}", 50 + i) for i in range(8)]
NAMES += [(f"reg_b{i}", 60 + i) for i in range(8)]
NAMES += [(f"reg_c{i}", 70 + i) for i in range(8)]
NAMES += [(f"reg_pcl{i}", 80 + i) for i in range(8)]
NAMES += [(f"reg_pch{i}", 90 + i) for i in range(8)]

TRANSISTORS = [(1, 3, 17, 1), (2, 18, 18, 1), (3, 19, 2, 19), (4, 15, 17, 19)]

PULLED_UP = (17, 18)


def transistor_line(number: int, gate: int, first: int, second: int, pullup: str) -> str:
    return f"['t{number}',{gate},{first},{second},[1,2,3,4],[1,1,1,1,5],{pullup},]"


def segment_line(number: int, mark: str) -> str:
    return f"[ {number},'{mark}',0,1,2,3,4,5,6,7,8]"


def build(
    where: Path,
    names: list[tuple[str, int]] | None = None,
    transistors: list[tuple[int, int, int, int]] | None = None,
    pulled_up: tuple[int, ...] = PULLED_UP,
    extra_names: str = "",
    extra_custom: str = "",
    extra_transistors: str = "",
    extra_segments: str = "",
) -> Path:
    chosen = NAMES if names is None else names
    body = "\n".join(f"{name}: {number}," for name, number in chosen)
    (where / "nodenames.js").write_text(
        "// a synthetic netlist\nvar nodenames = {\n" + body + "\n" + extra_names + "\n}\n"
    )
    (where / "netnames.js").write_text(
        "// overrides\nvar nodenames_override = {\n" + extra_custom + "\n}\n"
    )
    wanted = TRANSISTORS if transistors is None else transistors
    lines = [
        transistor_line(number, gate, first, second, "false")
        for number, gate, first, second in wanted
    ]
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
                "files": [
                    {
                        "file": name,
                        "bytes": (where / name).stat().st_size,
                        "sha256": hashlib.sha256((where / name).read_bytes()).hexdigest(),
                        "retrievedFrom": f"https://example.invalid/{name}",
                    }
                    for name in netlist.FILES
                ]
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


class LoadingTest(Fixture):
    def test_a_missing_file_names_itself_and_where_it_comes_from(self) -> None:
        (self.where / "transdefs.js").unlink()

        with self.assertRaises(netlist.Missing) as raised:
            self.parsed()

        self.assertIn("transdefs.js", str(raised.exception))
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

    def test_the_identity_carried_here_names_the_four_files(self) -> None:
        held = netlist.identity()

        self.assertEqual([one["file"] for one in held["files"]], list(netlist.FILES))

    def test_the_three_fixed_nets_are_checked_rather_than_trusted(self) -> None:
        moved = [(name, 5 if name == "vss" else number) for name, number in NAMES]
        build(self.where, names=moved)

        with self.assertRaises(netlist.Missing) as raised:
            self.parsed()

        self.assertIn("vss", str(raised.exception))

    def test_the_transistors_and_the_pullups_are_the_ones_written(self) -> None:
        held = self.parsed()

        self.assertEqual((held.transistors, held.pullups), (4, 2))

    def test_a_transistor_marked_a_pullup_is_counted_and_not_loaded(self) -> None:
        build(self.where, extra_transistors=transistor_line(9, 3, 17, 1, "true"))

        held = self.parsed()

        self.assertEqual((held.transistors, held.skipped_pullups), (4, 1))

    def test_a_rail_connection_is_moved_to_the_second_place(self) -> None:
        build(self.where, transistors=[(1, 3, 1, 17)])

        held = self.parsed()

        self.assertEqual((held.first_of[1], held.second_of[1]), (17, 1))

    def test_a_net_past_the_bound_this_was_read_at_is_refused(self) -> None:
        build(self.where, extra_names="beyond: 99999,")

        with self.assertRaises(netlist.Missing) as raised:
            self.parsed()

        self.assertIn("99999", str(raised.exception))

    def test_a_transistor_past_the_bound_this_was_read_at_is_refused(self) -> None:
        build(self.where, extra_transistors=transistor_line(99999, 3, 17, 1, "false"))

        with self.assertRaises(netlist.Missing) as raised:
            self.parsed()

        self.assertIn("99999", str(raised.exception))

    def test_a_pulled_up_net_past_the_bound_is_refused(self) -> None:
        build(self.where, extra_segments=segment_line(99999, "+"))

        with self.assertRaises(netlist.Missing) as raised:
            self.parsed()

        self.assertIn("99999", str(raised.exception))

    def test_lines_that_are_not_entries_are_passed_over(self) -> None:
        build(
            self.where,
            extra_names="not an entry\nweird: abc,",
            extra_transistors="not an entry\n['t8',1,2]",
            extra_segments="not an entry\n[ 5,'-']",
        )

        held = self.parsed()

        self.assertEqual(held.transistors, 4)

    def test_a_duplicate_name_keeps_the_first_one(self) -> None:
        build(self.where, extra_names="out: 150,\nfresh: 17,")

        held = self.parsed()

        self.assertEqual((held.number("out"), held.number("fresh")), (17, 0))

    def test_the_custom_file_renames_rather_than_shadowing(self) -> None:
        build(self.where, extra_custom="out: 150,")

        held = self.parsed()

        self.assertEqual((held.number("out"), held.named[17]), (150, ""))

    def test_the_custom_file_carries_buses(self) -> None:
        build(self.where, extra_custom="pair: [17,18],\nlone: [19],")

        held = self.parsed()

        self.assertEqual((held.buses["pair"], held.number("lone")), ((17, 18), 19))

    def test_an_unknown_name_is_net_zero_rather_than_an_error(self) -> None:
        held = self.parsed()

        self.assertEqual(held.number("nothing_is_called_this"), 0)


class ReadoutTest(Fixture):
    def test_a_net_that_is_not_floating_reads_its_level(self) -> None:
        held = self.parsed()
        held.state[17] = 1

        self.assertEqual(held.read("out"), 1)

    def test_a_floating_net_nothing_drives_reads_as_high_impedance(self) -> None:
        held = self.parsed()
        held.floats[19] = 1
        held.pulled_up[19] = 0

        self.assertEqual(held.read("quiet"), 2)

    def test_a_floating_net_with_a_pullup_reads_high(self) -> None:
        held = self.parsed()
        held.floats[17] = 1

        self.assertEqual(held.read("out"), 1)

    def test_a_floating_net_something_drives_reads_its_level(self) -> None:
        held = self.parsed()
        held.floats[17] = 1
        held.on[1] = 1
        held.state[17] = 0

        self.assertEqual(held.read("out"), 0)

    def test_a_bus_reads_least_significant_net_first(self) -> None:
        held = self.parsed()
        held.state[40] = 1
        held.state[42] = 1

        self.assertEqual(held.bus("db", 8), 0x05)


class ResolutionTest(Fixture):
    def test_a_group_that_reaches_ground_settles_low(self) -> None:
        part = self.part()
        part.state[17] = 1
        part.on[1] = 1

        part.settle([17])

        self.assertEqual(part.state[17], 0)

    def test_a_group_that_reaches_power_settles_high(self) -> None:
        part = self.part()
        part.on[3] = 1
        part.state[19] = 0

        part.settle([19])

        self.assertEqual(part.state[19], 1)

    def test_a_net_being_pulled_low_settles_low(self) -> None:
        part = self.part()
        part.high[17] = 0
        part.low[17] = 1
        part.state[17] = 1

        part.settle([17])

        self.assertEqual(part.state[17], 0)

    def test_a_group_nothing_drives_takes_the_best_connected_level(self) -> None:
        part = self.part()
        part.high[17] = 0
        part.on[4] = 1
        part.state[17] = 0
        part.state[19] = 1

        part.settle([17])

        self.assertEqual(part.state[17], 1)

    def test_a_net_nobody_gates_settles_low_rather_than_keeping_its_level(self) -> None:
        """The reference starts its weight at zero, so a net with no gates loses.

        Starting it at minus one instead lets such a net keep whatever level it
        happened to hold, which is a different chip. Both run the real netlist to
        the same registers, and the reference's choice is the one carried.
        """
        part = self.part()
        part.high[17] = 0
        part.state[17] = 1

        part.settle([17])

        self.assertEqual(part.state[17], 0)

    def test_a_ring_that_never_rests_is_recorded_rather_than_raised(self) -> None:
        part = self.part()

        part.settle([18])

        self.assertEqual(part.unsettled, 1)

    def test_driving_a_net_to_the_level_it_already_holds_does_nothing(self) -> None:
        part = self.part()
        part.high[17] = 1
        before = part.unsettled

        part.drive(1, "out")

        self.assertEqual(part.unsettled, before)

    def test_the_rails_are_never_queued_for_resolution(self) -> None:
        part = self.part()
        queued: list[int] = []

        part._queue(netlist.GROUND, queued)

        self.assertEqual(queued, [])

    def test_resolving_a_rail_does_nothing(self) -> None:
        part = self.part()
        before = bytes(part.state)

        part._resolve(netlist.POWER, [])

        self.assertEqual(bytes(part.state), before)

    def test_a_net_is_queued_once_however_many_times_it_is_reached(self) -> None:
        part = self.part()
        queued: list[int] = []

        part._queue(17, queued)
        part._queue(17, queued)

        self.assertEqual(queued, [17])

    def test_a_group_seeded_on_a_rail_is_just_that_rail(self) -> None:
        """The swap to the front has nothing to swap when the rail arrives first.

        Nothing reaches this through a normal propagation, because resolution
        refuses a rail before it ever collects a group. It is reached here so the
        ordering rule is stated for every case rather than for the ones that
        happen to come up.
        """
        part = self.part()

        part._collect(netlist.GROUND)

        self.assertEqual(part._group, [netlist.GROUND])

    def test_a_net_going_low_leaves_an_already_open_transistor_alone(self) -> None:
        part = self.part()
        part.high[19] = 0
        part.low[19] = 1
        part.state[19] = 1
        part.on[3] = 0

        part.settle([19])

        self.assertEqual((part.state[19], part.on[3]), (0, 0))

    def test_the_connected_nets_leave_out_the_rails(self) -> None:
        part = self.part()

        found = part.connected()

        self.assertNotIn(netlist.GROUND, found)


class ClockTest(Fixture):
    def quiet(self) -> netlist.Simulation:
        """A synthetic part whose control nets are read as levels rather than as buses.

        Every net the reference marks floating is cleared here, because a
        floating net with nothing attached reads as high impedance, and high
        impedance is truthy. Leaving them floating would make every condition in
        `half_cycle` read as though the line were released.
        """
        part = self.part()
        for number in (17, 18):
            part.high[number] = 0
            part.pulled_up[number] = 0
        for number in range(len(part.floats)):
            part.floats[number] = 0
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


class CommandLineTest(Fixture):
    def test_no_arguments_asks_for_the_default_run(self) -> None:
        found = netlist.options([])

        self.assertEqual(found, 130)

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
        held = io.StringIO()

        with redirect_stdout(held):
            code = netlist.main(["--half-cycles", "2"], self.where, self.where / "netlist.json")

        self.assertEqual(code, 1)


REAL = netlist.ROOT
PRESENT = all((REAL / name).is_file() for name in netlist.FILES)


@unittest.skipUnless(PRESENT, "the Z80Explorer netlist is not on this machine")
class AgainstTheDieTest(unittest.TestCase):
    """The one thing a synthetic circuit cannot show: that it runs the part."""

    part: ClassVar[netlist.Simulation]

    @classmethod
    @override
    def setUpClass(cls) -> None:
        cls.part = netlist.Simulation(REAL)
        cls.part.reset()
        cls.part.load(bytes([0x3E, 0x42, 0x06, 0x99, 0x0E, 0x17, 0x04, 0x00]))
        for _ in range(130):
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


if __name__ == "__main__":
    unittest.main()
