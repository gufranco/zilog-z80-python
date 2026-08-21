import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from z80 import bus


def recorder() -> bus.Bus:
    return bus.Bus(recording=True)


class CountingTest(unittest.TestCase):
    """Counting is always on, because a cycle count nobody can read is not a claim."""

    def test_a_fresh_bus_has_spent_nothing(self) -> None:
        self.assertEqual(len(bus.Bus()), 0)

    def test_an_opcode_fetch_costs_the_four_the_manual_gives_it(self) -> None:
        line = bus.Bus()

        line.fetch(0x1234, 0x5678, 0x00)

        self.assertEqual(len(line), bus.FETCH_STATES)

    def test_a_memory_access_costs_three(self) -> None:
        line = bus.Bus()

        line.read(0x1234, 0x00)

        self.assertEqual(len(line), bus.MEMORY_STATES)

    def test_a_port_access_costs_four_because_of_the_automatic_wait(self) -> None:
        line = bus.Bus()

        line.port_read(0x1234, 0x00)

        self.assertEqual(len(line), bus.PORT_STATES)

    def test_a_port_access_costs_one_more_than_a_memory_access(self) -> None:
        self.assertEqual(bus.PORT_STATES - bus.MEMORY_STATES, 1)

    def test_counting_happens_without_recording(self) -> None:
        line = bus.Bus()

        line.read(0x1234, 0x00)

        self.assertEqual((len(line), line.log), (3, []))

    def test_clearing_starts_the_next_instruction_from_nothing(self) -> None:
        line = recorder()
        line.read(0x1234, 0x00)

        line.clear()

        self.assertEqual((len(line), line.log), (0, []))


class FetchTest(unittest.TestCase):
    def test_the_counter_is_on_the_bus_for_the_first_two_states(self) -> None:
        line = recorder()

        line.fetch(0x1234, 0x5678, 0xAB)

        self.assertEqual([entry[0] for entry in line.log[:2]], [0x1234, 0x1234])

    def test_and_the_refresh_address_for_the_last_two(self) -> None:
        line = recorder()

        line.fetch(0x1234, 0x5678, 0xAB)

        self.assertEqual([entry[0] for entry in line.log[2:]], [0x5678, 0x5678])

    def test_the_read_strobe_falls_on_the_second_state(self) -> None:
        line = recorder()

        line.fetch(0x1234, 0x5678, 0xAB)

        self.assertEqual(
            [entry[2] for entry in line.log], [bus.IDLE, bus.MEMORY_READ, bus.IDLE, bus.IDLE]
        )

    def test_the_opcode_appears_on_the_third(self) -> None:
        line = recorder()

        line.fetch(0x1234, 0x5678, 0xAB)

        self.assertEqual([entry[1] for entry in line.log], [None, None, 0xAB, None])


class MemoryTest(unittest.TestCase):
    def test_a_read_holds_one_address_throughout(self) -> None:
        line = recorder()

        line.read(0x2000, 0x42)

        self.assertEqual({entry[0] for entry in line.log}, {0x2000})

    def test_a_read_latches_its_value_at_the_end(self) -> None:
        line = recorder()

        line.read(0x2000, 0x42)

        self.assertEqual([entry[1] for entry in line.log], [None, None, 0x42])

    def test_a_write_drives_its_value_a_state_earlier_than_a_read_latches_one(self) -> None:
        line = recorder()

        line.write(0x2000, 0x42)

        self.assertEqual([entry[1] for entry in line.log], [None, 0x42, None])

    def test_a_read_asserts_read_and_memory_request(self) -> None:
        line = recorder()

        line.read(0x2000, 0x42)

        self.assertEqual(line.log[1][2], bus.MEMORY_READ)

    def test_a_write_asserts_write_and_memory_request(self) -> None:
        line = recorder()

        line.write(0x2000, 0x42)

        self.assertEqual(line.log[1][2], bus.MEMORY_WRITE)

    def test_the_two_never_assert_the_same_pins(self) -> None:
        self.assertNotEqual(bus.MEMORY_READ, bus.MEMORY_WRITE)


class PortTest(unittest.TestCase):
    def test_a_port_read_asserts_read_and_the_port_request(self) -> None:
        line = recorder()

        line.port_read(0x8000, 0x42)

        self.assertEqual(line.log[2][2], bus.PORT_READ)

    def test_a_port_write_asserts_write_and_the_port_request(self) -> None:
        line = recorder()

        line.port_write(0x8000, 0x42)

        self.assertEqual(line.log[2][2], bus.PORT_WRITE)

    def test_the_request_falls_a_state_late_because_of_the_inserted_wait(self) -> None:
        line = recorder()

        line.port_read(0x8000, 0x42)

        self.assertEqual([entry[2] for entry in line.log[:2]], [bus.IDLE, bus.IDLE])

    def test_a_port_read_latches_its_value_at_the_end(self) -> None:
        line = recorder()

        line.port_read(0x8000, 0x42)

        self.assertEqual([entry[1] for entry in line.log], [None, None, None, 0x42])

    def test_a_port_write_drives_its_value_with_the_strobe(self) -> None:
        line = recorder()

        line.port_write(0x8000, 0x42)

        self.assertEqual([entry[1] for entry in line.log], [None, None, 0x42, None])

    def test_a_port_uses_all_sixteen_address_lines(self) -> None:
        line = recorder()

        line.port_read(0xABCD, 0x00)

        self.assertEqual(line.log[0][0], 0xABCD)


class IdleTest(unittest.TestCase):
    """An internal cycle drives nothing and invents no address."""

    def test_an_internal_cycle_asserts_no_pin(self) -> None:
        line = recorder()
        line.read(0x2000, 0x42)

        line.idle()

        self.assertEqual(line.log[-1][2], bus.IDLE)

    def test_it_holds_the_address_the_last_access_left(self) -> None:
        line = recorder()
        line.read(0x2000, 0x42)

        line.idle()

        self.assertEqual(line.log[-1][0], 0x2000)

    def test_and_after_a_fetch_that_is_the_refresh_address(self) -> None:
        line = recorder()
        line.fetch(0x1234, 0x5678, 0xAB)

        line.idle()

        self.assertEqual(line.log[-1][0], 0x5678)

    def test_it_puts_no_value_on_the_data_pins(self) -> None:
        line = recorder()
        line.read(0x2000, 0x42)

        line.idle()

        self.assertEqual(line.log[-1][1], None)

    def test_several_can_be_asked_for_at_once(self) -> None:
        line = bus.Bus()

        line.idle(7)

        self.assertEqual(len(line), 7)

    def test_asking_for_none_spends_nothing(self) -> None:
        line = bus.Bus()

        line.idle(0)

        self.assertEqual(len(line), 0)


class AddressTest(unittest.TestCase):
    def test_an_address_above_sixteen_bits_is_carried_round(self) -> None:
        line = recorder()

        line.read(0x1_2000, 0x00)

        self.assertEqual(line.log[0][0], 0x2000)

    def test_a_cycle_with_no_address_records_that_rather_than_inventing_one(self) -> None:
        line = recorder()

        line.mark(None, None, bus.IDLE)

        self.assertEqual(line.log[0][0], None)

    def test_and_leaves_the_held_address_alone(self) -> None:
        line = recorder()
        line.read(0x2000, 0x42)

        line.mark(None, None, bus.IDLE)

        self.assertEqual(line.address, 0x2000)


class ReprTest(unittest.TestCase):
    def test_a_bus_prints_what_it_has_spent(self) -> None:
        line = recorder()
        line.read(0x2000, 0x42)

        self.assertIn("3 T states", repr(line))


if __name__ == "__main__":
    unittest.main()
