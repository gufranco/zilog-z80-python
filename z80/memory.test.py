import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from z80 import Cpu, memory
from z80.memory import Memory


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


class MemoryTest(unittest.TestCase):
    """The dense one, which is where a ROM image goes."""

    def test_it_holds_a_pattern_rather_than_zeroes(self) -> None:
        held = Memory(0x100)

        self.assertNotEqual(held.data, bytearray(0x100))

    def test_a_cleared_one_has_to_be_asked_for_in_writing(self) -> None:
        """The rule is the default, not the absence of an option.

        A caller who genuinely wants zeroes says so, and the request is the same
        word in every member of this family. What must never happen is getting
        them without asking.
        """
        self.assertEqual(set(Memory(0x100, fill=0).data), {0})

    def test_and_the_default_is_not_one_byte_repeated(self) -> None:
        held = Memory(0x100)

        self.assertGreater(len(set(held.data)), 1)

    def test_one_seed_gives_one_pattern(self) -> None:
        self.assertEqual(Memory(0x100, seed=3).data, Memory(0x100, seed=3).data)

    def test_and_a_different_seed_a_different_one(self) -> None:
        self.assertNotEqual(Memory(0x100, seed=1).data, Memory(0x100, seed=2).data)

    def test_an_image_is_what_the_board_knows(self) -> None:
        held = Memory(0x10, image=b"\x3e\x42")

        self.assertEqual(bytes(held.data[:2]), b"\x3e\x42")

    def test_and_the_rest_is_what_it_does_not(self) -> None:
        bare = Memory(0x10, seed=7)
        loaded = Memory(0x10, image=b"\x3e", seed=7)

        self.assertEqual(loaded.data[1:], bare.data[1:])

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
