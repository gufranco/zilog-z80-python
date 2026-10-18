import sys
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.bench import FACTS, START, cycle_lengths, loaded, ran, spent

SHAPES = FACTS["machineCycleShapes"]

RESPONSE = FACTS["interruptResponse"]

FETCH_STATES = SHAPES["opcodeFetch"]["tStates"]

OFFERS: dict[str, tuple[dict[str, Any], Callable[[Any], object]]] = {
    "nonmaskable": ({}, lambda cpu: cpu.nmi()),
    "mode1": ({"iff1": True, "im": 1}, lambda cpu: cpu.irq(0xFF)),
    "mode2": ({"iff1": True, "im": 2}, lambda cpu: cpu.irq(0xFF)),
}


def response_cycles(name: str) -> list[int]:
    setup, offer = OFFERS[name]
    cpu = loaded((0x00,), setup)
    offer(cpu)
    return cycle_lengths(cpu)


def raised_in(cpu: Any, line: str, states: frozenset[int]) -> None:
    seen = [0]

    def hook() -> None:
        seen[0] += 1
        setattr(cpu, line, seen[0] + 1 in states)

    setattr(cpu, line, 1 in states)
    cpu.on_cycle = hook


def counter_after_a_step(cpu: Any) -> int:
    cpu.step()
    counter: int = cpu.registers.pc
    return counter


def offered_after_a_step(cpu: Any) -> bool:
    cpu.step()
    taken: bool = cpu.irq(0xFF)
    return taken


class PrintedFactTest(unittest.TestCase):
    def test_an_accepted_interrupt_opens_with_the_cycle_figure_9_draws(self) -> None:
        # Arrange
        drawn = SHAPES["interruptAcknowledge"]["columns"]
        cpu = loaded((0x00,), {"iff1": True, "im": 1})

        # Act
        cpu.irq(0xFF)

        # Assert
        self.assertEqual([pins for _, _, pins in cpu.bus.log[: len(drawn)]], drawn)

    def test_a_nonmaskable_response_ignores_the_byte_it_fetches_and_restarts(self) -> None:
        # Arrange
        shape = SHAPES["nonmaskableInterrupt"]
        cpu = loaded((0x3C,), {"a": 0x10})

        # Act
        cpu.nmi()

        # Assert
        stacked = cpu.memory.read8(cpu.registers.sp) | (cpu.memory.read8(cpu.registers.sp + 1) << 8)
        self.assertEqual(
            (cpu.registers.pc, cpu.registers.a, stacked, cpu.bus.cycles[0][1]),
            (shape["restartsAt"], 0x10, START, "fetch"),
        )

    def test_the_mode_instructions_select_the_printed_number_of_modes(self) -> None:
        # Arrange
        programs = ((0xED, 0x46), (0xED, 0x56), (0xED, 0x5E))

        # Act
        modes = {ran(program).registers.im for program in programs}

        # Assert
        self.assertEqual(modes, set(range(FACTS["interruptModes"]["count"])))

    def test_a_nonmaskable_request_waits_for_the_instruction_and_ignores_the_enable(self) -> None:
        # Arrange
        cpu = loaded((0x3C,), {"a": 0x10, "iff1": False})
        cpu.nmi_line = True

        # Act
        cpu.step()

        # Assert
        self.assertEqual(
            (cpu.registers.a, cpu.registers.pc), (0x11, FACTS["interruptModes"]["nmiVector"])
        )

    def test_an_accepted_maskable_interrupt_resets_both_flip_flops(self) -> None:
        # Arrange
        cleared = FACTS["interruptResponse"]["maskableClears"]
        cpu = loaded((0x00,), {"iff1": True, "iff2": True, "im": 1})

        # Act
        cpu.irq(0xFF)

        # Assert
        self.assertEqual(
            {name: getattr(cpu.registers, name) for name in cleared},
            dict.fromkeys(cleared, False),
        )

    def test_an_enable_holds_a_request_off_for_the_printed_number_of_instructions(self) -> None:
        # Arrange
        held = FACTS["interruptResponse"]["instructionsHeldOffAfterEnable"]
        cpu = loaded((0xFB, *([0x00] * held)), {"im": 1})

        # Act
        answers = [offered_after_a_step(cpu) for _ in range(held + 1)]

        # Assert
        self.assertEqual(answers, [False] * held + [True])

    def test_a_request_present_in_the_final_state_is_taken(self) -> None:
        # Arrange
        cpu = loaded((0x00,), {"iff1": True, "im": 1})
        raised_in(cpu, "irq_line", frozenset({FETCH_STATES}))

        # Act
        cpu.step()

        # Assert
        self.assertEqual(
            cpu.registers.pc,
            RESPONSE["mode1"]["restartsAt"],
            FACTS["interruptResponse"]["sampledQuote"],
        )

    def test_a_request_gone_by_the_final_state_is_not(self) -> None:
        # Arrange
        cpu = loaded((0x00,), {"iff1": True, "im": 1})
        raised_in(cpu, "irq_line", frozenset(range(1, FETCH_STATES)))

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.registers.pc, START + 1, FACTS["interruptResponse"]["sampledQuote"])

    def test_a_nonmaskable_interrupt_keeps_the_previous_enable_in_iff2(self) -> None:
        # Arrange
        response = RESPONSE["nonmaskable"]
        cpu = loaded((0x00,), {"iff1": True, "iff2": True})

        # Act
        cpu.nmi()

        # Assert
        self.assertEqual((cpu.registers.iff1, cpu.registers.iff2), (response["iff1"], True))

    def test_every_response_spends_the_machine_cycles_the_manual_breaks_it_into(self) -> None:
        # Arrange
        names = ("nonmaskable", "mode1", "mode2")

        # Act
        found = {name: response_cycles(name) for name in names}

        # Assert
        self.assertEqual(found, {name: RESPONSE[name]["machineCycles"] for name in names})

    def test_mode_zero_runs_what_the_device_supplies_at_two_more_than_its_cost(self) -> None:
        # Arrange
        cpu = loaded((0x00,), {"iff1": True, "im": 0, "a": 0x10})
        alone = spent((0x3C,))

        # Act
        cpu.irq(0x3C)

        # Assert
        self.assertEqual(
            (cpu.registers.a, len(cpu.bus) - alone), (0x11, RESPONSE["mode0"]["addedStates"])
        )

    def test_mode_two_jumps_through_the_table_the_i_register_points_into(self) -> None:
        # Arrange
        cpu = loaded((0x00,), {"iff1": True, "im": 2, "i": 0x12})
        cpu.memory.write8(0x1234, 0x78)
        cpu.memory.write8(0x1235, 0x56)

        # Act
        cpu.irq(0x34)

        # Assert
        self.assertEqual(cpu.registers.pc, 0x5678, RESPONSE["mode2"]["vectorQuote"])

    def test_mode_zero_takes_a_restart_with_a_single_acknowledge(self) -> None:
        # Arrange
        cpu = loaded((0x00,), {"iff1": True, "im": 0})

        # Act
        cpu.irq(0xC7)

        # Assert
        self.assertEqual(
            ([name for _, name in cpu.bus.cycles].count("acknowledge"), cpu.registers.pc),
            (FACTS["modeZeroGeneratesOneAcknowledge"]["acknowledges"], 0x0000),
        )

    def test_an_edge_that_lands_before_the_deadline_is_taken_at_the_boundary(self) -> None:
        # Arrange
        deadline = FACTS["nonmaskableEdgeMustLandBeforeTheLastState"]["deadlineStatesBeforeTheEnd"]
        cpu = loaded((0x00,))
        raised_in(cpu, "nmi_line", frozenset(range(FETCH_STATES - deadline + 1, FETCH_STATES + 2)))

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.registers.pc, RESPONSE["nonmaskable"]["restartsAt"])

    def test_an_edge_that_lands_in_the_last_state_waits_for_the_next_boundary(self) -> None:
        # Arrange
        printed = FACTS["nonmaskableEdgeMustLandBeforeTheLastState"]
        cpu = loaded((0x00, 0x00))
        raised_in(cpu, "nmi_line", frozenset(range(FETCH_STATES, 2 * FETCH_STATES + 2)))

        # Act
        landed = [counter_after_a_step(cpu) for _ in range(2)]

        # Assert
        self.assertEqual(
            landed, [START + 1, RESPONSE["nonmaskable"]["restartsAt"]], printed["quote"]
        )


if __name__ == "__main__":
    unittest.main()
