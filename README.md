# Zilog Z80

The Zilog Z80, the NEC µPD780C and the Zilog Z84C00 in Python, driven one instruction or one T state at a time and held to Zilog's user manual for the shape of every machine cycle and to a per-opcode corpus for every T state of every opcode.

English | [日本語](README.ja.md) | [简体中文](README.zh-Hans.md) | [繁體中文（香港）](README.zh-HK.md)

[![CI](https://github.com/gufranco/zilog-z80-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/zilog-z80-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/zilog-z80-python)](https://github.com/gufranco/zilog-z80-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**3** parts, **1,604,000** conformance cases and **22,005,372** T states compared, **0** failures, **1,368** tests, **100%** statement and branch coverage, no dependencies

```python
from z80 import Cpu, Memory

cpu = Cpu("z80", Memory(image=bytes([0x3E, 0x42, 0x47, 0x76])))
cpu.reset()

spent = [cpu.step(), cpu.step(), cpu.step()]
print(f"b={cpu.registers.b:02X} pc={cpu.registers.pc:04X}", spent, cpu.held(), cpu.cycles)
```

```
b=42 pc=0004 [7, 4, 4] True 20
```

The program is `ld a,$42`, `ld b,a`, `halt`. Each `step()` runs one instruction and returns the T states it cost: 7, 4 and 4. `held()` is true once `HALT` executes. `cycles` reads 20 because `reset()` spends 5 T states before the first instruction.

## Install

| Requirement | Version |
|:--|:--|
| Python | 3.12 or newer |
| git | Any, to clone |

```bash
git clone https://github.com/gufranco/zilog-z80-python.git
cd zilog-z80-python
python3 z80/doctor.py
```

The package imports nothing outside the standard library. `pip install git+https://github.com/gufranco/zilog-z80-python.git` installs the `z80` package alone, without the conformance tools.

The doctor reports the machine, each of the three parts it builds and resets, and whether the corpus is fetched and complete. It runs as a file so that it still reports when the package will not import. It exits 0 when every check passes and 1 otherwise. Paste its whole output into any bug report. On a fresh checkout it ends with:

```
  8 checks, nothing to report
```

Releases follow [Semantic Versioning](https://semver.org/) and are cut from the commit history by semantic-release. Every release is tagged and listed on the [releases page](https://github.com/gufranco/zilog-z80-python/releases).

## The interface

Everything below is exported from `z80`. Nothing else is public.

### Building a part

`Cpu(model, memory=None, fill=None, ports=None, seed=UNSET_SEED, recording=False, shape="manual")` builds one part, powered and not reset.

| Argument | Meaning |
|:--|:--|
| `model` | Required. A model name or alias, case and separators ignored. Leaving it out raises `UnknownModelError`, which lists every model |
| `memory` | Any object with `read8(address)` and `write8(address, value)`. The part keeps the one it is handed. Left out, the part builds a `SparseMemory` |
| `fill` | Used only when `memory` is left out: builds a 64 KB `Memory` holding that byte everywhere |
| `ports` | Any object with `read(address)` and `write(address, value)`. Left out, an input reads the model's floating output and an output goes nowhere |
| `seed` | Seeds the power-on scramble of the registers |
| `recording` | `True` keeps a per-T-state log in `cpu.bus.log` |
| `shape` | `"manual"` or `"recording"`, the edge each control pin is read on. Anything else raises `UnknownShape` |

### Running it

| Call | Does | Returns |
|:--|:--|:--|
| `reset()` | Drives RESET: the 3 T states Zilog names as the minimum the pin is held, then the 2 the part spends after release. Sets `pc`, `i`, `r` and `im` to 0, clears both interrupt flip-flops and `steps`, leaves every other register as it was | the `Cpu` |
| `step()` | Runs one instruction, or one `HALT` cycle while halted | T states it cost |
| `run_for(cycles)` | Runs whole instructions until at least `cycles` T states have passed | T states spent, which can exceed `cycles` |
| `run_until(check, limit=None)` | Steps while `check(cpu)` is false. After `limit` instructions it raises `RunLimit` | the `Cpu` |
| `held()` | Whether a `HALT` is executing | `bool` |
| `irq(vector=0xFF)` | Offers a maskable interrupt now. `vector` is the byte the device supplies, or a callable returning one byte per read, which is how a device supplies a longer instruction in mode 0 | `True` if taken |
| `nmi()` | Takes a non-maskable interrupt now and restarts at `$0066` | `None` |

### Pins and state

| Attribute | Is |
|:--|:--|
| `irq_line` | The maskable request as a level, sampled at the final T state of each instruction |
| `nmi_line` | The non-maskable request. The transition interrupts; holding it does not interrupt again |
| `wait_line` | Read after T2 of every machine cycle. Each T state it stays set repeats T2 |
| `on_cycle` | Called once per T state, after that state's bus activity |
| `cycles` | T states since the part was built, across resets |
| `steps` | Instructions since the last reset |
| `halted` | Whether a `HALT` is executing; each `HALT` cycle costs 4 T states |
| `registers` | The `Registers` file below |
| `bus` | The last instruction: `states`, its T state count; `cycles`, a list of `(state, kind)` per machine cycle; `log`, a list of `(address, value, pins)` per T state. The two lists fill only with `recording=True` |
| `memory`, `ports` | What the part was built with |
| `model` | The canonical model name |

```python
from z80 import Cpu, Memory

cpu = Cpu("z80", Memory(image=bytes([0x3E, 0x42])))
cpu.reset()
seen = []


def each_state() -> None:
    seen.append(cpu.bus.states)
    cpu.wait_line = len(seen) < 4


cpu.on_cycle = each_state
cpu.wait_line = True
print(cpu.step(), seen)
```

```
9 [1, 2, 3, 4, 5, 6, 7, 8, 9]
```

`ld a,n` costs 7 T states. The wait line is still set when it is read after T2 of the opcode fetch, and again one state later, so T2 repeats twice and the instruction costs 9. `on_cycle` saw every one of them.

### Interrupts

```python
from z80 import Cpu, Memory, RunLimit

program = bytes([0xED, 0x56, 0xFB, 0x00, 0x18, 0xFD])
space = Memory(image=program, fill=0x00)
cpu = Cpu("z80", space)
cpu.reset()
cpu.registers.sp = 0x8000

cpu.run_until(lambda part: part.registers.pc == 0x0004)
cpu.irq_line = True
cpu.step()
cpu.irq_line = False
print(f"pc={cpu.registers.pc:04X} iff1={cpu.registers.iff1} im={cpu.registers.im}")
print(f"pushed {space.read8(0x7FFF):02X}{space.read8(0x7FFE):02X}")

try:
    cpu.run_until(lambda part: False, limit=3)
except RunLimit as error:
    print(error)
```

```
pc=0038 iff1=False im=1
pushed 0003
gave up after 3 instructions at $003B
```

The program is `im 1`, `ei`, `nop`, then `jr` back to the `nop`. With the line set, the `jr` completes, the part samples the request at its last T state, pushes the return address `$0003` and restarts at `$0038`. `run_until` with a check that never passes gives up after the 3 instructions `limit` allows.

### Memory and ports

| Name | Is |
|:--|:--|
| `SparseMemory(seed=UNSET_SEED)` | 64 KB that stores only what is written. An unwritten byte reads as a value derived from `seed` and the address |
| `Memory(size=0x10000, image=None, seed=UNSET_SEED, fill=None)` | A flat `bytearray`. Without `fill` it is scrambled from `seed`. `image` is copied in from address 0 |
| `Ports(seed=UNSET_SEED)` | An I/O space. Reads and writes go to `log` as `(address, value, "r" or "w")`. An unwritten port reads as a value derived from `seed` |
| `UNSET_SEED` | `0x5A5A5A5A`, the seed every scramble uses when none is given |

Addresses on every bus are 16 bits. A port address carries the accumulator or `B` in its high byte, as the part drives it.

```python
from z80 import Cpu, Memory, Ports

program = bytes([0x3E, 0x12, 0xD3, 0x34, 0x01, 0x99, 0x00, 0xED, 0x71])
ports = Ports()
cpu = Cpu("z84c00", Memory(image=program), ports=ports, recording=True)
cpu.reset()

cpu.step()
cpu.step()
print(cpu.bus.states, cpu.bus.cycles)
for address, value, pins in cpu.bus.log:
    print(f"{address:04X} {value} {pins}")

cpu.step()
cpu.step()
print(ports.log)
```

```
11 [(0, 'fetch'), (4, 'read'), (7, 'portWrite')]
0002 None r-m-
0002 None r-m-
0001 211 --m-
0001 None ----
0003 None r-m-
0003 None r-m-
0003 52 ----
1234 18 ----
1234 18 -w-i
1234 18 -w-i
1234 18 ----
[(4660, 18, 'w'), (153, 255, 'w')]
```

`out ($34),a` is an opcode fetch, an operand read and a port write: 11 T states. Each log row is the address on the bus, the value on the data lines or `None`, and four pins in the order RD, WR, MREQ, IORQ, with `-` for inactive. The last two states of the fetch carry the refresh address built from `I` and `R`. `out (c),0` on the Z84C00 then sends `$FF` to port `$0099`, which is the last entry of the port log.

### Registers

`cpu.registers` holds `a`, `f`, `b`, `c`, `d`, `e`, `h`, `l` and the pairs `af`, `bc`, `de`, `hl`; `sp` and `pc`; `ix` and `iy` with their halves `ixh`, `ixl`, `iyh`, `iyl`; the shadow set `af_`, `bc_`, `de_`, `hl_`; `i`, `r`, `iff1`, `iff2` and `im`; the internal pair `wz` with its halves `w` and `z`; and `q`, the latch the corpus records for the flag result of the last instruction. Writes are masked to the register's width.

`Registers(seed=UNSET_SEED)` builds a file on its own. `reset()` does what the RESET pin does to it, `exchange_set()` is `exx` and `exchange_accumulator()` is `ex af,af'`.

```python
from z80 import Registers

held = Registers(seed=7)
print(held)
held.reset()
held.hl = 0x1234
held.exchange_set()
print(f"pc={held.pc:04X} hl={held.hl:04X} hl_={held.hl_:04X} im={held.im} iff1={held.iff1}")
```

```
<Registers pc=1FAC af=A54D hl=BB1D>
pc=0000 hl=724C hl_=1234 im=0 iff1=False
```

### Models and errors

| Name | Is |
|:--|:--|
| `MODELS` | The three `Model` records, keyed by canonical name |
| `Model` | `name`, `aliases`, `summary`, `floating_output`, `carry_rule`, `interrupt_clears_parity`, `verified`, and `build(memory, **options)` |
| `UnknownModelError` | Raised by `Cpu` for a missing model or a name no model goes by. The message lists the three |
| `UnknownShape` | Raised by `Cpu` for a `shape` other than `manual` or `recording` |
| `UnknownCarryRule` | Raised by `Model` for a carry rule other than `zilog` or `nec` |
| `RunLimit` | Raised by `run_until` when `limit` instructions pass and the check never held |
| `Truncated` | Raised by `decode` when the bytes end inside an instruction |
| `ClockClosed` | Raised by `Clock.tick()` after the clock was closed |
| `__version__` | The installed version |

```python
import z80
from z80 import Clock, ClockClosed, Cpu, Model, UnknownCarryRule, UnknownShape

try:
    Cpu("z80", shape="sampled")
except UnknownShape as error:
    print(error)

try:
    Model("z80x", "a part nobody made", 0x00, carry_rule="intel")
except UnknownCarryRule as error:
    print(error)

clock = Clock(Cpu("z80").reset())
clock.run_for(3)
clock.close()
try:
    clock.tick()
except ClockClosed as error:
    print(error, clock.cycles)

print(len(z80.__version__.split(".")))
```

```
sampled is not a pin shape; there are manual, recording
intel is not a carry flag rule; there are zilog, nec
this clock has been closed 3
3
```

### Command-line tools

Every tool runs from the repository root. The conformance tools run as modules.

| Command | Does | Exit codes |
|:--|:--|:--|
| `python3 z80/doctor.py` | Reports the machine, the parts and the corpus | 0 every check passed, 1 one did not |
| `python3 -m conformance.fetch [directory] [--latest]` | Clones the corpus at its pinned commit, or at upstream's head with `--latest`, into `directory`, by default `~/.cache/conformance-suites` | 0 fetched, 1 upstream unreachable or a git step failed |
| `python3 -m conformance.singlestep <suite-directory> [--limit N] [--opcode NAME]` | Compares registers and memory after every case | 0 no failure, 1 a failure or no cases found, 2 bad arguments |
| `python3 -m conformance.cycles <suite-directory> [--limit N] [--opcode NAME] [--shape manual\|recording]` | Compares every T state's address, data and pins. The shape defaults to `recording` | 0 no failure, 1 a failure or no cases found, 2 bad arguments |
| `python3 -m conformance.regenerate <output-directory> [--full] [--clone DIR]` | Rebuilds the corpus from the generator that produced it. Needs `node` | 0 written, the generator's own code if it failed, 1 bad arguments |
| `python3 -m conformance.timing` | Runs every per-instruction timing row in the record and compares the T states | 0 every row agrees, 1 one does not |
| `python3 -m conformance.quotes` | Finds every quoted sentence in the document it cites, on a machine holding the documents | 0 every quote found, 1 one was not |
| `python3 -m conformance.documents [--check] [--only SUBSTRING]` | Downloads the documents that have an address and verifies every digest. `--check` only verifies | 0 every one verified, 1 one refused or bad arguments |
| `python3 -m conformance.netlist [--half-cycles N]` | Runs the transistor netlist from reset for `N` half cycles, 130 by default | 0 every node settled, 1 one did not or a data file is absent |
| `python3 -m conformance.wz [output]` | Reads what the netlist leaves in `WZ` and writes it to `output`, by default [`conformance/wz.json`](conformance/wz.json) | 0 written, 1 netlist absent or the probe uncalibrated |
| `python3 -m conformance.speed [--instructions N] [--repeats N]` | Times `run_for(N)` on a 64 KB image, 200,000 T states over 7 runs by default | 0 at or above 400,000 T states per second, 1 below, 2 bad arguments |
| `python3 -m conformance.links` | Requests every address in this file | 0 every address still exists, 1 one carries status `404` or `410` |
| `python3 -m conformance.package <wheel>` | Checks a built wheel ships every module and no test | 0 clean, 1 a fault or no such file, 2 no argument |

## Running it at a real speed

`step()` reports what an instruction cost, so a host holds the part to its crystal by spending a budget per slice of wall time.

```python
import time

from z80 import Cpu

HERTZ = 3_546_895
SLICE = 0.02

cpu = Cpu("z80")
cpu.reset()
per_slice = round(HERTZ * SLICE)
owed = 0

for _ in range(5):
    began = time.perf_counter()
    owed += per_slice
    owed -= cpu.run_for(owed)
    time.sleep(max(0.0, SLICE - (time.perf_counter() - began)))
```

An instruction cannot be cut in half, so `run_for()` overshoots and returns what it spent. Carrying the overshoot into the next slice keeps a long run from drifting.

## Driving it one T state at a time

`Clock(cpu)` stops the part between any two T states, which is where a board changes what a read will answer.

```python
from z80 import Clock, Cpu, Memory

space = Memory(image=bytes([0x3E, 0x42, 0x00, 0x00, 0x00, 0x00]))
cpu = Cpu("z80", space, recording=True)
cpu.reset()
cpu.registers.pc = 0x0000

with Clock(cpu) as clock:
    clock.tick()
    space.write8(0x0001, 0x99)
    clock.run_for(6)

print(0x99 in [value for _, value, _ in cpu.bus.log])
```

```
True
```

The byte at `$0001` changed after the first T state of the opcode fetch, and the operand read that follows the fetch picked up the new value.

| Call | Does |
|:--|:--|
| `tick()` | Advances one T state and returns the clock's count |
| `run_for(cycles)` | Calls `tick()` `cycles` times and returns the count |
| `close()` | Stops the part and gives `on_cycle` back. Leaving a `with` block calls it |
| `cycles`, `closed` | The count of ticks, and whether the clock is closed |

Iterating a clock ticks it until it is closed. An exception raised inside the part is raised again from `tick()`, and the clock closes.

The part runs on a thread, because Python cannot suspend an instruction's call stack. Each T state is a handoff between two semaphores, so a clock runs many times slower than `step()`. Use `step()` for speed and `Clock` when the question is where a T state falls.

## Models

The instruction set is the same on all three. Three behaviours differ.

| Build it with | Bare `OUT (C)` sends | Undocumented flag bits after `SCF` and `CCF` | Interrupt after `LD A,I` or `LD A,R` clears parity | These three columns measured |
|:--|:--|:--|:--|:--|
| `Cpu("z80")` | `$00` | accumulator and latch | yes, and Zilog documents it | yes, by the corpus |
| `Cpu("z84c00")` | `$FF` | accumulator and latch | no, Zilog fixed it | no, Zilog's own sentence |
| `Cpu("upd780c")` | `$00` | accumulator alone | not stated | no, independent research |

The corpus records the NMOS Z80 only. Everything the other two share with it is measured through it. The three columns that make them different parts are not measured, and `Model.verified` is `False` for both.

Each model answers to the part numbers its makers sold it under. Case, `-` and `_` are ignored, so `Cpu("Z84C00-10")` builds a `z84c00`.

| Build it with | Also answers to |
|:--|:--|
| `Cpu("z80")` | `z8400`, `nmosz80`, `z0840004psc`, `z0840006psc`, `z0840008psc`, `mostekmk3880`, `mk3880`, `mk3880n`, `sharplh0080`, `lh0080`, `lh0080a`, `u880`, `ud880d`, `kr1858vm1`, `t34vm1`, `mme`, `goldstargms z80`, `thesysz80` |
| `Cpu("upd780c")` | `necupd780c`, `d780c`, `d780c1`, `d780c2`, `upd780`, `upd780c1`, `upd780c2` |
| `Cpu("z84c00")` | `cmosz80`, `z80c`, `z8400c`, `z84c0006`, `z84c0008`, `z84c0010`, `z84c0020`, `toshibatmpz84c00`, `tmpz84c00`, `t84c00`, `kr1858vm3` |

```python
import z80

for name, model in z80.MODELS.items():
    floating = f"${model.floating_output:02X}"
    print(name, floating, model.carry_rule, model.interrupt_clears_parity, model.verified)

print(z80.Cpu("Z84C00-10").model, z80.Cpu("mk3880").model)

for asked in (None, "z180"):
    try:
        z80.Cpu(asked)
    except z80.UnknownModelError as error:
        print(error)
```

```
z80 $00 zilog True True
upd780c $00 nec False False
z84c00 $FF zilog False False
z84c00 z80
no model was named, and this package will not choose one for you. Name one of: upd780c, z80, z84c00
z180 is not a model this family covers; it has upd780c, z80, z84c00
```

A part number this package does not implement is refused rather than resolved to something close, so `Cpu("z180")` raises instead of returning a Z80 that lacks the instructions the caller asked for.

## Reading without running

`decode(data, offset=0, address=0)` reads one instruction. `disassemble(data, address=0)` reads all of them. Neither needs a part. Each returns `Instruction` objects with `address`, `size`, `raw` and `text`.

```python
from z80 import Truncated, decode, disassemble

program = bytes([0x3E, 0x42, 0xDD, 0x7E, 0xFE, 0x10, 0xFA, 0xED, 0x71, 0xC3])

for found in disassemble(program, 0x8000):
    print(f"{found.address:04X}  {found.raw.hex(' '):<9} {found.text}")

one = decode(bytes([0xCD, 0x34, 0x12]), address=0x0100)
print(one, one.size)

try:
    decode(bytes([0xCD, 0x34]))
except Truncated as error:
    print(error)
```

```
8000  3e 42     ld a,$42
8002  dd 7e fe  ld a,(ix-$02)
8005  10 fa     djnz $8001
8007  ed 71     out (c),0
8009  c3        db $C3
<0100 call $1234> 3
instruction at 0 runs past the end of the data
```

Relative jumps print their target. `decode` raises `Truncated` when the bytes end inside an instruction. `disassemble` writes the first byte of such an instruction as `db` and carries on.

## Nothing starts clean

Registers and memory power up holding a reproducible scrambled pattern, because a read of a byte nothing wrote is a defect on real silicon and memory that answers zero turns that defect into a passing test. No argument clears the registers. Memory holds a single value only when the caller builds it with `fill`.

```python
from z80 import Cpu, SparseMemory

print(hex(SparseMemory().read8(0x1234)))
print(SparseMemory().read8(0x1234) == SparseMemory().read8(0x1234))

powered = Cpu("z80", SparseMemory())
print(hex(powered.registers.pc), powered.cycles)
```

```
0x84
True
0x8926 0
```

The byte is derived from the seed and the address, so it is the same on every run and is not zero. The program counter is scrambled too, and `cycles` is 0 because nothing has driven RESET yet. Stepping a part before `reset()` executes whatever that address holds.

## Is it right

Every instruction is run against the SingleStepTests corpus, which states each register and each byte of memory before and after: **1,604,000 cases, 0 failures**. A second runner compares what the part put on the bus, T state by T state, address, data and pins: **22,005,372 T states, 0 failures**.

```bash
python3 -m conformance.fetch ~/.cache/conformance-suites
python3 -m conformance.singlestep ~/.cache/conformance-suites/z80/v1
python3 -m conformance.cycles ~/.cache/conformance-suites/z80/v1
```

```
1604000 cases, 0 failed, 0 opcodes affected
1604000 cases, 22005372 T states compared, 0 failed, 0 opcodes affected, 0 opening states skipped, shape recording
```

The corpus commit is pinned in [`conformance/suites.json`](conformance/suites.json), and a weekly job runs against upstream's head and opens a pull request or an issue. Each runner prints how many cases it checked, because a run that parsed nothing exits 0 just like one that checked everything.

The manual is held separately. [`conformance/hardware.json`](conformance/hardware.json) carries every fact taken from a document with its sentence and page, and [`conformance/hardware.test.py`](conformance/hardware.test.py) checks the model's constants and machine cycles against it with no corpus on the machine. `python3 -m conformance.timing` runs all 217 per-instruction timing rows and compares each with the T states the part spends. The manual contradicts itself in five places: three timing rows, on pages 99, 260 and 269, whose M cycle count disagrees with their own T state breakdown, and two where the prose and a figure disagree. Every place where two sources disagree is in [`conformance/divergences.json`](conformance/divergences.json) with what would settle it.

[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) lists the 17 questions where fidelity is a claim rather than a measurement, each with the measurement that would close it. Bits 3 and 5 of the flag register and the internal `WZ` register appear nowhere in the 780 pages of Zilog's user manual and data book.

### Asking the die

[`conformance/netlist.py`](conformance/netlist.py) runs the part as a net of transistors, from a netlist extracted from die photographs. Driven from reset, it fetches from `$0000` and executes a sample program.

```bash
python3 -m conformance.netlist
```

The resolver follows `chipsim.js` and `wires.js` from the Visual 6502 project, which are MIT licensed. Their notice is in [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md). The three data files are not in this repository. [`conformance/netlist.manifest.json`](conformance/netlist.manifest.json) names them, says where they come from and records each digest. Put them in `docs/independent/visual6502`, and a load refuses any file whose digest differs.

The transistor file marks 32 entries as pull-ups, and the net settles only when they load as pull-ups. The doubled net names hold the register set an instruction writes and the single-letter ones hold the shadow set, which `LD r,n` across every register and every bit position shows.

Nothing in the package is held to the netlist. It ranks below the manufacturer's documents and below a recording from a real part, because a netlist is an extraction and an extraction can be wrong.

## Working on it

| Need | Where |
|:--|:--|
| Every gate and the order to run them | [CONTRIBUTING.md](CONTRIBUTING.md) |
| The same material for a coding agent | [AGENTS.md](AGENTS.md) |
| The standard this repository shares with the rest of the family | [FAMILY.md](FAMILY.md) |
| Bug reports | [GitHub Issues](https://github.com/gufranco/zilog-z80-python/issues) |
| Security reports | [SECURITY.md](SECURITY.md) |

```bash
uvx ruff@0.16.3 format --check .
uvx ruff@0.16.3 check .
uvx --python 3.12 mypy==1.14.1
python3 -m coverage erase
for file in $(find z80 conformance -name '*.test.py' | sort); do
  python3 -m coverage run -a "$file"
done
python3 -m coverage report
python3 -m conformance.speed
```

Each module has a test file beside it, named `<module>.test.py`, and each runs on its own. Coverage is a hard gate at 100% statement and branch. Types are `mypy` at strict. The speed check fails below 400,000 T states per second and runs outside the coverage step. Commits follow [Conventional Commits](https://www.conventionalcommits.org/).

## References

This repository carries no documents. Each row gives the page count and the first sixteen characters of the file's SHA-256, so a reader can fetch the same file and check the same page. Compute the full digest with `shasum -a 256 <file>`.

Every manufacturer document below is copyrighted and not redistributable. Individual sentences are quoted in [`conformance/hardware.json`](conformance/hardware.json) with the page they came from.

| Document | Date | Pages | SHA-256 | Redistributable |
|:---------|:-----|------:|:--------|:----------------|
| [Zilog, *Z80 CPU User Manual*, UM008011-0816](https://www.zilog.com/docs/z80/um0080.pdf) | 2016-08 | 332 | `e3c83da5a5d8e372…` | No |
| Zilog, *Z80 Family Data Book*, 00-2490-01 | 1989-01 | 448 | `844681b63ffc45bd…` | No |
| Zilog, *Z84C00 Product Specification*, PS017801-0602 | undated | 36 | `06198d3c22a79a3f…` | No |
| NEC, *µPD780C* data sheet | undated | 24 | `2036fa845533feee…` | No |

Independent research is used only where two lineages that never consulted each other agree, and never as a citation for a figure a manufacturer gave.

| Document | Author | Pages | SHA-256 | Licence |
|:---------|:-------|------:|:--------|:--------|
| [*The Undocumented Z80 Documented*, v0.91](https://archive.org/details/the-undocumented-z80-documented) | Sean Young, 2005-09-18 | 52 | `6413048f39c2e735…` | GFDL 1.1 or later |
| [*Z80 CCF SCF Outcome Stability*](https://github.com/redcode/Z80/wiki/Z80-CCF-SCF-Outcome-Stability) | Sainz de Baranda y Goñi, Brewer, Helcmanovsky | 4 | `be87311012f9edaf…` | GFDL 1.3 |
| *Undocumented Z80 Flags*, rev 1.0 | David Banks, 2018-08-21 | 3 | `33766df5494e2fdf…` | None stated |
| *MEMPTR, esoteric register of the ZiLOG Z80 CPU* | Boo-boo, trans. Vladimir Kladov | text | `f9e8e87cdd205e15…` | None stated |
| [redcode/Z80 wiki: Interrupts](https://github.com/redcode/Z80/wiki/Interrupts) and [MEMPTR](https://github.com/redcode/Z80/wiki/MEMPTR) | Sainz de Baranda y Goñi and contributors | web | n/a | GFDL 1.3 |

| Source | Used for |
|:-------|:---------|
| [SingleStepTests/z80](https://github.com/SingleStepTests/z80.git) | The pinned corpus, 1,604,000 cases. Commit in [`conformance/suites.json`](conformance/suites.json) |
| [raddad772/jsmoo](https://github.com/raddad772/jsmoo.git) | The generator that produced it, so it can be rebuilt rather than only downloaded |
| [gdevic/Z80Explorer](https://github.com/gdevic/Z80Explorer) | The netlist whose behaviour is recorded in [`conformance/divergences.json`](conformance/divergences.json) |

[`conformance/documents.json`](conformance/documents.json) carries the full digest and byte count of each document. [`conformance/documents.py`](conformance/documents.py) downloads into `docs/`, which git ignores, and refuses any file whose digest does not match.

```bash
python3 -m conformance.documents
python3 -m conformance.documents --check
```

Two of the eight documents carry an address and are downloaded. The other six were printed from a web page, so the command verifies a copy you supply and never replaces it.

The MEMPTR paper is pinned above as text. The copy in `docs/` is a print of the same writing, so the two digests differ, and checking one against the other's digest reports a mismatch that means nothing.

## Citing this

[CITATION.cff](CITATION.cff) is updated with each release by the script that stamps the package version. GitHub renders it as a Cite this repository button.

## License

MIT. See [LICENSE](LICENSE).
