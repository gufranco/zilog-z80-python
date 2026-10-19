import itertools
import sys
import unittest
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance import timing
from conformance.bench import FACTS, RECORD, ROWS, loaded
from z80 import Clock, Cpu, Memory

NOP = (0x00,)

FETCH_STATES = 4

LAST_FETCH_STATE = FETCH_STATES - 1

BLOCK_INPUT = (0xED, 0xA2)

MASKABLE = {"iff1": True, "iff2": True, "im": 1}


def holding(cpu: Any, states: Sequence[int]) -> list[int]:
    seen: list[int] = []
    granted: list[int] = []

    def each() -> None:
        granted.extend([len(seen)] if cpu.busack else [])
        seen.append(len(seen))
        cpu.busreq_line = len(seen) in states

    cpu.busreq_line = 0 in states
    cpu.on_cycle = each
    return granted


def floating(cpu: Any) -> list[int]:
    return [at for at, (address, _, _) in enumerate(cpu.bus.log) if address is None]


def granted_after_every_cycle(cpu: Any) -> list[int]:
    def each() -> None:
        cpu.busreq_line = not cpu.busack

    cpu.busreq_line = True
    cpu.on_cycle = each
    cpu.step()
    held = 0
    ends: list[int] = []
    for address, _, _ in cpu.bus.log:
        if address is None:
            ends.extend([] if ends and ends[-1] == held else [held])
            continue
        held += 1
    return ends


def contradiction(entries: Sequence[dict[str, Any]], name: str) -> dict[str, Any]:
    found: dict[str, Any] = next(entry for entry in entries if entry["id"] == name)
    return found


def last_state_of_a_fetch(fact: dict[str, Any]) -> int:
    return FETCH_STATES - int(fact["readInStatesBeforeTheEnd"])


class PrintedFactTest(unittest.TestCase):
    def test_a_request_seen_in_the_last_state_floats_the_bus_after_the_cycle(self) -> None:
        # Arrange
        fact = FACTS["busRequest"]
        cpu = loaded(NOP)
        granted = holding(cpu, [last_state_of_a_fetch(fact)])
        floats = fact["floatingStatesForEachStateHeld"]

        # Act
        spent = cpu.step()

        # Assert
        after = list(range(FETCH_STATES, FETCH_STATES + floats))
        self.assertEqual((spent, floating(cpu), granted), (FETCH_STATES + floats, after, after))

    def test_a_request_withdrawn_before_the_last_state_is_not_seen(self) -> None:
        # Arrange
        fact = FACTS["busRequest"]
        cpu = loaded(NOP)
        holding(cpu, [last_state_of_a_fetch(fact) - 1])

        # Act
        spent = cpu.step()

        # Assert
        self.assertEqual(spent, FETCH_STATES)

    def test_the_bus_floats_for_as_long_as_the_request_is_held(self) -> None:
        # Arrange
        fact = FACTS["busRequest"]
        held = [last_state_of_a_fetch(fact) + at for at in range(4)]
        cpu = loaded(NOP)
        granted = holding(cpu, held)

        # Act
        spent = cpu.step()

        # Assert
        floats = len(held) * fact["floatingStatesForEachStateHeld"]
        self.assertEqual(
            (spent, granted),
            (FETCH_STATES + floats, list(range(FETCH_STATES, FETCH_STATES + floats))),
        )

    def test_nothing_drives_the_bus_while_it_floats(self) -> None:
        # Arrange
        fact = FACTS["busRequest"]
        cpu = loaded(NOP)
        holding(cpu, [last_state_of_a_fetch(fact)])

        # Act
        cpu.step()

        # Assert
        self.assertEqual(list(cpu.bus.log[FETCH_STATES]), fact["floatingLogEntry"])

    def test_the_floating_states_are_their_own_entry_among_the_cycles(self) -> None:
        # Arrange
        fact = FACTS["busRequest"]
        cpu = loaded(NOP)
        holding(cpu, [last_state_of_a_fetch(fact)])

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.bus.cycles, [(0, "fetch"), (FETCH_STATES, fact["cycleKind"])])

    def test_every_documented_instruction_lets_go_at_its_printed_machine_cycle_ends(self) -> None:
        # Arrange
        reordered = set(FACTS["busRequest"]["breakdownNotFollowedOn"])
        known = timing.catalogue()
        rows = [row for row in ROWS if row["instruction"] not in reordered]

        # Act
        wrong = [
            (row["manualPage"], row["instruction"])
            for row in rows
            for program in timing.encodings_for(row["instruction"], known)
            for setup in timing.SETUPS
            if (ends := self.ends_of(program, setup))[-1] == row["tStates"]
            and ends != list(itertools.accumulate(row["machineCycles"]))
        ]

        # Assert
        self.assertEqual(wrong, [])

    def test_the_block_inputs_read_the_port_before_they_write_memory(self) -> None:
        # Arrange
        entry = contradiction(RECORD["documentContradictions"], "block-input-breakdown-order")
        cpu = loaded(BLOCK_INPUT)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(
            [kind for _, kind in cpu.bus.cycles],
            [kind for kind, _ in entry["reading"]],
        )

    def test_and_let_go_of_the_bus_at_the_ends_their_description_gives(self) -> None:
        # Arrange
        entry = contradiction(RECORD["documentContradictions"], "block-input-breakdown-order")
        cpu = loaded(BLOCK_INPUT)

        # Act
        ends = granted_after_every_cycle(cpu)

        # Assert
        lengths = [length for _, length in entry["reading"]]
        self.assertEqual(ends, list(itertools.accumulate(lengths)))

    def ends_of(self, program: Sequence[int], setup: dict[str, int]) -> list[int]:
        return granted_after_every_cycle(loaded(program, setup))

    def test_a_maskable_request_is_not_taken_at_a_boundary_that_gave_up_the_bus(self) -> None:
        # Arrange
        fact = FACTS["busRequestHoldsOffInterrupts"]
        cpu = loaded(NOP, MASKABLE)
        holding(cpu, [LAST_FETCH_STATE])
        cpu.irq_line = True

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.registers.pc == 0x0038, fact["maskableAcceptedAtThatBoundary"])

    def test_but_it_is_taken_at_the_next_boundary_if_still_held(self) -> None:
        # Arrange
        fact = FACTS["busRequestHoldsOffInterrupts"]
        cpu = loaded((*NOP, *NOP), MASKABLE)
        holding(cpu, [LAST_FETCH_STATE])
        cpu.irq_line = True
        cpu.step()

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.registers.pc, fact["maskableRestart"])

    def test_a_nonmaskable_edge_waits_out_the_floating_states(self) -> None:
        # Arrange
        fact = FACTS["busRequestHoldsOffInterrupts"]
        cpu = loaded(NOP)
        holding(cpu, [LAST_FETCH_STATE, FETCH_STATES])
        cpu.nmi_line = True
        before = cpu.cycles

        # Act
        cpu.step()

        # Assert
        self.assertEqual(
            (cpu.registers.pc, cpu.cycles - before),
            (fact["nonmaskableRestart"], FETCH_STATES + 2 + fact["nonmaskableStates"]),
        )


class ClockTest(unittest.TestCase):
    def test_a_clock_paused_in_a_floating_state_shows_the_acknowledge(self) -> None:
        # Arrange
        fact = FACTS["busRequest"]
        cpu = Cpu("z80", Memory(fill=0x00)).reset()
        cpu.registers.pc = 0x0000
        clock = Clock(cpu)
        self.addCleanup(clock.close)
        clock.run_for(LAST_FETCH_STATE)
        cpu.busreq_line = True
        clock.tick()

        # Act
        clock.tick()

        # Assert
        self.assertEqual(cpu.busack, fact["acknowledgedWhileFloating"])

    def test_but_not_in_the_last_state_of_the_cycle_before_it(self) -> None:
        # Arrange
        cpu = Cpu("z80", Memory(fill=0x00)).reset()
        cpu.registers.pc = 0x0000
        clock = Clock(cpu)
        self.addCleanup(clock.close)
        clock.run_for(LAST_FETCH_STATE)
        cpu.busreq_line = True

        # Act
        clock.tick()

        # Assert
        self.assertFalse(cpu.busack)


if __name__ == "__main__":
    unittest.main()
