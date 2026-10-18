from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar, override

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import netlist  # noqa: E402
from conformance.synthetic_netlist import Fixture  # noqa: E402


class ClockTest(Fixture):
    def quiet(self) -> netlist.Simulation:
        part = self.part()
        part.pullup[17] = 0
        part.drive(1, "clk")
        return part

    def arrange(self, part: netlist.Simulation, **levels: int) -> None:
        for name, level in levels.items():
            part.state[part.number(name)] = level

    def test_a_refresh_cycle_is_left_alone(self) -> None:
        part = self.quiet()
        self.arrange(part, clk=0, _rfsh=0)
        part.memory[0] = 0x5A

        part.half_cycle()

        self.assertEqual(part.data(), 0)

    def test_an_instruction_read_answers_from_memory(self) -> None:
        part = self.quiet()
        self.arrange(part, clk=0, _rfsh=1, _m1=0, _mreq=0, _rd=0, _wr=1, _iorq=1, t2=1, t3=0)
        part.memory[0] = 0x5A

        part.half_cycle()

        self.assertEqual(part.data(), 0x5A)

    def test_a_data_read_answers_from_memory(self) -> None:
        part = self.quiet()
        self.arrange(part, clk=0, _rfsh=1, _m1=1, _mreq=0, _rd=0, _wr=1, _iorq=1, t2=0, t3=1)
        part.memory[0] = 0x3C

        part.half_cycle()

        self.assertEqual(part.data(), 0x3C)

    def test_a_data_write_lands_in_memory(self) -> None:
        part = self.quiet()
        self.arrange(part, clk=0, _rfsh=1, _m1=1, _mreq=0, _rd=1, _wr=0, _iorq=1, t2=0, t3=1)
        self.arrange(part, db0=1, db1=1)

        part.half_cycle()

        self.assertEqual(part.memory[0], 0x03)

    def test_a_port_read_answers_from_the_ports(self) -> None:
        part = self.quiet()
        self.arrange(part, clk=0, _rfsh=1, _m1=1, _mreq=1, _rd=0, _wr=1, _iorq=0, t2=0, t3=1)
        part.ports[0] = 0x77

        part.half_cycle()

        self.assertEqual(part.data(), 0x77)

    def test_a_port_write_lands_in_the_ports(self) -> None:
        part = self.quiet()
        self.arrange(part, clk=0, _rfsh=1, _m1=1, _mreq=1, _rd=1, _wr=0, _iorq=0, t2=0, t3=1)
        self.arrange(part, db2=1)

        part.half_cycle()

        self.assertEqual(part.ports[0], 0x04)

    def test_a_cycle_matching_nothing_touches_neither_memory_nor_ports(self) -> None:
        part = self.quiet()
        self.arrange(part, clk=0, _rfsh=1, _m1=1, _mreq=1, _rd=1, _wr=1, _iorq=1, t2=0, t3=0)

        part.half_cycle()

        self.assertEqual((part.memory[0], part.ports[0]), (0, 0))

    def test_the_clock_turns_over_on_every_half_cycle(self) -> None:
        part = self.quiet()

        part.half_cycle()

        self.assertEqual((part.read("clk"), part.half_cycles), (0, 1))

    def test_a_reset_hands_the_part_back(self) -> None:
        part = self.quiet()

        self.assertIs(part.reset(), part)

    def test_a_reset_starts_the_count_at_the_half_cycles_it_holds_for(self) -> None:
        part = self.quiet()

        part.reset()

        self.assertEqual(part.half_cycles, netlist.RESET_HALF_CYCLES)

    def test_a_program_loads_where_it_is_asked_to(self) -> None:
        part = self.quiet()

        part.load(b"\x11\x22", at=4)

        self.assertEqual(bytes(part.memory[4:6]), b"\x11\x22")

    def test_the_program_counter_reads_high_byte_first(self) -> None:
        part = self.quiet()
        self.arrange(part, reg_pch0=1, reg_pcl1=1)

        self.assertEqual(part.pc(), 0x0102)

    def test_the_address_bus_reads_sixteen_nets(self) -> None:
        part = self.quiet()
        self.arrange(part, ab15=1, ab0=1)

        self.assertEqual(part.address(), 0x8001)

    def test_a_main_register_is_read_under_the_name_an_instruction_uses(self) -> None:
        part = self.quiet()
        self.arrange(part, reg_bb0=1, reg_bb3=1)

        self.assertEqual(part.register("b"), 0x09)

    def test_a_register_with_no_shadow_is_read_under_its_own_name(self) -> None:
        part = self.quiet()
        self.arrange(part, reg_a7=1)

        self.assertEqual(part.register("a"), 0x80)


PRESENT = all((netlist.ROOT / name).is_file() for name in netlist.FILES)


@unittest.skipUnless(PRESENT, "the Visual 6502 netlist is not on this machine")
class AgainstTheDieTest(unittest.TestCase):
    part: ClassVar[netlist.Simulation]

    @classmethod
    @override
    def setUpClass(cls) -> None:
        cls.part = netlist.Simulation()
        cls.part.reset()
        cls.part.load(netlist.SAMPLE)
        for _ in range(netlist.DEFAULT_HALF_CYCLES):
            cls.part.half_cycle()

    def test_the_netlist_is_the_one_that_was_read(self) -> None:
        self.assertEqual((self.part.transistors, self.part.pullups), (6781, 2059))

    def test_every_propagation_comes_to_rest(self) -> None:
        self.assertEqual(self.part.unsettled, 0)

    def test_it_executes_the_load_it_was_given(self) -> None:
        self.assertEqual(self.part.register("a"), 0x42)

    def test_it_executes_the_increment_after_the_load(self) -> None:
        self.assertEqual(self.part.register("b"), 0x9A)

    def test_it_carries_on_past_the_program(self) -> None:
        self.assertEqual((self.part.register("c"), self.part.pc()), (0x17, 0x0011))


@unittest.skipUnless(PRESENT, "the Visual 6502 netlist is not on this machine")
class MeasuredRatherThanTakenTest(unittest.TestCase):
    def test_the_single_letter_names_hold_the_shadow_set_rather_than_the_main_one(self) -> None:
        part = netlist.Simulation()
        part.reset()
        part.load(netlist.SAMPLE)
        for _ in range(netlist.DEFAULT_HALF_CYCLES):
            part.half_cycle()

        self.assertNotEqual(part.bus("reg_b", 8), 0x9A)

    def test_loading_the_pullup_entries_stops_the_netlist_ever_resting(self) -> None:
        # Arrange
        held = (netlist.ROOT / "transdefs.js").read_text().splitlines()
        flagged = [line for line in held if line.rstrip().endswith("true,],")]
        with tempfile.TemporaryDirectory() as hold:
            spare = Path(hold) / "transdefs.js"
            spare.write_text("\n".join(line.replace("true,", "false,") for line in flagged) + "\n")
            part = netlist.Simulation()
            part.read_transistors(spare)

        # Act
        part.reset()
        part.load(netlist.SAMPLE)
        for _ in range(netlist.DEFAULT_HALF_CYCLES):
            part.half_cycle()

        # Assert
        self.assertEqual(
            (len(flagged), part.unsettled > 0), (netlist.TRANSISTORS_THAT_ARE_PULLUPS, True)
        )


EVERY_REGISTER = bytes([0x01, 0xC1, 0xC2, 0x11, 0xE3, 0xE4, 0x21, 0x1A, 0x1B, 0x3E, 0xAF, 0x76])


@unittest.skipUnless(PRESENT, "the Visual 6502 netlist is not on this machine")
class EveryRegisterTest(unittest.TestCase):
    part: ClassVar[netlist.Simulation]

    @classmethod
    @override
    def setUpClass(cls) -> None:
        cls.part = netlist.Simulation()
        cls.part.reset()
        cls.part.load(EVERY_REGISTER)
        for _ in range(340):
            cls.part.half_cycle()

    def test_the_program_ran_to_the_halt(self) -> None:
        self.assertEqual(self.part.pc(), 0x000C)

    def test_every_register_holds_what_was_loaded_into_it(self) -> None:
        found = {name: self.part.register(name) for name in "abcdehl"}

        self.assertEqual(
            found,
            {"a": 0xAF, "b": 0xC2, "c": 0xC1, "d": 0xE4, "e": 0xE3, "h": 0x1B, "l": 0x1A},
        )

    def test_no_two_registers_were_given_the_same_value(self) -> None:
        loaded = [0xAF, 0xC2, 0xC1, 0xE4, 0xE3, 0x1B, 0x1A]

        self.assertEqual(len(set(loaded)), len(loaded))

    def test_and_none_of_them_is_the_power_up_pattern(self) -> None:
        self.assertNotIn(0x55, [self.part.register(name) for name in "abcdehl"])

    def test_the_shadow_set_was_not_written(self) -> None:
        shadows = [self.part.bus(f"reg_{name}", 8) for name in ("b", "c", "d", "e", "h", "l")]

        self.assertEqual(set(shadows), {0x55})


if __name__ == "__main__":
    unittest.main()
