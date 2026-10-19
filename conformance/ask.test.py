import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, ClassVar, override

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import ask, netlist  # noqa: E402

PRESENT = all(
    (ROOT / "docs" / "independent" / "visual6502" / str(one["file"])).is_file()
    for one in netlist.identity()["netlist"]
)


def an_answer(question: str, agrees: bool) -> dict[str, Any]:
    return {"question": question, "divergence": "x", "die": 1, "model": 1 if agrees else 2}


class AnswerTest(unittest.TestCase):
    def test_an_answer_says_the_two_agree_when_they_do(self) -> None:
        # Arrange
        same = {"a": 1}

        # Act
        found = ask.answer("q", "d", same, {"a": 1})

        # Assert
        self.assertEqual(found["agrees"], True)

    def test_and_says_they_part_when_they_do_not(self) -> None:
        # Arrange
        theirs = {"a": 1}

        # Act
        found = ask.answer("q", "d", theirs, {"a": 2})

        # Assert
        self.assertEqual(found["agrees"], False)


class RecordTest(unittest.TestCase):
    def test_the_record_beside_this_one_is_read_at_rung_three(self) -> None:
        # Arrange
        held = ask.recorded()

        # Act
        rung = held["rung"]

        # Assert
        self.assertEqual(rung, 3)

    def test_every_question_this_asks_is_in_the_record(self) -> None:
        # Arrange
        held = {one["question"] for one in ask.recorded()["answers"]}

        # Act
        asked = set(ask.QUESTIONS)

        # Assert
        self.assertEqual(held, asked)

    def test_every_answer_names_a_divergence_the_record_holds(self) -> None:
        # Arrange
        known = {
            one["id"]
            for one in json.loads((ROOT / "conformance" / "divergences.json").read_text())[
                "divergences"
            ]
        }

        # Act
        named = {one["divergence"] for one in ask.recorded()["answers"]}

        # Assert
        self.assertEqual(named - known, set())

    def test_the_sweep_compared_every_opcode_form_but_halt(self) -> None:
        # Arrange
        held = ask.recorded()["sweep"]

        # Act
        compared = held["compared"]

        # Assert
        self.assertEqual(compared, 1135)


class MainTest(unittest.TestCase):
    def test_a_refused_run_writes_nothing(self) -> None:
        # Arrange
        def refuse() -> list[dict[str, Any]]:
            raise netlist.Missing("no netlist here")

        out = Path(tempfile.mkdtemp()) / "die.json"

        # Act
        code = ask.main([str(out)], asking=refuse)

        # Assert
        self.assertEqual((code, out.is_file()), (1, False))

    def test_a_run_writes_every_answer_and_keeps_the_held_sweep(self) -> None:
        # Arrange
        given = [an_answer("one", True), an_answer("two", False)]
        out = Path(tempfile.mkdtemp()) / "die.json"

        # Act
        code = ask.main([str(out)], asking=lambda: given)

        # Assert
        written = json.loads(out.read_text())
        self.assertEqual(
            (code, written["answers"], written["sweep"]),
            (0, given, ask.recorded()["sweep"]),
        )

    def test_a_run_asked_to_sweep_writes_what_the_sweep_found(self) -> None:
        # Arrange
        out = Path(tempfile.mkdtemp()) / "die.json"
        swept = {"compared": 1, "differing": []}

        # Act
        code = ask.main([str(out), "--sweep"], asking=list, sweeping=lambda: swept)

        # Assert
        self.assertEqual((code, json.loads(out.read_text())["sweep"]), (0, swept))

    def test_an_unknown_option_is_refused(self) -> None:
        # Arrange
        argv = ["--everything"]

        # Act
        code = ask.main(argv, asking=list)

        # Assert
        self.assertEqual(code, 2)


@unittest.skipUnless(PRESENT, "the Visual 6502 netlist is not on this machine")
class AgainstTheDieTest(unittest.TestCase):
    found: ClassVar[dict[str, dict[str, Any]]]

    @classmethod
    @override
    def setUpClass(cls) -> None:
        cls.found = {one["question"]: one for one in ask.asked()}

    def test_every_answer_still_matches_the_record(self) -> None:
        # Arrange
        held = {one["question"]: one for one in ask.recorded()["answers"]}

        # Act
        found = self.found

        # Assert
        self.assertEqual(found, held)

    def test_a_sweep_compares_what_it_is_handed(self) -> None:
        # Arrange
        listing = [("add hl,bc", bytes([0x09]))]

        # Act
        found = ask.sweep(lambda: listing)

        # Assert
        self.assertEqual(found, {"compared": 1, "differing": []})

    def test_the_refresh_cycle_puts_the_vector_register_on_the_upper_pins(self) -> None:
        # Arrange
        found = self.found["refresh-address"]

        # Act
        upper = found["die"] >> 8

        # Assert
        self.assertEqual(upper, 0x9C)

    def test_a_halted_part_fetches_from_the_address_after_the_halt(self) -> None:
        # Arrange
        found = self.found["halt-fetch-address"]

        # Act
        addresses = found["die"]

        # Assert
        self.assertEqual(addresses, [0x0002, 0x0002])

    def test_the_acknowledge_cycle_takes_seven_states(self) -> None:
        # Arrange
        found = self.found["mode-one-response"]

        # Act
        states = found["die"]["firstCycleStates"]

        # Assert
        self.assertEqual(states, 7)

    def test_the_whole_vector_byte_reaches_the_pointer(self) -> None:
        # Arrange
        found = self.found["mode-two-response"]

        # Act
        pointer = found["die"]["pointer"]

        # Assert
        self.assertEqual(pointer, 0x0021)

    def test_a_short_nonmaskable_pulse_is_taken_by_the_die_and_not_by_the_model(self) -> None:
        # Arrange
        found = self.found["nonmaskable-short-pulse"]

        # Act
        pair = (found["die"], found["model"])

        # Assert
        self.assertEqual(pair, (True, False))

    def test_the_die_keeps_the_flags_latch_across_an_index_prefix(self) -> None:
        # Arrange
        found = self.found["prefixed-carry-flags"]

        # Act
        agrees = found["agrees"]

        # Assert
        self.assertFalse(agrees)

    def test_the_die_grants_the_bus_where_the_model_does(self) -> None:
        # Arrange
        found = self.found["bus-request"]

        # Act
        agrees = found["agrees"]

        # Assert
        self.assertTrue(agrees)


if __name__ == "__main__":
    unittest.main()
