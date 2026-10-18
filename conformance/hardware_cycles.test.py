import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.bench import (
    FACTS,
    FLAG,
    RECORD,
    ROWS,
    START,
    acknowledged,
    cycle_lengths,
    cycle_names,
    loaded,
    pins_of,
    ran,
)

HELD = RECORD

SHAPES = FACTS["machineCycleShapes"]

EDGES = SHAPES["figureEdges"]

NOP = (0x00,)

LOAD_IMMEDIATE = (0x06, 0x00)

STORE_THROUGH_HL = (0x70,)

INPUT_IMMEDIATE = (0xDB, 0x34)

MISPRINTED_RUNS: dict[int, tuple[tuple[int, ...], dict[str, int]]] = {
    99: ((0x01, 0x00, 0x20), {}),
    260: ((0xCB, 0x80), {}),
    269: ((0x30, 0x02), {"f": FLAG["c"]}),
}


def bounded_first_cycles() -> set[int]:
    longest = SHAPES["opcodeFetch"]["tStates"] + SHAPES["memoryReadOrWrite"]["tStates"]
    found = (cycle_lengths(ran((opcode, 0, 0, 0))) for opcode in range(256))
    return {lengths[0] for lengths in found if len(lengths) > 1 or lengths[0] < longest}


def misprinted_row(page: int) -> dict[str, Any]:
    found: dict[str, Any] = {
        entry["manualPage"]: entry for entry in ROWS if entry.get("printedMCyclesIsAMisprint")
    }[page]
    return found


def released(cycle: str, pin: str) -> float:
    found: float = min(window["activeUntil"] for window in EDGES[cycle]["pins"][pin])
    return found


class MachineCycleShapeTest(unittest.TestCase):
    def test_a_fetch_is_as_long_as_the_manual_says(self) -> None:
        # Arrange
        cpu = ran(NOP)

        # Act
        lengths = cycle_lengths(cpu)

        # Assert
        self.assertEqual(lengths, [SHAPES["opcodeFetch"]["tStates"]])

    def test_a_memory_access_is_as_long_as_the_manual_says(self) -> None:
        # Arrange
        cpu = ran(LOAD_IMMEDIATE)

        # Act
        lengths = cycle_lengths(cpu)

        # Assert
        self.assertEqual(lengths[1], SHAPES["memoryReadOrWrite"]["tStates"])

    def test_a_port_access_is_as_long_as_the_manual_says(self) -> None:
        # Arrange
        cpu = ran(INPUT_IMMEDIATE)

        # Act
        lengths = cycle_lengths(cpu)

        # Assert
        self.assertEqual(lengths[2], SHAPES["inputOrOutput"]["tStates"])

    def test_the_port_access_carries_the_wait_the_manual_says_is_inserted(self) -> None:
        # Arrange
        inserted = SHAPES["inputOrOutput"]["automaticWaitStates"]

        # Act
        lengths = cycle_lengths(ran(INPUT_IMMEDIATE))

        # Assert
        self.assertEqual(lengths[2] - lengths[1], inserted)

    def test_the_bus_draws_the_states_the_acknowledge_figure_draws(self) -> None:
        # Arrange
        shape = SHAPES["interruptAcknowledge"]

        # Act
        pins = pins_of(acknowledged(), "acknowledge")

        # Assert
        self.assertEqual(
            (len(pins), pins[shape["drawnStates"] :]),
            (shape["tStates"], ["----"] * (shape["tStates"] - shape["drawnStates"])),
        )

    def test_and_the_cycle_costs_one_more_than_that(self) -> None:
        # Arrange
        shape = SHAPES["interruptAcknowledge"]

        # Act
        undrawn = shape["tStates"] - shape["drawnStates"]

        # Assert
        self.assertEqual(undrawn, 1)

    def test_which_the_response_spends_beyond_its_two_stack_writes(self) -> None:
        # Arrange
        shape = SHAPES["interruptAcknowledge"]
        undrawn = shape["tStates"] - shape["drawnStates"]

        # Act
        cpu = acknowledged()

        # Assert
        beyond = cpu.bus.states - shape["drawnStates"] - 2 * SHAPES["memoryReadOrWrite"]["tStates"]
        self.assertEqual(beyond, undrawn)

    def test_the_drawn_states_are_a_fetch_and_the_two_added_waits(self) -> None:
        # Arrange
        added = SHAPES["interruptAcknowledge"]["automaticWaitStates"]

        # Act
        refreshed = (
            pins_of(acknowledged(), "acknowledge").index("--m-"),
            pins_of(ran(NOP), "fetch").index("--m-"),
        )

        # Assert
        self.assertEqual(refreshed[0] - refreshed[1], added)

    def test_and_the_cost_is_the_five_state_kind_of_fetch_plus_them(self) -> None:
        # Arrange
        shape = SHAPES["interruptAcknowledge"]

        # Act
        cost = shape["baseM1States"] + shape["automaticWaitStates"]

        # Assert
        self.assertEqual(cost, shape["tStates"])


class PrintedFactTest(unittest.TestCase):
    def test_a_fetch_carries_the_counter_then_the_refresh_address(self) -> None:
        # Arrange
        shape = SHAPES["opcodeFetch"]
        cpu = loaded(NOP, {"i": 0x12, "r": 0x34})
        named = {"programCounter": START, "refresh": 0x1234}

        # Act
        cpu.step()

        # Assert
        self.assertEqual(
            [(address, "r" in pins) for address, _, pins in cpu.bus.log],
            [(named[shape["addressInT1T2"]], True)] * 2
            + [(named[shape["addressInT3T4"]], False)] * 2,
        )

    def test_a_fetch_takes_its_data_in_the_state_the_manual_samples_it(self) -> None:
        # Arrange
        state = SHAPES["opcodeFetch"]["dataSampledInState"]
        cpu = loaded(NOP)

        # Act
        cpu.step()

        # Assert
        carried = [index + 1 for index, entry in enumerate(cpu.bus.log) if entry[1] is not None]
        self.assertEqual((carried, "r" in cpu.bus.log[state - 1][2]), ([state], False))

    def test_every_first_machine_cycle_the_bus_bounds_is_a_printed_length(self) -> None:
        # Arrange
        printed = set(SHAPES["opcodeFetch"]["firstMachineCycleStates"])

        # Act
        found = bounded_first_cycles()

        # Assert
        self.assertEqual(found, printed)

    def test_a_memory_read_and_write_each_take_the_printed_states(self) -> None:
        # Arrange
        printed = SHAPES["memoryReadOrWrite"]["tStates"]

        # Act
        found = {
            "read": cycle_lengths(ran(LOAD_IMMEDIATE))[1],
            "write": cycle_lengths(ran(STORE_THROUGH_HL, {"hl": 0x2000}))[1],
        }

        # Assert
        self.assertEqual(found, {"read": printed, "write": printed})

    def test_a_port_cycle_is_a_memory_cycle_plus_the_inserted_wait(self) -> None:
        # Arrange
        shape = SHAPES["inputOrOutput"]

        # Act
        lengths = cycle_lengths(ran(INPUT_IMMEDIATE))

        # Assert
        self.assertEqual(
            (lengths[2], lengths[2] - lengths[1]),
            (shape["tStates"], shape["automaticWaitStates"]),
        )

    def test_mreq_marks_the_addresses_memory_is_read_or_written_at(self) -> None:
        # Arrange
        cpu = loaded((0x77,), {"hl": 0x3000, "a": 0x5A})

        # Act
        cpu.step()

        # Assert
        strobed = [
            address
            for address, _, pins in cpu.bus.log
            if "m" in pins and ("r" in pins or "w" in pins)
        ]
        self.assertEqual(strobed, [START, START, 0x3000], FACTS["pins"]["mreq"]["quote"])

    def test_iorq_puts_the_port_on_the_lower_half_of_the_address_bus(self) -> None:
        # Arrange
        cpu = loaded((0xD3, 0x34), {"a": 0x12})

        # Act
        cpu.step()

        # Assert
        requested = [address for address, _, pins in cpu.bus.log if "i" in pins]
        self.assertEqual(requested, [0x1234, 0x1234], FACTS["pins"]["iorq"]["quote"])

    def test_rd_is_asserted_only_in_cycles_that_read(self) -> None:
        # Arrange
        cpu = loaded((0xED, 0xA2), {"hl": 0x3000, "bc": 0x0110})

        # Act
        cpu.step()

        # Assert
        reading = {
            name
            for name, (_, _, pins) in zip(cycle_names(cpu), cpu.bus.log, strict=True)
            if "r" in pins
        }
        self.assertEqual(reading, {"fetch", "portRead"}, FACTS["pins"]["rd"]["quote"])

    def test_wr_is_asserted_only_while_the_data_bus_holds_the_stored_value(self) -> None:
        # Arrange
        cpu = loaded((0xED, 0xA3), {"hl": 0x3000, "bc": 0x0110})
        cpu.memory.write8(0x3000, 0x5A)

        # Act
        cpu.step()

        # Assert
        written = [value for _, value, pins in cpu.bus.log if "w" in pins]
        self.assertEqual(written, [0x5A, 0x5A], FACTS["pins"]["wr"]["quote"])

    def test_a_fetch_then_a_read_is_the_shape_the_notation_example_draws(self) -> None:
        # Arrange
        example = FACTS["instructionTiming"]["notationExample"]

        # Act
        cpu = ran(LOAD_IMMEDIATE)

        # Assert
        self.assertEqual(
            (cycle_lengths(cpu), cpu.bus.states), (example["machineCycles"], example["tStates"])
        )

    def test_every_misprinted_machine_cycle_count_is_run_as_the_reading(self) -> None:
        # Arrange
        pages = [
            entry["manualPage"]
            for entry in HELD["documentContradictions"]
            if entry["kind"] == "timingTableMisprint"
        ]

        # Act
        found = {page: cycle_lengths(ran(*MISPRINTED_RUNS[page])) for page in pages}

        # Assert
        self.assertEqual(found, {page: misprinted_row(page)["machineCycles"] for page in pages})

    def test_a_plain_read_holds_its_strobes_half_a_state_past_a_fetch(self) -> None:
        # Arrange
        entry = {one["id"]: one for one in HELD["documentContradictions"]}[
            "read-strobe-release-prose-versus-figure"
        ]
        strobes = ("RD", "MREQ")

        # Act
        later = {pin: released("memoryRead", pin) - released("opcodeFetch", pin) for pin in strobes}

        # Assert
        self.assertEqual(later, dict.fromkeys(strobes, entry["corroboration"]["additionalStates"]))


if __name__ == "__main__":
    unittest.main()
