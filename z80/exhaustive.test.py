import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from z80 import Ports, SparseMemory, core, opcodes
from z80.core import Cpu

AT = 0x8000

PREFIXES = ((), (0xCB,), (0xED,), (0xDD,), (0xFD,), (0xDD, 0xCB), (0xFD, 0xCB))

DISPLACED = ((0xDD, 0xCB), (0xFD, 0xCB))

STATES = (
    {"f": 0x00, "bc": 0x0002, "a": 0x00},
    {"f": 0xFF, "bc": 0x0001, "a": 0xFF},
    {"f": 0x54, "bc": 0x0100, "a": 0x99},
)


def program(prefix: tuple[int, ...], opcode: int) -> list[int]:
    """The bytes of one instruction, with the displacement where the part wants it."""
    if prefix in DISPLACED:
        return [*prefix, 0x02, opcode]
    return [*prefix, opcode]


def machine(bytes_: list[int], state: dict[str, int]) -> Cpu:
    space = SparseMemory(seed=3)
    for offset, value in enumerate(bytes_):
        space.write8(AT + offset, value)
    cpu = core.Cpu(space, Ports(seed=3), reset=False)
    cpu.registers.pc = AT
    cpu.registers.sp = 0x9000
    cpu.registers.hl = 0x4000
    cpu.registers.de = 0x4100
    cpu.registers.ix = 0x4200
    cpu.registers.iy = 0x4300
    cpu.registers.i = 0x11
    cpu.registers.r = 0x22
    cpu.registers.wz = 0x1234
    cpu.registers.q = 0x00
    for name, value in state.items():
        setattr(cpu.registers, name, value)
    return cpu


class ExecutionTest(unittest.TestCase):
    def test_every_instruction_in_the_whole_space_executes(self) -> None:
        for prefix in PREFIXES:
            for opcode in range(0x100):
                for state in STATES:
                    bytes_ = program(prefix, opcode)
                    cpu = machine(bytes_, state)

                    cpu.step()

                    self.assertIsInstance(cpu.registers.pc, int, f"{bytes_} {state}")

    def test_every_instruction_leaves_every_register_inside_its_width(self) -> None:
        for prefix in PREFIXES:
            for opcode in range(0x100):
                cpu = machine(program(prefix, opcode), STATES[0])

                cpu.step()

                self.assertLessEqual(cpu.registers.a, 0xFF)
                self.assertLessEqual(cpu.registers.f, 0xFF)
                self.assertLessEqual(cpu.registers.pc, 0xFFFF)
                self.assertLessEqual(cpu.registers.sp, 0xFFFF)
                self.assertLessEqual(cpu.registers.wz, 0xFFFF)

    def test_the_repeating_forms_all_finish_when_run_to_completion(self) -> None:
        for opcode in (0xB0, 0xB1, 0xB2, 0xB3, 0xB8, 0xB9, 0xBA, 0xBB):
            cpu = machine([0xED, opcode], {"f": 0x00, "bc": 0x0303, "a": 0x77})
            cpu.step_limit = 2000

            cpu.run_until(lambda machine: machine.registers.pc != AT)

            self.assertEqual(cpu.registers.pc, AT + 2, f"ED {opcode:02X}")

    def test_an_instruction_that_stops_the_processor_keeps_stopping_it(self) -> None:
        cpu = machine([0x76], STATES[0])

        cpu.step()
        cpu.step()

        self.assertTrue(cpu.halted)

    def test_a_machine_that_is_reset_starts_at_the_bottom_again(self) -> None:
        cpu = machine([0x76], STATES[0])
        cpu.step()

        cpu.reset()

        self.assertEqual((cpu.registers.pc, cpu.halted, cpu.steps), (0x0000, False, 0))

    def test_a_machine_with_no_ports_still_runs_the_instructions_that_use_them(self) -> None:
        space = SparseMemory(seed=3)
        for offset, value in enumerate([0xED, 0x40]):
            space.write8(AT + offset, value)
        cpu = core.Cpu(space, None, reset=False)
        cpu.registers.pc = AT

        cpu.step()

        self.assertEqual(cpu.registers.pc, AT + 2)

    def test_a_machine_with_no_ports_survives_every_instruction_that_reaches_one(self) -> None:
        for bytes_ in ([0xD3, 0x10], [0xDB, 0x10], [0xED, 0x41], [0xED, 0xA2], [0xED, 0xA3]):
            space = SparseMemory(seed=3)
            for offset, value in enumerate(bytes_):
                space.write8(AT + offset, value)
            cpu = core.Cpu(space, None, reset=False)
            cpu.registers.pc = AT
            cpu.registers.bc = 0x0102

            cpu.step()

            self.assertGreater(cpu.registers.pc, 0, str(bytes_))


class ListingTest(unittest.TestCase):
    def test_every_instruction_in_the_whole_space_has_a_name(self) -> None:
        for prefix in PREFIXES:
            for opcode in range(0x100):
                bytes_ = bytes([*program(prefix, opcode), 0x34, 0x12])

                found = opcodes.decode(bytes_, 0, AT)

                self.assertTrue(found.text.strip(), f"{bytes_.hex()}")

    def test_no_two_prefixes_produce_the_same_name_for_the_index_registers(self) -> None:
        first = opcodes.decode(bytes([0xDD, 0x7E, 0x05]), 0, AT).text
        second = opcodes.decode(bytes([0xFD, 0x7E, 0x05]), 0, AT).text

        self.assertNotEqual(first, second)

    def test_a_run_of_every_opcode_disassembles_without_stopping(self) -> None:
        listing = opcodes.disassemble(bytes(range(0x100)) * 2, AT)

        self.assertTrue(listing)

    def test_a_decoded_instruction_keeps_the_bytes_it_came_from(self) -> None:
        found = opcodes.decode(bytes([0x21, 0x34, 0x12]), 0, AT)

        self.assertEqual(found.raw, bytes([0x21, 0x34, 0x12]))

    def test_a_decoded_instruction_prints_as_its_address_and_its_name(self) -> None:
        found = opcodes.decode(bytes([0x00]), 0, AT)

        self.assertEqual(repr(found), "<8000 nop>")


class CarryFlagTest(unittest.TestCase):
    """The two instructions whose hidden bits depend on what ran before them."""

    def test_after_an_instruction_that_wrote_the_flags_the_accumulator_alone_decides(self) -> None:
        cpu = machine([0x37], {"f": 0x28, "a": 0x00})
        cpu.registers.q = 0x28

        cpu.step()

        self.assertEqual(cpu.registers.f & 0x28, 0x00)

    def test_after_one_that_did_not_the_flag_register_is_folded_in(self) -> None:
        cpu = machine([0x37], {"f": 0x28, "a": 0x00})
        cpu.registers.q = 0x00

        cpu.step()

        self.assertEqual(cpu.registers.f & 0x28, 0x28)

    def test_the_same_holds_for_the_instruction_that_inverts_the_carry(self) -> None:
        cpu = machine([0x3F], {"f": 0x28, "a": 0x00})
        cpu.registers.q = 0x28

        cpu.step()

        self.assertEqual(cpu.registers.f & 0x28, 0x00)


if __name__ == "__main__":
    unittest.main()
