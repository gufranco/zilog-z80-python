import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.bench import FACTS, RECORD, ROWS, ran, row
from z80 import MODELS, decode

HELD = RECORD

SHAPES = FACTS["machineCycleShapes"]

BIT_FORMS = {
    "BIT b, r": (0xCB, 0x40),
    "BIT b, (HL)": (0xCB, 0x46),
    "BIT b, (IX+d)": (0xDD, 0xCB, 0x01, 0x46),
    "BIT b, (IY+d)": (0xFD, 0xCB, 0x01, 0x46),
}

SETTING_FLAGS: dict[str, tuple[tuple[int, ...], dict[str, int], tuple[str, ...]]] = {
    "scf": ((0x37,), {"a": 0x00}, ("c",)),
    "cpl": ((0x2F,), {"a": 0x00}, ("h", "n", "x", "y")),
    "or a, negative": ((0xB7,), {"a": 0x80}, ("s",)),
    "xor a": ((0xAF,), {"a": 0x5A}, ("z", "pv")),
    "or a, bits 3 and 5": ((0xB7,), {"a": 0x28}, ("x", "y", "pv")),
}


def named_by_the_core() -> set[str]:
    found: set[str] = set()
    for byte in range(256):
        for encoding in (
            [byte, 0, 0, 0],
            [0xCB, byte, 0, 0],
            [0xED, byte, 0, 0],
            [0xDD, byte, 0, 0],
            [0xFD, byte, 0, 0],
            [0xDD, 0xCB, 0, byte],
            [0xFD, 0xCB, 0, byte],
        ):
            found.add(decode(bytes(encoding)).text.split()[0].lower())
    return found


def mnemonic_of(entry: dict[str, Any]) -> str:
    head = entry["instruction"].split(maxsplit=1)[0]
    return "".join(letter for letter in head if letter.isalpha()).lower()


def settled_by(program: tuple[int, ...]) -> dict[str, bool]:
    n, h = 1 << FACTS["flagRegister"]["bits"]["n"], 1 << FACTS["flagRegister"]["bits"]["h"]
    f = ran(program, {"f": n, "hl": 0x3000, "ix": 0x3000, "iy": 0x3000}).registers.f
    return {"h": bool(f & h), "n": bool(f & n)}


def flags_set_by(program: tuple[int, ...], setup: dict[str, int]) -> int:
    held: int = ran(program, {"f": 0x00, **setup}).registers.f
    return held


class RowLookupTest(unittest.TestCase):
    def test_a_page_with_one_row_gives_that_row(self) -> None:
        # Arrange
        page = 180

        # Act
        found = row(page)

        # Assert
        self.assertEqual(found["tStates"], 4)

    def test_a_page_with_no_row_is_refused_rather_than_guessed(self) -> None:
        # Arrange
        page = 1

        # Act
        attempt = lambda: row(page)  # noqa: E731

        # Assert
        self.assertRaises(AssertionError, attempt)

    def test_a_page_with_more_than_one_row_is_refused_too(self) -> None:
        # Arrange
        crowded = [
            page
            for page in {entry["manualPage"] for entry in ROWS}
            if len([entry for entry in ROWS if entry["manualPage"] == page]) > 1
        ]

        # Act
        attempt = lambda: row(crowded[0])  # noqa: E731

        # Assert
        self.assertRaises(AssertionError, attempt)


class DocumentTest(unittest.TestCase):
    def test_the_part_is_backed_by_a_named_document(self) -> None:
        # Arrange
        manual = HELD["documents"]["userManual"]

        # Act
        publisher = manual["publisher"]

        # Assert
        self.assertEqual(publisher, "Zilog, Inc.")

    def test_the_document_is_the_publisher_current_revision(self) -> None:
        # Arrange
        manual = HELD["documents"]["userManual"]

        # Act
        number = manual["documentNumber"]

        # Assert
        self.assertEqual(number, "UM008011-0816")

    def test_it_carries_a_digest_so_the_reading_can_be_repeated(self) -> None:
        # Arrange
        manual = HELD["documents"]["userManual"]

        # Act
        digest = manual["sha256"]

        # Assert
        self.assertRegex(digest, r"^[0-9a-f]{64}$")

    def test_the_part_is_marked_verified_because_the_document_exists(self) -> None:
        # Arrange
        record = HELD

        # Act
        verified = record["verified"]

        # Assert
        self.assertIs(verified, True)


class TimingTableTest(unittest.TestCase):
    def test_every_breakdown_sums_to_the_total_beside_it(self) -> None:
        # Arrange
        rows = ROWS

        # Act
        wrong = [
            entry["instruction"]
            for entry in rows
            if sum(entry["machineCycles"]) != entry["tStates"]
        ]

        # Assert
        self.assertEqual(wrong, [])

    def test_the_table_covers_the_whole_documented_instruction_set(self) -> None:
        # Arrange
        smallest = 180

        # Act
        count = len(ROWS)

        # Assert
        self.assertGreater(count, smallest)

    def test_every_row_names_the_page_it_was_read_from(self) -> None:
        # Arrange
        rows = ROWS

        # Act
        missing = [entry["instruction"] for entry in rows if not entry.get("manualPage")]

        # Assert
        self.assertEqual(missing, [])

    def test_no_instruction_takes_fewer_states_than_one_fetch(self) -> None:
        # Arrange
        fetch = SHAPES["opcodeFetch"]["tStates"]

        # Act
        short = [entry["instruction"] for entry in ROWS if entry["tStates"] < fetch]

        # Assert
        self.assertEqual(short, [])

    def test_the_rows_whose_machine_cycle_count_is_a_misprint_are_flagged(self) -> None:
        # Arrange
        rows = ROWS

        # Act
        flagged = {entry["manualPage"] for entry in rows if entry.get("printedMCyclesIsAMisprint")}

        # Assert
        self.assertEqual(flagged, {99, 260, 269})

    def test_and_each_of_those_is_written_up_as_a_contradiction(self) -> None:
        # Arrange
        contradictions = HELD["documentContradictions"]

        # Act
        pages = {
            entry["manualPage"]
            for entry in contradictions
            if entry["kind"] == "timingTableMisprint"
        }

        # Assert
        self.assertEqual(pages, {99, 260, 269})

    def test_every_contradiction_says_which_kind_it_is(self) -> None:
        # Arrange
        contradictions = HELD["documentContradictions"]

        # Act
        kinds = {entry["kind"] for entry in contradictions}

        # Assert
        self.assertEqual(
            kinds, {"timingTableMisprint", "proseVersusFigure", "timingTableVersusProse"}
        )

    def test_the_prose_a_figure_or_a_sibling_page_contradicts_is_quoted(self) -> None:
        # Arrange
        contradictions = HELD["documentContradictions"]

        # Act
        found = [
            entry["printedQuote"]
            for entry in contradictions
            if entry["kind"] == "proseVersusFigure"
        ]

        # Assert
        self.assertEqual(len(found), 2)

    def test_and_one_of_the_two_is_a_page_that_contradicts_itself(self) -> None:
        # Arrange
        named = "bit-instruction-negate-flag-printed-as-half-carry"

        # Act
        found = [entry for entry in HELD["documentContradictions"] if entry["id"] == named]

        # Assert
        self.assertEqual(found[0]["printedQuote"].count("H is"), 2)

    def test_every_row_names_an_instruction_this_core_can_name(self) -> None:
        # Arrange
        printed = {mnemonic_of(entry) for entry in ROWS}

        # Act
        stray = sorted(printed - named_by_the_core())

        # Assert
        self.assertEqual(stray, [])

    def test_and_the_only_ones_it_names_that_the_table_omits_are_not_documented(self) -> None:
        # Arrange
        printed = {mnemonic_of(entry) for entry in ROWS}

        # Act
        absent = sorted(named_by_the_core() - printed)

        # Assert
        self.assertEqual(absent, ["db", "sll"])

    def test_the_notation_example_is_kept_apart_from_the_instructions(self) -> None:
        # Arrange
        example = FACTS["instructionTiming"]["notationExample"]

        # Act
        found = (example["manualPage"], example["tStates"], example["machineCycles"])

        # Assert
        self.assertEqual(found, (69, 7, [4, 3]))

    def test_and_no_row_claims_the_page_that_example_sits_on(self) -> None:
        # Arrange
        page = FACTS["instructionTiming"]["notationExample"]["manualPage"]

        # Act
        claimed = [entry["instruction"] for entry in ROWS if entry["manualPage"] == page]

        # Assert
        self.assertEqual(claimed, [])

    def test_no_other_row_disagrees_with_its_own_breakdown(self) -> None:
        # Arrange
        rows = ROWS

        # Act
        wrong = [
            entry["manualPage"]
            for entry in rows
            if len(entry["machineCycles"]) != entry["printedMCycles"]
            and not entry.get("printedMCyclesIsAMisprint")
        ]

        # Assert
        self.assertEqual(wrong, [])


class ModelScopeTest(unittest.TestCase):
    def test_every_fact_names_the_models_it_governs(self) -> None:
        # Arrange
        facts = HELD["facts"]

        # Act
        unscoped = [
            name
            for name, fact in facts.items()
            if not isinstance(fact.get("appliesTo"), list) or not fact["appliesTo"]
        ]

        # Assert
        self.assertEqual(unscoped, [])

    def test_and_every_model_it_names_is_one_the_package_builds(self) -> None:
        # Arrange
        facts = HELD["facts"]

        # Act
        invented = sorted(
            {model for fact in facts.values() for model in fact["appliesTo"] if model not in MODELS}
        )

        # Assert
        self.assertEqual(invented, [])

    def test_the_recorded_differences_match_the_models(self) -> None:
        # Arrange
        recorded = HELD["modelDifferences"]["models"]

        # Act
        built = {
            name: {
                "carryRule": MODELS[name].carry_rule,
                "floatingOutput": MODELS[name].floating_output,
                "interruptClearsParity": MODELS[name].interrupt_clears_parity,
            }
            for name in recorded
        }

        # Assert
        self.assertEqual(
            built,
            {
                name: {
                    key: one[key]
                    for key in ("carryRule", "floatingOutput", "interruptClearsParity")
                }
                for name, one in recorded.items()
            },
        )

    def test_and_cover_every_model_the_package_builds(self) -> None:
        # Arrange
        recorded = HELD["modelDifferences"]["models"]

        # Act
        named = sorted(recorded)

        # Assert
        self.assertEqual(named, sorted(MODELS))

    def test_the_parity_defect_is_the_one_fact_that_is_not_every_part(self) -> None:
        # Arrange
        defect = HELD["facts"]["interruptResponse"]["nmosParityDefect"]

        # Act
        clearing = [name for name in sorted(MODELS) if MODELS[name].interrupt_clears_parity]

        # Assert
        self.assertEqual(defect["appliesTo"], clearing)


class FlagRegisterTest(unittest.TestCase):
    def test_every_flag_sits_in_the_bit_the_manual_gives_it(self) -> None:
        # Arrange
        printed = FACTS["flagRegister"]["bits"]

        # Act
        held = {
            name: flags_set_by(program, setup)
            for name, (program, setup, _) in SETTING_FLAGS.items()
        }

        # Assert
        self.assertEqual(
            held,
            {
                name: sum(1 << printed[flag] for flag in flags)
                for name, (_, _, flags) in SETTING_FLAGS.items()
            },
        )

    def test_and_every_one_of_them_is_set_by_one_of_those_runs(self) -> None:
        # Arrange
        printed = FACTS["flagRegister"]["bits"]

        # Act
        named = {flag for _, _, flags in SETTING_FLAGS.values() for flag in flags}

        # Assert
        self.assertEqual(named, set(printed))

    def test_the_two_the_manual_calls_unused_are_the_two_this_package_calls_undocumented(
        self,
    ) -> None:
        # Arrange
        printed = FACTS["flagRegister"]["bits"]
        documented = sum(1 << bit for name, bit in printed.items() if name not in ("x", "y"))

        # Act
        copied = flags_set_by((0xB7,), {"a": 0xFF}) & ~documented

        # Assert
        self.assertEqual(copied, (1 << printed["x"]) | (1 << printed["y"]))


class PrintedFactTest(unittest.TestCase):
    def test_clearing_the_accumulator_sets_exactly_the_zero_and_parity_bits(self) -> None:
        # Arrange
        bits = FACTS["flagRegister"]["bits"]
        program = (0xAF,)

        # Act
        cpu = ran(program, {"a": 0x5A, "f": 0xFF})

        # Assert
        self.assertEqual(cpu.registers.f, (1 << bits["z"]) | (1 << bits["pv"]))

    def test_every_bit_form_sets_the_half_carry_and_resets_the_negate(self) -> None:
        # Arrange
        entry = {one["id"]: one for one in HELD["documentContradictions"]}[
            "bit-instruction-negate-flag-printed-as-half-carry"
        ]

        # Act
        found = {form: settled_by(program) for form, program in BIT_FORMS.items()}

        # Assert
        self.assertEqual(found, dict.fromkeys(BIT_FORMS, entry["settles"]))


if __name__ == "__main__":
    unittest.main()
