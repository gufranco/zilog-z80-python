<div align="center">

<h1>Zilog Z80</h1>

<strong>A cycle-accurate Z80, held to Zilog's own user manual for the shape of every machine cycle and to a per-opcode suite for every T state of every opcode.</strong>

<br>
<br>

[![CI](https://github.com/gufranco/zilog-z80-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/zilog-z80-python/actions/workflows/ci.yml)
[![Conformance](https://img.shields.io/badge/conformance-1%2C604%2C000%20%2F%201%2C604%2C000-brightgreen)](#conformance)
[![Cycles](https://img.shields.io/badge/T%20states-22%2C005%2C372%20compared-brightgreen)](#cycle-by-cycle)
[![Manual](https://img.shields.io/badge/Zilog-UM008011--0816-brightgreen)](#where-each-answer-comes-from)
[![Coverage](https://img.shields.io/badge/coverage-100%25%20statement%20%2B%20branch-brightgreen)](#running-the-tests)
[![Types](https://img.shields.io/badge/mypy-strict-blue)](pyproject.toml)
[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

</div>

<p align="center">
  <a href="#quick-start">Quick start</a> &nbsp;|&nbsp;
  <a href="#conformance">Conformance</a> &nbsp;|&nbsp;
  <a href="#cycle-by-cycle">Cycle by cycle</a> &nbsp;|&nbsp;
  <a href="#where-each-answer-comes-from">Where answers come from</a> &nbsp;|&nbsp;
  <a href="#the-three-registers-nobody-documents">Hidden state</a> &nbsp;|&nbsp;
  <a href="#models">Models</a> &nbsp;|&nbsp;
  <a href="https://github.com/gufranco/zilog-z80-python/issues">Issues</a>
</p>

**3** parts · **1,604,000** conformance cases, **0** failures · **22,005,372** T states compared, **0** failures · **668** tests · **100%** statement and branch coverage

```python
from z80 import Cpu

cpu = Cpu("z80")
cpu.step()
```

## Quick start

### Prerequisites

| Tool | Version | Install |
|:-----|:--------|:--------|
| Python | 3.12 or newer | [python.org](https://www.python.org/downloads/) |

### Install

```bash
pip install git+https://github.com/gufranco/zilog-z80-python.git
```

### Run something

```python
from z80 import Cpu, SparseMemory

space = SparseMemory()
for offset, value in enumerate([0x3E, 0x42, 0x47]):
    space.write8(0x8000 + offset, value)

cpu = Cpu("z80", space)
cpu.registers.pc = 0x8000
cpu.step()
cpu.step()

print(f"{cpu.registers.b:02X}")
```

```
42
```

### Run it at a real speed

A part does not run at "as fast as the host manages". It runs at whatever its
crystal says, and every instruction costs a known number of T states. `step()`
returns what the instruction it ran cost, `cycles` is the running total, and
`run_for()` spends a budget of them so a host can hold the part to a real clock.

```python
import time

from z80 import Cpu

HERTZ = 3_546_895
SLICE = 0.02

cpu = Cpu("z80")
per_slice = round(HERTZ * SLICE)
owed = 0

for _ in range(5):
    began = time.perf_counter()
    owed += per_slice
    owed -= cpu.run_for(owed)
    time.sleep(max(0.0, SLICE - (time.perf_counter() - began)))

print(cpu.cycles)
```

An instruction is not divisible, so `run_for()` almost always overshoots its
budget slightly and returns what it really spent. Carrying that overshoot into
the next slice, rather than throwing it away, is what stops a long run drifting
away from the wall clock.

### Watching every cycle, and driving them one at a time

`step()` runs a whole instruction because that is the unit a program is written
in. A board has no such unit. Two things are offered for callers that need the
smaller one.

`on_cycle` is called once per cycle, after that cycle's bus activity. Every cycle
the part runs passes through one place, so a counter and a watcher cannot come
apart, and a watcher sees the cycles that touch no memory as well as the ones
that do.

```python
from z80 import Cpu, Memory

cpu = Cpu("z80", Memory(image=bytes([0x00])))
cpu.reset()
cpu.registers.pc = 0

watched = []
cpu.on_cycle = lambda: watched.append(cpu.cycles)

cpu.step()
print(watched)
```

```
[4, 5, 6, 7]
```

`Clock` goes further and suspends the part between any two cycles, which is what
a board does when a device changes what a read will answer part way through an
instruction.

```python
from z80 import Clock, Cpu, Memory

space = Memory(image=bytes([0x3E, 0x42, 0x00, 0x00, 0x00, 0x00]))
cpu = Cpu("z80", space, recording=True)
cpu.reset()
cpu.registers.pc = 0

with Clock(cpu) as clock:
    clock.tick()
    space.write8(0x0001, 0x99)
    clock.run_for(6)

print(0x99 in [value for _, value, _ in cpu.bus.log])
```

```
True
```

Note the difference from the part's own `run_for`, which spends whole
instructions and overshoots because an instruction cannot be cut in half. A
clock stops exactly where it is told, including mid-instruction.

The cost is real. An instruction is an ordinary call stack, and Python cannot
suspend one of those, so `Clock` runs the part on a thread of its own and lets it
block where a cycle is spent. That is the approach ares and bsnes take, and it
keeps every instruction written the way it reads now. A cycle costs a pair of
handoffs between two threads, so this is far slower than `step()`. Use `step()`
for speed and `Clock` when the question is where a cycle falls.

One thing to know: `tick()` returns once that cycle's bus activity is done, but
a register the instruction is about to write lands on the next resume. A board
cannot see a register mid-instruction either, so this matters for reading state
in a debugger rather than for fidelity.


### Read it back

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

## What this is

| | |
|:--|:--|
| **Held to an oracle** | Every instruction is checked against a published suite that states each register and each byte of memory before and after, for one thousand cases across each of one thousand six hundred and four opcode sequences. Where the model and the suite disagree, the suite is right. |
| **Decoded, not tabulated** | The core walks the opcode's bit fields the way the silicon does, so several hundred instructions come from one page of dispatch rather than from a table nobody can proofread. |
| **Nothing starts clean** | Memory and registers hold what they held. A model that starts at zero hides the class of bug that only appears on real hardware, where an unwritten byte is whatever the board powered up with. |
| **The undocumented parts too** | The two flag bits the datasheet leaves blank, the internal address register that only two instructions reveal, and the latch that records whether the previous instruction wrote the flags at all. |

## The whole interface

Everything a caller touches, in one place. Nothing else is public.

| Call | Does | Returns |
|:--|:--|:--|
| `Cpu(model="z80", memory=None, **options)` | Builds a part. Memory of its own if none is given, scrambled rather than cleared | a `Cpu` |
| `cpu.step()` | Runs one instruction | T states it cost |
| `cpu.run_for(cycles)` | Runs whole instructions until at least that many T states have passed | T states actually spent, usually a little over |
| `cpu.run_until(predicate, limit=None)` | Steps while `predicate(cpu)` is false. `limit` bounds the instructions and raises `RunLimit` | the `Cpu` |
| `cpu.reset()` | Drives RESET. The T state tally survives, because a clock does not rewind | the `Cpu` |
| `cpu.irq(vector=0xFF)` | Offers the maskable line with the byte the device puts on the bus | `True` if taken |
| `cpu.nmi()` | Offers the line no flag defends against | nothing, because the part cannot refuse |
| `disassemble(data, address)` | Reads bytes without a machine to run them in | `Instruction` objects with `.text` |
| `describe(model)` | The part behind a name, before building one | a `Model` |

| Attribute | Is |
|:--|:--|
| `cpu.cycles` | T states since construction, across resets |
| `cpu.steps` | instructions since the last reset |
| `cpu.halted` | whether a `HALT` is being executed, which still costs four T states a time |
| `cpu.registers` | `a`, `f`, `b`, `c`, `d`, `e`, `h`, `l` and the pairs `af`, `bc`, `de`, `hl`; `sp`, `pc`, `ix`, `iy` with their halves; the shadow set as `af_`, `bc_`, `de_`, `hl_`; `i`, `r`, `iff1`, `iff2`, `im`; and `wz` and `q`, the two nobody documented |
| `cpu.bus` | the T states of the last instruction, and the recorded cycles when `recording=True` |
| `cpu.memory`, `cpu.ports` | what was handed in, or what was made |

**A part arrives powered, not reset.** There is no option to skip that and no
option to start clean, because no board offers one. Every register holds rubbish
derived from the seed, the program counter included, and nothing has been spent
because nothing has driven RESET yet. Stepping it executes rubbish from a rubbish
address, which is what the silicon does. Call `reset()` to get a machine that
runs a program: it sets only what a reset defines, leaves the working registers
holding what they held, and costs the three T states Zilog names as the minimum
the pin must be held for.

Options to `Cpu`: `seed=` fixes the undefined state. `recording=True` to keep a bus log, `shape=` to pick which
edge a pin is read on. `ports=` takes an I/O bus, which is a separate space on
this part.

## Conformance

The suite is the definition of correct. It is not written by this project and it
does not agree with any particular reading of a datasheet: it was produced from
hardware, and it states outcomes rather than intentions.

| Measure | Value |
|:--------|:------|
| Opcode sequences | 1,604 |
| Cases per sequence | 1,000 |
| Cases run | 1,604,000 |
| Failures | 0 |
| Source | [SingleStepTests/z80](https://github.com/SingleStepTests/z80) |

Run it yourself:

```bash
python conformance/fetch.py ~/.cache/conformance-suites
python conformance/singlestep.py ~/.cache/conformance-suites/z80/v1
```

```
1604000 cases, 0 failed, 0 opcodes affected
```

The suite is pinned by commit, so a run is reproducible and an upstream change
cannot turn this repository red without a commit of its own explaining it. A
weekly job fetches whatever upstream holds now, runs the whole suite against it,
and opens a pull request proposing the newer pin only when every case still
passes.

### What the suite caught

Each of these was a defect in this model that no amount of reading would have
found, because in every case the datasheet either says nothing or says something
that is not what the part does.

| Disagreement | What the part actually does |
|:-------------|:----------------------------|
| Two instructions swapped | `LD I,A` and `LD A,I` sit at opcodes that look transposed and are not |
| Return from interrupt | Both forms restore the interrupt enable, though only one is documented as doing so |
| Bit test against memory | Takes its hidden flags from an internal register, not from the byte tested |
| Set and complement carry after an index prefix | The prefix clears the flag-written latch, which changes where the hidden bits come from |
| Repeating block transfers | Revise the half carry and the parity they just computed, using the counter one step further along |
| Repeating anything, across a page boundary | Reports the hidden bits from the address it resumes at, not the byte after it |

The last one appeared in two cases out of four thousand. Both sat on a page
boundary, which is the only place the two candidate rules differ.

## Cycle by cycle

The state comparison above asks what an instruction left behind. This asks what
the part did while producing it: the address, the value, and which of the four
control pins were asserted, for every T state.

The two are not interchangeable. A core can spend the right number of cycles
doing the wrong thing, and no comparison of registers and memory will show it.

| Measure | Value |
|:--------|:------|
| Cases | 1,604,000 |
| T states compared | 22,005,372 |
| Failures | 0 |
| Opcode forms cycle-exact | 1,604 of 1,604 |

```bash
python conformance/cycles.py ~/.cache/conformance-suites/z80/v1
```

```
1604000 cases, 22005372 T states compared, 0 failed, 0 opcodes affected
```

### What the bus caught that the state could not

**A push wrote the low half of the pair first.** The part writes the high half
first, at one below the stack pointer, then the low half at two below. Both
orders touch the same two addresses and leave identical final state, so the state
comparison passed it for as long as it existed. The bus comparison found it on
the first run.

That is the whole argument for this gate in one defect.

### What a cycle claim here does and does not mean

The shape of each machine cycle is Zilog's. A fetch is four T states with the
refresh address replacing the counter for the last two, a memory access is three,
an input or output is four because "During I/O operations, a single wait state is
automatically inserted". Those figures are pinned in
[`conformance/hardware.json`](conformance/hardware.json) with the sentence each
came from, and
[`conformance/hardware.test.py`](conformance/hardware.test.py) assembles fifty-four
documented instructions, steps them, and checks the T states spent against the
figure printed for that instruction, naming the manual page rather than repeating
the number. That check needs no suite on the machine.

### What a flag claim here does and does not mean

Every instruction page in the manual ends with a Condition Bits Affected block.
Most of those blocks say something conditional, "Z is set if the result is zero",
which only a model of the instruction can check. A hundred and twenty six of them
say something absolute instead: this flag is set, this one is reset, this one is
untouched, whatever the inputs were. Those hundred and twenty six are pinned in
[`conformance/instruction-flags.json`](conformance/instruction-flags.json) with
the line each came from, and
[`conformance/instruction_flags.test.py`](conformance/instruction_flags.test.py)
runs every one of them against forty states.

A hundred and twenty four hold. The two that do not are recorded rather than
quietly followed:

- The eight block input and output instructions. The manual says the negate flag
  is set and the carry is not affected. Both are wrong on every part anyone has
  measured, and the corpus fixes different values on every case. The rule this
  package implements comes from independent research and is in
  [`conformance/divergences.json`](conformance/divergences.json) with what would
  settle it.
- Two of the four pages of `BIT`. They print the half carry twice, once set and
  once reset, and never print the negate flag at all. The other two pages print
  the negate flag in the position where these print the second half carry. It is
  a wrong letter rather than a different instruction, and it is recorded as a
  contradiction inside the document rather than as a disagreement with anything
  outside it.


### Two shapes, because one column cannot hold half a clock

Every control pin edge in the manual falls on a clock edge, which is half a T
state. A model whose smallest column is a whole T state has to pick a rule for
turning a waveform into a column, and the manual states no such rule. So there
are two shapes and both are named.

`bus.MANUAL` is the default. Its rule is stated rather than implied: a pin
belongs to a T state when it went active before the clock edge that ends that
state and had not yet gone inactive at it. That names a real instant, and it is
insensitive to the slew every edge in a drawing carries, which a rule asking
whether a pin was asserted at any point during the state is not. The edges it is
applied to were measured off the pages of the pinned document rendered at 200
dpi, and every one of them is in
[`conformance/hardware.json`](conformance/hardware.json) under `figureEdges`, so
a reader can apply a different rule without opening the PDF. The rule that was
not chosen is recorded there too, with the columns it gives instead.

`bus.RECORDING` draws one strobe per transfer, which is what the pinned corpus
contains and what its own generator describes as a deliberate simplification.
Only [`conformance/cycles.py`](conformance/cycles.py) asks for it, so the corpus
still checks this core cycle for cycle without either shape being bent to fit the
other.

It is also not only this package's reading. The corpus generator has a flag that
widens the data strobes to what the figures draw, and a corpus regenerated with
it on carries exactly these columns for a read, a write, a port read and a port
write, from an implementation that read the same figures independently:

```bash
python3 conformance/regenerate.py ~/.cache/z80-full --full
python3 conformance/cycles.py ~/.cache/z80-full --shape manual
```

That reports 7,000 differences across 1,610,000 cases, which is every case of
seven opcodes and no case of any other, and all seven are opcodes where the
generator's current commit already disagrees with the pinned corpus about
behaviour Zilog never printed. It skips one state per fetch and per read, because
the generator writes that column idle without consulting the flag that widens
every other strobe, and it prints how many it skipped, so a run that checked less
than it looks like says so.

Running the generator without `--full` rebuilds the published corpus instead.
1,593 of its 1,604 files come out byte for byte identical; the eleven that do
not are the same seven plus four where only the two undocumented flag bits
differ. That is how those eleven were found, and it is why the generator is
pinned by commit next to the corpus rather than merely credited.

Measuring the figures rather than reading the prose turned up three things the
prose does not give. A memory read outside a fetch holds its strobes half a clock
longer than a fetch does, which the summary on manual page 9 flatly denies and
which prose on page 23 confirms. A port cycle does not start where a memory cycle
starts: its strobes wait for the rising edge of T2 rather than falling half a
clock into T1, so it leaves its first state bare and strobes the other three. And
an interrupt acknowledge is seven T states rather than the six a four state fetch
plus two waits would give, which is the only reading that makes the manual's own
printed totals for mode 1 and mode 2 come out right.

One detail of the pin encoding is the suite's rather than Zilog's, and its own
generator documents it: it puts the refresh value on all sixteen address pins
where the manual guarantees only seven.
[`conformance/divergences.json`](conformance/divergences.json) records it,
quoting the generator admitting it. **This core draws the columns the manual's
own edges give under a stated rule, and reproduces the recorded bus exactly when
asked for the recorded shape. Neither is a measurement of silicon, and the
difference is written down rather than glossed.**

## Where each answer comes from

| Rung | Source | Settles |
|:-----|:-------|:--------|
| 1 | [Zilog, *Z80 CPU User Manual* UM008011-0816](conformance/hardware.json) | Anything Zilog printed: pin function, machine cycle shape, T states per instruction, what reset does, which bit of the flag register is which |
| 2 | The pinned suite | What the manual does not: the two undocumented flag bits, the internal `WZ` register, the `Q` latch, every opcode the manual does not list, and where the idle states sit inside a long machine cycle |
| 3 | [The independent research](conformance/independent.json), listed under References below | Nothing on its own. It is never a citation for a figure a manufacturer gave. It is kept because where two lineages that never consulted each other agree, the agreement is worth checking against |

### The manual contradicts itself in four places

Its M Cycles column disagrees with its own T states breakdown on pages 99, 260
and 269. `LD dd,nn` is printed as two machine cycles of `10 (4, 3, 3)`; three
groups cannot be two machine cycles. `RES r` is printed as four of `8 (4, 4)`.
`JR NC,e` not taken is printed as seven of `7 (4, 3)`, where the M Cycles column
has plainly been copied from the T States column beside it.

All three were found mechanically, by checking every one of the 184 timing rows
twice: that its breakdown sums to its total, and that the number of groups equals
the M Cycles column. The first check passes everywhere. The second fails on
exactly those three, and each was then read off the rendered page image to
confirm the document really prints it rather than the extraction having damaged
it.

The breakdown wins, and the reason is recorded rather than assumed: it is
internally consistent on all 184 rows, and a summary column is written last and
reviewed least.

**The tables in that PDF have an unreliable text layer.** The prose extracts
cleanly and the large opcode maps do not, so anything numeric was read off the
page image.

The fourth is not a misprint but a summary that its own figures do not support.
Manual page 9 says the memory request and read signals of a plain read "are used
the same way as in a fetch cycle". Figure 5 releases them on the rising edge of
T3, so that the refresh address can take the bus; Figure 6 releases them half a
clock later, because a plain read has no refresh address waiting. Prose on page
23 settles it in the figures' favour without mentioning the contradiction:
"Memory access time requirements ... are most severe during the M1 cycle
instruction fetch. All other memory access cycles complete in an additional one
half clock cycle."

### The interrupt lines

Both are offered rather than raised, because the manual samples them between
instructions: the part "samples the interrupt signal (INT) with the rising edge
of the final clock at the end of any instruction".

```python
from z80 import Cpu

cpu = Cpu("z80")

cpu.irq(0xFF)  # the maskable line, with the byte the device puts on the bus
cpu.nmi()  # the other one, which is always taken
```

`irq` reports whether the part took it, and refuses while the enable flip flop is
clear or for one instruction after an enable, which is the delay that exists so
an enable followed by a return is not interrupted between the two. `nmi` reports
nothing, because the part has no way of refusing it.

Offering them only between steps is less of a restriction than it sounds. A
repeating block instruction is one step per iteration here, exactly as it is one
machine cycle group per iteration on the part, which backs the counter up by two
rather than looping internally. An interrupt offered between iterations therefore
pushes the address of the instruction itself, and the service routine returns to
an instruction that carries on where it left off.

The four responses cost 13, 13, 19 and 11 T states, and not one of those numbers
is written down in this package. The bus spends them and
[`conformance/hardware.test.py`](conformance/hardware.test.py) compares what was
spent against what the manual prints. Two of the four the manual prints outright.
The other two it gives only as arithmetic: mode 1 is a restart taking "two more
than normal", and the nonmaskable line makes the part function "as if it had
recycled a restart instruction".

That arithmetic is what makes an interrupt acknowledge seven T states rather than
six. Reading the manual's "Two wait states are automatically added" as two added
to an ordinary four state fetch gives six, and six makes the printed mode 2 total
eighteen against a printed nineteen. The M1 underneath those waits is the five
state kind a restart already has.

### A halted part is not an idle one

It keeps performing fetch cycles, and the manual says why: "The purpose of
executing NOP instructions while in the HALT state is to keep the memory refresh
signals active." A halted step here spends a whole four state fetch with the pins
of one. Which address it carries is the part the manual does not settle, and that
is recorded rather than decided quietly.

## The three registers nobody documents

A Z80 that runs software correctly and a Z80 that is right differ in three
places, all of them invisible until something looks.

**The two blank flag bits.** Bits three and five of the flag register have no
names and no stated meaning, and they are not spare. Almost every instruction
copies bits three and five of its own result into them. A compare copies them
from its operand instead, because the result is discarded and never reaches the
register. The block instructions copy bits three and *one*, with bit one landing
where bit five sits.

**`WZ`.** An internal register where the processor assembles an address it has
not finished with. Nothing can read it, and two instructions report it anyway
through those same two flag bits. A store through a pointer leaves its two halves
holding unrelated things, because different steps write them and nothing puts
them back together.

**`Q`.** A latch recording whether the instruction just executed wrote the flags.
The two carry instructions consult it: when the previous instruction wrote the
flags, their hidden bits come from the accumulator; when it did not, from the
accumulator combined with the flag register. An index prefix counts as an
instruction that wrote nothing, so `DD 37` and `37` are the same instruction with
different flags.

## Models

The instruction set did not change across the family. Three other things did, and
all three are undocumented or defective, which is why none was ever specified and
why software that depended on any of them had to know which board it was on.

An output instruction whose opcode names no source sends nothing on the NMOS
parts and every bit on the CMOS ones, so a program that clears a device register
with it sets every bit of the same register on the other part. The two
undocumented flag bits after a carry instruction come from the accumulator and a
latch on Zilog's parts and from the accumulator alone on NEC's. And on the NMOS
part an interrupt taken while one of the two instructions that read the interrupt
latch is executing clears the parity flag, reporting that interrupts were
disabled at the one moment they cannot have been. That last one is Zilog's own:
*"On CMOS Z80 CPU, we've fixed this problem."*

| Build it with | Bare `OUT (C)` sends | Carry flag bits | Interrupt clears parity | Suite |
|:--|:--|:--|:--|:--|
| `Cpu("z80")` | nothing | accumulator and latch | yes, and Zilog documents it | yes |
| `Cpu("z84c00")` | every bit | accumulator and latch | no, Zilog fixed it | yes |
| `Cpu("upd780c")` | nothing | accumulator alone | not stated | no |

Every part the package accepts is in that table. A name it does not know is
refused rather than quietly resolved to something close, so `Cpu("z180")` raises
`UnknownModelError` instead of handing back a Z80 that is missing instructions
the caller asked for.

Each answers to the part numbers its manufacturer sold it under. `z80` covers the
Zilog NMOS parts and the second sources built from the same design: Mostek,
Sharp, MME, Thesys, Goldstar and the Soviet KR1858VM1. `z84c00` covers the CMOS
parts, Zilog's and Toshiba's and the KR1858VM3. `upd780c` covers NEC's, which is
NMOS and is not one of the others.

| Build it with | Also answers to |
|:--|:--|
| `Cpu("z80")` | `z8400`, `nmosz80`, `z0840004psc`, `z0840006psc`, `z0840008psc`, `mostekmk3880`, `mk3880`, `mk3880n`, `sharplh0080`, `lh0080`, `lh0080a`, `u880`, `ud880d`, `kr1858vm1`, `t34vm1`, `mme`, `goldstargms z80`, `thesysz80` |
| `Cpu("upd780c")` | `necupd780c`, `d780c`, `d780c1`, `d780c2`, `upd780`, `upd780c1`, `upd780c2` |
| `Cpu("z84c00")` | `cmosz80`, `z80c`, `z8400c`, `z84c0006`, `z84c0008`, `z84c0010`, `z84c0020`, `toshibatmpz84c00`, `tmpz84c00`, `t84c00`, `kr1858vm3` |

```python
from z80 import Cpu

nmos = Cpu("z80")
cmos = Cpu("Z84-C00")
```

Names are matched however they are written: case and separators do not matter,
and each part answers to the names its second sources shipped under.

A part number nothing here implements is refused rather than answered. The Z180
and the eZ80 used to resolve to the CMOS model and no longer do: the Z180 has
instructions the Z80 does not and the eZ80 addresses twenty four bits, so a core
that answered for either would decode their programs as something else.

The remaining differences across the family are in timing and in what happens
when an interrupt lands mid-instruction, neither of which a per-instruction model
can observe. They are absent here rather than guessed at. So is ST's reported
carry rule, because the survey that would confirm it says the reverse; the
disagreement is in [`conformance/divergences.json`](conformance/divergences.json)
rather than resolved by preference.

## What "nothing starts clean" means

`SparseMemory` holds no array. An address that has never been written derives its
value from the address itself: arbitrary, never zero, and the same every time it
is asked.

```python
from z80 import SparseMemory

space = SparseMemory(seed=1)
space.read8(0x8000)  # some byte, not zero, stable across reads
```

Two spaces built with different seeds hold different rubbish, so a test can prove
a program does not depend on what it never wrote. `Registers.reset()` clears only
what the reset pin clears, which is less than most models clear.

Ports are a separate sixteen bit space, addressed by all sixteen bits. Software
that treats only the low eight as significant works until something answers on
the top half, and this will let it fail the way hardware would.

## Layout

| File | Holds |
|:-----|:------|
| [`z80/core.py`](z80/core.py) | Decode and execution for the base, `CB`, `ED`, `DD`, `FD` and doubly prefixed groups |
| [`z80/blocks.py`](z80/blocks.py) | The move, compare, input and output instructions that repeat |
| [`z80/registers.py`](z80/registers.py) | Main set, shadow set, `WZ`, `Q`, and the refresh counter |
| [`z80/flags.py`](z80/flags.py) | The eight bits, including the two the datasheet leaves blank |
| [`z80/memory.py`](z80/memory.py) | Sixteen bit memory and the separate sixteen bit port space |
| [`z80/opcodes.py`](z80/opcodes.py) | The disassembler, built from the same decomposition the core uses |
| [`z80/models.py`](z80/models.py) | Which parts this covers and what separates them |
| [`z80/bus.py`](z80/bus.py) | The shape of every machine cycle, and the only place that knows it |
| [`conformance/hardware.json`](conformance/hardware.json) | What Zilog printed, fact by fact, with the sentence each came from |
| [`conformance/divergences.json`](conformance/divergences.json) | Every place the manual and the suite disagree, and what would settle each |
| [`conformance/instruction-flags.json`](conformance/instruction-flags.json) | Every absolute the manual states about a flag, and the two it gets wrong |
| [`conformance/independent.json`](conformance/independent.json) | What the research outside Zilog establishes, in a form a test can check |
| [`conformance/hardware.test.py`](conformance/hardware.test.py) | The gate that holds the model's timing to the manual, with no suite needed |
| [`conformance/singlestep.py`](conformance/singlestep.py) | The runner that holds the final state to the suite |
| [`conformance/cycles.py`](conformance/cycles.py) | The runner that holds every T state to it |
| [`conformance/fetch.py`](conformance/fetch.py) | Brings the suite down, pinned by commit |
| [`conformance/regenerate.py`](conformance/regenerate.py) | Rebuilds the suite from the generator that made it, pinned the same way |

## For contributors and reviewers

### Running the tests

Each module has its test file beside it, named after it.

```bash
python -m coverage erase
for file in $(find z80 conformance -name '*.test.py' | sort); do
  python -m coverage run -a "$file"
done
python -m coverage report
```

Coverage is a gate, not a report: the build fails below 100% of statements and
branches. Types are a gate too, `mypy` in strict mode with every optional error
class the checker offers.

### Reproducing a conformance failure

```bash
python conformance/fetch.py ~/.cache/conformance-suites
python conformance/singlestep.py ~/.cache/conformance-suites/z80/v1 --opcode "ed b3"
```

`--opcode` takes the file name without its extension, which is the opcode bytes
separated by spaces. `--limit` bounds how many of the thousand cases per file are
read, for a quicker answer while iterating.

### Project conventions

| Convention | Source |
|:-----------|:-------|
| Commit format | [Conventional Commits](https://www.conventionalcommits.org/) |
| Format and lint | [ruff](https://docs.astral.sh/ruff/), configured in [pyproject.toml](pyproject.toml) |
| Releases | [semantic-release](https://semantic-release.gitbook.io/), from the commit history |
| Test naming | A sentence stating the behaviour, not the function name |

### Non-obvious decisions

- The core decodes bit fields rather than indexing a table. A table is a second
  description of the instruction set, and two descriptions drift.
- The disassembler walks the same decomposition, for the same reason.
- Memory is sparse and seeded rather than a zeroed array, so a program that
  depends on uninitialised state fails here the way it would on hardware.
- Interrupt handling is absent rather than approximated. The suite steps one
  instruction at a time and cannot measure it, so anything written would be
  unverified.
- Cycle timing is absent for the same reason.

## References

This repository carries no documents. Every claim it makes is traced to something
published elsewhere, and that is listed here so a reader can fetch the same file
and check the same page. Each row gives the page count and the first sixteen
characters of the file's SHA-256, because vendor links move and a link that has
rotted into a different revision is easy to follow without noticing.

### Rung 1: what the manufacturers printed

| Document | Date | Pages | SHA-256 | Redistributable |
|:---------|:-----|------:|:--------|:----------------|
| [Zilog, *Z80 CPU User Manual*, UM008011-0816](https://www.zilog.com/docs/z80/um0080.pdf) | 2016-08 | 332 | `e3c83da5a5d8e372…` | No |
| Zilog, *Z80 Family Data Book*, 00-2490-01 | 1989-01 | 448 | `844681b63ffc45bd…` | No |
| Zilog, *Z84C00 Product Specification*, PS017801-0602 | undated | 36 | `06198d3c22a79a3f…` | No |
| NEC, *µPD780C* data sheet | undated | 24 | `2036fa845533feee…` | No |

Zilog's notice reads "Copyright ©2016 Zilog, Inc. All rights reserved." Individual
sentences are quoted in [`conformance/hardware.json`](conformance/hardware.json)
with the page each came from, which is what makes those records checkable without
reproducing the work.

The 1989 data book earns its place twice over. Its Questions and Answers section
is the one Zilog publication that corrects another Zilog publication: it states
that a sentence in the CPU Technical Manual is wrong, says which of its own
documents still carries the withdrawn wording, and answers several questions the
User Manual leaves open.

### Rung 3: the research nobody at Zilog wrote

These settle nothing on their own. They are here because the model is held to
them in [`conformance/independent.json`](conformance/independent.json), and
because where two lineages that never consulted each other agree, the agreement
is evidence worth having.

| Document | Author | Pages | SHA-256 | Licence |
|:---------|:-------|------:|:--------|:--------|
| [*The Undocumented Z80 Documented*, v0.91](https://archive.org/details/the-undocumented-z80-documented) | Sean Young, 2005-09-18 | 52 | `6413048f39c2e735…` | GFDL 1.1 or later |
| [*Z80 CCF SCF Outcome Stability*](https://github.com/redcode/Z80/wiki/Z80-CCF-SCF-Outcome-Stability) | Sainz de Baranda y Goñi, Brewer, Helcmanovsky | 4 | `be87311012f9edaf…` | GFDL 1.3 |
| *Undocumented Z80 Flags*, rev 1.0 | David Banks, 2018-08-21 | 3 | `33766df5494e2fdf…` | None stated |
| *MEMPTR, esoteric register of the ZiLOG Z80 CPU* | Boo-boo, trans. Vladimir Kladov | text | `f9e8e87cdd205e15…` | None stated |
| [redcode/Z80 wiki: Interrupts](https://github.com/redcode/Z80/wiki/Interrupts) and [MEMPTR](https://github.com/redcode/Z80/wiki/MEMPTR) | Sainz de Baranda y Goñi and contributors | web | n/a | GFDL 1.3 |

The first two carry an explicit grant and could be redistributed. They are linked
rather than vendored because a link and a digest serve a reader identically and
keep binaries out of the history. The last two state no licence, which is the
absence of permission rather than the presence of it, so only the sentences they
are cited for appear here.

### The corpora and the tools

| Source | Used for |
|:-------|:---------|
| [SingleStepTests/z80](https://github.com/SingleStepTests/z80.git) | The pinned corpus, 1,604,000 cases. Commit in [`conformance/suites.json`](conformance/suites.json) |
| [raddad772/jsmoo](https://github.com/raddad772/jsmoo.git) | The generator that produced that corpus, so it can be rebuilt rather than only downloaded |
| [gdevic/Z80Explorer](https://github.com/gdevic/Z80Explorer) | The netlist whose behaviour is recorded in [`conformance/divergences.json`](conformance/divergences.json) |

## Licence

[MIT](LICENSE).

The conformance suite is a separate work under its own licence, fetched at build
time and never vendored here.
