from __future__ import annotations

from typing import TYPE_CHECKING

from . import flags

if TYPE_CHECKING:
    from .core import Cpu

FORWARD = 1
BACKWARD = -1


def undocumented_pair(value: int) -> int:
    return (value & 0x08) | ((value & 0x02) << 4)


def repeat_undocumented(address: int) -> int:
    return ((address >> 8) & 0xFF) & (flags.X | flags.Y)


def move(cpu: Cpu, step: int, repeating: bool) -> None:
    value = cpu.read8(cpu.registers.hl)
    cpu.write8(cpu.registers.de, value)
    cpu.idle(2)
    cpu.registers.hl = cpu.registers.hl + step
    cpu.registers.de = cpu.registers.de + step
    cpu.registers.bc = cpu.registers.bc - 1

    carried = value + cpu.registers.a
    f = cpu.registers.f & (flags.S | flags.Z | flags.C)
    f |= flags.PV if cpu.registers.bc else 0
    f |= undocumented_pair(carried)

    if repeating and cpu.registers.bc:
        cpu.idle(5)
        cpu.registers.pc = cpu.registers.pc - 2
        f &= ~(flags.X | flags.Y)
        f |= repeat_undocumented(cpu.registers.pc)
        cpu.registers.wz = cpu.registers.pc + 1
    cpu.set_flags(f)


def compare(cpu: Cpu, step: int, repeating: bool) -> None:
    value = cpu.read8(cpu.registers.hl)
    cpu.idle(5)
    result = (cpu.registers.a - value) & 0xFF
    half = ((cpu.registers.a & 0x0F) - (value & 0x0F)) < 0
    cpu.registers.hl = cpu.registers.hl + step
    cpu.registers.bc = cpu.registers.bc - 1
    cpu.registers.wz = cpu.registers.wz + step

    f = cpu.registers.f & flags.C
    f |= flags.N
    f |= flags.S if result & 0x80 else 0
    f |= flags.Z if result == 0 else 0
    f |= flags.H if half else 0
    f |= flags.PV if cpu.registers.bc else 0
    f |= undocumented_pair((result - 1) & 0xFF if half else result)

    if repeating and cpu.registers.bc and result:
        cpu.idle(5)
        cpu.registers.pc = cpu.registers.pc - 2
        f &= ~(flags.X | flags.Y)
        f |= repeat_undocumented(cpu.registers.pc)
        cpu.registers.wz = cpu.registers.pc + 1
    cpu.set_flags(f)


def read_port(cpu: Cpu, step: int, repeating: bool) -> None:
    cpu.idle()
    address = cpu.registers.bc
    value = cpu.port_read(address)
    cpu.registers.wz = address + step
    cpu.write8(cpu.registers.hl, value)
    cpu.registers.b = (cpu.registers.b - 1) & 0xFF
    cpu.registers.hl = cpu.registers.hl + step

    carried = value + ((cpu.registers.c + step) & 0xFF)
    cpu.set_flags(port_flags(cpu, value, carried, repeating))


def write_port(cpu: Cpu, step: int, repeating: bool) -> None:
    cpu.idle()
    value = cpu.read8(cpu.registers.hl)
    cpu.registers.b = (cpu.registers.b - 1) & 0xFF
    address = cpu.registers.bc
    cpu.port_write(address, value)
    cpu.registers.wz = address + step
    cpu.registers.hl = cpu.registers.hl + step

    carried = value + (cpu.registers.l & 0xFF)
    cpu.set_flags(port_flags(cpu, value, carried, repeating))


def port_flags(cpu: Cpu, value: int, carried: int, repeating: bool) -> int:
    counter = cpu.registers.b
    carry = carried > 0xFF
    f = flags.sign_zero(counter)
    f |= flags.N if value & 0x80 else 0
    f |= flags.H | flags.C if carry else 0
    f |= flags.parity(((carried & 0x07) ^ counter) & 0xFF)

    if repeating and counter:
        cpu.idle(5)
        cpu.registers.pc = cpu.registers.pc - 2
        cpu.registers.wz = cpu.registers.pc + 1
        f &= ~(flags.X | flags.Y)
        f |= repeat_undocumented(cpu.registers.pc)
        f = repeat_adjustment(f, counter, value, carry)
    return f


def repeat_adjustment(f: int, counter: int, value: int, carry: bool) -> int:
    if carry:
        toward = -1 if value & 0x80 else 1
        overflowed = (counter & 0x0F) == (0x00 if value & 0x80 else 0x0F)
        f = (f & ~flags.H) | (flags.H if overflowed else 0)
        neighbour = (counter + toward) & 0x07
    else:
        neighbour = counter & 0x07
    settled = bool(f & flags.PV) ^ bool(flags.parity(neighbour)) ^ True
    return (f & ~flags.PV) | (flags.PV if settled else 0)


OPERATIONS = (move, compare, read_port, write_port)


def execute(cpu: Cpu, y: int, z: int) -> None:
    if y < 4 or z > 3:
        cpu.keep_flags()
        return None
    OPERATIONS[z](cpu, FORWARD if y % 2 == 0 else BACKWARD, y >= 6)
    return None
