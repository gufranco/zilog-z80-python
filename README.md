<div align="center">

<h1>Zilog Z80</h1>

<strong>A Z80 interpreter, every instruction and every undocumented flag, held to a per-opcode conformance suite.</strong>

<br>
<br>

[![CI](https://github.com/gufranco/zilog-z80-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/zilog-z80-python/actions/workflows/ci.yml)
[![Conformance](https://img.shields.io/badge/conformance-1%2C604%2C000%20%2F%201%2C604%2C000-brightgreen)](#conformance)
[![Coverage](https://img.shields.io/badge/coverage-100%25%20statement%20%2B%20branch-brightgreen)](#tests)
[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

</div>

<p align="center">
  <a href="#quick-start">Quick start</a> &nbsp;|&nbsp;
  <a href="#conformance">Conformance</a> &nbsp;|&nbsp;
  <a href="#the-three-registers-nobody-documents">Hidden state</a> &nbsp;|&nbsp;
  <a href="#models">Models</a> &nbsp;|&nbsp;
  <a href="https://github.com/gufranco/zilog-z80-python/issues">Issues</a>
</p>

**2** parts · **1,604,000** conformance cases, **0** failures · **1,604** opcode sequences · **218** tests · **100%** statement and branch coverage

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
| [`conformance/singlestep.py`](conformance/singlestep.py) | The runner that holds all of it to the suite |
| [`conformance/fetch.py`](conformance/fetch.py) | Brings the suite down, pinned by commit |

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
branches.

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
