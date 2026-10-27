import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import cputype, exercisers  # noqa: E402
from z80 import RunLimit  # noqa: E402

ROUTINE = 0x0100

SET_ADDRESS = bytes([0x0E, 0xBF, 0xED, 0x69, 0xED, 0x61, 0xC9])

DETECT = bytes(
    [
        *(0x21, 0x00, 0x40),
        0xCF,
        0x0D,
        *(0xED, 0x71),
        *(0x21, 0x00, 0x00),
        0xCF,
        0x0D,
        *(0xED, 0x78),
        *(0x20, 0x03),
        *(0x2E, 0x00),
        0xC9,
        *(0x2E, 0x01),
        0xC9,
    ]
)


def a_detector() -> bytes:
    image = bytearray(0x0200)
    image[0x0008 : 0x0008 + len(SET_ADDRESS)] = SET_ADDRESS
    image[ROUTINE : ROUTINE + len(DETECT)] = DETECT
    return bytes(image)


A_DETECTOR = a_detector()


def a_record(folder: Path, image: bytes, answers: dict[str, int] | None = None) -> Path:
    path = folder / "testroms.json"
    listed = [
        {
            "id": "probe",
            "sha256": hashlib.sha256(image).hexdigest(),
            "outcome": "run",
            "routine": ROUTINE,
            "answers": answers,
        },
        {"id": "absent", "sha256": "cd" * 32, "outcome": "run", "routine": ROUTINE},
        {"id": "waits", "sha256": "ab" * 32, "outcome": "hosted", "needs": "x"},
    ]
    path.write_text(json.dumps({"cartridges": listed}))
    return path


def held_in(folder: Path, image: bytes) -> Path:
    path = folder / "probe.img"
    path.write_bytes(image)
    return path


class RecordedAnswerTest(unittest.TestCase):
    def test_the_test_suite_calls_the_nmos_parts_nmos_and_the_cmos_part_cmos(self) -> None:
        # Arrange
        held = exercisers.entry("test-suite-cpu-type")

        # Act
        found = held["answers"]

        # Assert
        self.assertEqual(found, {"upd780c": 0, "z80": 0, "z84c00": 1})


class VideoMemoryTest(unittest.TestCase):
    def test_a_byte_written_reads_back_at_the_address_set(self) -> None:
        # Arrange
        memory = cputype.VideoMemory()
        for port, value in ((0xBF, 0x34), (0xBF, 0x52), (0xBE, 0xA5), (0xBF, 0x34), (0xBF, 0x12)):
            memory.write(port, value)

        # Act
        found = memory.read(0xBE)

        # Assert
        self.assertEqual(found, 0xA5)

    def test_any_other_port_reads_as_nothing_there(self) -> None:
        # Arrange
        memory = cputype.VideoMemory()

        # Act
        found = memory.read(0x7E)

        # Assert
        self.assertEqual(found, 0xFF)

    def test_a_write_to_any_other_port_changes_nothing(self) -> None:
        # Arrange
        memory = cputype.VideoMemory()
        memory.write(0x7F, 0x9F)

        # Act
        found = memory.read(0xBE)

        # Assert
        self.assertEqual(found, 0x00)


class AnswerTest(unittest.TestCase):
    def test_each_part_answers_what_its_output_with_no_source_sends(self) -> None:
        # Arrange
        image = A_DETECTOR

        # Act
        found = cputype.answers(image, ROUTINE)

        # Assert
        self.assertEqual(found, {"upd780c": 0, "z80": 0, "z84c00": 1})

    def test_a_routine_that_never_returns_stops_at_its_limit(self) -> None:
        # Arrange
        image = bytes(0x0100) + bytes([0x18, 0xFE])

        # Act
        attempt = lambda: cputype.answer(image, ROUTINE, "z80")  # noqa: E731

        # Assert
        self.assertRaises(RunLimit, attempt)


class MainTest(unittest.TestCase):
    def test_answers_that_match_the_record_exit_zero(self) -> None:
        # Arrange
        folder = Path(tempfile.mkdtemp())
        record = a_record(folder, A_DETECTOR, {"upd780c": 0, "z80": 0, "z84c00": 1})

        # Act
        code = cputype.main([str(held_in(folder, A_DETECTOR))], record)

        # Assert
        self.assertEqual(code, 0)

    def test_answers_that_differ_exit_one(self) -> None:
        # Arrange
        folder = Path(tempfile.mkdtemp())
        record = a_record(folder, A_DETECTOR, {"upd780c": 1, "z80": 1, "z84c00": 1})

        # Act
        code = cputype.main([str(held_in(folder, A_DETECTOR))], record)

        # Assert
        self.assertEqual(code, 1)

    def test_writing_keeps_the_answers(self) -> None:
        # Arrange
        folder = Path(tempfile.mkdtemp())
        record = a_record(folder, A_DETECTOR)

        # Act
        cputype.main(["--write", str(held_in(folder, A_DETECTOR))], record)

        # Assert
        self.assertEqual(
            exercisers.entry("probe", record)["answers"], {"upd780c": 0, "z80": 0, "z84c00": 1}
        )

    def test_with_no_image_anywhere_it_exits_two(self) -> None:
        # Arrange
        environment = {k: v for k, v in os.environ.items() if k != exercisers.PLACES}

        nothing = Path(tempfile.mkdtemp()) / "external"

        # Act
        with mock.patch.dict(os.environ, environment, clear=True):
            code = cputype.main([], kept=nothing)

        # Assert
        self.assertEqual(code, cputype.NOTHING_TO_RUN)

    def test_an_option_it_does_not_know_is_a_usage_error(self) -> None:
        # Arrange
        argv = ["--frames"]

        # Act
        code = cputype.main(argv)

        # Assert
        self.assertEqual(code, cputype.USAGE_ERROR)


if __name__ == "__main__":
    unittest.main()
