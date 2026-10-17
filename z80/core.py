from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from . import blocks, bus, flags, models
from .errors import RunLimit
from .memory import UNSET_SEED
from .registers import Registers

if TYPE_CHECKING:
    from .memory import PortBus, SparseMemory


REGISTER_NAMES = ("b", "c", "d", "e", "h", "l", "(hl)", "a")

PAIRS_SP = ("bc", "de", "hl", "sp")
PAIRS_AF = ("bc", "de", "hl", "af")

INTERRUPT_MODES = (0, 0, 1, 2, 0, 0, 1, 2)

INDEX_PREFIX = {0xDD: "ix", 0xFD: "iy"}

RESET_STATES = 3

RESUME_STATES = 2

NONMASKABLE_RESTART = 0x0066

MODE_ONE_RESTART = 0x0038

VECTOR_MASK = 0xFF


class Cpu:
    __slots__ = (
        "bus",
        "carry_rule",
        "cycles",
        "deferring_interrupt",
        "floating_output",
        "halted",
        "holding_counter",
        "interrupt_clears_parity",
        "irq_line",
        "memory",
        "model",
        "nmi_line",
        "nmi_seen",
        "on_cycle",
        "ports",
        "registers",
        "responding",
        "sampled_irq",
        "steps",
        "wait_line",
    )

    model: str

    carry_rule: str

    interrupt_clears_parity: bool

    holding_counter: bool

    deferring_interrupt: bool

    def __init__(
        self,
        memory: SparseMemory,
        ports: PortBus | None = None,
        seed: int = UNSET_SEED,
        recording: bool = False,
        shape: str = bus.MANUAL,
    ) -> None:
        self.memory = memory
        self.ports = ports
        self.registers = Registers(seed)
        self.wait_line = False

        self.irq_line = False

        self.nmi_line = False

        self.nmi_seen = False

        self.sampled_irq = False

        self.on_cycle: Callable[[], None] | None = None

        self.bus = bus.Bus(
            recording=recording, shape=shape, on_state=self.spend, waiting=self.wants_a_wait
        )
        self.steps = 0
        self.cycles = 0
        self.halted = False
        self.model = "z80"
        self.floating_output = 0x00
        self.carry_rule = models.ZILOG_CARRY
        self.interrupt_clears_parity = True
        self.holding_counter = False
        self.responding: Callable[[], int] | None = None
        self.deferring_interrupt = False

    def spend(self) -> None:
        self.cycles += 1
        self.sampled_irq = self.irq_line
        if self.on_cycle is not None:
            self.on_cycle()

    def wants_a_wait(self) -> bool:
        return self.wait_line

    def sample_pins(self) -> bool:
        edge = self.nmi_line and not self.nmi_seen
        self.nmi_seen = self.nmi_line
        if edge:
            self.nmi()
            return True
        if self.sampled_irq:
            return self.irq()
        return False

    def reset(self) -> Cpu:
        for _ in range(RESET_STATES + RESUME_STATES):
            self.spend()
        self.nmi_seen = self.nmi_line
        self.registers.reset()
        self.halted = False
        self.steps = 0
        return self

    def read8(self, address: int) -> int:
        address &= 0xFFFF
        value = self.memory.read8(address)
        self.bus.read(address, value)
        return value

    def write8(self, address: int, value: int) -> None:
        address &= 0xFFFF
        value &= 0xFF
        self.memory.write8(address, value)
        self.bus.write(address, value)

    def idle(self, count: int = 1) -> None:
        self.bus.idle(count)

    def port_read(self, address: int) -> int:
        address &= 0xFFFF
        value = self.ports.read(address) if self.ports is not None else self.floating_output
        self.bus.port_read(address, value)
        return value & 0xFF

    def port_write(self, address: int, value: int) -> None:
        address &= 0xFFFF
        value &= 0xFF
        if self.ports is not None:
            self.ports.write(address, value)
        self.bus.port_write(address, value)

    def read16(self, address: int) -> int:
        return self.read8(address) | (self.read8(address + 1) << 8)

    def write16(self, address: int, value: int) -> None:
        self.write8(address, value & 0xFF)
        self.write8(address + 1, value >> 8)

    def fetch8(self) -> int:
        value = (
            self.answered(self.registers.pc)
            if self.responding is not None
            else self.read8(self.registers.pc)
        )
        if not self.holding_counter:
            self.registers.pc = self.registers.pc + 1
        return value

    def fetch16(self) -> int:
        low = self.fetch8()
        return low | (self.fetch8() << 8)

    def fetch_signed(self) -> int:
        value = self.fetch8()
        return value - 0x100 if value & 0x80 else value

    def push16(self, value: int) -> None:
        self.registers.sp = self.registers.sp - 1
        self.write8(self.registers.sp, (value >> 8) & 0xFF)
        self.registers.sp = self.registers.sp - 1
        self.write8(self.registers.sp, value & 0xFF)

    def pop16(self) -> int:
        value = self.read16(self.registers.sp)
        self.registers.sp = self.registers.sp + 2
        return value

    def answered(self, address: int) -> int:
        assert self.responding is not None
        value = self.responding() & 0xFF
        self.bus.read(address & 0xFFFF, value)
        return value

    def opcode_fetch(self) -> int:
        counter = self.registers.pc
        refresh = (self.registers.i << 8) | self.registers.r
        if self.responding is not None:
            opcode = self.responding() & 0xFF
        else:
            opcode = self.memory.read8(counter & 0xFFFF)
        if not self.holding_counter:
            self.registers.pc = counter + 1
        self.bus.fetch(counter, refresh, opcode)
        self.registers.tick_refresh()
        return opcode

    def condition(self, index: int) -> bool:
        f = self.registers.f
        if index == 0:
            return not f & flags.Z
        if index == 1:
            return bool(f & flags.Z)
        if index == 2:
            return not f & flags.C
        if index == 3:
            return bool(f & flags.C)
        if index == 4:
            return not f & flags.PV
        if index == 5:
            return bool(f & flags.PV)
        if index == 6:
            return not f & flags.S
        return bool(f & flags.S)

    def set_flags(self, value: int) -> None:
        self.registers.f = value
        self.registers.q = value

    def keep_flags(self) -> None:
        self.registers.q = 0

    def index_pair(self, prefix: str | None) -> str:
        return "hl" if prefix is None else prefix

    def register_name(self, index: int, prefix: str | None) -> str:
        name = REGISTER_NAMES[index]
        if prefix is None:
            return name
        if name == "h":
            return f"{prefix}h"
        if name == "l":
            return f"{prefix}l"
        return name

    def register_read(self, index: int, prefix: str | None = None, displacement: int = 0) -> int:
        if index == 6:
            return self.read8(self.address_for(prefix, displacement))
        return int(getattr(self.registers, self.register_name(index, prefix)))

    def register_write(
        self, index: int, value: int, prefix: str | None = None, displacement: int = 0
    ) -> None:
        if index == 6:
            self.write8(self.address_for(prefix, displacement), value)
            return
        setattr(self.registers, self.register_name(index, prefix), value)

    def address_for(self, prefix: str | None, displacement: int) -> int:
        if prefix is None:
            return self.registers.hl
        address = (int(getattr(self.registers, prefix)) + displacement) & 0xFFFF
        self.registers.wz = address
        return address

    def add8(self, value: int, carry: int = 0) -> None:
        a = self.registers.a
        total = a + value + carry
        result = total & 0xFF
        f = flags.sign_zero(result)
        f |= flags.C if total > 0xFF else 0
        f |= flags.H if ((a & 0x0F) + (value & 0x0F) + carry) > 0x0F else 0
        f |= flags.PV if (~(a ^ value) & (a ^ result)) & 0x80 else 0
        self.registers.a = result
        self.set_flags(f)

    def sub8(self, value: int, carry: int = 0, store: bool = True) -> None:
        a = self.registers.a
        total = a - value - carry
        result = total & 0xFF
        f = flags.N
        f |= flags.S if result & 0x80 else 0
        f |= flags.Z if result == 0 else 0
        f |= flags.C if total < 0 else 0
        f |= flags.H if ((a & 0x0F) - (value & 0x0F) - carry) < 0 else 0
        f |= flags.PV if ((a ^ value) & (a ^ result)) & 0x80 else 0
        f |= flags.undocumented(result if store else value)
        if store:
            self.registers.a = result
        self.set_flags(f)

    def and8(self, value: int) -> None:
        result = self.registers.a & value
        self.registers.a = result
        self.set_flags(flags.sign_zero(result) | flags.H | flags.parity(result))

    def or8(self, value: int) -> None:
        result = self.registers.a | value
        self.registers.a = result
        self.set_flags(flags.sign_zero(result) | flags.parity(result))

    def xor8(self, value: int) -> None:
        result = self.registers.a ^ value
        self.registers.a = result
        self.set_flags(flags.sign_zero(result) | flags.parity(result))

    def inc8(self, value: int) -> int:
        result = (value + 1) & 0xFF
        f = self.registers.f & flags.C
        f |= flags.sign_zero(result)
        f |= flags.H if (value & 0x0F) == 0x0F else 0
        f |= flags.PV if value == 0x7F else 0
        self.set_flags(f)
        return result

    def dec8(self, value: int) -> int:
        result = (value - 1) & 0xFF
        f = self.registers.f & flags.C
        f |= flags.N
        f |= flags.sign_zero(result)
        f |= flags.H if (value & 0x0F) == 0x00 else 0
        f |= flags.PV if value == 0x80 else 0
        self.set_flags(f)
        return result

    def add16(self, left: int, right: int) -> int:
        total = left + right
        result = total & 0xFFFF
        f = self.registers.f & (flags.S | flags.Z | flags.PV)
        f |= flags.C if total > 0xFFFF else 0
        f |= flags.H if ((left & 0x0FFF) + (right & 0x0FFF)) > 0x0FFF else 0
        f |= flags.undocumented(result >> 8)
        self.registers.wz = left + 1
        self.set_flags(f)
        return result

    def begin(self) -> None:
        self.bus.clear()
        self.steps += 1
        self.registers.ei = 0
        self.registers.p = 0
        self.deferring_interrupt = False

    def step(self) -> int:
        self.begin()
        if self.halted:
            self.halt_cycle()
            self.keep_flags()
        else:
            self.execute(self.opcode_fetch(), None)
        self.sample_pins()
        return self.bus.states

    def run_for(self, cycles: int) -> int:
        spent = 0
        while spent < cycles:
            spent += self.step()
        return spent

    def run_until(self, predicate: Callable[[Cpu], bool], limit: int | None = None) -> Cpu:
        taken = 0
        while not predicate(self):
            self.step()
            taken += 1
            if limit is not None and taken >= limit:
                raise RunLimit(f"gave up after {taken} instructions at ${self.registers.pc:04X}")
        return self

    def held(self) -> bool:
        return self.halted

    def halt_cycle(self) -> None:
        counter = self.registers.pc
        refresh = (self.registers.i << 8) | self.registers.r
        self.bus.fetch(counter, refresh, self.memory.read8(counter & 0xFFFF))
        self.registers.tick_refresh()

    def acknowledge(self, vector: int) -> int:
        counter = self.registers.pc
        refresh = (self.registers.i << 8) | self.registers.r
        self.bus.acknowledge(counter, refresh, vector & 0xFF)
        self.registers.tick_refresh()
        return vector & 0xFF

    def begin_response(self) -> None:
        self.begin()
        self.halted = False

    def irq(self, vector: int | Callable[[], int] = 0xFF) -> bool:
        if not self.registers.iff1 or self.registers.ei or self.deferring_interrupt:
            return False
        reading_the_latch = self.registers.p
        self.begin_response()
        self.registers.iff1 = False
        self.registers.iff2 = False
        if reading_the_latch and self.interrupt_clears_parity:
            self.registers.f &= ~flags.PV
        if isinstance(vector, int):
            answering, first = None, vector
        else:
            answering, first = vector, vector()
        answer = self.acknowledge(first)
        if self.registers.im == 1:
            self.restart(MODE_ONE_RESTART)
            return True
        if self.registers.im == 2:
            self.idle()
            self.push16(self.registers.pc)
            pointer = (self.registers.i << 8) | (answer & VECTOR_MASK)
            self.registers.pc = self.read16(pointer)
            self.registers.wz = self.registers.pc
            self.keep_flags()
            return True
        self.holding_counter = True
        self.responding = answering
        try:
            self.execute(answer, None)
        finally:
            self.holding_counter = False
            self.responding = None
        return True

    def nmi(self) -> None:
        self.begin_response()
        self.opcode_fetch()
        self.registers.pc = self.registers.pc - 1
        self.registers.iff1 = False
        self.restart(NONMASKABLE_RESTART)

    def restart(self, address: int) -> None:
        self.idle()
        self.push16(self.registers.pc)
        self.registers.pc = address
        self.registers.wz = address
        self.keep_flags()

    def execute(self, opcode: int, prefix: str | None) -> None:
        if opcode in INDEX_PREFIX:
            self.keep_flags()
            return self.execute(self.opcode_fetch(), INDEX_PREFIX[opcode])
        if opcode == 0xCB:
            return self.execute_bit(prefix)
        if opcode == 0xED:
            return self.execute_extended()

        x = opcode >> 6
        y = (opcode >> 3) & 0x07
        z = opcode & 0x07
        p = y >> 1
        q = y & 1

        if x == 0:
            return self.execute_group0(y, z, p, q, prefix)
        if x == 1:
            return self.execute_load(y, z, prefix)
        if x == 2:
            return self.execute_arithmetic(y, self.operand(z, prefix))
        return self.execute_group3(y, z, p, q, prefix)

    def operand(self, z: int, prefix: str | None) -> int:
        displacement = self.fetch_signed() if z == 6 and prefix is not None else 0
        if z == 6 and prefix is not None:
            self.idle(5)
        return self.register_read(z, prefix, displacement)

    def execute_load(self, y: int, z: int, prefix: str | None) -> None:
        if y == 6 and z == 6:
            self.halted = True
            self.keep_flags()
            return None
        displacement = self.fetch_signed() if (y == 6 or z == 6) and prefix is not None else 0
        if (y == 6 or z == 6) and prefix is not None:
            self.idle(5)
        value = self.register_read(z, None if y == 6 else prefix, displacement)
        self.register_write(y, value, None if z == 6 else prefix, displacement)
        self.keep_flags()
        return None

    def execute_arithmetic(self, y: int, value: int) -> None:
        if y == 0:
            return self.add8(value)
        if y == 1:
            return self.add8(value, 1 if self.registers.f & flags.C else 0)
        if y == 2:
            return self.sub8(value)
        if y == 3:
            return self.sub8(value, 1 if self.registers.f & flags.C else 0)
        if y == 4:
            return self.and8(value)
        if y == 5:
            return self.xor8(value)
        if y == 6:
            return self.or8(value)
        return self.sub8(value, store=False)

    def execute_group0(self, y: int, z: int, p: int, q: int, prefix: str | None) -> None:
        if z == 0:
            return self.group0_control(y)
        if z == 1:
            return self.group0_wide(p, q, prefix)
        if z == 2:
            return self.group0_indirect(p, q, prefix)
        if z == 3:
            return self.group0_count(p, q, prefix)
        if z == 4:
            return self.group0_step(y, prefix, self.inc8)
        if z == 5:
            return self.group0_step(y, prefix, self.dec8)
        if z == 6:
            return self.group0_immediate(y, prefix)
        return self.group0_accumulator(y)

    def group0_control(self, y: int) -> None:
        if y == 0:
            self.keep_flags()
            return None
        if y == 1:
            self.registers.exchange_accumulator()
            self.keep_flags()
            return None
        if y == 2:
            self.idle()
            offset = self.fetch_signed()
            self.registers.b = (self.registers.b - 1) & 0xFF
            return self.take_branch(offset, bool(self.registers.b))
        if y == 3:
            return self.take_branch(self.fetch_signed(), True)
        offset = self.fetch_signed()
        return self.take_branch(offset, self.condition(y - 4))

    def take_branch(self, offset: int, taken: bool) -> None:
        if taken:
            self.idle(5)
            self.registers.pc = self.registers.pc + offset
            self.registers.wz = self.registers.pc
        self.keep_flags()

    def wide_name(self, p: int, prefix: str | None) -> str:
        name = PAIRS_SP[p]
        return self.index_pair(prefix) if name == "hl" else name

    def group0_wide(self, p: int, q: int, prefix: str | None) -> None:
        name = self.wide_name(p, prefix)
        if q == 0:
            setattr(self.registers, name, self.fetch16())
            self.keep_flags()
            return None
        target = self.index_pair(prefix)
        self.idle(7)
        setattr(
            self.registers,
            target,
            self.add16(getattr(self.registers, target), getattr(self.registers, name)),
        )
        return None

    def group0_indirect(self, p: int, q: int, prefix: str | None) -> None:
        if p == 0:
            return self.indirect_accumulator(self.registers.bc, q)
        if p == 1:
            return self.indirect_accumulator(self.registers.de, q)
        address = self.fetch16()
        if p == 3:
            return self.indirect_accumulator(address, q)
        name = self.index_pair(prefix)
        if q == 0:
            self.write16(address, getattr(self.registers, name))
        else:
            setattr(self.registers, name, self.read16(address))
        self.registers.wz = address + 1
        self.keep_flags()
        return None

    def indirect_accumulator(self, address: int, q: int) -> None:
        if q == 0:
            self.write8(address, self.registers.a)
            self.registers.wz = ((self.registers.a << 8) | ((address + 1) & 0xFF)) & 0xFFFF
        else:
            self.registers.a = self.read8(address)
            self.registers.wz = address + 1
        self.keep_flags()

    def group0_count(self, p: int, q: int, prefix: str | None) -> None:
        self.idle(2)
        name = self.wide_name(p, prefix)
        setattr(self.registers, name, getattr(self.registers, name) + (1 if q == 0 else -1))
        self.keep_flags()

    def group0_step(self, y: int, prefix: str | None, operation: Callable[[int], int]) -> None:
        displacement = self.fetch_signed() if y == 6 and prefix is not None else 0
        if y == 6 and prefix is not None:
            self.idle(5)
        value = self.register_read(y, prefix, displacement)
        if y == 6:
            self.idle()
        self.register_write(y, operation(value), prefix, displacement)

    def group0_immediate(self, y: int, prefix: str | None) -> None:
        displacement = self.fetch_signed() if y == 6 and prefix is not None else 0
        value = self.fetch8()
        if y == 6 and prefix is not None:
            self.idle(2)
        self.register_write(y, value, prefix, displacement)
        self.keep_flags()

    def group0_accumulator(self, y: int) -> None:
        if y == 0:
            return self.rotate_accumulator(circular=True, left=True)
        if y == 1:
            return self.rotate_accumulator(circular=True, left=False)
        if y == 2:
            return self.rotate_accumulator(circular=False, left=True)
        if y == 3:
            return self.rotate_accumulator(circular=False, left=False)
        if y == 4:
            return self.decimal_adjust()
        if y == 5:
            return self.complement()
        if y == 6:
            return self.set_carry()
        return self.complement_carry()

    def rotate_accumulator(self, circular: bool, left: bool) -> None:
        a = self.registers.a
        if left:
            carry = a & 0x80
            incoming = a >> 7 if circular else (1 if self.registers.f & flags.C else 0)
            result = ((a << 1) | incoming) & 0xFF
        else:
            carry = a & 0x01
            incoming = (a << 7) if circular else (0x80 if self.registers.f & flags.C else 0)
            result = ((a >> 1) | incoming) & 0xFF
        self.registers.a = result
        self.set_flags(
            (self.registers.f & (flags.S | flags.Z | flags.PV))
            | (flags.C if carry else 0)
            | flags.undocumented(result)
        )

    def decimal_adjust(self) -> None:
        a = self.registers.a
        f = self.registers.f
        correction = 0
        carry = bool(f & flags.C)
        if f & flags.H or (a & 0x0F) > 9:
            correction |= 0x06
        if carry or a > 0x99:
            correction |= 0x60
            carry = True
        subtracting = bool(f & flags.N)
        result = (a - correction if subtracting else a + correction) & 0xFF
        half = bool(f & flags.H) and (a & 0x0F) < 6 if subtracting else (a & 0x0F) > 9
        self.registers.a = result
        self.set_flags(
            flags.sign_zero(result)
            | flags.parity(result)
            | (flags.N if subtracting else 0)
            | (flags.H if half else 0)
            | (flags.C if carry else 0)
        )

    def complement(self) -> None:
        result = self.registers.a ^ 0xFF
        self.registers.a = result
        self.set_flags(
            (self.registers.f & (flags.S | flags.Z | flags.PV | flags.C))
            | flags.H
            | flags.N
            | flags.undocumented(result)
        )

    def set_carry(self) -> None:
        self.set_flags(
            (self.registers.f & (flags.S | flags.Z | flags.PV))
            | flags.C
            | self.carry_undocumented()
        )

    def complement_carry(self) -> None:
        carry = self.registers.f & flags.C
        self.set_flags(
            (self.registers.f & (flags.S | flags.Z | flags.PV))
            | (flags.H if carry else 0)
            | (0 if carry else flags.C)
            | self.carry_undocumented()
        )

    def carry_undocumented(self) -> int:
        if self.carry_rule == models.NEC_CARRY:
            return flags.undocumented(self.registers.a)
        return flags.undocumented((self.registers.q ^ self.registers.f) | self.registers.a)

    def execute_group3(self, y: int, z: int, p: int, q: int, prefix: str | None) -> None:
        if z == 0:
            self.idle()
            if self.condition(y):
                self.registers.pc = self.pop16()
                self.registers.wz = self.registers.pc
            self.keep_flags()
            return None
        if z == 1:
            return self.group3_pop(p, q, prefix)
        if z == 2:
            address = self.fetch16()
            self.registers.wz = address
            if self.condition(y):
                self.registers.pc = address
            self.keep_flags()
            return None
        if z == 3:
            return self.group3_misc(y, prefix)
        if z == 4:
            address = self.fetch16()
            self.registers.wz = address
            if self.condition(y):
                self.idle()
                self.push16(self.registers.pc)
                self.registers.pc = address
            self.keep_flags()
            return None
        if z == 5:
            return self.group3_push(p, q, prefix)
        if z == 6:
            return self.execute_arithmetic(y, self.fetch8())
        self.idle()
        self.push16(self.registers.pc)
        self.registers.pc = y * 8
        self.registers.wz = self.registers.pc
        self.keep_flags()
        return None

    def stack_name(self, p: int, prefix: str | None) -> str:
        name = PAIRS_AF[p]
        return self.index_pair(prefix) if name == "hl" else name

    def group3_pop(self, p: int, q: int, prefix: str | None) -> None:
        if q == 0:
            setattr(self.registers, self.stack_name(p, prefix), self.pop16())
            self.registers.q = 0
            return None
        if p == 0:
            self.registers.pc = self.pop16()
            self.registers.wz = self.registers.pc
        elif p == 1:
            self.registers.exchange_set()
        elif p == 2:
            self.registers.pc = getattr(self.registers, self.index_pair(prefix))
        else:
            self.idle(2)
            self.registers.sp = getattr(self.registers, self.index_pair(prefix))
        self.keep_flags()
        return None

    def group3_push(self, p: int, q: int, prefix: str | None) -> None:
        if q == 0:
            self.idle()
            self.push16(getattr(self.registers, self.stack_name(p, prefix)))
            self.keep_flags()
            return None
        address = self.fetch16()
        self.registers.wz = address
        self.idle()
        self.push16(self.registers.pc)
        self.registers.pc = address
        self.keep_flags()
        return None

    def group3_misc(self, y: int, prefix: str | None) -> None:
        if y == 0:
            address = self.fetch16()
            self.registers.wz = address
            self.registers.pc = address
            self.keep_flags()
            return None
        if y == 2:
            return self.out_to_immediate()
        if y == 3:
            return self.in_from_immediate()
        if y == 4:
            return self.exchange_stack(prefix)
        if y == 5:
            self.registers.de, self.registers.hl = self.registers.hl, self.registers.de
            self.keep_flags()
            return None
        if y == 6:
            self.registers.iff1 = False
            self.registers.iff2 = False
            self.keep_flags()
            return None
        self.registers.iff1 = True
        self.registers.iff2 = True
        self.registers.ei = 1
        self.keep_flags()
        return None

    def out_to_immediate(self) -> None:
        low = self.fetch8()
        address = (self.registers.a << 8) | low
        self.port_write(address, self.registers.a)
        self.registers.wz = ((self.registers.a << 8) | ((low + 1) & 0xFF)) & 0xFFFF
        self.keep_flags()

    def in_from_immediate(self) -> None:
        low = self.fetch8()
        address = (self.registers.a << 8) | low
        self.registers.a = self.port_read(address)
        self.registers.wz = address + 1
        self.keep_flags()

    def exchange_stack(self, prefix: str | None) -> None:
        name = self.index_pair(prefix)
        low = self.read8(self.registers.sp)
        high = self.read8(self.registers.sp + 1)
        self.idle()
        held = low | (high << 8)
        value = getattr(self.registers, name)
        self.write8(self.registers.sp + 1, (value >> 8) & 0xFF)
        self.write8(self.registers.sp, value & 0xFF)
        self.idle(2)
        setattr(self.registers, name, held)
        self.registers.wz = held
        self.keep_flags()

    def execute_bit(self, prefix: str | None) -> None:
        displacement = self.fetch_signed() if prefix is not None else 0
        opcode = self.opcode_fetch() if prefix is None else self.fetch8()
        if prefix is not None:
            self.idle(2)

        x = opcode >> 6
        y = (opcode >> 3) & 0x07
        z = opcode & 0x07

        if prefix is None:
            value = self.register_read(z)
        else:
            address = (getattr(self.registers, prefix) + displacement) & 0xFFFF
            self.registers.wz = address
            value = self.read8(address)
        if prefix is not None or z == 6:
            self.idle()

        if x == 1:
            return self.test_bit(y, value, prefix is not None or z == 6)
        if x == 0:
            result = self.shift(y, value)
        else:
            result = value & ~(1 << y) & 0xFF if x == 2 else value | (1 << y)
            self.keep_flags()
        self.store_bit_result(z, result, prefix, displacement)
        return None

    def store_bit_result(self, z: int, result: int, prefix: str | None, displacement: int) -> None:
        if prefix is None:
            self.register_write(z, result)
            return
        self.write8((getattr(self.registers, prefix) + displacement) & 0xFFFF, result)
        if z != 6:
            self.register_write(z, result)

    def shift(self, y: int, value: int) -> int:
        if y == 0:
            carry = value & 0x80
            result = ((value << 1) | (value >> 7)) & 0xFF
        elif y == 1:
            carry = value & 0x01
            result = ((value >> 1) | (value << 7)) & 0xFF
        elif y == 2:
            carry = value & 0x80
            result = ((value << 1) | (1 if self.registers.f & flags.C else 0)) & 0xFF
        elif y == 3:
            carry = value & 0x01
            result = (value >> 1) | (0x80 if self.registers.f & flags.C else 0)
        elif y == 4:
            carry = value & 0x80
            result = (value << 1) & 0xFF
        elif y == 5:
            carry = value & 0x01
            result = (value >> 1) | (value & 0x80)
        elif y == 6:
            carry = value & 0x80
            result = ((value << 1) | 0x01) & 0xFF
        else:
            carry = value & 0x01
            result = value >> 1
        self.set_flags(flags.sign_zero(result) | flags.parity(result) | (flags.C if carry else 0))
        return result

    def test_bit(self, bit: int, value: int, from_memory: bool) -> None:
        result = value & (1 << bit)
        f = self.registers.f & flags.C
        f |= flags.H
        f |= flags.Z | flags.PV if result == 0 else 0
        f |= flags.S if bit == 7 and result else 0
        f |= flags.undocumented(self.registers.wz >> 8 if from_memory else value)
        self.set_flags(f)

    def execute_extended(self) -> None:
        opcode = self.opcode_fetch()
        x = opcode >> 6
        y = (opcode >> 3) & 0x07
        z = opcode & 0x07
        p = y >> 1
        q = y & 1

        if x == 2:
            blocks.execute(self, y, z)
            return None
        if x != 1:
            self.keep_flags()
            return None
        if z == 0:
            return self.extended_in(y)
        if z == 1:
            return self.extended_out(y)
        if z == 2:
            return self.extended_wide(p, q)
        if z == 3:
            return self.extended_move(p, q)
        if z == 4:
            return self.negate()
        if z == 5:
            return self.extended_return(y)
        if z == 6:
            self.registers.im = INTERRUPT_MODES[y]
            self.keep_flags()
            return None
        return self.extended_accumulator(y)

    def extended_in(self, y: int) -> None:
        address = self.registers.bc
        value = self.port_read(address)
        self.registers.wz = address + 1
        if y != 6:
            self.register_write(y, value)
        self.set_flags((self.registers.f & flags.C) | flags.sign_zero(value) | flags.parity(value))

    def extended_out(self, y: int) -> None:
        address = self.registers.bc
        value = self.floating_output if y == 6 else self.register_read(y)
        self.port_write(address, value)
        self.registers.wz = address + 1
        self.keep_flags()

    def extended_wide(self, p: int, q: int) -> None:
        self.idle(7)
        value = getattr(self.registers, PAIRS_SP[p])
        left = self.registers.hl
        carry = 1 if self.registers.f & flags.C else 0
        if q == 0:
            total = left - value - carry
            result = total & 0xFFFF
            f = flags.N
            f |= flags.C if total < 0 else 0
            f |= flags.H if ((left & 0x0FFF) - (value & 0x0FFF) - carry) < 0 else 0
            f |= flags.PV if ((left ^ value) & (left ^ result)) & 0x8000 else 0
        else:
            total = left + value + carry
            result = total & 0xFFFF
            f = 0
            f |= flags.C if total > 0xFFFF else 0
            f |= flags.H if ((left & 0x0FFF) + (value & 0x0FFF) + carry) > 0x0FFF else 0
            f |= flags.PV if (~(left ^ value) & (left ^ result)) & 0x8000 else 0
        f |= flags.sign_zero16(result)
        self.registers.wz = left + 1
        self.registers.hl = result
        self.set_flags(f)

    def extended_move(self, p: int, q: int) -> None:
        address = self.fetch16()
        name = PAIRS_SP[p]
        if q == 0:
            self.write16(address, getattr(self.registers, name))
        else:
            setattr(self.registers, name, self.read16(address))
        self.registers.wz = address + 1
        self.keep_flags()

    def negate(self) -> None:
        value = self.registers.a
        self.registers.a = 0
        self.sub8(value)

    def extended_return(self, y: int) -> None:
        held = self.registers.iff1 != self.registers.iff2
        self.registers.pc = self.pop16()
        self.registers.wz = self.registers.pc
        self.registers.iff1 = self.registers.iff2
        self.deferring_interrupt = held
        self.keep_flags()

    def extended_accumulator(self, y: int) -> None:
        if y < 4:
            self.idle()
        if y == 0:
            self.registers.i = self.registers.a
            self.keep_flags()
            return None
        if y == 1:
            self.registers.r = self.registers.a
            self.keep_flags()
            return None
        if y == 2:
            return self.load_from_interrupt(self.registers.i)
        if y == 3:
            return self.load_from_interrupt(self.registers.r)
        if y == 4:
            return self.rotate_digit(left=False)
        if y == 5:
            return self.rotate_digit(left=True)
        self.keep_flags()
        return None

    def load_from_interrupt(self, value: int) -> None:
        self.registers.a = value
        self.registers.p = 1
        self.set_flags(
            (self.registers.f & flags.C)
            | flags.sign_zero(value)
            | (flags.PV if self.registers.iff2 else 0)
        )

    def rotate_digit(self, left: bool) -> None:
        address = self.registers.hl
        held = self.read8(address)
        self.idle(4)
        a = self.registers.a
        if left:
            self.write8(address, ((held << 4) | (a & 0x0F)) & 0xFF)
            self.registers.a = (a & 0xF0) | (held >> 4)
        else:
            self.write8(address, ((a << 4) | (held >> 4)) & 0xFF)
            self.registers.a = (a & 0xF0) | (held & 0x0F)
        self.registers.wz = address + 1
        self.set_flags(
            (self.registers.f & flags.C)
            | flags.sign_zero(self.registers.a)
            | flags.parity(self.registers.a)
        )
