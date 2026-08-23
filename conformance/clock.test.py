"""That a part can be driven one cycle at a time, and stopped between any two.

The claim worth testing is not that the count comes out right. It is that the
part is genuinely suspended part way through an instruction, which is shown by
changing what memory answers between two cycles and watching the instruction
pick the new value up. A model that ran the instruction and replayed its cycles
afterwards would pass a count test and fail that one.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import z80  # noqa: E402


class ClockTest(unittest.TestCase):
    def part(self) -> Any:
        self.memory = z80.Memory(image=bytes([0x3E, 0x42, 0x00, 0x00, 0x00, 0x00]))
        cpu = z80.Cpu("z80", self.memory, recording=True)
        cpu.reset()
        cpu.registers.pc = 0x0000
        return cpu

    def test_a_tick_spends_exactly_one_cycle(self) -> None:
        cpu = self.part()
        before = cpu.cycles

        with z80.Clock(cpu) as clock:
            clock.tick()

        self.assertEqual((clock.cycles, cpu.cycles - before), (1, 1))

    def test_a_budget_stops_between_cycles_rather_than_overshooting(self) -> None:
        cpu = self.part()

        with z80.Clock(cpu) as clock:
            spent = clock.run_for(7)

        self.assertEqual(spent, 7)

    def test_the_part_is_suspended_part_way_through_an_instruction(self) -> None:
        cpu = self.part()

        with z80.Clock(cpu) as clock:
            clock.tick()
            self.memory.write8(0x0001, 0x99)
            clock.run_for(6)

        self.assertIn(0x99, [value for _, value, _ in cpu.bus.log])

    def test_a_halted_part_keeps_costing_cycles_under_a_clock(self) -> None:
        space = z80.Memory(image=bytes([0x76]))
        cpu = z80.Cpu("z80", space)
        cpu.reset()
        cpu.registers.pc = 0x0000

        with z80.Clock(cpu) as clock:
            clock.run_for(12)

        self.assertEqual((clock.cycles, cpu.held()), (12, True))

    def test_a_clock_can_be_iterated(self) -> None:
        cpu = self.part()

        with z80.Clock(cpu) as clock:
            spent = [total for total, _ in zip(clock, range(4), strict=False)]

        self.assertEqual(spent, [1, 2, 3, 4])

    def test_iteration_ends_when_the_clock_is_closed(self) -> None:
        clock = z80.Clock(self.part())
        clock.close()

        self.assertEqual(list(clock), [])

    def test_a_closed_clock_refuses_to_tick(self) -> None:
        clock = z80.Clock(self.part())
        clock.close()

        with self.assertRaises(z80.ClockClosed):
            clock.tick()

    def test_closing_twice_is_not_an_error(self) -> None:
        clock = z80.Clock(self.part())
        clock.close()

        clock.close()

        self.assertTrue(clock.closed)

    def test_closing_gives_the_part_its_hook_back(self) -> None:
        cpu = self.part()
        watched: list[int] = []
        cpu.on_cycle = lambda: watched.append(1)

        with z80.Clock(cpu) as clock:
            clock.tick()
        cpu.step()

        self.assertEqual((clock.cycles, bool(watched)), (1, True))

    def test_a_failure_inside_the_part_reaches_the_driver(self) -> None:
        cpu = self.part()
        clock = z80.Clock(cpu)
        self.addCleanup(clock.close)

        def explode() -> None:
            raise RuntimeError("a device said no")

        clock.tick()
        cpu.on_cycle = explode

        with self.assertRaises(RuntimeError):
            clock.run_for(8)

    def test_and_the_clock_refuses_to_go_on_afterwards(self) -> None:
        cpu = self.part()
        clock = z80.Clock(cpu)
        self.addCleanup(clock.close)

        def explode() -> None:
            raise RuntimeError("a device said no")

        clock.tick()
        cpu.on_cycle = explode
        with self.assertRaises(RuntimeError):
            clock.run_for(8)

        with self.assertRaises(z80.ClockClosed):
            clock.tick()


if __name__ == "__main__":
    unittest.main()
