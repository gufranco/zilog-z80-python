import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from z80 import bus


def recorder() -> bus.Bus:
    return bus.Bus(recording=True)


def recorder_as_recorded() -> bus.Bus:
    return bus.Bus(recording=True, shape=bus.RECORDING)


class ShapeTest(unittest.TestCase):
    """Two shapes, and the manual is the one a caller gets without asking."""

    def test_a_bus_follows_the_manual_unless_told_otherwise(self) -> None:
        self.assertTrue(bus.Bus().follows_the_manual)

    def test_the_recorded_shape_has_to_be_asked_for(self) -> None:
        self.assertFalse(bus.Bus(shape=bus.RECORDING).follows_the_manual)

    def test_a_shape_that_is_neither_is_refused_rather_than_guessed(self) -> None:
        with self.assertRaises(bus.UnknownShape):
            bus.Bus(shape="invented")

    def test_and_the_refusal_names_the_shapes_there_are(self) -> None:
        with self.assertRaises(bus.UnknownShape) as raised:
            bus.Bus(shape="invented")

        self.assertIn(bus.MANUAL, str(raised.exception))

    def test_there_are_exactly_two(self) -> None:
        self.assertEqual(bus.SHAPES, (bus.MANUAL, bus.RECORDING))


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

    def test_the_shape_changes_no_count(self) -> None:
        manual, recorded = bus.Bus(), bus.Bus(shape=bus.RECORDING)

        manual.fetch(0x1234, 0x5678, 0x00)
        recorded.fetch(0x1234, 0x5678, 0x00)

        self.assertEqual(len(manual), len(recorded))

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

    def test_the_read_strobe_covers_the_two_states_the_counter_is_out(self) -> None:
        line = recorder()

        line.fetch(0x1234, 0x5678, 0xAB)

        self.assertEqual([entry[2] for entry in line.log[:2]], [bus.MEMORY_READ] * 2)

    def test_memory_request_continues_through_refresh_but_read_does_not(self) -> None:
        line = recorder()

        line.fetch(0x1234, 0x5678, 0xAB)

        self.assertEqual([entry[2] for entry in line.log[2:]], [bus.MEMORY_REQUEST] * 2)

    def test_the_opcode_appears_on_the_third(self) -> None:
        line = recorder()

        line.fetch(0x1234, 0x5678, 0xAB)

        self.assertEqual([entry[1] for entry in line.log], [None, None, 0xAB, None])

    def test_the_recorded_shape_strobes_for_one_state_only(self) -> None:
        line = recorder_as_recorded()

        line.fetch(0x1234, 0x5678, 0xAB)

        self.assertEqual(
            [entry[2] for entry in line.log], [bus.IDLE, bus.MEMORY_READ, bus.IDLE, bus.IDLE]
        )

    def test_and_puts_the_same_addresses_and_value_where_the_manual_does(self) -> None:
        manual, recorded = recorder(), recorder_as_recorded()

        manual.fetch(0x1234, 0x5678, 0xAB)
        recorded.fetch(0x1234, 0x5678, 0xAB)

        self.assertEqual([entry[:2] for entry in manual.log], [entry[:2] for entry in recorded.log])


class MemoryTest(unittest.TestCase):
    def test_a_read_holds_one_address_throughout(self) -> None:
        line = recorder()

        line.read(0x2000, 0x42)

        self.assertEqual({entry[0] for entry in line.log}, {0x2000})

    def test_a_read_latches_its_value_at_the_end(self) -> None:
        line = recorder()

        line.read(0x2000, 0x42)

        self.assertEqual([entry[1] for entry in line.log], [None, None, 0x42])

    def test_a_read_strobes_every_state_because_no_refresh_is_waiting(self) -> None:
        line = recorder()

        line.read(0x2000, 0x42)

        self.assertEqual([entry[2] for entry in line.log], [bus.MEMORY_READ] * 3)

    def test_a_write_asserts_memory_request_before_the_write_strobe(self) -> None:
        line = recorder()

        line.write(0x2000, 0x42)

        self.assertEqual(
            [entry[2] for entry in line.log],
            [bus.MEMORY_REQUEST, bus.MEMORY_WRITE, bus.MEMORY_WRITE],
        )

    def test_a_write_drives_its_value_from_the_start_because_the_part_is_driving(self) -> None:
        line = recorder()

        line.write(0x2000, 0x42)

        self.assertEqual([entry[1] for entry in line.log], [0x42, 0x42, 0x42])

    def test_the_recorded_shape_reads_with_a_single_state_strobe(self) -> None:
        line = recorder_as_recorded()

        line.read(0x2000, 0x42)

        self.assertEqual([entry[2] for entry in line.log], [bus.IDLE, bus.MEMORY_READ, bus.IDLE])

    def test_and_writes_with_one_too(self) -> None:
        line = recorder_as_recorded()

        line.write(0x2000, 0x42)

        self.assertEqual([entry[2] for entry in line.log], [bus.IDLE, bus.MEMORY_WRITE, bus.IDLE])

    def test_and_shows_the_written_value_only_while_the_strobe_is_down(self) -> None:
        line = recorder_as_recorded()

        line.write(0x2000, 0x42)

        self.assertEqual([entry[1] for entry in line.log], [None, 0x42, None])

    def test_the_two_never_assert_the_same_pins(self) -> None:
        self.assertNotEqual(bus.MEMORY_READ, bus.MEMORY_WRITE)

    def test_refresh_requests_memory_without_reading_it(self) -> None:
        self.assertEqual((bus.MEMORY_REQUEST.count("r"), bus.MEMORY_REQUEST.count("m")), (0, 1))


class PortTest(unittest.TestCase):
    def test_a_port_read_asserts_read_and_the_port_request(self) -> None:
        line = recorder()

        line.port_read(0x8000, 0x42)

        self.assertEqual(line.log[2][2], bus.PORT_READ)

    def test_a_port_write_asserts_write_and_the_port_request(self) -> None:
        line = recorder()

        line.port_write(0x8000, 0x42)

        self.assertEqual(line.log[2][2], bus.PORT_WRITE)

    def test_the_request_falls_a_whole_state_later_than_a_memory_one(self) -> None:
        line = recorder()

        line.port_read(0x8000, 0x42)

        self.assertEqual([entry[2] for entry in line.log], [bus.IDLE] + [bus.PORT_READ] * 3)

    def test_a_port_read_latches_its_value_at_the_end(self) -> None:
        line = recorder()

        line.port_read(0x8000, 0x42)

        self.assertEqual([entry[1] for entry in line.log], [None, None, None, 0x42])

    def test_a_port_write_drives_its_value_from_the_first_state(self) -> None:
        line = recorder()

        line.port_write(0x8000, 0x42)

        self.assertEqual([entry[1] for entry in line.log], [0x42] * 4)

    def test_and_strobes_the_three_states_after_the_address_settles(self) -> None:
        line = recorder()

        line.port_write(0x8000, 0x42)

        self.assertEqual([entry[2] for entry in line.log], [bus.IDLE] + [bus.PORT_WRITE] * 3)

    def test_a_port_uses_all_sixteen_address_lines(self) -> None:
        line = recorder()

        line.port_read(0xABCD, 0x00)

        self.assertEqual(line.log[0][0], 0xABCD)

    def test_the_recorded_shape_strobes_the_wait_state_alone(self) -> None:
        line = recorder_as_recorded()

        line.port_read(0x8000, 0x42)

        self.assertEqual(
            [entry[2] for entry in line.log],
            [bus.IDLE, bus.IDLE, bus.PORT_READ, bus.IDLE],
        )

    def test_and_writes_the_same_way(self) -> None:
        line = recorder_as_recorded()

        line.port_write(0x8000, 0x42)

        self.assertEqual(
            [entry[2] for entry in line.log],
            [bus.IDLE, bus.IDLE, bus.PORT_WRITE, bus.IDLE],
        )


class AcknowledgeTest(unittest.TestCase):
    """The special fetch that answers an interrupt, with its two added waits."""

    def test_it_costs_the_six_the_manual_accounts_for(self) -> None:
        line = bus.Bus()

        line.acknowledge(0x1234, 0x5678, 0xFF)

        self.assertEqual(len(line), bus.ACKNOWLEDGE_STATES)

    def test_which_is_a_fetch_plus_the_two_waits_the_manual_adds(self) -> None:
        self.assertEqual(bus.ACKNOWLEDGE_STATES - bus.FETCH_STATES, 2)

    def test_it_requests_a_port_where_a_fetch_requests_memory(self) -> None:
        line = recorder()

        line.acknowledge(0x1234, 0x5678, 0xFF)

        self.assertEqual([entry[2] for entry in line.log[2:4]], [bus.PORT_REQUEST] * 2)

    def test_it_never_asserts_the_read_strobe(self) -> None:
        line = recorder()

        line.acknowledge(0x1234, 0x5678, 0xFF)

        self.assertEqual([entry[2].count("r") for entry in line.log], [0] * 6)

    def test_the_state_the_figure_does_not_draw_is_not_drawn_here_either(self) -> None:
        line = bus.Bus()

        line.acknowledge(0x1234, 0x5678, 0xFF)

        self.assertEqual(len(line), 6)

    def test_it_refreshes_exactly_as_an_ordinary_fetch_does(self) -> None:
        line = recorder()

        line.acknowledge(0x1234, 0x5678, 0xFF)

        self.assertEqual([entry[2] for entry in line.log[4:]], [bus.MEMORY_REQUEST] * 2)

    def test_the_refresh_address_reaches_the_bus_for_the_last_two(self) -> None:
        line = recorder()

        line.acknowledge(0x1234, 0x5678, 0xFF)

        self.assertEqual([entry[0] for entry in line.log[4:]], [0x5678] * 2)

    def test_the_vector_arrives_on_the_second_wait_state(self) -> None:
        line = recorder()

        line.acknowledge(0x1234, 0x5678, 0xFF)

        self.assertEqual([entry[1] for entry in line.log], [None, None, None, 0xFF, None, None])

    def test_the_recorded_shape_strobes_that_one_state_alone(self) -> None:
        line = recorder_as_recorded()

        line.acknowledge(0x1234, 0x5678, 0xFF)

        self.assertEqual(
            [entry[2] for entry in line.log],
            [bus.IDLE] * 3 + [bus.PORT_REQUEST] + [bus.IDLE] * 2,
        )

    def test_and_costs_the_same_either_way(self) -> None:
        manual, recorded = bus.Bus(), bus.Bus(shape=bus.RECORDING)

        manual.acknowledge(0x1234, 0x5678, 0xFF)
        recorded.acknowledge(0x1234, 0x5678, 0xFF)

        self.assertEqual(len(manual), len(recorded))


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

    def test_and_which_shape_it_is_drawing(self) -> None:
        self.assertIn(bus.RECORDING, repr(bus.Bus(shape=bus.RECORDING)))


if __name__ == "__main__":
    unittest.main()
