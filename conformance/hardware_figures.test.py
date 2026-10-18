import sys
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.bench import FACTS, acknowledged, pins_of, ran

SHAPES = FACTS["machineCycleShapes"]

EDGES = SHAPES["figureEdges"]

PIN_LETTERS = {"RD": "r", "WR": "w", "MREQ": "m", "IORQ": "i"}

CYCLES_WITH_FIGURES = (
    "opcodeFetch",
    "memoryRead",
    "memoryWrite",
    "inputOrOutput",
    "interruptAcknowledge",
)

MEMORY_FIGURES = ("opcodeFetch", "memoryRead", "memoryWrite", "interruptAcknowledge")

PORT_DIRECTIONS = {"read": "WR", "write": "RD"}

Holds = Callable[[int, float, float], bool]


def at_the_end_of_the_state(state: int, start: float, end: float) -> bool:
    return start < state + 1 <= end


def at_any_point_in_the_state(state: int, start: float, end: float) -> bool:
    return start < state + 1 and end > state


def columns_from(name: str, holds: Holds, states: int, leaving: str = "") -> list[str]:
    windows = EDGES[name]["pins"]
    return [
        "".join(
            letter
            if label != leaving
            and any(
                holds(state, one["activeFrom"], one["activeUntil"])
                for one in windows.get(label, [])
            )
            else "-"
            for label, letter in PIN_LETTERS.items()
        )
        for state in range(states)
    ]


def derived(holds: Holds) -> dict[str, Any]:
    found: dict[str, Any] = {
        name: columns_from(name, holds, len(EDGES[name]["columns"])) for name in MEMORY_FIGURES
    }
    port = EDGES["inputOrOutput"]["columns"]
    found["inputOrOutput"] = {
        direction: columns_from("inputOrOutput", holds, len(port[direction]), leaving)
        for direction, leaving in PORT_DIRECTIONS.items()
    }
    return found


def drawn() -> dict[str, Any]:
    acknowledge = pins_of(acknowledged(), "acknowledge")
    return {
        "opcodeFetch": pins_of(ran((0x00,)), "fetch"),
        "memoryRead": pins_of(ran((0x06, 0x42)), "read"),
        "memoryWrite": pins_of(ran((0x70,), {"hl": 0x2000}), "write"),
        "inputOrOutput": {
            "read": pins_of(ran((0xDB, 0x34)), "portRead"),
            "write": pins_of(ran((0xD3, 0x34)), "portWrite"),
        },
        "interruptAcknowledge": acknowledge[: SHAPES["interruptAcknowledge"]["drawnStates"]],
    }


def asserted(columns: list[str]) -> int:
    return sum(len(column) - column.count("-") for column in columns)


class FigureEdgeTest(unittest.TestCase):
    def test_a_fetch_draws_the_columns_figure_5_gives_it(self) -> None:
        # Arrange
        cpu = ran((0x00,))

        # Act
        pins = pins_of(cpu, "fetch")

        # Assert
        self.assertEqual(pins, EDGES["opcodeFetch"]["columns"])

    def test_a_read_draws_the_columns_figure_6_gives_it(self) -> None:
        # Arrange
        cpu = ran((0x06, 0x42))

        # Act
        pins = pins_of(cpu, "read")

        # Assert
        self.assertEqual(pins, EDGES["memoryRead"]["columns"])

    def test_a_write_draws_the_columns_figure_6_gives_it(self) -> None:
        # Arrange
        cpu = ran((0x70,), {"hl": 0x2000})

        # Act
        pins = pins_of(cpu, "write")

        # Assert
        self.assertEqual(pins, EDGES["memoryWrite"]["columns"])

    def test_a_port_read_draws_the_columns_figure_7_gives_it(self) -> None:
        # Arrange
        cpu = ran((0xDB, 0x34))

        # Act
        pins = pins_of(cpu, "portRead")

        # Assert
        self.assertEqual(pins, EDGES["inputOrOutput"]["columns"]["read"])

    def test_a_port_write_draws_the_columns_figure_7_gives_it(self) -> None:
        # Arrange
        cpu = ran((0xD3, 0x34))

        # Act
        pins = pins_of(cpu, "portWrite")

        # Assert
        self.assertEqual(pins, EDGES["inputOrOutput"]["columns"]["write"])

    def test_an_acknowledge_draws_the_columns_figure_9_gives_it(self) -> None:
        # Arrange
        figure = EDGES["interruptAcknowledge"]["columns"]

        # Act
        pins = pins_of(acknowledged(), "acknowledge")

        # Assert
        self.assertEqual(pins[: len(figure)], figure)

    def test_every_set_of_columns_is_as_long_as_the_cycle_the_part_runs(self) -> None:
        # Arrange
        runs = drawn()

        # Act
        found = {name: len(EDGES[name]["columns"]) for name in MEMORY_FIGURES}

        # Assert
        self.assertEqual(found, {name: len(runs[name]) for name in MEMORY_FIGURES})

    def test_and_a_port_cycle_is_as_long_either_way_round(self) -> None:
        # Arrange
        runs = drawn()["inputOrOutput"]

        # Act
        both = EDGES["inputOrOutput"]["columns"]

        # Assert
        self.assertEqual(
            (len(both["read"]), len(both["write"])), (len(runs["read"]), len(runs["write"]))
        )

    def test_the_acknowledge_asserts_no_read_because_the_figure_draws_none(self) -> None:
        # Arrange
        figure = EDGES["interruptAcknowledge"]

        # Act
        pins = figure["pins"]

        # Assert
        self.assertNotIn("RD", pins)

    def test_the_clock_rises_at_the_boundary_and_falls_mid_state(self) -> None:
        # Arrange
        clock = EDGES["clock"]

        # Act
        edges = (clock["rises"], float(clock["falls"]))

        # Assert
        self.assertEqual(edges, ("+0.00", 0.56))

    def test_the_part_draws_what_the_recorded_edges_give_under_the_chosen_rule(self) -> None:
        # Arrange
        runs = drawn()

        # Act
        found = derived(at_the_end_of_the_state)

        # Assert
        self.assertEqual(found, runs)

    def test_every_edge_in_the_record_falls_on_the_clock(self) -> None:
        # Arrange
        windows = [
            window
            for name in CYCLES_WITH_FIGURES
            for held in EDGES[name]["pins"].values()
            for window in held
        ]

        # Act
        offsets = {
            value % 0.5
            for window in windows
            for value in (window["activeFrom"], window["activeUntil"])
        }

        # Assert
        self.assertEqual(offsets, {0.0})

    def test_the_rule_that_turns_an_edge_into_a_column_is_written_down(self) -> None:
        # Arrange
        rule = EDGES["rule"]

        # Act
        name = rule["name"]

        # Assert
        self.assertEqual(name, "read at the clock edge that ends each T state")

    def test_the_reading_that_was_not_chosen_is_recorded_as_it_computes(self) -> None:
        # Arrange
        gives = EDGES["rule"]["alternative"]["gives"]

        # Act
        found = derived(at_any_point_in_the_state)

        # Assert
        self.assertEqual(gives, found)

    def test_and_it_differs_from_the_reading_that_was(self) -> None:
        # Arrange
        gives = EDGES["rule"]["alternative"]["gives"]

        # Act
        same = [name for name in gives if gives[name] == EDGES[name]["columns"]]

        # Assert
        self.assertEqual(same, [])

    def test_it_holds_every_strobe_longer_and_never_shorter(self) -> None:
        # Arrange
        gives = EDGES["rule"]["alternative"]["gives"]

        # Act
        longer = {
            name: asserted(gives[name]) - asserted(EDGES[name]["columns"])
            for name in MEMORY_FIGURES
        }

        # Assert
        self.assertEqual([name for name, more in longer.items() if more <= 0], [])

    def test_every_measured_edge_is_recorded_as_read_from_a_figure(self) -> None:
        # Arrange
        edges = EDGES

        # Act
        provenance = edges["provenance"]

        # Assert
        self.assertEqual(provenance, "read from the figure rather than from the prose")

    def test_each_cycle_names_the_figure_it_was_read_from(self) -> None:
        # Arrange
        names = CYCLES_WITH_FIGURES

        # Act
        named = {name: EDGES[name]["figure"] for name in names}

        # Assert
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


if __name__ == "__main__":
    unittest.main()
