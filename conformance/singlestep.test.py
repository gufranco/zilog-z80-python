import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import singlestep


def case(name="00 0000", **overrides):
    built = {
        "name": name,
        "initial": {
            "pc": 0x8000,
            "sp": 0xFFFE,
            "a": 0x00,
            "b": 0x00,
            "c": 0x00,
            "d": 0x00,
            "e": 0x00,
            "f": 0x00,
            "h": 0x00,
            "l": 0x00,
            "i": 0x00,
            "r": 0x00,
            "ei": 0,
            "wz": 0x0000,
            "ix": 0x0000,
            "iy": 0x0000,
            "af_": 0x0000,
            "bc_": 0x0000,
            "de_": 0x0000,
            "hl_": 0x0000,
            "im": 0,
            "p": 0,
            "q": 0,
            "iff1": 0,
            "iff2": 0,
            "ram": [[0x8000, 0x00]],
        },
        "final": {
            "a": 0x00,
            "b": 0x00,
            "c": 0x00,
            "d": 0x00,
            "e": 0x00,
            "f": 0x00,
            "h": 0x00,
            "l": 0x00,
            "i": 0x00,
            "r": 0x01,
            "ei": 0,
            "wz": 0x0000,
            "ix": 0x0000,
            "iy": 0x0000,
            "af_": 0x0000,
            "bc_": 0x0000,
            "de_": 0x0000,
            "hl_": 0x0000,
            "im": 0,
            "p": 0,
            "q": 0,
            "iff1": 0,
            "iff2": 0,
            "pc": 0x8001,
            "sp": 0xFFFE,
            "ram": [[0x8000, 0x00]],
        },
    }
    built.update(overrides)
    return built


class CheckTest(unittest.TestCase):
    def test_a_case_the_core_reproduces_reports_nothing(self):
        self.assertEqual(singlestep.check(case()), [])

    def test_a_register_the_core_gets_wrong_is_named(self):
        wrong = case()
        wrong["final"]["b"] = 0x42

        found = singlestep.check(wrong)

        self.assertEqual(found, [("b", 0x42, 0x00)])

    def test_a_byte_of_memory_the_core_gets_wrong_is_named_by_address(self):
        wrong = case()
        wrong["final"]["ram"] = [[0x8000, 0x99]]

        found = singlestep.check(wrong)

        self.assertEqual(found[0][0], "ram[8000]")

    def test_a_flag_the_case_omits_is_not_compared(self):
        partial = case()
        del partial["final"]["wz"]

        self.assertEqual(singlestep.check(partial), [])

    def test_a_register_the_case_never_mentions_is_left_holding_what_it_held(self):
        partial = case()
        del partial["initial"]["ix"]
        del partial["final"]["ix"]

        self.assertEqual(singlestep.check(partial), [])

    def test_an_interrupt_latch_is_compared_as_a_state_rather_than_a_number(self):
        latched = case()
        latched["initial"]["iff1"] = 1
        latched["final"]["iff1"] = 1

        self.assertEqual(singlestep.check(latched), [])


class PortTest(unittest.TestCase):
    def test_a_read_is_answered_with_what_the_case_says_the_port_gave(self):
        reading = case(
            name="ED 40",
            initial={**case()["initial"], "ram": [[0x8000, 0xED], [0x8001, 0x40]]},
        )
        reading["final"] = {
            **case()["final"],
            "b": 0x42,
            "f": 0x04,
            "r": 0x02,
            "pc": 0x8002,
            "q": 0x04,
            "wz": 0x0001,
            "ram": [[0x8000, 0xED], [0x8001, 0x40]],
        }
        reading["ports"] = [[0x0000, 0x42, "r"]]

        self.assertEqual(singlestep.check(reading), [])

    def test_a_transaction_the_core_does_not_perform_is_reported(self):
        expecting = case()
        expecting["ports"] = [[0x0000, 0x42, "r"]]

        found = singlestep.check(expecting)

        self.assertEqual(found[-1][0], "ports")

    def test_a_port_answers_zero_once_the_case_runs_out_of_answers(self):
        ports = singlestep.ScriptedPorts([])

        self.assertEqual(ports.read(0x1234), 0)

    def test_a_write_is_recorded_rather_than_answered(self):
        ports = singlestep.ScriptedPorts([])

        ports.write(0x1234, 0x42)

        self.assertEqual(ports.log, [[0x1234, 0x42, "w"]])


class OptionTest(unittest.TestCase):
    def test_a_directory_alone_is_enough(self):
        self.assertEqual(singlestep.options(["suite"]), (Path("suite"), None, None))

    def test_a_limit_bounds_the_cases_read_from_each_file(self):
        self.assertEqual(singlestep.options(["suite", "--limit", "5"])[1], 5)

    def test_an_opcode_narrows_the_run_to_one_file(self):
        self.assertEqual(singlestep.options(["suite", "--opcode", "00"])[2], "00")

    def test_no_arguments_at_all_is_refused(self):
        with self.assertRaises(singlestep.Usage):
            singlestep.options([])

    def test_a_limit_with_no_number_is_refused(self):
        with self.assertRaises(singlestep.Usage):
            singlestep.options(["suite", "--limit"])

    def test_an_opcode_with_no_name_is_refused(self):
        with self.assertRaises(singlestep.Usage):
            singlestep.options(["suite", "--opcode"])

    def test_a_second_directory_is_refused(self):
        with self.assertRaises(singlestep.Usage):
            singlestep.options(["one", "two"])

    def test_options_with_no_directory_among_them_is_refused(self):
        with self.assertRaises(singlestep.Usage):
            singlestep.options(["--limit", "5"])


class RunTest(unittest.TestCase):
    def suite(self, cases, name="00"):
        directory = Path(tempfile.mkdtemp())
        (directory / f"{name}.json").write_text(json.dumps(cases))
        return directory

    def test_a_suite_the_core_reproduces_exits_clean(self):
        directory = self.suite([case()])

        self.assertEqual(singlestep.run([str(directory)]), 0)

    def test_a_suite_with_a_disagreement_does_not(self):
        wrong = case()
        wrong["final"]["b"] = 0x42
        directory = self.suite([wrong])

        self.assertEqual(singlestep.run([str(directory)]), 1)

    def test_a_directory_with_no_cases_is_reported_rather_than_passing(self):
        self.assertEqual(singlestep.run([str(Path(tempfile.mkdtemp()))]), 1)

    def test_naming_an_opcode_that_is_not_there_is_the_same(self):
        directory = self.suite([case()])

        self.assertEqual(singlestep.run([str(directory), "--opcode", "ff"]), 1)

    def test_a_limit_stops_the_run_reading_the_whole_file(self):
        wrong = case()
        wrong["final"]["b"] = 0x42
        directory = self.suite([case(), wrong])

        self.assertEqual(singlestep.run([str(directory), "--limit", "1"]), 0)

    def test_more_than_twenty_failures_are_counted_rather_than_all_printed(self):
        wrong = case()
        wrong["final"]["b"] = 0x42
        directory = self.suite([wrong] * 25)

        self.assertEqual(singlestep.run([str(directory)]), 1)


class EntryTest(unittest.TestCase):
    def test_no_arguments_prints_the_usage_and_says_so(self):
        self.assertEqual(singlestep.main([]), 2)

    def test_a_real_run_returns_what_the_run_returned(self):
        directory = Path(tempfile.mkdtemp())
        (directory / "00.json").write_text(json.dumps([case()]))

        self.assertEqual(singlestep.main([str(directory)]), 0)


if __name__ == "__main__":
    unittest.main()
