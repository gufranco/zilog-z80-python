"""The block instructions, which are one instruction that runs until it is finished.

Four operations, each in four forms: forwards, backwards, and the same two again
with the processor putting the program counter back so the instruction executes
again. The repeating forms are not loops the programmer writes. They are one
instruction that declines to finish, which is why an interrupt can land in the
middle of a block move and why the program counter goes backwards rather than
forwards.

The flags are where these earn their reputation. A move reports whether any count
remains in the flag that normally reports overflow, and takes its two hidden bits
from the byte moved added to the accumulator, which no other instruction consults.
A compare takes them from its own result adjusted by the half carry. The input and
output pair take them from the counter and compute their carry from an addition
the programmer never wrote, involving the port address rather than the data.

None of that is in the datasheet. All of it is what the part does.
"""

from . import flags

FORWARD = 1
BACKWARD = -1


def undocumented_pair(value):
    """Bits three and one of a value, the second moved up to where the flag sits.

    The block instructions do not copy bits three and five the way everything else
    does. They copy bits three and one, and bit one lands in the flag bit five
    occupies. Reading the value as though it were an ordinary result puts the
    second bit in the wrong place and produces an answer that is right half the
    time.
    """
    return (value & 0x08) | ((value & 0x02) << 4)


def repeat_undocumented(address):
    """The two hidden bits of a repeating instruction that has not finished.

    A repeating form that still has work to do does not report the bits its single
    step form would. It reports them from the high half of the address it is about
    to resume at, because by then the value the single step form would have used is
    gone.
    """
    return ((address >> 8) & 0xFF) & (flags.X | flags.Y)


def move(cpu, step, repeating):
    """One byte from one pointer to the other, and the count that decides the rest."""
    value = cpu.read8(cpu.registers.hl)
    cpu.write8(cpu.registers.de, value)
    cpu.registers.hl = cpu.registers.hl + step
    cpu.registers.de = cpu.registers.de + step
    cpu.registers.bc = cpu.registers.bc - 1

    carried = value + cpu.registers.a
    f = cpu.registers.f & (flags.S | flags.Z | flags.C)
    f |= flags.PV if cpu.registers.bc else 0
    f |= undocumented_pair(carried)

    if repeating and cpu.registers.bc:
        cpu.registers.pc = cpu.registers.pc - 2
        f &= ~(flags.X | flags.Y)
        f |= repeat_undocumented(cpu.registers.pc)
        cpu.registers.wz = cpu.registers.pc + 1
    cpu.set_flags(f)


def compare(cpu, step, repeating):
    """The accumulator against one byte, without keeping the answer."""
    value = cpu.read8(cpu.registers.hl)
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
        cpu.registers.pc = cpu.registers.pc - 2
        f &= ~(flags.X | flags.Y)
        f |= repeat_undocumented(cpu.registers.pc)
        cpu.registers.wz = cpu.registers.pc + 1
    cpu.set_flags(f)


def read_port(cpu, step, repeating):
    """One byte in from the port the pair names, stored where the pointer points."""
    address = cpu.registers.bc
    value = cpu.ports.read(address) if cpu.ports is not None else 0
    cpu.registers.wz = address + step
    cpu.write8(cpu.registers.hl, value)
    cpu.registers.b = (cpu.registers.b - 1) & 0xFF
    cpu.registers.hl = cpu.registers.hl + step

    carried = value + ((cpu.registers.c + step) & 0xFF)
    cpu.set_flags(port_flags(cpu, value, carried, repeating))


def write_port(cpu, step, repeating):
    """One byte out to the port the pair names, taken from where the pointer points."""
    value = cpu.read8(cpu.registers.hl)
    cpu.registers.b = (cpu.registers.b - 1) & 0xFF
    address = cpu.registers.bc
    if cpu.ports is not None:
        cpu.ports.write(address, value)
    cpu.registers.wz = address + step
    cpu.registers.hl = cpu.registers.hl + step

    carried = value + (cpu.registers.l & 0xFF)
    cpu.set_flags(port_flags(cpu, value, carried, repeating))


def port_flags(cpu, value, carried, repeating):
    """The flags of a block transfer, which are computed from an addition nobody wrote.

    The carry and half carry do not come from the data alone. They come from the
    data added to one half of the port address, an addition the instruction never
    performs and whose result it never keeps. The parity flag then reports the
    parity of the low three bits of that same sum combined with the counter.
    """
    counter = cpu.registers.b
    carry = carried > 0xFF
    f = flags.sign_zero(counter)
    f |= flags.N if value & 0x80 else 0
    f |= flags.H | flags.C if carry else 0
    f |= flags.parity(((carried & 0x07) ^ counter) & 0xFF)

    if repeating and counter:
        cpu.registers.pc = cpu.registers.pc - 2
        cpu.registers.wz = cpu.registers.pc + 1
        f &= ~(flags.X | flags.Y)
        f |= repeat_undocumented(cpu.registers.pc)
        f = repeat_adjustment(f, counter, value, carry)
    return f


def repeat_adjustment(f, counter, value, carry):
    """The correction a repeating transfer applies to two flags it already computed.

    The single step forms settle the half carry and the parity from the counter and
    the byte. A repeating form that has not finished then revises both, using the
    counter one step further along in the direction the byte's own sign chooses.
    There is no reading of the datasheet that predicts this. It was measured.
    """
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


def execute(cpu, y, z):
    """One block instruction, or nothing when the opcode names none.

    The sixteen opcodes that mean something sit in the top half of the group. The
    bottom half decodes cleanly and does nothing at all, which is a documented
    property of the part rather than a gap in this table.
    """
    if y < 4 or z > 3:
        cpu.keep_flags()
        return None
    OPERATIONS[z](cpu, FORWARD if y % 2 == 0 else BACKWARD, y >= 6)
    return None
