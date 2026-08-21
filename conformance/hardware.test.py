"""Hold the core's own constants and timing to what Zilog printed.

A datasheet figure quoted in a docstring rots and cannot fail. This file is what
turns hardware.json from a record of a reading into a gate.

It checks two different things, and the difference matters. The first is that
the constants in this package match the figures in the document. The second is
that the number of T states this core spends on a documented instruction is the
number the document gives it, assembled and stepped rather than looked up. That
second check is the only place the core is held to Zilog rather than to the
recording, and it is deliberately independent of the conformance suite: a
machine with no suite on it still runs it.
"""

import json
import sys
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any, override

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from z80 import bus, core, flags, memory, models

HELD = json.loads((Path(__file__).resolve().parent / "hardware.json").read_text())

DIVERGENCES = json.loads((Path(__file__).resolve().parent / "divergences.json").read_text())

SUITES = json.loads((Path(__file__).resolve().parent / "suites.json").read_text())

FACTS = HELD["facts"]

SHAPES = FACTS["machineCycleShapes"]

ROWS = FACTS["instructionTiming"]["rows"]

EDGES = SHAPES["figureEdges"]

RESPONSE = FACTS["interruptResponse"]

PIN_LABELS = {"r": "RD", "w": "WR", "m": "MREQ", "i": "IORQ"}

CYCLE_KEYS = {
    bus.FETCH: "opcodeFetch",
    bus.READ_CYCLE: "memoryRead",
    bus.WRITE_CYCLE: "memoryWrite",
    bus.ACKNOWLEDGE: "interruptAcknowledge",
}

CYCLES_WITH_FIGURES = (
    "opcodeFetch",
    "memoryRead",
    "memoryWrite",
    "inputOrOutput",
    "interruptAcknowledge",
)

START = 0x0100
"""Where a probe instruction is assembled, clear of the vectors and of zero."""


def spent(program: tuple[int, ...], setup: dict[str, int] | None = None) -> int:
    """The T states this core spends on one instruction, assembled and stepped.

    Nothing is looked up. The bytes are written into memory, the part is pointed
    at them, and the bus counts what it spends. A model whose timing came from a
    table would pass this by construction, which is why it does not have one.
    """
    space = memory.SparseMemory()
    for offset, byte in enumerate(program):
        space.write8(START + offset, byte)
    cpu = core.Cpu(space, reset=True)
    cpu.registers.pc = START
    for name, value in (setup or {}).items():
        setattr(cpu.registers, name, value)
    cpu.step()
    return len(cpu.bus)


def row(page: int) -> dict[str, Any]:
    """The manual's timing row from one page, which is where each one is unique."""
    found = [entry for entry in ROWS if entry["manualPage"] == page]
    if len(found) != 1:
        raise AssertionError(f"manual page {page} has {len(found)} timing rows, expected one")
    only: dict[str, Any] = found[0]
    return only


class RowLookupTest(unittest.TestCase):
    """The helper the timing cases lean on, which has to refuse an ambiguous page."""

    def test_a_page_with_one_row_gives_that_row(self) -> None:
        self.assertEqual(row(180)["tStates"], 4)

    def test_a_page_with_no_row_is_refused_rather_than_guessed(self) -> None:
        with self.assertRaises(AssertionError):
            row(1)

    def test_a_page_with_more_than_one_row_is_refused_too(self) -> None:
        crowded = [
            page
            for page in {entry["manualPage"] for entry in ROWS}
            if len([entry for entry in ROWS if entry["manualPage"] == page]) > 1
        ]

        with self.assertRaises(AssertionError):
            row(crowded[0])


class DocumentTest(unittest.TestCase):
    def test_the_part_is_backed_by_a_named_document(self) -> None:
        self.assertEqual(HELD["document"]["publisher"], "Zilog, Inc.")

    def test_the_document_is_the_publisher_current_revision(self) -> None:
        self.assertEqual(HELD["document"]["documentNumber"], "UM008011-0816")

    def test_it_carries_a_digest_so_the_reading_can_be_repeated(self) -> None:
        self.assertRegex(HELD["document"]["sha256"], r"^[0-9a-f]{64}$")

    def test_the_part_is_marked_verified_because_the_document_exists(self) -> None:
        self.assertTrue(HELD["verified"])


class TimingTableTest(unittest.TestCase):
    """The document's own internal redundancy, used as a check on the reading."""

    def test_every_breakdown_sums_to_the_total_beside_it(self) -> None:
        wrong = [
            entry["instruction"]
            for entry in ROWS
            if sum(entry["machineCycles"]) != entry["tStates"]
        ]

        self.assertEqual(wrong, [])

    def test_the_table_covers_the_whole_documented_instruction_set(self) -> None:
        self.assertGreater(len(ROWS), 180)

    def test_every_row_names_the_page_it_was_read_from(self) -> None:
        missing = [entry["instruction"] for entry in ROWS if not entry.get("manualPage")]

        self.assertEqual(missing, [])

    def test_no_instruction_takes_fewer_states_than_one_fetch(self) -> None:
        short = [entry["instruction"] for entry in ROWS if entry["tStates"] < bus.FETCH_STATES]

        self.assertEqual(short, [])

    def test_the_rows_whose_machine_cycle_count_is_a_misprint_are_flagged(self) -> None:
        flagged = {entry["manualPage"] for entry in ROWS if entry.get("printedMCyclesIsAMisprint")}

        self.assertEqual(flagged, {99, 260, 269})

    def test_and_each_of_those_is_written_up_as_a_contradiction(self) -> None:
        pages = {
            entry["manualPage"]
            for entry in HELD["documentContradictions"]
            if entry["kind"] == "timingTableMisprint"
        }

        self.assertEqual(pages, {99, 260, 269})

    def test_every_contradiction_says_which_kind_it_is(self) -> None:
        kinds = {entry["kind"] for entry in HELD["documentContradictions"]}

        self.assertEqual(kinds, {"timingTableMisprint", "proseVersusFigure"})

    def test_the_prose_a_figure_or_a_sibling_page_contradicts_is_quoted(self) -> None:
        found = [
            entry["printed"]
            for entry in HELD["documentContradictions"]
            if entry["kind"] == "proseVersusFigure"
        ]

        self.assertEqual(len(found), 2)

    def test_and_one_of_the_two_is_a_page_that_contradicts_itself(self) -> None:
        found = [
            entry
            for entry in HELD["documentContradictions"]
            if entry["id"] == "bit-instruction-negate-flag-printed-as-half-carry"
        ]

        self.assertEqual(found[0]["printed"].count("H is"), 2)

    def test_no_other_row_disagrees_with_its_own_breakdown(self) -> None:
        wrong = [
            entry["manualPage"]
            for entry in ROWS
            if len(entry["machineCycles"]) != entry["printedMCycles"]
            and not entry.get("printedMCyclesIsAMisprint")
        ]

        self.assertEqual(wrong, [])


class MachineCycleShapeTest(unittest.TestCase):
    def test_a_fetch_is_as_long_as_the_manual_says(self) -> None:
        self.assertEqual(bus.FETCH_STATES, SHAPES["opcodeFetch"]["tStates"])

    def test_a_memory_access_is_as_long_as_the_manual_says(self) -> None:
        self.assertEqual(bus.MEMORY_STATES, SHAPES["memoryReadOrWrite"]["tStates"])

    def test_a_port_access_is_as_long_as_the_manual_says(self) -> None:
        self.assertEqual(bus.PORT_STATES, SHAPES["inputOrOutput"]["tStates"])

    def test_the_port_access_carries_the_wait_the_manual_says_is_inserted(self) -> None:
        inserted = SHAPES["inputOrOutput"]["automaticWaitStates"]

        self.assertEqual(bus.PORT_STATES - bus.MEMORY_STATES, inserted)

    def test_the_bus_draws_the_states_the_acknowledge_figure_draws(self) -> None:
        self.assertEqual(bus.ACKNOWLEDGE_STATES, SHAPES["interruptAcknowledge"]["drawnStates"])

    def test_and_the_cycle_costs_one_more_than_that(self) -> None:
        drawn = SHAPES["interruptAcknowledge"]["drawnStates"]

        self.assertEqual(SHAPES["interruptAcknowledge"]["tStates"] - drawn, 1)

    def test_which_the_response_spends_beyond_its_two_stack_writes(self) -> None:
        cpu = core.Cpu(memory.SparseMemory(), reset=True)
        cpu.registers.sp, cpu.registers.iff1, cpu.registers.im = 0x8000, True, 1
        undrawn = SHAPES["interruptAcknowledge"]["tStates"] - bus.ACKNOWLEDGE_STATES

        cpu.interrupt(0xFF)

        beyond = len(cpu.bus) - bus.ACKNOWLEDGE_STATES - 2 * bus.MEMORY_STATES
        self.assertEqual(beyond, undrawn)

    def test_the_drawn_states_are_a_fetch_and_the_two_added_waits(self) -> None:
        added = SHAPES["interruptAcknowledge"]["automaticWaitStates"]

        self.assertEqual(bus.ACKNOWLEDGE_STATES - bus.FETCH_STATES, added)

    def test_and_the_cost_is_the_five_state_kind_of_fetch_plus_them(self) -> None:
        base = SHAPES["interruptAcknowledge"]["baseM1States"]
        added = SHAPES["interruptAcknowledge"]["automaticWaitStates"]

        self.assertEqual(SHAPES["interruptAcknowledge"]["tStates"], base + added)


class FigureEdgeTest(unittest.TestCase):
    """The pins this bus draws, against the edges measured off the manual's figures.

    The record holds where each edge falls and the columns the rule gives when
    applied to them. This asserts the bus produces those columns, so a change to
    either has to be a change to both.
    """

    def pins(self, cycle: Callable[[bus.Bus], None]) -> list[str]:
        line = bus.Bus(recording=True)
        cycle(line)
        return [entry[2] for entry in line.log]

    def test_a_fetch_draws_the_columns_figure_5_gives_it(self) -> None:
        self.assertEqual(
            self.pins(lambda line: line.fetch(0x1234, 0x5678, 0xAB)),
            EDGES["opcodeFetch"]["columns"],
        )

    def test_a_read_draws_the_columns_figure_6_gives_it(self) -> None:
        self.assertEqual(
            self.pins(lambda line: line.read(0x2000, 0x42)),
            EDGES["memoryRead"]["columns"],
        )

    def test_a_write_draws_the_columns_figure_6_gives_it(self) -> None:
        self.assertEqual(
            self.pins(lambda line: line.write(0x2000, 0x42)),
            EDGES["memoryWrite"]["columns"],
        )

    def test_a_port_read_draws_the_columns_figure_7_gives_it(self) -> None:
        self.assertEqual(
            self.pins(lambda line: line.port_read(0x8000, 0x42)),
            EDGES["inputOrOutput"]["columns"]["read"],
        )

    def test_a_port_write_draws_the_columns_figure_7_gives_it(self) -> None:
        self.assertEqual(
            self.pins(lambda line: line.port_write(0x8000, 0x42)),
            EDGES["inputOrOutput"]["columns"]["write"],
        )

    def test_an_acknowledge_draws_the_columns_figure_9_gives_it(self) -> None:
        self.assertEqual(
            self.pins(lambda line: line.acknowledge(0x1234, 0x5678, 0xFF)),
            EDGES["interruptAcknowledge"]["columns"],
        )

    def test_every_set_of_columns_is_as_long_as_its_cycle(self) -> None:
        lengths = {
            "opcodeFetch": bus.FETCH_STATES,
            "memoryRead": bus.MEMORY_STATES,
            "memoryWrite": bus.MEMORY_STATES,
            "interruptAcknowledge": bus.ACKNOWLEDGE_STATES,
        }

        found = {name: len(EDGES[name]["columns"]) for name in lengths}

        self.assertEqual(found, lengths)

    def test_and_a_port_cycle_is_as_long_either_way_round(self) -> None:
        both = EDGES["inputOrOutput"]["columns"]

        self.assertEqual(
            (len(both["read"]), len(both["write"])), (bus.PORT_STATES, bus.PORT_STATES)
        )

    def test_the_acknowledge_asserts_no_read_because_the_figure_draws_none(self) -> None:
        self.assertNotIn("RD", EDGES["interruptAcknowledge"]["pins"])

    def test_the_clock_rises_at_the_boundary_and_falls_mid_state(self) -> None:
        clock = EDGES["clock"]

        self.assertEqual((clock["rises"], float(clock["falls"])), ("+0.00", 0.56))

    def test_the_record_holds_the_same_edges_the_bus_derives_from(self) -> None:
        recorded = {
            (name, pin, window["activeFrom"], window["activeUntil"])
            for name in CYCLES_WITH_FIGURES
            for pin, windows in EDGES[name]["pins"].items()
            for window in windows
            if pin in set(PIN_LABELS.values())
        }
        held = {
            (name, PIN_LABELS[pin], start, end)
            for key, name in CYCLE_KEYS.items()
            for pin, start, end in bus.EDGES[key][1]
        }

        self.assertLessEqual(held, recorded)

    def test_every_edge_in_the_record_falls_on_the_clock(self) -> None:
        offsets = {
            value % 0.5
            for name in CYCLES_WITH_FIGURES
            for windows in EDGES[name]["pins"].values()
            for window in windows
            for value in (window["activeFrom"], window["activeUntil"])
        }

        self.assertEqual(offsets, {0.0})

    def test_the_rule_that_turns_an_edge_into_a_column_is_written_down(self) -> None:
        self.assertEqual(EDGES["rule"]["name"], "read at the clock edge that ends each T state")

    def covered(self, cycle: str) -> list[str]:
        """The reading that was not chosen, applied to the same measured edges.

        A pin belongs to a state when it is asserted at any point during it,
        rather than when the state ends. Computing it here rather than reading it
        out of the record is what makes the record's copy a checked figure.
        """
        states, edges = bus.EDGES[cycle]
        return [
            "".join(
                pin
                if any(pin == name and start < n + 1 and end > n for name, start, end in edges)
                else "-"
                for pin in bus.PIN_ORDER
            )
            for n in range(states)
        ]

    def test_the_reading_that_was_not_chosen_is_recorded_as_it_computes(self) -> None:
        gives = EDGES["rule"]["alternative"]["gives"]
        found: dict[str, Any] = {name: self.covered(cycle) for cycle, name in CYCLE_KEYS.items()}
        found["inputOrOutput"] = {
            "read": self.covered(bus.PORT_READ_CYCLE),
            "write": self.covered(bus.PORT_WRITE_CYCLE),
        }

        self.assertEqual(gives, found)

    def test_and_it_differs_from_the_reading_that_was(self) -> None:
        gives = EDGES["rule"]["alternative"]["gives"]

        same = [name for name in gives if gives[name] == EDGES[name]["columns"]]

        self.assertEqual(same, [])

    def asserted(self, columns: list[str]) -> int:
        return sum(len(column) - column.count("-") for column in columns)

    def test_it_holds_every_strobe_longer_and_never_shorter(self) -> None:
        gives = EDGES["rule"]["alternative"]["gives"]
        longer = {
            name: self.asserted(gives[name]) - self.asserted(EDGES[name]["columns"])
            for name in CYCLE_KEYS.values()
        }

        self.assertEqual([name for name, more in longer.items() if more <= 0], [])

    def test_every_measured_edge_is_recorded_as_read_from_a_figure(self) -> None:
        self.assertEqual(EDGES["provenance"], "read from the figure rather than from the prose")

    def test_each_cycle_names_the_figure_it_was_read_from(self) -> None:
        named = {name: EDGES[name]["figure"] for name in CYCLES_WITH_FIGURES}

        self.assertEqual(
            named,
            {
                "opcodeFetch": 5,
                "memoryRead": 6,
                "memoryWrite": 6,
                "inputOrOutput": 7,
                "interruptAcknowledge": 9,
            },
        )


class SpentAgainstTheManualTest(unittest.TestCase):
    """The core stepped, against the figure printed for that instruction.

    Each case names the manual page rather than repeating the number, so the
    expected value comes out of the document and not out of this file.
    """

    def test_a_register_to_register_load_costs_what_page_71_says(self) -> None:
        self.assertEqual(spent((0x41,)), row(71)["tStates"])

    def test_an_immediate_load_costs_what_page_72_says(self) -> None:
        self.assertEqual(spent((0x06, 0x00)), row(72)["tStates"])

    def test_a_load_through_the_pair_costs_what_page_74_says(self) -> None:
        self.assertEqual(spent((0x46,)), row(74)["tStates"])

    def test_an_indexed_load_costs_what_page_75_says(self) -> None:
        self.assertEqual(spent((0xDD, 0x46, 0x01)), row(75)["tStates"])

    def test_a_store_through_the_pair_costs_what_page_79_says(self) -> None:
        self.assertEqual(spent((0x70,)), row(79)["tStates"])

    def test_an_indexed_store_costs_what_page_81_says(self) -> None:
        self.assertEqual(spent((0xDD, 0x70, 0x01)), row(81)["tStates"])

    def test_an_immediate_store_through_the_pair_costs_what_page_85_says(self) -> None:
        self.assertEqual(spent((0x36, 0x00)), row(85)["tStates"])

    def test_an_indexed_immediate_store_costs_what_page_86_says(self) -> None:
        self.assertEqual(spent((0xDD, 0x36, 0x01, 0x00)), row(86)["tStates"])

    def test_a_load_through_a_pair_costs_what_page_88_says(self) -> None:
        self.assertEqual(spent((0x0A,)), row(88)["tStates"])

    def test_an_extended_load_costs_what_page_90_says(self) -> None:
        self.assertEqual(spent((0x3A, 0x00, 0x20)), row(90)["tStates"])

    def test_reading_the_interrupt_register_costs_what_page_94_says(self) -> None:
        self.assertEqual(spent((0xED, 0x57)), row(94)["tStates"])

    def test_writing_it_costs_what_page_96_says(self) -> None:
        self.assertEqual(spent((0xED, 0x47)), row(96)["tStates"])

    def test_a_wide_immediate_load_costs_what_page_99_says(self) -> None:
        self.assertEqual(spent((0x01, 0x00, 0x20)), row(99)["tStates"])

    def test_an_indexed_wide_immediate_load_costs_what_page_100_says(self) -> None:
        self.assertEqual(spent((0xDD, 0x21, 0x00, 0x20)), row(100)["tStates"])

    def test_a_wide_extended_load_costs_what_page_102_says(self) -> None:
        self.assertEqual(spent((0x2A, 0x00, 0x20)), row(102)["tStates"])

    def test_the_extended_form_of_it_costs_what_page_103_says(self) -> None:
        self.assertEqual(spent((0xED, 0x4B, 0x00, 0x20)), row(103)["tStates"])

    def test_a_wide_extended_store_costs_what_page_107_says(self) -> None:
        self.assertEqual(spent((0x22, 0x00, 0x20)), row(107)["tStates"])

    def test_loading_the_stack_pointer_costs_what_page_112_says(self) -> None:
        self.assertEqual(spent((0xF9,)), row(112)["tStates"])

    def test_a_push_costs_what_page_115_says(self) -> None:
        self.assertEqual(spent((0xC5,)), row(115)["tStates"])

    def test_an_indexed_push_costs_what_page_117_says(self) -> None:
        self.assertEqual(spent((0xDD, 0xE5)), row(117)["tStates"])

    def test_a_pop_costs_what_page_119_says(self) -> None:
        self.assertEqual(spent((0xC1,)), row(119)["tStates"])

    def test_exchanging_the_pairs_costs_what_page_124_says(self) -> None:
        self.assertEqual(spent((0xEB,)), row(124)["tStates"])

    def test_exchanging_the_shadow_set_costs_what_page_126_says(self) -> None:
        self.assertEqual(spent((0xD9,)), row(126)["tStates"])

    def test_exchanging_through_the_stack_costs_what_page_127_says(self) -> None:
        self.assertEqual(spent((0xE3,)), row(127)["tStates"])

    def test_a_block_move_costs_what_page_130_says(self) -> None:
        self.assertEqual(
            spent(
                (
                    0xED,
                    0xA0,
                ),
                {"bc": 1},
            ),
            row(130)["tStates"],
        )

    def test_a_block_compare_costs_what_page_138_says(self) -> None:
        self.assertEqual(
            spent(
                (
                    0xED,
                    0xA1,
                ),
                {"bc": 1},
            ),
            row(138)["tStates"],
        )

    def test_an_arithmetic_register_operation_costs_what_page_145_says(self) -> None:
        self.assertEqual(spent((0x80,)), row(145)["tStates"])

    def test_an_arithmetic_immediate_costs_what_page_147_says(self) -> None:
        self.assertEqual(spent((0xC6, 0x00)), row(147)["tStates"])

    def test_arithmetic_through_the_pair_costs_what_page_148_says(self) -> None:
        self.assertEqual(spent((0x86,)), row(148)["tStates"])

    def test_indexed_arithmetic_costs_what_page_149_says(self) -> None:
        self.assertEqual(spent((0xDD, 0x86, 0x01)), row(149)["tStates"])

    def test_incrementing_a_register_costs_what_page_165_says(self) -> None:
        self.assertEqual(spent((0x04,)), row(165)["tStates"])

    def test_incrementing_through_the_pair_costs_what_page_167_says(self) -> None:
        self.assertEqual(spent((0x34,)), row(167)["tStates"])

    def test_incrementing_through_an_index_costs_what_page_168_says(self) -> None:
        self.assertEqual(spent((0xDD, 0x34, 0x01)), row(168)["tStates"])

    def test_the_decimal_adjust_costs_what_page_174_says(self) -> None:
        self.assertEqual(spent((0x27,)), row(174)["tStates"])

    def test_complementing_the_accumulator_costs_what_page_175_says(self) -> None:
        self.assertEqual(spent((0x2F,)), row(175)["tStates"])

    def test_negating_it_costs_what_page_176_says(self) -> None:
        self.assertEqual(spent((0xED, 0x44)), row(176)["tStates"])

    def test_the_no_operation_costs_what_page_180_says(self) -> None:
        self.assertEqual(spent((0x00,)), row(180)["tStates"])

    def test_disabling_interrupts_costs_what_page_182_says(self) -> None:
        self.assertEqual(spent((0xF3,)), row(182)["tStates"])

    def test_a_wide_add_costs_what_page_188_says(self) -> None:
        self.assertEqual(spent((0x09,)), row(188)["tStates"])

    def test_a_wide_add_with_carry_costs_what_page_190_says(self) -> None:
        self.assertEqual(spent((0xED, 0x4A)), row(190)["tStates"])

    def test_an_indexed_wide_add_costs_what_page_194_says(self) -> None:
        self.assertEqual(spent((0xDD, 0x09)), row(194)["tStates"])

    def test_incrementing_a_pair_costs_what_page_198_says(self) -> None:
        self.assertEqual(spent((0x03,)), row(198)["tStates"])

    def test_incrementing_an_index_costs_what_page_199_says(self) -> None:
        self.assertEqual(spent((0xDD, 0x23)), row(199)["tStates"])

    def test_rotating_the_accumulator_costs_what_page_205_says(self) -> None:
        self.assertEqual(spent((0x07,)), row(205)["tStates"])

    def test_rotating_a_register_costs_what_page_213_says(self) -> None:
        self.assertEqual(spent((0xCB, 0x00)), row(213)["tStates"])

    def test_the_nibble_rotate_costs_what_page_238_says(self) -> None:
        self.assertEqual(spent((0xED, 0x6F)), row(238)["tStates"])

    def test_an_unconditional_jump_costs_what_page_262_says(self) -> None:
        self.assertEqual(spent((0xC3, 0x00, 0x20)), row(262)["tStates"])

    def test_a_jump_through_the_pair_costs_what_page_275_says(self) -> None:
        self.assertEqual(spent((0xE9,)), row(275)["tStates"])

    def test_an_unconditional_call_costs_what_page_281_says(self) -> None:
        self.assertEqual(spent((0xCD, 0x00, 0x20)), row(281)["tStates"])

    def test_a_return_costs_what_page_285_says(self) -> None:
        self.assertEqual(spent((0xC9,)), row(285)["tStates"])

    def test_a_restart_costs_what_page_293_says(self) -> None:
        self.assertEqual(spent((0xC7,)), row(293)["tStates"])

    def test_an_immediate_input_costs_what_page_295_says(self) -> None:
        self.assertEqual(spent((0xDB, 0x00)), row(295)["tStates"])

    def test_a_register_input_costs_what_page_296_says(self) -> None:
        self.assertEqual(spent((0xED, 0x40)), row(296)["tStates"])

    def test_an_immediate_output_costs_what_page_306_says(self) -> None:
        self.assertEqual(spent((0xD3, 0x00)), row(306)["tStates"])


class InterruptResponseTest(unittest.TestCase):
    """What an accepted interrupt costs, against the totals the manual prints.

    Nothing here assembles a figure. The machine is offered a line and the bus
    reports what it spent, so a model that carried a table of totals would not
    pass this by construction.
    """

    def offered(self, offer: Callable[[core.Cpu], object], mode: int = 0) -> tuple[object, int]:
        cpu = core.Cpu(memory.SparseMemory(), reset=True)
        cpu.registers.sp = 0x8000
        cpu.registers.pc = START
        cpu.registers.iff1 = True
        cpu.registers.im = mode

        taken = offer(cpu)

        return taken, len(cpu.bus)

    def test_the_nonmaskable_line_costs_what_a_restart_costs(self) -> None:
        self.assertEqual(
            self.offered(lambda cpu: cpu.nonmaskable()),
            (None, RESPONSE["nonmaskable"]["tStates"]),
        )

    def test_mode_one_costs_the_two_more_the_manual_adds(self) -> None:
        self.assertEqual(
            self.offered(lambda cpu: cpu.interrupt(0xFF), mode=1),
            (True, RESPONSE["mode1"]["tStates"]),
        )

    def test_mode_two_costs_the_nineteen_the_manual_prints(self) -> None:
        self.assertEqual(
            self.offered(lambda cpu: cpu.interrupt(0xFF), mode=2),
            (True, RESPONSE["mode2"]["tStates"]),
        )

    def test_mode_zero_costs_the_supplied_instruction_plus_two(self) -> None:
        supplied = 0xC7

        _, spent_now = self.offered(lambda cpu: cpu.interrupt(supplied), mode=0)

        self.assertEqual(spent_now - spent((supplied,)), 2)

    def supplied(self, program: tuple[int, ...]) -> int:
        """What a mode zero response to this instruction costs over the instruction."""
        cpu = core.Cpu(memory.SparseMemory(), reset=True)
        cpu.registers.pc, cpu.registers.sp = START, 0x8000
        cpu.registers.iff1, cpu.registers.im = True, 0
        cpu.interrupt(program[0])
        return len(cpu.bus) - spent(program)

    def test_whatever_the_supplied_instruction_is(self) -> None:
        added = {
            "nothing at all": self.supplied((0x00,)),
            "a restart": self.supplied((0xC7,)),
            "a jump": self.supplied((0xC3, 0x00, 0x20)),
            "a push": self.supplied((0xC5,)),
            "an exchange": self.supplied((0x08,)),
        }

        self.assertEqual(set(added.values()), {2})

    def test_a_response_of_more_than_one_byte_reads_the_rest_without_advancing(self) -> None:
        space = memory.SparseMemory()
        space.write8(START, 0x34)
        cpu = core.Cpu(space, reset=True)
        cpu.registers.pc, cpu.registers.sp = START, 0x8000
        cpu.registers.iff1, cpu.registers.im = True, 0

        cpu.interrupt(0xC3)

        self.assertEqual(cpu.registers.pc, 0x3434)

    def test_which_is_written_up_because_a_device_supplies_them_on_the_part(self) -> None:
        named = {entry["id"] for entry in DIVERGENCES["divergences"]}

        self.assertIn("mode-zero-response-of-more-than-one-byte", named)

    def test_and_so_is_the_register_nothing_constrains_afterwards(self) -> None:
        named = {entry["id"] for entry in DIVERGENCES["divergences"]}

        self.assertIn("wz-after-an-interrupt-response", named)

    def test_and_that_addition_is_the_two_wait_states_the_manual_names(self) -> None:
        self.assertEqual(SHAPES["interruptAcknowledge"]["automaticWaitStates"], 2)

    def test_mode_one_lands_where_the_manual_says(self) -> None:
        cpu = core.Cpu(memory.SparseMemory(), reset=True)
        cpu.registers.sp, cpu.registers.iff1, cpu.registers.im = 0x8000, True, 1

        cpu.interrupt(0xFF)

        self.assertEqual(cpu.registers.pc, RESPONSE["mode1"]["restartsAt"])

    def test_the_nonmaskable_line_lands_where_the_manual_says(self) -> None:
        cpu = core.Cpu(memory.SparseMemory(), reset=True)
        cpu.registers.sp = 0x8000

        cpu.nonmaskable()

        self.assertEqual(cpu.registers.pc, RESPONSE["nonmaskable"]["restartsAt"])

    def test_mode_two_uses_every_bit_the_device_supplies(self) -> None:
        space = memory.SparseMemory()
        space.write8(0x00FE, 0x34)
        space.write8(0x00FF, 0x12)
        space.write8(0x0100, 0x56)
        cpu = core.Cpu(space, reset=True)
        cpu.registers.sp, cpu.registers.iff1, cpu.registers.im = 0x8000, True, 2

        cpu.interrupt(0xFF)

        self.assertEqual(cpu.registers.pc, 0x5612)

    def test_which_is_the_one_place_a_measurement_beat_the_manual(self) -> None:
        self.assertEqual(core.VECTOR_MASK, 0xFF)

    def test_a_maskable_interrupt_clears_both_flip_flops(self) -> None:
        cpu = core.Cpu(memory.SparseMemory(), reset=True)
        cpu.registers.sp, cpu.registers.iff1, cpu.registers.iff2 = 0x8000, True, True
        cpu.registers.im = 1

        cpu.interrupt(0xFF)

        self.assertEqual((cpu.registers.iff1, cpu.registers.iff2), (False, False))

    def test_the_nonmaskable_one_clears_only_the_first(self) -> None:
        cpu = core.Cpu(memory.SparseMemory(), reset=True)
        cpu.registers.sp, cpu.registers.iff1, cpu.registers.iff2 = 0x8000, True, True

        cpu.nonmaskable()

        self.assertEqual((cpu.registers.iff1, cpu.registers.iff2), (False, True))

    def test_a_disabled_part_refuses_the_maskable_line(self) -> None:
        cpu = core.Cpu(memory.SparseMemory(), reset=True)
        cpu.registers.sp, cpu.registers.iff1 = 0x8000, False

        self.assertEqual(cpu.interrupt(0xFF), False)

    def test_and_takes_the_nonmaskable_one_anyway(self) -> None:
        cpu = core.Cpu(memory.SparseMemory(), reset=True)
        cpu.registers.sp, cpu.registers.iff1 = 0x8000, False

        cpu.nonmaskable()

        self.assertEqual(cpu.registers.pc, RESPONSE["nonmaskable"]["restartsAt"])

    def test_an_enable_holds_the_line_off_for_one_more_instruction(self) -> None:
        space = memory.SparseMemory()
        space.write8(START, 0xFB)
        cpu = core.Cpu(space, reset=True)
        cpu.registers.sp, cpu.registers.pc, cpu.registers.im = 0x8000, START, 1
        cpu.step()

        self.assertEqual(cpu.interrupt(0xFF), False)

    def test_and_lets_it_through_once_that_instruction_has_run(self) -> None:
        space = memory.SparseMemory()
        space.write8(START, 0xFB)
        cpu = core.Cpu(space, reset=True)
        cpu.registers.sp, cpu.registers.pc, cpu.registers.im = 0x8000, START, 1
        cpu.step()
        cpu.step()

        self.assertEqual(cpu.interrupt(0xFF), True)

    def test_a_repeating_instruction_is_resumed_rather_than_abandoned(self) -> None:
        space = memory.SparseMemory()
        space.write8(START, 0xED)
        space.write8(START + 1, 0xB0)
        cpu = core.Cpu(space, reset=True)
        cpu.registers.pc, cpu.registers.sp = START, 0x8000
        cpu.registers.bc, cpu.registers.hl, cpu.registers.de = 4, 0x3000, 0x4000
        cpu.registers.iff1, cpu.registers.im = True, 1
        cpu.step()

        cpu.interrupt(0xFF)

        self.assertEqual(
            cpu.memory.read8(cpu.registers.sp) | (cpu.memory.read8(0x7FFF) << 8), START
        )

    def test_which_is_the_part_backing_the_counter_up_rather_than_looping(self) -> None:
        space = memory.SparseMemory()
        space.write8(START, 0xED)
        space.write8(START + 1, 0xB0)
        cpu = core.Cpu(space, reset=True)
        cpu.registers.pc = START
        cpu.registers.bc, cpu.registers.hl, cpu.registers.de = 4, 0x3000, 0x4000

        cpu.step()

        self.assertEqual((cpu.registers.pc, cpu.registers.bc), (START, 3))

    def test_reset_leaves_the_part_in_the_mode_the_manual_names(self) -> None:
        cpu = core.Cpu(memory.SparseMemory(), reset=True)

        self.assertEqual((cpu.registers.im, RESPONSE["mode0"]["afterReset"]), (0, True))


class ParityDefectTest(unittest.TestCase):
    """The NMOS defect Zilog documents, and the CMOS part that does not have it."""

    def taken(self, name: str, opcode: int = 0x57) -> tuple[int, int]:
        space = memory.SparseMemory()
        space.write8(START, 0xED)
        space.write8(START + 1, opcode)
        cpu = models.describe(name).build(space, reset=True)
        cpu.registers.pc, cpu.registers.sp = START, 0x8000
        cpu.registers.iff1 = cpu.registers.iff2 = True
        cpu.registers.im = 1
        cpu.step()
        before = cpu.registers.f & flags.PV
        cpu.interrupt(0xFF)
        return before, cpu.registers.f & flags.PV

    def test_the_instruction_reports_the_latch_before_the_interrupt(self) -> None:
        before, _ = self.taken("z80")

        self.assertEqual(before, flags.PV)

    def test_and_the_nmos_part_clears_it_when_the_interrupt_is_taken(self) -> None:
        _, after = self.taken("z80")

        self.assertEqual(after, 0)

    def test_the_other_instruction_that_reads_the_latch_too(self) -> None:
        _, after = self.taken("z80", opcode=0x5F)

        self.assertEqual(after, 0)

    def test_the_cmos_part_does_not_because_zilog_says_it_was_fixed(self) -> None:
        _, after = self.taken("z84c00")

        self.assertEqual(after, flags.PV)

    def test_the_record_names_the_parts_it_affects_and_the_one_it_does_not(self) -> None:
        defect = RESPONSE["nmosParityDefect"]

        self.assertEqual((defect["affects"], defect["fixedIn"]), (["z80"], ["z84c00"]))

    def test_and_quotes_zilog_saying_the_later_part_fixed_it(self) -> None:
        self.assertIn("we've fixed this problem", RESPONSE["nmosParityDefect"]["quote"])

    def test_an_interrupt_after_any_other_instruction_leaves_the_flag_alone(self) -> None:
        space = memory.SparseMemory()
        space.write8(START, 0x00)
        cpu = models.describe("z80").build(space, reset=True)
        cpu.registers.pc, cpu.registers.sp = START, 0x8000
        cpu.registers.iff1, cpu.registers.im = True, 1
        cpu.registers.f = flags.PV
        cpu.step()

        cpu.interrupt(0xFF)

        self.assertEqual(cpu.registers.f & flags.PV, flags.PV)


class HaltTest(unittest.TestCase):
    """A halted part keeps fetching, which is the whole reason it is not idle."""

    def halted(self) -> core.Cpu:
        space = memory.SparseMemory()
        space.write8(START, 0x76)
        cpu = core.Cpu(space, reset=True)
        cpu.registers.pc = START
        cpu.step()
        return cpu

    def test_a_halted_step_costs_a_whole_fetch(self) -> None:
        cpu = self.halted()

        cpu.step()

        self.assertEqual(len(cpu.bus), FACTS["halt"]["tStatesPerCycle"])

    def test_and_that_is_the_length_of_an_ordinary_one(self) -> None:
        self.assertEqual(FACTS["halt"]["tStatesPerCycle"], bus.FETCH_STATES)

    def test_it_draws_the_pins_of_a_fetch_because_that_is_what_it_is(self) -> None:
        cpu = self.halted()
        cpu.bus.recording = True

        cpu.step()

        self.assertEqual([entry[2] for entry in cpu.bus.log], EDGES["opcodeFetch"]["columns"])

    def test_the_counter_does_not_advance(self) -> None:
        cpu = self.halted()
        before = cpu.registers.pc

        cpu.step()

        self.assertEqual(cpu.registers.pc, before)

    def test_the_refresh_counter_does(self) -> None:
        cpu = self.halted()
        before = cpu.registers.r

        cpu.step()

        self.assertNotEqual(cpu.registers.r, before)

    def test_an_accepted_interrupt_leaves_the_halt_state(self) -> None:
        cpu = self.halted()
        cpu.registers.sp, cpu.registers.iff1, cpu.registers.im = 0x8000, True, 1

        cpu.interrupt(0xFF)

        self.assertEqual(cpu.halted, False)

    def test_and_so_does_the_nonmaskable_line(self) -> None:
        cpu = self.halted()
        cpu.registers.sp = 0x8000

        cpu.nonmaskable()

        self.assertEqual(cpu.halted, False)


class ConditionalTimingTest(unittest.TestCase):
    """The instructions the manual prints two timings for, checked both ways."""

    def test_a_relative_jump_taken_costs_more_than_one_not_taken(self) -> None:
        taken = spent((0x20, 0x02), {"f": 0x00})
        passed = spent((0x20, 0x02), {"f": flags.Z})

        self.assertEqual(taken - passed, 5)

    def test_a_conditional_call_taken_costs_more_than_one_not_taken(self) -> None:
        taken = spent((0xC4, 0x00, 0x20), {"f": 0x00})
        passed = spent((0xC4, 0x00, 0x20), {"f": flags.Z})

        self.assertEqual(taken - passed, 7)

    def test_a_conditional_return_taken_costs_more_than_one_not_taken(self) -> None:
        taken = spent((0xC0,), {"f": 0x00})
        passed = spent((0xC0,), {"f": flags.Z})

        self.assertEqual(taken - passed, 6)

    def test_a_decrementing_branch_taken_costs_more_than_one_not_taken(self) -> None:
        taken = spent((0x10, 0x02), {"b": 5})
        passed = spent((0x10, 0x02), {"b": 1})

        self.assertEqual(taken - passed, 5)

    def test_a_repeating_block_move_costs_more_while_it_repeats(self) -> None:
        repeating = spent((0xED, 0xB0), {"bc": 4})
        last = spent((0xED, 0xB0), {"bc": 1})

        self.assertEqual(repeating - last, 5)


class ResetTest(unittest.TestCase):
    def test_reset_clears_what_the_manual_says_it_clears(self) -> None:
        cpu = core.Cpu(memory.SparseMemory(), reset=True)

        cleared = {name: getattr(cpu.registers, name) for name in FACTS["reset"]["clears"]}

        self.assertEqual(cleared, dict.fromkeys(FACTS["reset"]["clears"], 0))

    def test_and_leaves_the_interrupt_mode_where_the_manual_says(self) -> None:
        cpu = core.Cpu(memory.SparseMemory(), reset=True)

        self.assertEqual(cpu.registers.im, FACTS["reset"]["interruptMode"])

    def test_and_clears_the_interrupt_enable(self) -> None:
        cpu = core.Cpu(memory.SparseMemory(), reset=True)

        self.assertEqual((cpu.registers.iff1, cpu.registers.iff2), (False, False))

    def test_it_does_not_clear_a_register_the_manual_does_not_name(self) -> None:
        cpu = core.Cpu(memory.SparseMemory(seed=7), seed=7, reset=True)

        held = (cpu.registers.a, cpu.registers.bc, cpu.registers.de, cpu.registers.hl)

        self.assertNotEqual(held, (0, 0, 0, 0))


class FlagRegisterTest(unittest.TestCase):
    def test_every_flag_sits_in_the_bit_the_manual_gives_it(self) -> None:
        printed = FACTS["flagRegister"]["bits"]

        held = {
            "c": flags.C,
            "n": flags.N,
            "pv": flags.PV,
            "x": flags.X,
            "h": flags.H,
            "y": flags.Y,
            "z": flags.Z,
            "s": flags.S,
        }

        self.assertEqual(held, {name: 1 << bit for name, bit in printed.items()})

    def test_the_two_the_manual_calls_unused_are_the_two_this_package_calls_undocumented(
        self,
    ) -> None:
        printed = FACTS["flagRegister"]["bits"]

        unused = (1 << printed["x"]) | (1 << printed["y"])

        self.assertEqual(flags.UNDOCUMENTED, unused)


class SuiteRecordTest(unittest.TestCase):
    """The corpus pin, and the generator that lets it be rebuilt rather than trusted."""

    @override
    def setUp(self) -> None:
        self.suite = SUITES["suites"][0]
        self.generator = self.suite["generator"]

    def test_the_corpus_is_pinned_by_commit(self) -> None:
        self.assertEqual(len(self.suite["commit"]), 40)

    def test_and_so_is_the_generator_that_produced_it(self) -> None:
        self.assertEqual(len(self.generator["commit"]), 40)

    def test_the_generator_names_every_file_it_has_to_be_given(self) -> None:
        self.assertEqual(len(self.generator["requires"]), 3)

    def test_the_flag_that_would_widen_the_strobes_is_recorded_as_off(self) -> None:
        self.assertEqual(self.generator["flags"]["Z80_DO_FULL_MEMCYCLES"], False)

    def test_which_is_why_the_recorded_shape_strobes_one_state(self) -> None:
        line = bus.Bus(recording=True, shape=bus.RECORDING)

        line.read(0x2000, 0x42)

        self.assertEqual([entry[2] for entry in line.log].count(bus.MEMORY_READ), 1)

    def test_the_flag_that_puts_refresh_on_the_address_pins_is_recorded_as_on(self) -> None:
        self.assertEqual(self.generator["flags"]["Z80_DO_MEM_REFRESHES"], True)

    def test_which_is_why_both_shapes_carry_a_refresh_address(self) -> None:
        shapes = [bus.Bus(recording=True, shape=name) for name in bus.SHAPES]
        for line in shapes:
            line.fetch(0x1234, 0x5678, 0xAB)

        found = {line.log[2][0] for line in shapes}

        self.assertEqual(found, {0x5678})

    def test_the_entries_the_generator_emits_and_the_corpus_omits_are_named(self) -> None:
        self.assertEqual(len(self.generator["excludedFromPublication"]), 2)

    def test_the_second_oracle_is_recorded_with_the_flags_that_build_it(self) -> None:
        run = self.generator["fullMemoryCycleRun"]

        self.assertEqual(run["flags"]["Z80_DO_FULL_MEMCYCLES"], True)

    def test_and_with_what_it_reported_rather_than_only_that_it_was_run(self) -> None:
        measured = self.generator["fullMemoryCycleRun"]["measured"]
        every_case = len(measured["opcodesAffected"]) * self.suite["tests_per_opcode"]

        self.assertEqual(measured["failed"], every_case)

    def test_every_opcode_it_reported_is_one_the_generator_already_moved_on(self) -> None:
        moved = [
            entry
            for entry in DIVERGENCES["divergences"]
            if entry["id"] == "generator-head-disagrees-with-the-pinned-corpus"
        ]
        listed = " ".join(moved[0]["referenceDoes"]["detail"])
        affected = self.generator["fullMemoryCycleRun"]["measured"]["opcodesAffected"]

        missing = [name for name in affected if name not in listed]

        self.assertEqual(missing, [])

    def test_the_states_it_skips_are_named_and_counted(self) -> None:
        allowance = self.generator["fullMemoryCycleRun"]["allowance"]

        self.assertEqual(set(allowance), {"what", "why", "counted"})

    def test_the_command_that_rebuilds_the_corpus_exists(self) -> None:
        named = self.generator["howToRun"].split()[1]

        self.assertTrue((Path(__file__).resolve().parent.parent / named).is_file())

    def test_and_so_does_the_one_that_compares_against_it(self) -> None:
        named = self.generator["fullMemoryCycleRun"]["howToCompare"].split()[1]

        self.assertTrue((Path(__file__).resolve().parent.parent / named).is_file())


class DivergenceTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.entries = DIVERGENCES["divergences"]

    def test_no_two_entries_share_an_id(self) -> None:
        names = [entry["id"] for entry in self.entries]

        self.assertEqual(len(names), len(set(names)))

    def test_every_entry_says_which_side_the_package_follows(self) -> None:
        missing = [entry["id"] for entry in self.entries if not entry.get("packageFollows")]

        self.assertEqual(missing, [])

    def test_every_open_entry_says_what_would_settle_it(self) -> None:
        missing = [
            entry["id"]
            for entry in self.entries
            if entry["status"] == "open" and not entry.get("wouldSettleIt")
        ]

        self.assertEqual(missing, [])

    def test_every_closed_entry_says_what_would_reopen_it(self) -> None:
        missing = [
            entry["id"]
            for entry in self.entries
            if entry["status"] == "closed" and not entry.get("wouldReopenIt")
        ]

        self.assertEqual(missing, [])

    def test_the_two_places_the_recording_departs_from_the_manual_are_both_written_up(
        self,
    ) -> None:
        named = {entry["id"] for entry in self.entries}

        self.assertLessEqual(
            {"recording-single-state-strobe", "recording-refresh-on-address-pins"}, named
        )

    def test_each_of_those_quotes_the_generator_admitting_it(self) -> None:
        admitted = [
            entry["id"]
            for entry in self.entries
            if entry["id"].startswith("recording-")
            and "generatorSaysSoItself" in entry["referenceDoes"]
        ]

        self.assertEqual(len(admitted), 2)

    def test_every_entry_carries_a_severity_the_record_uses_elsewhere(self) -> None:
        found = {entry["severity"] for entry in self.entries}

        self.assertLessEqual(
            found,
            {
                "documentContradiction",
                "contradiction",
                "convention",
                "unstated",
                "unmodelled",
                "unchecked",
                "outOfScope",
            },
        )

    def test_every_timing_chapter_cycle_is_modelled_or_written_up(self) -> None:
        named = {entry["id"] for entry in self.entries}

        self.assertLessEqual(
            {
                "wait-states-not-modelled",
                "bus-request-not-modelled",
                "power-down-not-modelled",
            },
            named,
        )

    def test_and_each_of_those_says_what_would_bring_it_into_scope(self) -> None:
        missing = [
            entry["id"]
            for entry in self.entries
            if entry["severity"] == "outOfScope" and not entry.get("wouldReopenIt")
        ]

        self.assertEqual(missing, [])

    def test_the_places_the_manual_is_silent_are_each_written_up(self) -> None:
        named = {entry["id"] for entry in self.entries}

        self.assertLessEqual(
            {
                "undocumented-flag-bits",
                "internal-register-wz",
                "undocumented-opcodes",
                "internal-cycle-placement",
                "acknowledge-internal-state-placement",
                "halt-fetch-address-unstated",
            },
            named,
        )

    def test_the_generator_moving_away_from_the_pinned_corpus_is_written_up(self) -> None:
        found = [
            entry
            for entry in self.entries
            if entry["id"] == "generator-head-disagrees-with-the-pinned-corpus"
        ]

        self.assertEqual(len(found[0]["referenceDoes"]["detail"]), 4)

    def test_and_that_entry_names_what_would_reopen_it_because_a_bump_would(self) -> None:
        found = [
            entry
            for entry in self.entries
            if entry["id"] == "generator-head-disagrees-with-the-pinned-corpus"
        ]

        self.assertTrue(found[0]["wouldReopenIt"])


if __name__ == "__main__":
    unittest.main()
