import json
import sys
import unittest
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.bench import FACTS, FLAG, STACK, START, spent
from z80 import Cpu, SparseMemory

DIVERGENCES = json.loads((Path(__file__).resolve().parent / "divergences.json").read_text())

SHAPES = FACTS["machineCycleShapes"]

RESPONSE = FACTS["interruptResponse"]

BLOCK_MOVE = (0xED, 0xB0)


def reset_part(
    program: Sequence[int] = (),
    setup: Mapping[str, Any] | None = None,
    model: str = "z80",
) -> Any:
    space = SparseMemory()
    for offset, byte in enumerate(program):
        space.write8(START + offset, byte)
    cpu = Cpu(model, space)
    cpu.reset()
    cpu.registers.pc = START
    cpu.registers.sp = STACK
    for name, value in (setup or {}).items():
        setattr(cpu.registers, name, value)
    return cpu


def offered(offer: Callable[[Any], object], mode: int = 0) -> tuple[object, int]:
    cpu = reset_part(setup={"iff1": True, "im": mode})
    taken = offer(cpu)
    states: int = cpu.bus.states
    return taken, states


def supplied(program: tuple[int, ...]) -> int:
    cpu = reset_part(setup={"iff1": True, "im": 0})
    cpu.irq(program[0])
    states: int = cpu.bus.states
    return states - spent(program)


def stacked(cpu: Any) -> int:
    held: int = cpu.memory.read8(cpu.registers.sp) | (cpu.memory.read8(cpu.registers.sp + 1) << 8)
    return held


def divergence_named(name: str) -> bool:
    return name in {entry["id"] for entry in DIVERGENCES["divergences"]}


class InterruptResponseTest(unittest.TestCase):
    def test_the_nonmaskable_line_costs_what_a_restart_costs(self) -> None:
        # Arrange
        offer = lambda cpu: cpu.nmi()  # noqa: E731

        # Act
        found = offered(offer)

        # Assert
        self.assertEqual(found, (None, RESPONSE["nonmaskable"]["tStates"]))

    def test_mode_one_costs_the_two_more_the_manual_adds(self) -> None:
        # Arrange
        offer = lambda cpu: cpu.irq(0xFF)  # noqa: E731

        # Act
        found = offered(offer, mode=1)

        # Assert
        self.assertEqual(found, (True, RESPONSE["mode1"]["tStates"]))

    def test_mode_two_costs_the_nineteen_the_manual_prints(self) -> None:
        # Arrange
        offer = lambda cpu: cpu.irq(0xFF)  # noqa: E731

        # Act
        found = offered(offer, mode=2)

        # Assert
        self.assertEqual(found, (True, RESPONSE["mode2"]["tStates"]))

    def test_mode_zero_costs_the_supplied_instruction_plus_two(self) -> None:
        # Arrange
        restart = 0xC7

        # Act
        _, states = offered(lambda cpu: cpu.irq(restart), mode=0)

        # Assert
        self.assertEqual(states - spent((restart,)), 2)

    def test_whatever_the_supplied_instruction_is(self) -> None:
        # Arrange
        programs = {
            "nothing at all": (0x00,),
            "a restart": (0xC7,),
            "a jump": (0xC3, 0x00, 0x20),
            "a push": (0xC5,),
            "an exchange": (0x08,),
        }

        # Act
        added = {name: supplied(program) for name, program in programs.items()}

        # Assert
        self.assertEqual(added, dict.fromkeys(programs, 2))

    def test_a_response_of_more_than_one_byte_reads_the_rest_without_advancing(self) -> None:
        # Arrange
        cpu = reset_part((0x34,), {"iff1": True, "im": 0})

        # Act
        cpu.irq(0xC3)

        # Assert
        self.assertEqual(cpu.registers.pc, 0x3434)

    def test_which_is_written_up_because_a_device_supplies_them_on_the_part(self) -> None:
        # Arrange
        name = "mode-zero-response-of-more-than-one-byte"

        # Act
        named = divergence_named(name)

        # Assert
        self.assertIs(named, True)

    def test_and_so_is_the_register_nothing_constrains_afterwards(self) -> None:
        # Arrange
        name = "wz-after-an-interrupt-response"

        # Act
        named = divergence_named(name)

        # Assert
        self.assertIs(named, True)

    def test_and_that_addition_is_the_two_wait_states_the_manual_names(self) -> None:
        # Arrange
        shape = SHAPES["interruptAcknowledge"]

        # Act
        added = shape["automaticWaitStates"]

        # Assert
        self.assertEqual(added, 2)

    def test_mode_one_lands_where_the_manual_says(self) -> None:
        # Arrange
        cpu = reset_part(setup={"iff1": True, "im": 1})

        # Act
        cpu.irq(0xFF)

        # Assert
        self.assertEqual(cpu.registers.pc, RESPONSE["mode1"]["restartsAt"])

    def test_the_nonmaskable_line_lands_where_the_manual_says(self) -> None:
        # Arrange
        cpu = reset_part()

        # Act
        cpu.nmi()

        # Assert
        self.assertEqual(cpu.registers.pc, RESPONSE["nonmaskable"]["restartsAt"])

    def test_mode_two_uses_every_bit_the_device_supplies(self) -> None:
        # Arrange
        cpu = reset_part(setup={"iff1": True, "im": 2, "i": 0x00})
        for address, byte in ((0x00FE, 0x34), (0x00FF, 0x12), (0x0100, 0x56)):
            cpu.memory.write8(address, byte)

        # Act
        cpu.irq(0xFF)

        # Assert
        self.assertEqual(cpu.registers.pc, 0x5612)

    def test_which_is_the_one_place_a_measurement_beat_the_manual(self) -> None:
        # Arrange
        cpu = reset_part(setup={"iff1": True, "im": 2, "i": 0x12})
        for address, byte in ((0x1234, 0x22), (0x1235, 0x78), (0x1236, 0x56)):
            cpu.memory.write8(address, byte)

        # Act
        cpu.irq(0x35)

        # Assert
        self.assertEqual(cpu.registers.pc, 0x5678)

    def test_a_maskable_interrupt_clears_both_flip_flops(self) -> None:
        # Arrange
        cpu = reset_part(setup={"iff1": True, "iff2": True, "im": 1})

        # Act
        cpu.irq(0xFF)

        # Assert
        self.assertEqual((cpu.registers.iff1, cpu.registers.iff2), (False, False))

    def test_the_nonmaskable_one_clears_only_the_first(self) -> None:
        # Arrange
        cpu = reset_part(setup={"iff1": True, "iff2": True})

        # Act
        cpu.nmi()

        # Assert
        self.assertEqual((cpu.registers.iff1, cpu.registers.iff2), (False, True))

    def test_a_disabled_part_refuses_the_maskable_line(self) -> None:
        # Arrange
        cpu = reset_part(setup={"iff1": False})

        # Act
        taken = cpu.irq(0xFF)

        # Assert
        self.assertEqual(taken, False)

    def test_and_takes_the_nonmaskable_one_anyway(self) -> None:
        # Arrange
        cpu = reset_part(setup={"iff1": False})

        # Act
        cpu.nmi()

        # Assert
        self.assertEqual(cpu.registers.pc, RESPONSE["nonmaskable"]["restartsAt"])

    def test_an_enable_holds_the_line_off_for_one_more_instruction(self) -> None:
        # Arrange
        cpu = reset_part((0xFB,), {"im": 1})
        cpu.step()

        # Act
        taken = cpu.irq(0xFF)

        # Assert
        self.assertEqual(taken, False)

    def test_and_lets_it_through_once_that_instruction_has_run(self) -> None:
        # Arrange
        cpu = reset_part((0xFB,), {"im": 1})
        cpu.step()
        cpu.step()

        # Act
        taken = cpu.irq(0xFF)

        # Assert
        self.assertEqual(taken, True)

    def test_a_repeating_instruction_is_resumed_rather_than_abandoned(self) -> None:
        # Arrange
        setup = {"bc": 4, "hl": 0x3000, "de": 0x4000, "iff1": True, "im": 1}
        cpu = reset_part(BLOCK_MOVE, setup)
        cpu.step()

        # Act
        cpu.irq(0xFF)

        # Assert
        self.assertEqual(stacked(cpu), START)

    def test_which_is_the_part_backing_the_counter_up_rather_than_looping(self) -> None:
        # Arrange
        cpu = reset_part(BLOCK_MOVE, {"bc": 4, "hl": 0x3000, "de": 0x4000})

        # Act
        cpu.step()

        # Assert
        self.assertEqual((cpu.registers.pc, cpu.registers.bc), (START, 3))

    def test_reset_leaves_the_part_in_the_mode_the_manual_names(self) -> None:
        # Arrange
        cpu = Cpu("z80", SparseMemory())
        cpu.registers.im = 2

        # Act
        cpu.reset()

        # Assert
        self.assertEqual((cpu.registers.im, RESPONSE["mode0"]["afterReset"]), (0, True))


def parity_around_an_interrupt(name: str, opcode: int = 0x57) -> tuple[int, int]:
    cpu = reset_part((0xED, opcode), {"iff1": True, "iff2": True, "im": 1}, model=name)
    cpu.step()
    before: int = cpu.registers.f & FLAG["pv"]
    cpu.irq(0xFF)
    after: int = cpu.registers.f & FLAG["pv"]
    return before, after


class ParityDefectTest(unittest.TestCase):
    def test_the_instruction_reports_the_latch_before_the_interrupt(self) -> None:
        # Arrange
        name = "z80"

        # Act
        before, _ = parity_around_an_interrupt(name)

        # Assert
        self.assertEqual(before, FLAG["pv"])

    def test_and_the_nmos_part_clears_it_when_the_interrupt_is_taken(self) -> None:
        # Arrange
        name = "z80"

        # Act
        _, after = parity_around_an_interrupt(name)

        # Assert
        self.assertEqual(after, 0)

    def test_the_other_instruction_that_reads_the_latch_too(self) -> None:
        # Arrange
        reading_r = 0x5F

        # Act
        _, after = parity_around_an_interrupt("z80", opcode=reading_r)

        # Assert
        self.assertEqual(after, 0)

    def test_the_cmos_part_does_not_because_zilog_says_it_was_fixed(self) -> None:
        # Arrange
        name = "z84c00"

        # Act
        _, after = parity_around_an_interrupt(name)

        # Assert
        self.assertEqual(after, FLAG["pv"])

    def test_the_record_names_the_parts_it_affects_and_the_one_it_does_not(self) -> None:
        # Arrange
        defect = RESPONSE["nmosParityDefect"]

        # Act
        named = (defect["affects"], defect["fixedIn"])

        # Assert
        self.assertEqual(named, (["z80"], ["z84c00"]))

    def test_and_quotes_zilog_saying_the_later_part_fixed_it(self) -> None:
        # Arrange
        defect = RESPONSE["nmosParityDefect"]

        # Act
        quoted = defect["quote"]

        # Assert
        self.assertIn("we've fixed this problem", quoted)

    def test_an_interrupt_after_any_other_instruction_leaves_the_flag_alone(self) -> None:
        # Arrange
        cpu = reset_part((0x00,), {"iff1": True, "im": 1, "f": FLAG["pv"]})
        cpu.step()

        # Act
        cpu.irq(0xFF)

        # Assert
        self.assertEqual(cpu.registers.f & FLAG["pv"], FLAG["pv"])

    def test_the_parts_the_defect_affects_lose_the_flag_and_the_fixed_one_keeps_it(self) -> None:
        # Arrange
        defect = FACTS["interruptResponse"]["nmosParityDefect"]
        parts = [*defect["affects"], *defect["fixedIn"]]

        # Act
        kept = {name: parity_around_an_interrupt(name)[1] == FLAG["pv"] for name in parts}

        # Assert
        self.assertEqual(
            kept,
            {**dict.fromkeys(defect["affects"], False), **dict.fromkeys(defect["fixedIn"], True)},
        )


if __name__ == "__main__":
    unittest.main()
