"""That the WZ probe reports the die and refuses when it cannot."""

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, ClassVar, override

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "conformance"))

netlist = importlib.import_module("netlist")
wz = importlib.import_module("wz")

PRESENT = all(
    (ROOT / "docs" / "independent" / "visual6502" / str(one["file"])).is_file()
    for one in netlist.identity()["netlist"]
)


def a_probe(name: str, group: str, pair: str, written: bool) -> dict[str, Any]:
    return {"instruction": name, "group": group, "pair": pair, "written": written, "a": "0x00"}


class CalibrationTest(unittest.TestCase):
    def held(self, **changes: Any) -> list[dict[str, Any]]:
        found = [
            a_probe("nop", "control", "0x5555", False),
            a_probe("ld a,n", "control", "0x5555", False),
            a_probe("ld a,(nn)", "reads", "0x1235", True),
        ]
        for at, value in changes.items():
            found[int(at[1:])]["pair"] = value
            found[int(at[1:])]["written"] = value != "0x5555"
        return found

    def test_a_run_that_answers_both_controls_is_calibrated(self) -> None:
        self.assertTrue(wz.calibrated(self.held()))

    def test_a_control_that_reports_a_value_fails_calibration(self) -> None:
        self.assertFalse(wz.calibrated(self.held(n0="0x1234")))

    def test_the_documented_case_giving_the_wrong_value_fails_it_too(self) -> None:
        self.assertFalse(wz.calibrated(self.held(n2="0x1234")))

    def test_a_run_with_no_controls_in_it_is_not_calibrated(self) -> None:
        self.assertFalse(wz.calibrated([a_probe("ld a,(nn)", "reads", "0x1235", True)]))

    def test_a_run_missing_the_documented_case_is_not_calibrated(self) -> None:
        self.assertFalse(wz.calibrated([a_probe("nop", "control", "0x5555", False)]))


class RecordTest(unittest.TestCase):
    def test_the_record_beside_this_one_reads_back(self) -> None:
        self.assertEqual(wz.recorded()["rung"], 3)

    def test_it_names_what_an_unwritten_pair_reads_as(self) -> None:
        self.assertEqual(wz.recorded()["unwritten"], f"{wz.UNWRITTEN:#06x}")

    def test_every_probe_in_it_says_which_instruction_it_ran(self) -> None:
        missing = [one for one in wz.recorded()["probes"] if not one.get("instruction")]

        self.assertEqual(missing, [])

    def test_the_recorded_run_is_itself_calibrated(self) -> None:
        self.assertTrue(wz.calibrated(wz.recorded()["probes"]))

    def test_every_probe_this_runs_is_in_the_record(self) -> None:
        held = {one["instruction"] for one in wz.recorded()["probes"]}

        self.assertEqual(held, {name for name, _group, _program in wz.PROBES})


class ProbeSetTest(unittest.TestCase):
    def test_no_probe_loads_the_power_up_pattern(self) -> None:
        loaded = [byte for _name, _group, program in wz.PROBES for byte in program]

        self.assertNotIn(0x55, loaded)

    def test_both_directions_are_probed(self) -> None:
        groups = {group for _name, group, _program in wz.PROBES}

        self.assertEqual(groups, {"control", "reads", "writes", "ports", "jumps"})

    def test_there_are_at_least_two_controls(self) -> None:
        controls = [one for one in wz.PROBES if one[1] == "control"]

        self.assertGreaterEqual(len(controls), 2)


@unittest.skipUnless(PRESENT, "the Visual 6502 netlist is not on this machine")
class AgainstTheDieTest(unittest.TestCase):
    found: ClassVar[list[dict[str, Any]]]

    @classmethod
    @override
    def setUpClass(cls) -> None:
        cls.found = wz.measure()

    def by_name(self, name: str) -> dict[str, Any]:
        return next(one for one in self.found if one["instruction"] == name)

    def test_the_run_is_calibrated(self) -> None:
        self.assertTrue(wz.calibrated(self.found))

    def test_an_instruction_that_touches_nothing_leaves_the_pair_alone(self) -> None:
        self.assertEqual(self.by_name("nop")["pair"], f"{wz.UNWRITTEN:#06x}")

    def test_a_load_from_an_address_leaves_that_address_plus_one(self) -> None:
        self.assertEqual(self.by_name("ld a,(nn)")["pair"], "0x1235")

    def test_a_jump_leaves_where_it_jumped_to(self) -> None:
        self.assertEqual(self.by_name("jp nn")["pair"], "0x0010")

    def test_a_port_read_leaves_the_accumulator_over_the_port_plus_one(self) -> None:
        self.assertEqual(self.by_name("in a,(n)")["pair"], "0x9c57")

    def test_storing_a_pair_keeps_the_high_byte(self) -> None:
        self.assertEqual(self.by_name("ld (nn),hl")["pair"], "0x1235")

    def test_storing_the_accumulator_clears_it(self) -> None:
        self.assertEqual(self.by_name("ld (nn),a")["pair"], "0x0035")

    def test_and_writing_a_port_clears_it_the_same_way(self) -> None:
        self.assertEqual(self.by_name("out (n),a")["pair"], "0x0057")

    def test_the_cleared_byte_was_loaded_before_it_was_cleared(self) -> None:
        seen = [value for _at, value in wz.trace(bytes([0x3E, 0x9C, 0x32, 0x34, 0x12]))]

        self.assertIn(0x1235, seen)

    def test_the_record_beside_this_one_still_matches_the_die(self) -> None:
        held = {one["instruction"]: one["pair"] for one in wz.recorded()["probes"]}

        self.assertEqual({one["instruction"]: one["pair"] for one in self.found}, held)


class MainTest(unittest.TestCase):
    def test_a_refused_run_writes_nothing(self) -> None:
        def _refuse() -> list[dict[str, Any]]:
            raise wz.netlist.Missing("no netlist here")

        with tempfile.TemporaryDirectory() as where:
            out = Path(where) / "wz.json"

            code = wz.main([str(out)], read=_refuse)

            self.assertEqual((code, out.is_file()), (1, False))

    def test_an_uncalibrated_run_writes_nothing_either(self) -> None:
        with tempfile.TemporaryDirectory() as where:
            out = Path(where) / "wz.json"

            code = wz.main([str(out)], read=lambda: [a_probe("nop", "control", "0x1234", True)])

            self.assertEqual((code, out.is_file()), (1, False))

    def test_a_calibrated_run_writes_a_record_that_reads_back(self) -> None:
        held = [
            a_probe("nop", "control", "0x5555", False),
            a_probe("ld a,(nn)", "reads", "0x1235", True),
        ]
        with tempfile.TemporaryDirectory() as where:
            out = Path(where) / "wz.json"

            code = wz.main([str(out)], read=lambda: held)

            self.assertEqual((code, json.loads(out.read_text())["rung"]), (0, 3))

    def test_the_record_it_writes_carries_every_probe_it_was_given(self) -> None:
        held = [
            a_probe("nop", "control", "0x5555", False),
            a_probe("ld a,(nn)", "reads", "0x1235", True),
        ]
        with tempfile.TemporaryDirectory() as where:
            out = Path(where) / "wz.json"
            wz.main([str(out)], read=lambda: held)

            self.assertEqual(len(wz.recorded(out)["probes"]), 2)


if __name__ == "__main__":
    unittest.main()
