import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from z80 import Cpu, Memory, Ports, SparseMemory


class SparseTest(unittest.TestCase):
    def test_a_byte_reads_back_as_it_was_written(self) -> None:
        # Arrange
        space = SparseMemory()

        # Act
        space.write8(0x1234, 0x42)

        # Assert
        self.assertEqual(space.read8(0x1234), 0x42)

    def test_an_address_never_written_still_reads_as_a_byte(self) -> None:
        # Arrange
        space = SparseMemory(seed=1)

        # Act
        found = space.read8(0x8000)

        # Assert
        self.assertIn(found, range(0x100))

    def test_and_reads_as_the_same_thing_twice(self) -> None:
        # Arrange
        space = SparseMemory(seed=1)

        # Act
        found = (space.read8(0x8000), space.read8(0x8000))

        # Assert
        self.assertEqual(found[0], found[1])

    def test_an_unwritten_address_is_not_simply_zero_everywhere(self) -> None:
        # Arrange
        space = SparseMemory(seed=1)

        # Act
        found = {space.read8(at) for at in range(0x100)}

        # Assert
        self.assertGreater(len(found - {0}), 0)

    def test_two_spaces_seeded_differently_hold_different_rubbish(self) -> None:
        # Arrange
        first, second = SparseMemory(seed=1), SparseMemory(seed=2)

        # Act
        found = ([first.read8(at) for at in range(0x20)], [second.read8(at) for at in range(0x20)])

        # Assert
        self.assertNotEqual(found[0], found[1])

    def test_addresses_wrap_at_the_top_of_the_space(self) -> None:
        # Arrange
        space = SparseMemory()

        # Act
        space.write8(0x10000, 0x42)

        # Assert
        self.assertEqual(space.read8(0x0000), 0x42)

    def test_a_value_wider_than_a_byte_is_narrowed(self) -> None:
        # Arrange
        space = SparseMemory()

        # Act
        space.write8(0x0000, 0x1FF)

        # Assert
        self.assertEqual(space.read8(0x0000), 0xFF)


def contents(held: Memory, size: int) -> bytes:
    return bytes(held.read8(address) for address in range(size))


class MemoryTest(unittest.TestCase):
    def test_it_holds_a_pattern_rather_than_zeroes(self) -> None:
        # Arrange
        held = Memory(0x100)

        # Act
        found = contents(held, 0x100)

        # Assert
        self.assertNotEqual(found, bytes(0x100))

    def test_a_cleared_one_has_to_be_asked_for_in_writing(self) -> None:
        # Arrange
        held = Memory(0x100, fill=0)

        # Act
        found = set(contents(held, 0x100))

        # Assert
        self.assertEqual(found, {0})

    def test_and_the_default_is_not_one_byte_repeated(self) -> None:
        # Arrange
        held = Memory(0x100)

        # Act
        found = set(contents(held, 0x100))

        # Assert
        self.assertGreater(len(found), 1)

    def test_one_seed_gives_one_pattern(self) -> None:
        # Arrange
        first, second = Memory(0x100, seed=3), Memory(0x100, seed=3)

        # Act
        found = (contents(first, 0x100), contents(second, 0x100))

        # Assert
        self.assertEqual(found[0], found[1])

    def test_and_a_different_seed_a_different_one(self) -> None:
        # Arrange
        first, second = Memory(0x100, seed=1), Memory(0x100, seed=2)

        # Act
        found = (contents(first, 0x100), contents(second, 0x100))

        # Assert
        self.assertNotEqual(found[0], found[1])

    def test_an_image_is_what_the_board_knows(self) -> None:
        # Arrange
        image = b"\x3e\x42"

        # Act
        held = Memory(0x10, image=image)

        # Assert
        self.assertEqual(contents(held, 2), image)

    def test_and_the_rest_is_what_it_does_not(self) -> None:
        # Arrange
        bare = Memory(0x10, seed=7)

        # Act
        loaded = Memory(0x10, image=b"\x3e", seed=7)

        # Assert
        self.assertEqual(contents(loaded, 0x10)[1:], contents(bare, 0x10)[1:])

    def test_it_reads_back_what_was_written(self) -> None:
        held = Memory(0x100)
        held.write8(0x40, 0x99)

        self.assertEqual(held.read8(0x40), 0x99)

    def test_a_write_keeps_only_the_low_byte(self) -> None:
        held = Memory(0x100)
        held.write8(0x40, 0x1FF)

        self.assertEqual(held.read8(0x40), 0xFF)

    def test_an_address_wraps_to_sixteen_bits(self) -> None:
        held = Memory(0x10000)
        held.write8(0x0010, 0x77)

        self.assertEqual(held.read8(0x10010), 0x77)

    def test_it_drives_a_processor(self) -> None:
        cpu = Cpu("z80", Memory(image=b"\x3e\x42"))
        cpu.registers.pc = 0

        cpu.step()

        self.assertEqual(cpu.registers.a, 0x42)


class PortTest(unittest.TestCase):
    def test_a_port_never_written_still_answers_a_byte(self) -> None:
        # Arrange
        ports = Ports(seed=1)

        # Act
        found = ports.read(0x1234)

        # Assert
        self.assertIn(found, range(0x100))

    def test_a_port_reads_back_what_was_put_there(self) -> None:
        # Arrange
        ports = Ports()

        # Act
        ports.write(0x1234, 0x42)

        # Assert
        self.assertEqual(ports.read(0x1234), 0x42)

    def test_the_address_is_the_whole_sixteen_bits(self) -> None:
        # Arrange
        ports = Ports()

        # Act
        ports.write(0x1234, 0x42)

        # Assert
        self.assertNotEqual(ports.read(0x0034), 0x42)

    def test_every_transaction_is_recorded_in_order(self) -> None:
        # Arrange
        ports = Ports()

        # Act
        ports.write(0x1234, 0x42)
        answered = ports.read(0x5678)

        # Assert
        self.assertEqual(ports.log, [(0x1234, 0x42, "w"), (0x5678, answered, "r")])

    def test_a_read_records_what_it_answered_with(self) -> None:
        # Arrange
        ports = Ports()
        ports.write(0x1234, 0x42)
        ports.log.clear()

        # Act
        ports.read(0x1234)

        # Assert
        self.assertEqual(ports.log, [(0x1234, 0x42, "r")])

    def test_the_log_can_be_cleared_between_instructions(self) -> None:
        # Arrange
        ports = Ports()
        ports.write(0x1234, 0x42)

        # Act
        ports.log.clear()

        # Assert
        self.assertEqual(ports.log, [])


if __name__ == "__main__":
    unittest.main()
