import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from z80 import bus, errors


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
        with self.assertRaises(errors.UnknownShape):
            bus.Bus(shape="invented")

    def test_and_the_refusal_names_the_shapes_there_are(self) -> None:
        with self.assertRaises(errors.UnknownShape) as raised:
            bus.Bus(shape="invented")

        self.assertIn(bus.MANUAL, str(raised.exception))

    def test_there_are_exactly_two(self) -> None:
        self.assertEqual(bus.SHAPES, (bus.MANUAL, bus.RECORDING))


class EdgeTest(unittest.TestCase):
    """The columns are derived from the measured edges, not written out by hand."""

    def test_every_machine_cycle_kind_has_a_measured_edge_table(self) -> None:
        self.assertEqual(
            set(bus.EDGES),
            {
                bus.FETCH,
                bus.READ_CYCLE,
                bus.WRITE_CYCLE,
                bus.PORT_READ_CYCLE,
                bus.PORT_WRITE_CYCLE,
                bus.ACKNOWLEDGE,
            },
        )

    def test_every_edge_names_a_pin_the_encoding_carries(self) -> None:
        named = {pin for states, edges in bus.EDGES.values() for pin, _, _ in edges}

        self.assertLessEqual(named, set(bus.PIN_ORDER))

    def test_every_edge_falls_on_the_clock(self) -> None:
        offsets = {
            value % 0.5
            for states, edges in bus.EDGES.values()
            for _, start, end in edges
            for value in (start, end)
        }

        self.assertEqual(offsets, {0.0})

    def test_no_pin_goes_inactive_before_it_goes_active(self) -> None:
        backwards = [
            (name, pin)
            for name, (states, edges) in bus.EDGES.items()
            for pin, start, end in edges
            if end <= start
        ]

        self.assertEqual(backwards, [])

    def test_no_edge_falls_outside_the_cycle_it_belongs_to(self) -> None:
        outside = [
            (name, pin)
            for name, (states, edges) in bus.EDGES.items()
            for pin, start, end in edges
            if start < 0 or end > states
        ]

        self.assertEqual(outside, [])

    def test_a_column_is_as_wide_as_the_pins_there_are(self) -> None:
        widths = {len(column) for name in bus.EDGES for column in bus.columns(name)}

        self.assertEqual(widths, {len(bus.PIN_ORDER)})

    def test_a_cycle_has_as_many_columns_as_it_has_states(self) -> None:
        found = {name: len(bus.columns(name)) for name in bus.EDGES}

        self.assertEqual(found, {name: states for name, (states, _) in bus.EDGES.items()})

    def test_the_pins_are_written_in_the_order_the_corpus_writes_them(self) -> None:
        self.assertEqual("".join(bus.PIN_ORDER), "rwmi")

    def test_a_strobe_belongs_to_the_state_whose_end_it_is_still_active_at(self) -> None:
        edges = ((bus.MEMORY, 0.5, 2.0),)

        held = [any(start < state + 1 <= end for _, start, end in edges) for state in range(3)]

        self.assertEqual(held, [True, True, False])

    def test_and_not_to_one_it_merely_overlaps(self) -> None:
        self.assertEqual(bus.columns(bus.FETCH)[2], bus.MEMORY_REQUEST)

    def test_the_refresh_state_requests_memory_without_reading_it(self) -> None:
        self.assertEqual(bus.columns(bus.FETCH)[2].count(bus.READ), 0)

    def test_the_derivation_and_the_table_it_fills_agree(self) -> None:
        derived = {name: bus.columns(name) for name in bus.EDGES}

        self.assertEqual(bus.COLUMNS, derived)

    def test_the_table_covers_every_machine_cycle_kind(self) -> None:
        self.assertEqual(set(bus.COLUMNS), set(bus.EDGES))

    def test_a_port_cycle_leaves_its_first_state_bare_and_a_memory_one_does_not(self) -> None:
        first = (bus.columns(bus.PORT_READ_CYCLE)[0], bus.columns(bus.READ_CYCLE)[0])

        self.assertEqual(first, (bus.IDLE, bus.MEMORY_READ))


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

        self.assertEqual([entry[2] for entry in line.log[2:]], [bus.MEMORY_REQUEST, bus.IDLE])

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

    def test_a_read_holds_its_strobes_half_a_state_longer_than_a_fetch(self) -> None:
        released = {
            name: [end for pin, _, end in bus.EDGES[name][1] if pin == bus.READ]
            for name in (bus.FETCH, bus.READ_CYCLE)
        }

        self.assertEqual(released[bus.READ_CYCLE][0] - released[bus.FETCH][0], 0.5)

    def test_a_write_asserts_memory_request_before_the_write_strobe(self) -> None:
        line = recorder()

        line.write(0x2000, 0x42)

        self.assertEqual(
            [entry[2] for entry in line.log],
            [bus.MEMORY_REQUEST, bus.MEMORY_WRITE, bus.IDLE],
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

        self.assertEqual(
            [entry[2] for entry in line.log],
            [bus.IDLE, bus.PORT_READ, bus.PORT_READ, bus.IDLE],
        )

    def test_a_port_read_latches_its_value_at_the_end(self) -> None:
        line = recorder()

        line.port_read(0x8000, 0x42)

        self.assertEqual([entry[1] for entry in line.log], [None, None, None, 0x42])

    def test_a_write_drives_its_value_through_the_whole_cycle(self) -> None:
        line = recorder()

        line.write(0x2000, 0x42)

        self.assertEqual([entry[1] for entry in line.log], [0x42] * 3)

    def test_a_port_write_drives_its_value_from_the_first_state(self) -> None:
        line = recorder()

        line.port_write(0x8000, 0x42)

        self.assertEqual([entry[1] for entry in line.log], [0x42] * 4)

    def test_and_strobes_the_three_states_after_the_address_settles(self) -> None:
        line = recorder()

        line.port_write(0x8000, 0x42)

        self.assertEqual(
            [entry[2] for entry in line.log],
            [bus.IDLE, bus.PORT_WRITE, bus.PORT_WRITE, bus.IDLE],
        )

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

    def test_it_draws_the_six_states_the_figure_draws(self) -> None:
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

        self.assertEqual([entry[2] for entry in line.log[4:]], [bus.MEMORY_REQUEST, bus.IDLE])

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
