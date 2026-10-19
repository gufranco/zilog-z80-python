import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import z80test  # noqa: E402

PRINT_OK = bytes([0x3E, 0x4F, 0xD7, 0x3E, 0x4B, 0xD7, 0x3E, 0x0D, 0xD7, 0xC9])

PRINT_PASSED = b"".join(bytes([0x3E, byte, 0xD7]) for byte in z80test.PASSED.encode()) + bytes(
    [0x3E, 0x0D, 0xD7, 0xC9]
)

READ_THE_PORTS = bytes([0xDB, 0xFE, 0xD6, 0x80, 0xD7, 0xDB, 0xFF, 0xD6, 0xBF, 0xD7, 0xC9])


def block(flag: int, data: bytes) -> bytes:
    body = bytes([flag]) + data
    checksum = 0
    for byte in body:
        checksum ^= byte
    whole = body + bytes([checksum])
    return len(whole).to_bytes(2, "little") + whole


def tape(program: bytes) -> bytes:
    return block(0x00, bytes(17)) + block(0xFF, program)


def held_as(folder: Path, program: bytes) -> tuple[Path, Path]:
    path = folder / "probe.tap"
    path.write_bytes(tape(program))
    record = folder / "z80test.json"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    record.write_text(json.dumps({"taps": {"probe.tap": digest}}))
    return path, record


class TapeTest(unittest.TestCase):
    def test_a_tape_splits_into_its_blocks(self) -> None:
        # Arrange
        data = tape(PRINT_OK)

        # Act
        found = z80test.blocks(data)

        # Assert
        self.assertEqual(len(found), 2)

    def test_the_code_is_the_last_data_block_without_its_flag_and_checksum(self) -> None:
        # Arrange
        data = tape(PRINT_OK)

        # Act
        found = z80test.code(data)

        # Assert
        self.assertEqual(found, PRINT_OK)

    def test_a_tape_with_no_data_block_holds_no_code(self) -> None:
        # Arrange
        data = block(0x00, bytes(17))

        # Act
        found = z80test.code(data)

        # Assert
        self.assertEqual(found, b"")


class RunTest(unittest.TestCase):
    def test_every_character_the_program_prints_is_kept_line_by_line(self) -> None:
        # Arrange
        program = PRINT_OK

        # Act
        lines = z80test.run(program)

        # Assert
        self.assertEqual(lines, ["OK", ""])

    def test_a_control_code_reads_as_a_space(self) -> None:
        # Arrange
        program = bytes([0x3E, 0x17, 0xD7, 0x3E, 0x41, 0xD7, 0xC9])

        # Act
        lines = z80test.run(program)

        # Assert
        self.assertEqual(lines, [" A"])

    def test_an_even_port_and_an_odd_one_answer_what_the_suite_checks_for(self) -> None:
        # Arrange
        program = READ_THE_PORTS

        # Act
        lines = z80test.run(program)

        # Assert
        self.assertEqual(lines, ["?@"])

    def test_a_port_write_goes_nowhere_and_the_run_carries_on(self) -> None:
        # Arrange
        program = bytes([0x3E, 0x42, 0xD3, 0xFE, 0xD7, 0xC9])

        # Act
        lines = z80test.run(program)

        # Assert
        self.assertEqual(lines, ["B"])

    def test_a_run_that_never_returns_stops_at_its_limit(self) -> None:
        # Arrange
        program = bytes([0x18, 0xFE])

        # Act
        with self.assertRaises(z80test.Unfinished) as raised:
            z80test.run(program, limit=50)

        # Assert
        self.assertIn("50", str(raised.exception))


class CheckTest(unittest.TestCase):
    def test_a_tape_whose_digest_is_held_is_accepted(self) -> None:
        # Arrange
        path, record = held_as(Path(tempfile.mkdtemp()), PRINT_OK)

        # Act
        name = z80test.check(path, z80test.identity(record))

        # Assert
        self.assertEqual(name, "probe.tap")

    def test_any_other_file_is_refused(self) -> None:
        # Arrange
        folder = Path(tempfile.mkdtemp())
        _path, record = held_as(folder, PRINT_OK)
        other = folder / "other.tap"
        other.write_bytes(tape(PRINT_PASSED))

        # Act
        with self.assertRaises(z80test.Refused) as raised:
            z80test.check(other, z80test.identity(record))

        # Assert
        self.assertIn("other.tap", str(raised.exception))

    def test_an_absent_file_is_refused_by_name(self) -> None:
        # Arrange
        folder = Path(tempfile.mkdtemp())
        _path, record = held_as(folder, PRINT_OK)

        # Act
        with self.assertRaises(z80test.Refused) as raised:
            z80test.check(folder / "absent.tap", z80test.identity(record))

        # Assert
        self.assertIn("absent.tap", str(raised.exception))


class RecordTest(unittest.TestCase):
    def test_the_record_pins_the_suite_by_commit(self) -> None:
        # Arrange
        held = z80test.identity()

        # Act
        commit = held["commit"]

        # Assert
        self.assertEqual(len(commit), 40)

    def test_every_variant_it_reports_was_run_against_a_held_tape(self) -> None:
        # Arrange
        held = z80test.identity()

        # Act
        reported = set(held["measured"])

        # Assert
        self.assertLessEqual(reported, set(held["taps"]))


class MainTest(unittest.TestCase):
    def test_a_tape_that_passes_every_test_exits_zero(self) -> None:
        # Arrange
        path, record = held_as(Path(tempfile.mkdtemp()), PRINT_PASSED)

        # Act
        code = z80test.main([str(path)], record)

        # Assert
        self.assertEqual(code, 0)

    def test_a_tape_that_reports_anything_else_exits_one(self) -> None:
        # Arrange
        path, record = held_as(Path(tempfile.mkdtemp()), PRINT_OK)

        # Act
        code = z80test.main([str(path)], record)

        # Assert
        self.assertEqual(code, 1)

    def test_a_refused_tape_exits_one_without_running(self) -> None:
        # Arrange
        folder = Path(tempfile.mkdtemp())
        _path, record = held_as(folder, PRINT_OK)

        # Act
        code = z80test.main([str(folder / "absent.tap")], record)

        # Assert
        self.assertEqual(code, 1)

    def test_no_tape_named_is_a_usage_error(self) -> None:
        # Arrange
        argv: list[str] = []

        # Act
        code = z80test.main(argv)

        # Assert
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
