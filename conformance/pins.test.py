"""That the interrupt inputs behave as lines rather than as events.

The distinction is the whole content of these tests. A request that is raised
and withdrawn before the part looks must produce nothing, and a non-maskable
line held low after its transition must not interrupt twice. Neither is
reachable without a clock that can stop between two cycles, which is why these
live beside it rather than with the instruction tests.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import z80  # noqa: E402


class RequestLineTest(unittest.TestCase):
    def part(self) -> Any:
        space = z80.Memory(image=bytes([0x00] * 16))
        cpu = z80.Cpu("z80", space)
        cpu.reset()
        cpu.registers.pc = 0x0000
        cpu.registers.sp = 0x8000
        cpu.registers.iff1 = True
        cpu.registers.im = 1
        return cpu

    def test_a_line_held_low_is_taken_when_the_part_looks(self) -> None:
        cpu = self.part()
        cpu.irq_line = True

        cpu.step()

        self.assertEqual(cpu.registers.pc, 0x0038)

    def test_a_line_never_raised_is_not(self) -> None:
        cpu = self.part()

        cpu.step()

        self.assertNotEqual(cpu.registers.pc, 0x0038)

    def test_a_request_withdrawn_before_the_part_looks_is_not_taken(self) -> None:
        cpu = self.part()

        with z80.Clock(cpu) as clock:
            clock.tick()
            cpu.irq_line = True
            clock.tick()
            cpu.irq_line = False
            clock.run_for(6)

        self.assertNotEqual(cpu.registers.pc, 0x0038)

    def test_a_request_still_held_at_that_moment_is(self) -> None:
        cpu = self.part()
        cpu.memory.write8(0x0038, 0x76)

        with z80.Clock(cpu) as clock:
            clock.tick()
            cpu.irq_line = True
            clock.run_for(40)

        self.assertTrue(cpu.held())


class NonMaskableLineTest(unittest.TestCase):
    def part(self) -> Any:
        space = z80.Memory(image=bytes([0x00] * 16))
        cpu = z80.Cpu("z80", space)
        cpu.reset()
        cpu.registers.pc = 0x0000
        cpu.registers.sp = 0x8000
        cpu.registers.iff1 = True
        cpu.registers.im = 1
        return cpu

    def test_the_transition_interrupts(self) -> None:
        cpu = self.part()
        cpu.nmi_line = True

        cpu.step()

        self.assertEqual(cpu.registers.pc, 0x0066)

    def test_and_holding_it_afterwards_does_not_interrupt_again(self) -> None:
        cpu = self.part()
        cpu.nmi_line = True
        cpu.step()
        landed = cpu.registers.pc

        cpu.step()

        self.assertNotEqual(cpu.registers.pc, landed)

    def test_a_second_transition_interrupts_again(self) -> None:
        cpu = self.part()
        cpu.nmi_line = True
        cpu.step()
        cpu.nmi_line = False
        cpu.step()
        cpu.nmi_line = True

        cpu.step()

        self.assertEqual(cpu.registers.pc, 0x0066)


if __name__ == "__main__":
    unittest.main()
