import sys
import unittest
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import die, netlist  # noqa: E402

PRESENT = all(
    (ROOT / "docs" / "independent" / "visual6502" / str(one["file"])).is_file()
    for one in netlist.identity()["netlist"]
)

ADD_HL_BC = bytes([0x09])


class StrobeTest(unittest.TestCase):
    def levels(self, *active: str) -> Callable[[str], bool]:
        return lambda name: name in active

    def test_a_port_request_during_an_opcode_fetch_is_an_acknowledge(self) -> None:
        # Arrange
        level = self.levels("_m1", "_iorq")

        # Act
        kind = die.strobed(level)

        # Assert
        self.assertEqual(kind, "acknowledge")

    def test_a_memory_read_outside_an_opcode_fetch_is_a_read(self) -> None:
        # Arrange
        level = self.levels("_mreq", "_rd")

        # Act
        kind = die.strobed(level)

        # Assert
        self.assertEqual(kind, "read")

    def test_a_port_request_with_neither_strobe_is_nothing_yet(self) -> None:
        # Arrange
        level = self.levels("_iorq")

        # Act
        kind = die.strobed(level)

        # Assert
        self.assertIsNone(kind)


class ModelCycleTest(unittest.TestCase):
    def test_a_sixteen_bit_add_is_a_fetch_and_two_internal_machine_cycles(self) -> None:
        # Arrange
        program = ADD_HL_BC + die.TAIL

        # Act
        found = die.model_cycles(program)

        # Assert
        self.assertEqual(
            found,
            [
                die.Cycle(0, "fetch", 0x0000, 4),
                die.Cycle(4, die.INTERNAL, None, 4),
                die.Cycle(8, die.INTERNAL, None, 3),
            ],
        )


class CatalogueTest(unittest.TestCase):
    def test_the_catalogue_holds_every_opcode_form_but_halt(self) -> None:
        # Arrange
        halt = bytes([die.HALT])

        # Act
        found = die.catalogue()

        # Assert
        self.assertEqual((len(found), halt in {program for _, program in found}), (1135, False))

    def test_the_record_beside_this_one_reads_back(self) -> None:
        # Arrange
        where = die.RECORD

        # Act
        held = die.recorded(where)

        # Assert
        self.assertEqual(held["rung"], 3)


@unittest.skipUnless(PRESENT, "the Visual 6502 netlist is not on this machine")
class AgainstTheDieTest(unittest.TestCase):
    def test_the_die_splits_a_sixteen_bit_add_the_same_way(self) -> None:
        # Arrange
        program = ADD_HL_BC + die.TAIL

        # Act
        found = die.die_cycles(die.bench(program).states)

        # Assert
        self.assertEqual(found[:3], die.model_cycles(program))

    def test_a_comparison_counts_what_it_compared(self) -> None:
        # Arrange
        names = [("add hl,bc", ADD_HL_BC), ("ini", bytes([0xED, 0xA2]))]

        # Act
        found = die.compare(names)

        # Assert
        self.assertEqual(found, {"compared": 2, "differing": []})

    def test_a_form_whose_cycles_part_is_named(self) -> None:
        # Arrange
        names = [("add hl,bc", ADD_HL_BC)]

        # Act
        found = die.compare(names, modelled=lambda _program: [die.Cycle(0, "read", 0, 3)])

        # Assert
        self.assertEqual(found, {"compared": 1, "differing": ["add hl,bc"]})


if __name__ == "__main__":
    unittest.main()
