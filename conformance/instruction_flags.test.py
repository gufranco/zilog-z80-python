import json
import random
import sys
import unittest
from collections.abc import Sequence
from pathlib import Path
from typing import override

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from z80 import core, flags, memory  # noqa: E402

HELD = json.loads((Path(__file__).resolve().parent / "instruction-flags.json").read_text())

BIT = {"S": flags.S, "Z": flags.Z, "H": flags.H, "P/V": flags.PV, "N": flags.N, "C": flags.C}

START = 0x0100

SEEDS = 40
"""How many states each rule is tried against.

An absolute holds for every input or it is not an absolute, so the only thing a
count buys is the chance of hitting the input that breaks it. Forty states across
a hundred and twenty six rules is four and a half thousand runs, which is cheap.
"""


class ScriptedPorts:
    """A port space that answers, so a block instruction has something to move."""

    def __init__(self, generator: random.Random) -> None:
        self.generator = generator

    def read(self, address: int) -> int:
        return self.generator.randrange(256)

    def write(self, address: int, value: int) -> None:
        return None


def machine(program: Sequence[int], seed: int, finishing: str | None) -> core.Cpu:
    generator = random.Random(seed)
    space = memory.SparseMemory()
    for offset, byte in enumerate(program):
        space.write8(START + offset, byte)
    for address in range(0x2000, 0x2010):
        space.write8(address, generator.randrange(256))
    cpu = core.Cpu(space, ports=ScriptedPorts(generator), reset=True)
    cpu.registers.pc = START
    cpu.registers.a = generator.randrange(256)
    cpu.registers.f = generator.randrange(256)
    cpu.registers.bc = generator.randrange(0x10000)
    if finishing == "byPair":
        cpu.registers.bc = 0x0001
    elif finishing == "byCounter":
        cpu.registers.bc = 0x0101
    cpu.registers.de = 0x3000 + generator.randrange(16)
    cpu.registers.hl = 0x2000 + generator.randrange(8)
    cpu.registers.ix = 0x2000
    cpu.registers.iy = 0x2000
    cpu.registers.sp = 0x8000
    return cpu


def finishing_kind(name: str) -> str | None:
    for kind in ("byPair", "byCounter"):
        if name in HELD["repeating"][kind]:
            return kind
    return None


def holds(name: str, flag: str, rule: str, seed: int) -> bool:
    cpu = machine(HELD["encodings"][name], seed, finishing_kind(name))
    mask = BIT[flag]
    before = cpu.registers.f
    cpu.step()
    after = cpu.registers.f
    if rule == "is reset":
        return not after & mask
    if rule == "is set":
        return bool(after & mask)
    return (before & mask) == (after & mask)


class RecordTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.rules = HELD["rules"]

    def test_the_manual_states_absolutes_for_forty_five_instructions(self) -> None:
        self.assertEqual(len(self.rules), 45)

    def test_and_a_hundred_and_twenty_six_of_them_in_all(self) -> None:
        self.assertEqual(sum(len(held) for held in self.rules.values()), 126)

    def test_every_rule_names_a_flag_the_register_carries(self) -> None:
        named = {flag for held in self.rules.values() for flag in held}

        self.assertLessEqual(named, set(BIT))

    def test_every_rule_is_one_of_the_three_kinds_a_run_can_check(self) -> None:
        kinds = {rule for held in self.rules.values() for rule in held.values()}

        self.assertEqual(kinds, {"is reset", "is set", "is not affected"})

    def test_every_instruction_has_an_encoding_to_check_it_with(self) -> None:
        missing = [name for name in self.rules if name not in HELD["encodings"]]

        self.assertEqual(missing, [])

    def test_and_every_encoding_belongs_to_a_rule(self) -> None:
        extra = [name for name in HELD["encodings"] if name != "note" and name not in self.rules]

        self.assertEqual(extra, [])

    def test_every_rule_names_the_line_of_the_manual_it_came_from(self) -> None:
        missing = [name for name in self.rules if not HELD["manualLine"].get(name)]

        self.assertEqual(missing, [])


class AbsoluteTest(unittest.TestCase):
    """Every absolute the manual states, tried against forty states each."""

    def broken(self) -> dict[str, list[str]]:
        found: dict[str, list[str]] = {}
        for name, held in HELD["rules"].items():
            for flag, rule in held.items():
                if not all(holds(name, flag, rule, seed) for seed in range(SEEDS)):
                    found.setdefault(name, []).append(flag)
        return found

    def test_exactly_the_recorded_rules_do_not_hold(self) -> None:
        self.assertEqual(self.broken(), HELD["doNotHold"])

    def test_which_is_nine_instructions_of_forty_five(self) -> None:
        self.assertEqual(len(HELD["doNotHold"]), 9)

    def test_and_eight_of_the_nine_are_the_block_transfer_group(self) -> None:
        block = {name for name in HELD["doNotHold"] if name != "BIT b, (IY+d)"}

        self.assertEqual(len(block), 8)

    def test_the_ninth_is_the_page_that_prints_one_letter_for_another(self) -> None:
        self.assertEqual(HELD["doNotHold"]["BIT b, (IY+d)"], ["H"])

    def test_the_record_says_why_each_exception_is_not_a_defect(self) -> None:
        self.assertEqual(len(HELD["exceptions"]), 3)


class BitInstructionTest(unittest.TestCase):
    """The four pages of one instruction, two of which print the wrong letter."""

    def after(self, program: Sequence[int]) -> tuple[int, int]:
        space = memory.SparseMemory()
        for offset, byte in enumerate(program):
            space.write8(START + offset, byte)
        cpu = core.Cpu(space, reset=True)
        cpu.registers.pc = START
        cpu.registers.hl = cpu.registers.ix = cpu.registers.iy = 0x2000
        cpu.registers.f = 0x00
        cpu.step()
        return cpu.registers.f & flags.H, cpu.registers.f & flags.N

    def test_every_form_sets_the_half_carry_and_resets_the_negate(self) -> None:
        forms = {
            "register": (0xCB, 0x40),
            "through the pair": (0xCB, 0x46),
            "indexed by ix": (0xDD, 0xCB, 0x00, 0x46),
            "indexed by iy": (0xFD, 0xCB, 0x00, 0x46),
        }

        found = {name: self.after(program) for name, program in forms.items()}

        self.assertEqual(set(found.values()), {(flags.H, 0)})


class BlockTransferTest(unittest.TestCase):
    """The eight instructions the manual is wrong about, against the measured rule."""

    class Port:
        def __init__(self, value: int) -> None:
            self.value = value
            self.written: int | None = None

        def read(self, address: int) -> int:
            return self.value

        def write(self, address: int, value: int) -> None:
            self.written = value

    def parity(self, value: int) -> int:
        return flags.PV if bin(value & 0xFF).count("1") % 2 == 0 else 0

    def input_step(self, program: Sequence[int], value: int, b: int, c: int) -> int:
        space = memory.SparseMemory()
        for offset, byte in enumerate(program):
            space.write8(START + offset, byte)
        cpu = core.Cpu(space, ports=self.Port(value), reset=True)
        cpu.registers.pc, cpu.registers.b, cpu.registers.c = START, b, c
        cpu.registers.hl, cpu.registers.f = 0x2000, 0x00
        cpu.step()
        return int(cpu.registers.f)

    def test_the_negate_flag_carries_bit_seven_of_the_byte_moved(self) -> None:
        wrong = [
            value
            for value in (0x00, 0x7F, 0x80, 0xFF)
            if bool(self.input_step((0xED, 0xA2), value, 0x40, 0x10) & flags.N)
            != bool(value & 0x80)
        ]

        self.assertEqual(wrong, [])

    def runs(self) -> list[tuple[int, int, int, int]]:
        """Every state tried, paired with the flags one block input left behind."""
        return [
            (b, c, value, self.input_step((0xED, 0xA2), value, b, c))
            for b, c, value in self.states()
        ]

    def states(self) -> list[tuple[int, int, int]]:
        return [
            (b, c, value)
            for b in (0x01, 0x40, 0x81, 0xFF)
            for c in (0x00, 0x7F, 0x80, 0xFF)
            for value in (0x00, 0x01, 0x7F, 0x80, 0xFF)
        ]

    def test_the_carry_and_half_carry_come_from_a_sum_the_manual_never_mentions(
        self,
    ) -> None:
        wrong = [
            (b, c, value)
            for b, c, value, f in self.runs()
            if (bool(f & flags.C), bool(f & flags.H)) != (value + ((c + 1) & 0xFF) > 0xFF,) * 2
        ]

        self.assertEqual(wrong, [])

    def test_and_the_parity_flag_from_the_same_sum(self) -> None:
        wrong = [
            (b, c, value)
            for b, c, value, f in self.runs()
            if f & flags.PV != self.parity(((value + ((c + 1) & 0xFF)) & 7) ^ ((b - 1) & 0xFF))
        ]

        self.assertEqual(wrong, [])

    def test_the_sum_the_manual_never_mentions_does_overflow_for_some_of_these(
        self,
    ) -> None:
        carried = [
            (b, c, value) for b, c, value in self.states() if value + ((c + 1) & 0xFF) > 0xFF
        ]

        self.assertTrue(carried)

    def test_an_output_instruction_moves_the_byte_the_other_way(self) -> None:
        port = self.Port(0x00)
        space = memory.SparseMemory()
        for offset, byte in enumerate((0xED, 0xA3)):
            space.write8(START + offset, byte)
        space.write8(0x2000, 0x5A)
        cpu = core.Cpu(space, ports=port, reset=True)
        cpu.registers.pc, cpu.registers.b, cpu.registers.c = START, 0x40, 0x10
        cpu.registers.hl = 0x2000

        cpu.step()

        self.assertEqual(port.written, 0x5A)

    def test_the_manual_says_the_carry_is_untouched_and_it_is_not(self) -> None:
        held = self.input_step((0xED, 0xA2), 0xFF, 0x40, 0x10)

        self.assertEqual(
            (HELD["rules"]["INI"]["C"], bool(held & flags.C)), ("is not affected", True)
        )


if __name__ == "__main__":
    unittest.main()
