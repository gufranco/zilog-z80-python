<div align="center">

<h1>Zilog Z80</h1>

<strong>A Z80 you can drive from a clock, held to Zilog's own manual for the shape of every machine cycle and to a per-opcode suite for every T state of every opcode.</strong>

<br>
<br>

[![CI](https://github.com/gufranco/zilog-z80-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/zilog-z80-python/actions/workflows/ci.yml)
[![Conformance](https://img.shields.io/badge/conformance-1%2C604%2C000%20%2F%201%2C604%2C000-brightgreen)](#is-it-right)
[![Cycles](https://img.shields.io/badge/T%20states-22%2C005%2C372%20compared-brightgreen)](#is-it-right)
[![Coverage](https://img.shields.io/badge/coverage-100%25%20statement%20%2B%20branch-brightgreen)](#working-on-it)
[![Types](https://img.shields.io/badge/mypy-strict-blue)](pyproject.toml)
[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

</div>

**3** parts · **1,604,000** conformance cases and **22,005,372** T states compared, **0** failures · **783** tests · **100%** statement and branch coverage · no dependencies

```python
from z80 import Cpu, Memory

cpu = Cpu("z80", Memory(image=bytes([0x3E, 0x42, 0x47])))
cpu.reset()
cpu.registers.pc = 0x0000

cpu.step()
cpu.step()

print(f"{cpu.registers.b:02X}")
```

```
42
```

## Install

```bash
pip install git+https://github.com/gufranco/zilog-z80-python.git
```

Python 3.12 or newer. Nothing else.

## The interface

Everything a caller touches. Nothing else is public.

| Call | Does | Returns |
|:--|:--|:--|
| `Cpu(model="z80", memory=None, **options)` | Builds a part, powered and not yet reset. Memory of its own if none is given | a `Cpu` |
| `cpu.reset()` | Drives RESET. Costs the three T states Zilog names as the minimum the pin must be held | the `Cpu` |
| `cpu.step()` | Runs one instruction | T states it cost |
| `cpu.run_for(cycles)` | Runs whole instructions until at least that many T states have passed | T states actually spent, usually a little over |
| `cpu.run_until(check, limit=None)` | Steps while `check(cpu)` is false. `limit` bounds the instructions and raises `RunLimit` | the `Cpu` |
| `cpu.held()` | Whether the part has stopped advancing the program | `bool` |
| `cpu.irq(vector=0xFF)` / `cpu.nmi()` | Offers a line and acts on it now. `vector` may be a callable, which is how a device supplies an instruction longer than one byte in mode zero | `True` if taken / nothing |
| `disassemble(data, address)` | Reads bytes with no machine to run them in | `Instruction` objects with `.text` |
| `describe(model)` | The part behind a name, before building one | a `Model` |

| Pin or attribute | Is |
|:--|:--|
| `cpu.irq_line` | The request line as a level. Read at the final T state of an instruction, where the manual says the part reads it, so a request withdrawn before then is not taken |
| `cpu.nmi_line` | The non-maskable line. Edge sensitive: the transition interrupts, and holding it afterwards does not interrupt again |
| `cpu.wait_line` | Memory asking for more time. Read after T2 of each machine cycle, and every state it adds repeats T2 |
| `cpu.cycles` / `cpu.steps` | T states since construction, across resets; instructions since the last reset |
| `cpu.halted` | Whether a `HALT` is being executed, which still costs four T states a time |
| `cpu.registers` | `a`, `f`, `b`, `c`, `d`, `e`, `h`, `l` and the pairs `af`, `bc`, `de`, `hl`; `sp`, `pc`, `ix`, `iy` with their halves; the shadow set as `af_`, `bc_`, `de_`, `hl_`; `i`, `r`, `iff1`, `iff2`, `im`; and `wz` and `q`, the two nobody documents |
| `cpu.bus` | The T states of the last instruction, and the recorded cycles when `recording=True` |
| `cpu.on_cycle` | Called once per T state, after that state's bus activity |

Options: `seed=` fixes the undefined state, `recording=True` keeps a bus log, `shape=` picks which edge a pin is read on, `ports=` takes an I/O bus.

**A part arrives powered, not reset**, because no board hands over one that has reset itself. Every register holds rubbish derived from the seed, the program counter included, so stepping it executes rubbish from a rubbish address. Call `reset()` to get a machine that runs a program.

## Running it at a real speed

A part runs at whatever its crystal says. `step()` reports what an instruction cost, so a host can hold the part to a real clock.

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

An instruction cannot be cut in half, so `run_for()` overshoots and returns what it really spent. Carrying the overshoot into the next slice is what stops a long run drifting.

## Driving it one T state at a time

`Clock` stops the part between any two T states, which is where a board changes what a read will answer.

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

The instruction picked up a byte written after it had already begun. That is real suspension rather than a replay, and it is what makes the three pins above mean anything.

It is not free. An instruction is an ordinary call stack and Python cannot suspend one, so the clock runs the part on a thread and lets it block where the T state is spent, which is what ares and bsnes do. Expect roughly fifty times slower than `step()`. Use `step()` for speed and `Clock` when the question is where a T state falls.

## Models

The instruction set never changed. Three things did, all undocumented or defective, which is why software that depended on any of them had to know which board it was on.

| Build it with | Bare `OUT (C)` sends | Carry flag bits | Interrupt clears parity | These three columns measured |
|:--|:--|:--|:--|:--|
| `Cpu("z80")` | nothing | accumulator and latch | yes, and Zilog documents it | yes, by the corpus |
| `Cpu("z84c00")` | every bit | accumulator and latch | no, Zilog fixed it | no, Zilog's own sentence |
| `Cpu("upd780c")` | nothing | accumulator alone | not stated | no, independent research |

The last column is narrow on purpose. One corpus exists, for the NMOS part, and everything the other two share with it is measured through it. What is not measured is the handful of behaviours that make them different parts, which is the three columns before it.

Each answers to the numbers its manufacturer sold it under. Case and separators do not matter.

| Build it with | Also answers to |
|:--|:--|
| `Cpu("z80")` | `z8400`, `nmosz80`, `z0840004psc`, `z0840006psc`, `z0840008psc`, `mostekmk3880`, `mk3880`, `mk3880n`, `sharplh0080`, `lh0080`, `lh0080a`, `u880`, `ud880d`, `kr1858vm1`, `t34vm1`, `mme`, `goldstargms z80`, `thesysz80` |
| `Cpu("upd780c")` | `necupd780c`, `d780c`, `d780c1`, `d780c2`, `upd780`, `upd780c1`, `upd780c2` |
| `Cpu("z84c00")` | `cmosz80`, `z80c`, `z8400c`, `z84c0006`, `z84c0008`, `z84c0010`, `z84c0020`, `toshibatmpz84c00`, `tmpz84c00`, `t84c00`, `kr1858vm3` |

A part number nothing here implements is refused rather than resolved to something close, so `Cpu("z180")` raises `UnknownModelError` instead of handing back a Z80 missing instructions the caller asked for.

## Reading without running

A survey of a ROM has nothing but the file, so reading and running are separate halves.

```python
from z80 import disassemble

for found in disassemble(bytes([0x3E, 0x42, 0x47, 0xC9]), 0x8000):
    print(f"{found.address:04X}  {found.text}")
```

```
8000  ld a,$42
8002  ld b,a
8003  ret
```

A run of bytes too short to complete its instruction raises `Truncated` rather than returning a guess.

## Nothing starts clean

Memory and registers hold a reproducible scrambled pattern. There is no parameter that clears them and there will not be one: a read of a byte nothing wrote is a defect on real silicon, and memory that answers zero turns that defect into a passing test.

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

A byte derived from the address, the same every time, and not zero. The part has spent nothing because nothing has driven RESET yet.

## Is it right

Every instruction is checked against a published per-opcode suite that states each register and each byte of memory before and after: **1,604,000 cases, no failures**. The comparison then goes further and checks what the part put on the bus, T state by T state, address by address, pin by pin: **22,005,372 T states, no failures**.

```bash
python conformance/fetch.py ~/.cache/conformance-suites
python conformance/singlestep.py ~/.cache/conformance-suites/z80/v1
python conformance/cycles.py ~/.cache/conformance-suites/z80/v1
```

The suite commit is pinned so a build is reproducible, and a weekly job runs against whatever upstream holds now and opens a pull request or an issue. A runner reports what it checked rather than a bare pass, because a run that parsed nothing and found no failures exits zero and looks identical to one that checked everything.

Where the manual and the recordings disagree, both are kept. [`conformance/hardware.json`](conformance/hardware.json) holds every fact taken from a document with the sentence it came from and the page. [`conformance/divergences.json`](conformance/divergences.json) holds every place two sources part, with what would settle it. That reading found four places where the manual contradicts itself, three of them in its own timing tables.

**Seventeen questions remain** where being faithful is a claim rather than a measurement, and each names the measurement that would close it: [`OPEN-QUESTIONS.md`](OPEN-QUESTIONS.md). Some cannot be closed by anyone. Bits 3 and 5 of the flag register have gone undocumented through eleven revisions in forty years, and the internal register the recordings call `WZ` appears nowhere in 780 pages of Zilog's own paper.

## Working on it

```bash
python -m coverage erase
for file in $(find z80 conformance -name '*.test.py' | sort); do
  python -m coverage run -a "$file"
done
python -m coverage report
```

Tests sit beside the module they cover, named `<module>.test.py`. Coverage is 100% of statements and branches, enforced. Types are `mypy` at strict. Commits follow [Conventional Commits](https://www.conventionalcommits.org/), and releases are cut by [semantic-release](https://semantic-release.gitbook.io/).

[`AGENTS.md`](AGENTS.md) is the document for an agent working here. [`FAMILY.md`](FAMILY.md) is the standard this repository shares with [mos65xx-python](https://github.com/gufranco/mos65xx-python), kept identical in both.

```
z80/
  core.py          the processor
  bus.py           machine cycles, and the pins each T state carries
  clock.py         driving it one T state at a time
  models.py        the three parts, by name and alias
  memory.py        memory that holds what it held
  opcodes.py       the opcode table and a disassembler
  registers.py     the register file, shadow set included
conformance/
  suites.json      which corpus, at which commit
  singlestep.py    running it, state by state
  cycles.py        running it, T state by T state
  hardware.json    what Zilog printed, fact by fact
  divergences.json where sources part
```

## References

This repository carries no documents. Every claim is traced to something published elsewhere, listed here so a reader can fetch the same file and check the same page. Each row gives the page count and the first sixteen characters of the file's SHA-256, because vendor links move and a link that has rotted into a different revision is easy to follow without noticing. Compute the full digest with `shasum -a 256 <file>`.

Every manufacturer document below is copyrighted and not redistributable, which is why none is in this repository. Individual sentences are quoted in [`conformance/hardware.json`](conformance/hardware.json) with the page they came from.

| Document | Date | Pages | SHA-256 | Redistributable |
|:---------|:-----|------:|:--------|:----------------|
| [Zilog, *Z80 CPU User Manual*, UM008011-0816](https://www.zilog.com/docs/z80/um0080.pdf) | 2016-08 | 332 | `e3c83da5a5d8e372…` | No |
| Zilog, *Z80 Family Data Book*, 00-2490-01 | 1989-01 | 448 | `844681b63ffc45bd…` | No |
| Zilog, *Z84C00 Product Specification*, PS017801-0602 | undated | 36 | `06198d3c22a79a3f…` | No |
| NEC, *µPD780C* data sheet | undated | 24 | `2036fa845533feee…` | No |

Independent research, used only where two lineages that never consulted each other agree, and never as a citation for a figure a manufacturer gave.

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

## License

[MIT](LICENSE)
