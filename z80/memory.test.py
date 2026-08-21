import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from z80 import memory


class SparseTest(unittest.TestCase):
    def test_a_byte_reads_back_as_it_was_written(self) -> None:
        space = memory.SparseMemory()

        space.write8(0x1234, 0x42)

        self.assertEqual(space.read8(0x1234), 0x42)

    def test_an_address_never_written_still_reads_as_something(self) -> None:
        space = memory.SparseMemory(seed=1)

        self.assertIsInstance(space.read8(0x8000), int)

    def test_and_reads_as_the_same_thing_twice(self) -> None:
        space = memory.SparseMemory(seed=1)

        self.assertEqual(space.read8(0x8000), space.read8(0x8000))

    def test_an_unwritten_address_is_not_simply_zero_everywhere(self) -> None:
        space = memory.SparseMemory(seed=1)

        self.assertTrue(any(space.read8(at) for at in range(0x100)))

    def test_two_spaces_seeded_differently_hold_different_rubbish(self) -> None:
        first = memory.SparseMemory(seed=1)
        second = memory.SparseMemory(seed=2)

        self.assertNotEqual(
            [first.read8(at) for at in range(0x20)],
            [second.read8(at) for at in range(0x20)],
        )

    def test_addresses_wrap_at_the_top_of_the_space(self) -> None:
        space = memory.SparseMemory()

        space.write8(0x10000, 0x42)

        self.assertEqual(space.read8(0x0000), 0x42)

    def test_a_value_wider_than_a_byte_is_narrowed(self) -> None:
        space = memory.SparseMemory()

        space.write8(0x0000, 0x1FF)

        self.assertEqual(space.read8(0x0000), 0xFF)


class PortTest(unittest.TestCase):
    def test_a_port_never_written_still_answers(self) -> None:
        ports = memory.Ports(seed=1)

        self.assertIsInstance(ports.read(0x1234), int)

    def test_a_port_reads_back_what_was_put_there(self) -> None:
        ports = memory.Ports()

        ports.write(0x1234, 0x42)

        self.assertEqual(ports.read(0x1234), 0x42)

    def test_the_address_is_the_whole_sixteen_bits(self) -> None:
        ports = memory.Ports()

        ports.write(0x1234, 0x42)

        self.assertNotEqual(ports.read(0x0034), 0x42)

    def test_every_transaction_is_recorded_in_order(self) -> None:
        ports = memory.Ports()

        ports.write(0x1234, 0x42)
        answered = ports.read(0x5678)

        self.assertEqual(ports.log, [(0x1234, 0x42, "w"), (0x5678, answered, "r")])

    def test_a_read_records_what_it_answered_with(self) -> None:
        ports = memory.Ports()
        ports.write(0x1234, 0x42)
        ports.log.clear()

        ports.read(0x1234)

        self.assertEqual(ports.log, [(0x1234, 0x42, "r")])

    def test_the_log_can_be_cleared_between_instructions(self) -> None:
        ports = memory.Ports()
        ports.write(0x1234, 0x42)

        ports.log.clear()

        self.assertEqual(ports.log, [])


if __name__ == "__main__":
    unittest.main()
