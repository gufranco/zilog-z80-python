<div align="center">

<h1>Zilog Z80</h1>

<strong>A cycle-accurate Z80, held to Zilog's own user manual for the shape of every machine cycle and to a per-opcode suite for every T state of every opcode.</strong>

<br>
<br>

[![CI](https://github.com/gufranco/zilog-z80-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/zilog-z80-python/actions/workflows/ci.yml)
[![Conformance](https://img.shields.io/badge/conformance-1%2C604%2C000%20%2F%201%2C604%2C000-brightgreen)](#conformance)
[![Cycles](https://img.shields.io/badge/T%20states-22%2C005%2C372%20compared-brightgreen)](#cycle-by-cycle)
[![Manual](https://img.shields.io/badge/Zilog-UM008011--0816-brightgreen)](#where-each-answer-comes-from)
[![Coverage](https://img.shields.io/badge/coverage-100%25%20statement%20%2B%20branch-brightgreen)](#tests)
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

**2** parts · **1,604,000** conformance cases, **0** failures · **22,005,372** T states compared, **0** failures · **370** tests · **100%** statement and branch coverage

```python
from z80 import Ports, SparseMemory, describe

cpu = describe("z80").build(SparseMemory(), ports=Ports())
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

cpu = Cpu(space, reset=False)
cpu.registers.pc = 0x8000
cpu.step()
cpu.step()

print(f"{cpu.registers.b:02X}")
```

```
42
```

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

<table>
<tr>
<td width="50%" valign="top">

### Held to an oracle

Every instruction is checked against a published suite that states each register
and each byte of memory before and after, for one thousand cases across each of
one thousand six hundred and four opcode sequences. Where the model and the suite
disagree, the suite is right.

</td>
<td width="50%" valign="top">

### Decoded, not tabulated

The core walks the opcode's bit fields the way the silicon does, so several
hundred instructions come from one page of dispatch rather than from a table
nobody can proofread.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### Nothing starts clean

Memory and registers hold what they held. A model that starts at zero hides the
class of bug that only appears on real hardware, where an unwritten byte is
whatever the board powered up with.

</td>
<td width="50%" valign="top">

### The undocumented parts too

The two flag bits the datasheet leaves blank, the internal address register that
only two instructions reveal, and the latch that records whether the previous
instruction wrote the flags at all.

</td>
</tr>
</table>

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

### Two shapes, because one column cannot hold half a clock

Every control pin edge in the manual falls on a clock edge, which is half a T
state. A model whose smallest column is a whole T state has to pick a rule for
turning a waveform into a column, and the manual states no such rule. So there
are two shapes and both are named.

`bus.MANUAL` is the default and draws a pin in every state the figure shows it
asserted in. The edges behind it were measured off the pages of the pinned
document rendered at 200 dpi, and every one of them is in
[`conformance/hardware.json`](conformance/hardware.json) under `figureEdges`, so
a reader can apply a different rule without opening the PDF. `bus.RECORDING`
draws one strobe per transfer, which is what the pinned corpus contains and what
its own generator describes as a deliberate simplification. Only
[`conformance/cycles.py`](conformance/cycles.py) asks for it, so the corpus still
checks this core cycle for cycle without either shape being bent to fit the
other.

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
quoting the generator admitting it. **This core draws the coverage the manual's
figures give, and reproduces the recorded bus exactly when asked for the recorded
shape. Neither is a measurement of silicon, and the difference is written down
rather than glossed.**

## Where each answer comes from

| Rung | Source | Settles |
|:-----|:-------|:--------|
| 1 | [Zilog, *Z80 CPU User Manual* UM008011-0816](conformance/hardware.json) | Anything Zilog printed: pin function, machine cycle shape, T states per instruction, what reset does, which bit of the flag register is which |
| 2 | The pinned suite | What the manual does not: the two undocumented flag bits, the internal `WZ` register, the `Q` latch, every opcode the manual does not list, and where the idle states sit inside a long machine cycle |
| 3 | Nothing else | Nothing |

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
cpu.interrupt(0xFF)  # the maskable line, with the byte the device puts on the bus
cpu.nonmaskable()  # the other one, which is always taken
```

`interrupt` reports whether the part took it, and refuses while the enable flip
flop is clear or for one instruction after an enable, which is the delay that
exists so an enable followed by a return is not interrupted between the two.
`nonmaskable` always reports taken.

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

The instruction set did not change across the family. One instruction's behaviour
did, and it is enough to matter: a program that clears a device register with it
works on one part and sets every bit of the same register on the other.

| Model | The output instruction that names no source sends | Also answers to |
|:------|:--------------------------------------------------|:----------------|
| `z80` | nothing | `z8400`, `upd780c`, `u880`, `kr1858vm1`, `mostekmk3880` |
| `z84c00` | every bit | `z80c`, `z8400c`, `z180`, `ez80` |

```python
from z80 import describe

nmos = describe("z80").build(space, ports=ports)
cmos = describe("Z84-C00").build(space, ports=ports)
```

Names are matched however they are written: case and separators do not matter,
and each part answers to the names its second sources shipped under.

The remaining differences across the family are in timing and in what happens
when an interrupt lands mid-instruction, neither of which a per-instruction model
can observe. They are absent here rather than guessed at.

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
| [`conformance/hardware.test.py`](conformance/hardware.test.py) | The gate that holds the model's timing to the manual, with no suite needed |
| [`conformance/singlestep.py`](conformance/singlestep.py) | The runner that holds the final state to the suite |
| [`conformance/cycles.py`](conformance/cycles.py) | The runner that holds every T state to it |
| [`conformance/fetch.py`](conformance/fetch.py) | Brings the suite down, pinned by commit |
| [`specs/current/`](specs/current/) | What the part does, as requirements somebody could test against |
| [`AGENTS.md`](AGENTS.md) | The working instructions, including the things that will bite you |

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

## Licence

[MIT](LICENSE).

The conformance suite is a separate work under its own licence, fetched at build
time and never vendored here.
