import hashlib
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Any
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import exercisers  # noqa: E402
from z80 import Memory  # noqa: E402

TABLE = 0x0100

HEADER = 0x0200

TRAILER = 0x0210

FIRST = 0x0300

SECOND = 0x0320

THIRD = 0x0340

PROGRAM = bytes(
    [
        *(0x31, 0x00, 0xF0),
        *(0x11, HEADER & 0xFF, HEADER >> 8),
        *(0xCD, 0x40, 0x00),
        *(0x21, TABLE & 0xFF, TABLE >> 8),
        *(0x5E, 0x23, 0x56, 0x23, 0x7B, 0xB2),
        *(0x28, 0x05),
        *(0xCD, 0x40, 0x00),
        *(0x18, 0xF3),
        *(0x11, TRAILER & 0xFF, TRAILER >> 8),
        *(0xCD, 0x40, 0x00),
        *(0x18, 0xFE),
    ]
)

COUNTER = bytes(
    [
        *(0x31, 0x00, 0xF0),
        *(0x3E, 0x30, 0x32, 0x00, 0xC0),
        *(0x21, TABLE & 0xFF, TABLE >> 8),
        *(0x5E, 0x23, 0x56, 0x23, 0x7B, 0xB2),
        *(0x28, 0x0F),
        *(0x3A, 0x00, 0xC0, 0x3C, 0x32, 0x00, 0xC0),
        *(0xD3, 0xFD, 0x3E, 0x0D, 0xD3, 0xFD),
        *(0x18, 0xE9),
        *(0x18, 0xFE),
    ]
)

A_COUNTER = COUNTER + bytes(TABLE - len(COUNTER)) + bytes([0x01, 0x00] * 4) + bytes(2)

PRINT = bytes([0x1A, 0xFE, 0x24, 0xC8, 0xD3, 0xFD, 0x13, 0x18, 0xF7])

PASSING = b"one....OK\r$"

FAILING = b"two....\x07CRC:12345678 expected:87654321\n$"


def placed(image: bytearray, address: int, data: bytes) -> None:
    image[address : address + len(data)] = data


def an_exerciser(*tests: bytes) -> bytes:
    image = bytearray(0x0400)
    placed(image, 0x0000, PROGRAM)
    placed(image, 0x0040, PRINT)
    placed(image, HEADER, b"Probe\r$")
    placed(image, TRAILER, b"Done\r$")
    at = TABLE
    for address, text in zip((FIRST, SECOND, THIRD), tests, strict=False):
        placed(image, address, text)
        placed(image, at, address.to_bytes(2, "little"))
        at += 2
    return bytes(image)


def a_record(folder: Path, *images: bytes, verdict: list[str] | None = None) -> Path:
    listed: list[dict[str, Any]] = [
        {
            "id": f"probe-{index}",
            "sha256": hashlib.sha256(image).hexdigest(),
            "outcome": "run",
            "testTable": TABLE,
            "verdict": verdict,
            "flagMasks": [ord("o")],
        }
        for index, image in enumerate(images)
    ]
    listed.append({"id": "elsewhere", "sha256": "ab" * 32, "outcome": "hosted", "needs": "x"})
    path = folder / "testroms.json"
    path.write_text(json.dumps({"cartridges": listed}))
    return path


def held_in(folder: Path, image: bytes, name: str = "probe.img") -> Path:
    path = folder / name
    path.write_bytes(image)
    return path


class RecordedVerdictTest(unittest.TestCase):
    def test_the_instruction_exerciser_reported_every_test_passed(self) -> None:
        # Arrange
        held = exercisers.entry("zexall-sdsc")

        # Act
        failed = [line for line in held["verdict"] if not line.endswith("OK")]

        # Assert
        self.assertEqual(failed, [])

    def test_it_reported_all_sixty_seven_of_its_tests(self) -> None:
        # Arrange
        held = exercisers.entry("zexall-sdsc")

        # Act
        reported = len(held["verdict"])

        # Assert
        self.assertEqual(reported, 67)

    def test_every_one_of_its_tests_masks_out_flag_bits_5_and_3(self) -> None:
        # Arrange
        held = exercisers.entry("zexall-sdsc")

        # Act
        found = held["flagMasks"]

        # Assert
        self.assertEqual(found, [0xD7])

    def test_the_video_chip_build_reported_the_same_lines(self) -> None:
        # Arrange
        expected = exercisers.entry("zexall-sdsc")["verdict"]

        # Act
        found = exercisers.entry("zexall-svpd")["verdict"]

        # Assert
        self.assertEqual(found, expected)

    def test_an_id_the_record_does_not_hold_is_refused(self) -> None:
        # Arrange
        name = "never-recorded"

        # Act
        attempt = lambda: exercisers.entry(name)  # noqa: E731

        # Assert
        self.assertRaisesRegex(AssertionError, name, attempt)

    def test_a_record_that_is_not_an_object_is_refused(self) -> None:
        # Arrange
        path = Path(tempfile.mkdtemp()) / "testroms.json"
        path.write_text("[]")

        # Act
        attempt = lambda: exercisers.record(path)  # noqa: E731

        # Assert
        self.assertRaises(AssertionError, attempt)


class DebugPortTest(unittest.TestCase):
    def test_a_read_finds_no_device(self) -> None:
        # Arrange
        port = exercisers.DebugPort()

        # Act
        value = port.read(0x00FD)

        # Assert
        self.assertEqual(value, 0xFF)

    def test_a_port_the_record_answers_for_gives_that_answer(self) -> None:
        # Arrange
        port = exercisers.DebugPort({0x7E: 0xC0})

        # Act
        value = port.read(0x007E)

        # Assert
        self.assertEqual(value, 0xC0)

    def test_the_record_names_the_host_by_hexadecimal_port(self) -> None:
        # Arrange
        held = {"printAt": 0x2526, "portAnswers": {"7E": 0xC0}}

        # Act
        host = exercisers.host_of(held)

        # Assert
        self.assertEqual(host, (0x2526, {0x7E: 0xC0}))

    def test_a_write_to_any_other_port_prints_nothing(self) -> None:
        # Arrange
        port = exercisers.DebugPort()

        # Act
        port.write(0x41FC, 0x41)

        # Assert
        self.assertEqual(port.text, [])


class RunTest(unittest.TestCase):
    def test_each_test_prints_its_own_line_and_the_frame_is_dropped(self) -> None:
        # Arrange
        image = an_exerciser(PASSING, FAILING)

        # Act
        lines = exercisers.verdict((image, None))

        # Assert
        self.assertEqual(lines, ["one....OK", "two.... CRC:12345678 expected:87654321"])

    def test_images_run_apart_give_the_same_lines(self) -> None:
        # Arrange
        work = [(an_exerciser(PASSING), None), (an_exerciser(FAILING), None)]

        # Act
        lines = exercisers.verdicts(work, jobs=2)

        # Assert
        self.assertEqual(lines, [["one....OK"], ["two.... CRC:12345678 expected:87654321"]])

    def test_what_one_test_leaves_in_memory_is_there_for_the_next(self) -> None:
        # Arrange
        image = A_COUNTER

        # Act
        lines = exercisers.printed(image)

        # Assert
        self.assertEqual(lines, ["1", "2", "3", "4"])

    def test_a_routine_that_prints_elsewhere_is_read_where_it_is_entered(self) -> None:
        # Arrange
        image = bytearray(an_exerciser(PASSING))
        image[0x0045] = 0xBE

        # Act
        lines = exercisers.verdict((bytes(image), (0x0044, {})))

        # Assert
        self.assertEqual(lines, ["one....OK"])

    def test_a_program_that_never_settles_stops_at_its_limit(self) -> None:
        # Arrange
        image = bytes([0x00, 0x18, 0xFD]) + bytes(0x0200)

        # Act
        attempt = lambda: exercisers.printed(image, limit=50)  # noqa: E731

        # Assert
        self.assertRaisesRegex(exercisers.Unfinished, "50", attempt)


class CartridgeTest(unittest.TestCase):
    def test_a_write_into_the_image_is_lost_as_on_a_read_only_memory(self) -> None:
        # Arrange
        space = exercisers.Cartridge(bytes([0x11, 0x22]))
        space.write8(0x0001, 0x99)

        # Act
        found = space.read8(0x0001)

        # Assert
        self.assertEqual(found, 0x22)

    def test_a_write_past_the_image_is_kept(self) -> None:
        # Arrange
        space = exercisers.Cartridge(bytes([0x11, 0x22]))
        space.write8(0xC070, 0x99)

        # Act
        found = space.read8(0xC070)

        # Assert
        self.assertEqual(found, 0x99)


class SettledTest(unittest.TestCase):
    def test_an_absolute_jump_to_itself_is_where_a_run_settles(self) -> None:
        # Arrange
        space = Memory(image=bytes([0x00, 0xC3, 0x01, 0x00]))

        # Act
        found = exercisers.settled(space, 0x0001)

        # Assert
        self.assertTrue(found)

    def test_an_absolute_jump_anywhere_else_is_not(self) -> None:
        # Arrange
        space = Memory(image=bytes([0x00, 0xC3, 0x00, 0x00]))

        # Act
        found = exercisers.settled(space, 0x0001)

        # Assert
        self.assertFalse(found)

    def test_a_block_move_repeating_in_place_is_not(self) -> None:
        # Arrange
        space = Memory(image=bytes([0xED, 0xB0]))

        # Act
        found = exercisers.settled(space, 0x0000)

        # Assert
        self.assertFalse(found)


class FlagMaskTest(unittest.TestCase):
    def test_the_first_byte_of_each_test_record_is_its_flag_mask(self) -> None:
        # Arrange
        image = an_exerciser(PASSING, FAILING)

        # Act
        found = exercisers.flag_masks(image, TABLE)

        # Assert
        self.assertEqual(found, [ord("o"), ord("t")])


class FindingImagesTest(unittest.TestCase):
    def test_an_image_inside_a_zip_inside_a_folder_is_found_by_digest(self) -> None:
        # Arrange
        folder = Path(tempfile.mkdtemp())
        image = an_exerciser(PASSING)
        with zipfile.ZipFile(folder / "held.zip", "w") as archive:
            archive.writestr("inner.img", image)
        held_in(folder, b"something else", "other.img")
        digest = hashlib.sha256(image).hexdigest()

        # Act
        found = exercisers.images([folder], {digest})

        # Assert
        self.assertEqual(list(found), [digest])

    def test_a_place_that_is_not_there_holds_nothing(self) -> None:
        # Arrange
        place = Path(tempfile.mkdtemp()) / "absent"

        # Act
        found = exercisers.images([place], {"ab" * 32})

        # Assert
        self.assertEqual(found, {})


class MainTest(unittest.TestCase):
    def test_an_image_that_matches_its_recorded_verdict_exits_zero(self) -> None:
        # Arrange
        folder = Path(tempfile.mkdtemp())
        image = an_exerciser(PASSING)
        record = a_record(folder, image, verdict=["one....OK"])

        # Act
        code = exercisers.main([str(held_in(folder, image))], record)

        # Assert
        self.assertEqual(code, 0)

    def test_a_failing_test_exits_one(self) -> None:
        # Arrange
        folder = Path(tempfile.mkdtemp())
        image = an_exerciser(FAILING)
        verdict = ["two.... CRC:12345678 expected:87654321"]
        record = a_record(folder, image, verdict=verdict)

        # Act
        code = exercisers.main([str(held_in(folder, image))], record)

        # Assert
        self.assertEqual(code, 1)

    def test_a_verdict_that_differs_from_the_record_exits_one(self) -> None:
        # Arrange
        folder = Path(tempfile.mkdtemp())
        image = an_exerciser(PASSING)
        record = a_record(folder, image, verdict=[])

        # Act
        code = exercisers.main([str(held_in(folder, image))], record)

        # Assert
        self.assertEqual(code, 1)

    def test_writing_keeps_the_verdict_measured(self) -> None:
        # Arrange
        folder = Path(tempfile.mkdtemp())
        image = an_exerciser(PASSING)
        record = a_record(folder, image)

        # Act
        exercisers.main(["--write", "--jobs", "1", str(held_in(folder, image))], record)

        # Assert
        self.assertEqual(exercisers.entry("probe-0", record)["verdict"], ["one....OK"])

    def test_an_image_that_is_absent_while_another_is_held_is_reported_skipped(self) -> None:
        # Arrange
        folder = Path(tempfile.mkdtemp())
        image = an_exerciser(PASSING)
        record = a_record(folder, image, an_exerciser(FAILING), verdict=["one....OK"])

        # Act
        code = exercisers.main([str(held_in(folder, image))], record)

        # Assert
        self.assertEqual(code, 0)

    def test_the_places_can_come_from_the_environment(self) -> None:
        # Arrange
        folder = Path(tempfile.mkdtemp())
        image = an_exerciser(PASSING)
        record = a_record(folder, image, verdict=["one....OK"])
        held_in(folder, image)

        # Act
        with mock.patch.dict(os.environ, {exercisers.PLACES: str(folder)}):
            code = exercisers.main([], record)

        # Assert
        self.assertEqual(code, 0)

    def test_with_nothing_named_it_reads_what_external_holds(self) -> None:
        # Arrange
        folder = Path(tempfile.mkdtemp())
        image = an_exerciser(PASSING)
        record = a_record(folder, image, verdict=["one....OK"])
        held_in(folder, image)
        environment = {k: v for k, v in os.environ.items() if k != exercisers.PLACES}

        # Act
        with mock.patch.dict(os.environ, environment, clear=True):
            code = exercisers.main([], record, kept=folder)

        # Assert
        self.assertEqual(code, 0)

    def test_with_no_image_anywhere_it_exits_two(self) -> None:
        # Arrange
        environment = {k: v for k, v in os.environ.items() if k != exercisers.PLACES}

        nothing = Path(tempfile.mkdtemp()) / "external"

        # Act
        with mock.patch.dict(os.environ, environment, clear=True):
            code = exercisers.main([], kept=nothing)

        # Assert
        self.assertEqual(code, exercisers.NOTHING_TO_RUN)

    def test_an_option_it_does_not_know_is_a_usage_error(self) -> None:
        # Arrange
        argv = ["--jobs"]

        # Act
        code = exercisers.main(argv)

        # Assert
        self.assertEqual(code, 3)


if __name__ == "__main__":
    unittest.main()
