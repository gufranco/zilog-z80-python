# Working in this repository

This file is for a coding agent. A person reading it will not be harmed, but
[README.md](README.md) is the document written for them.

## What this project is, in one paragraph

A model of the Zilog Z80, held to two different things at once. Its final state
after every instruction is held to a published per-opcode suite. What it does
with its pins while producing that state is held to the same suite, T state by T
state. The shape of each machine cycle, and how many T states a documented
instruction spends, come from Zilog's own user manual rather than from the suite,
so the two checks are independent of each other.

## The authority ladder

Every factual question is answered by the highest rung that has an answer, and a
lower rung never overrules a higher one.

1. **`conformance/hardware.json`**, which is Zilog's user manual UM008011-0816
   pinned fact by fact with the sentence each figure came from, including all 184
   of its per-instruction timing rows. It decides anything Zilog printed: pin
   function, machine cycle shape, T states per instruction, what reset does,
   which bit of the flag register is which.
2. **The recorded suite**, pinned by commit in `conformance/suites.json`. It
   decides what the manual does not, which for this part is a great deal: the two
   undocumented flag bits, the internal `WZ` register, the `Q` latch, every
   opcode the manual does not list, and the order of the idle states inside a
   long machine cycle.
3. **Nothing else.**

Where the two disagree, the manual wins and the disagreement goes in
`conformance/divergences.json`. There are ten entries. Two of them are places
where the suite's generator departs from the manual deliberately and says so in
its own README; both are quoted there.

**Never resolve a divergence by changing the model to match the suite.** If the
manual is wrong, say why, with the page.

## The manual contradicts itself in three places, and this is not a reading error

Its M Cycles column disagrees with its own T states breakdown on manual pages 99,
260 and 269. In each case the breakdown has a different number of groups than the
M Cycles column claims, while summing correctly to the printed total. All three
were read off the rendered page image to confirm the document really prints them.

The breakdown wins. It is internally consistent on all 184 rows and the M Cycles
column is a summary; on the JR row it has plainly been copied from the T States
column beside it.

**The tables in this PDF have an unreliable text layer.** The prose extracts
cleanly, the large opcode maps do not, and reading them as text produces
characters that are not in the printed tables. Anything numeric must be read off
the page image. `conformance/hardware.json` records which figures came from which.

## Every gate, in the order to run them

```bash
ruff format --check .                                   # formatting
ruff check .                                            # lint, zero warnings
mypy                                                    # types, strict
pnpm run format:check                                   # every JSON file
for f in $(find z80 conformance -name '*.test.py' | sort); do python3 "$f"; done
python3 -m coverage report                              # fails below 100%
python3 conformance/fetch.py ~/.cache/conformance-suites
python3 conformance/singlestep.py ~/.cache/conformance-suites/z80/v1   # state
python3 conformance/cycles.py ~/.cache/conformance-suites/z80/v1       # T states
```

Coverage is collected by running each test file under `coverage run -a`, not by a
test runner. All of it is 100% of statements and branches, enforced rather than
aspired to.

The full cycle sweep is 1,604,000 cases and 22,005,372 T states, and takes about
fifty seconds. There is no reason to run less than all of it locally.

## The two conformance runners are not interchangeable

`singlestep.py` compares the state an instruction leaves behind. `cycles.py`
compares what the part did while producing it. A core can spend the right number
of cycles doing the wrong thing and pass the first while failing the second;
holding this core to the recorded bus is what found a push writing the low half
of the pair first where the part writes the high half. Same two addresses,
opposite order, identical final state.

Both must pass. Neither replaces the other.

`conformance/hardware.test.py` is a third check and the only one that needs no
suite on the machine: it assembles a documented instruction, steps it, and
compares the T states spent against the figure Zilog printed for that instruction,
naming the manual page rather than repeating the number.

## Things that will bite you

**An opcode fetch is not a memory read.** It is four T states with the refresh
address replacing the counter for the last two, and it must go through
`bus.fetch` rather than `read8`. Every prefixed opcode is its own fetch: a
DD-prefixed instruction performs two, and the refresh counter advances twice.

**The refresh address carries the counter as it stood before the fetch advanced
it.** Advancing first and then reading is wrong by one on every instruction and
by more on a prefixed one.

**An indexed bit instruction is the one exception.** In `DD CB d op` the last
byte is not a fetch. It arrives as an ordinary three state read and the refresh
counter does not advance for it, which is why those forms leave the counter two
on rather than three.

**A write puts its value on the bus a T state earlier than a read latches one.**
On a read the part is waiting for memory; on a write it is driving. Treating the
two symmetrically disagrees on the middle T state of every store.

**Internal cycles hold the last address.** They invent nothing. After a fetch
that is the refresh address, after a read it is the address read.

**The pin columns are derived, not typed in.** `bus.EDGES` holds where each
control pin goes active and inactive, in T states from the start of the machine
cycle, measured off the figures and snapped to the clock. `bus.columns` turns
that into pins by reading them at the clock edge that ends each state. Changing a
column means changing a measurement, and `conformance/hardware.test.py` checks
the record holds the same edges.

**There is a second oracle for the manual shape.** `conformance/regenerate.py
<directory> --full` rebuilds the corpus with the generator's wide strobes, and
`conformance/cycles.py <directory> --shape manual` compares against it. Expect
7,000 differences over 1,610,000 cases, all of them in the seven opcodes already
recorded as places the generator's head has moved away from the pinned corpus.
Without `--full` the same command rebuilds the published corpus, which is how
those eleven opcodes were found in the first place.

**There are two pin shapes and the manual's is the default.** A four character
string per T state cannot express a waveform whose edges land on clock edges, so
turning a figure into a column is a modelling choice. `bus.MANUAL` draws a pin in
every state the figure shows it asserted in; `bus.RECORDING` draws one strobe per
transfer, which is what the corpus contains. Only `conformance/cycles.py` asks
for the second. Every edge behind the first is in `hardware.json` under
`figureEdges`, measured off the rendered pages rather than eyeballed.

**A port cycle strobes three of its four states and a memory cycle strobes all
of its three.** They do not start alike either: memory request falls half a clock
into T1, and the port request waits for the rising edge of T2. Copying the memory
shape onto a port cycle gets both ends wrong.

**Where an idle state goes is per instruction and comes from the manual's
breakdown.** `(4, 4, 3)` for `INC (HL)` means the middle machine cycle is a three
state read with one state of arithmetic after it. Getting the count right and the
placement wrong passes the T state total and fails the sequence.

**Run the suite on the oldest Python supported, not only the newest.**
Annotations are evaluated eagerly before 3.14 and lazily from 3.14 on. Every
module here carries `from __future__ import annotations`.

## What the model deliberately does not do

Recorded in `divergences.json` with the reason and what would change it.

- **Nothing checks the interrupt response.** `Cpu.interrupt` and
  `Cpu.nonmaskable` are implemented, and the four totals they spend match the
  four the manual prints. No recording verifies the pins, because the corpus
  contains no acknowledge cycles. The generator does emit an entry for the
  interrupt request and the published corpus leaves it out, and that entry would
  not help anyway: every case in it is a plain four state opcode fetch.
- **Nothing checks a halted fetch either.** A halted step spends a whole fetch
  with the pins of one, which is what the manual describes. Which address it
  carries is not settled: the note under Figure 11 says the halt instruction is
  repeated, and this fetches from the counter, which has already passed it.
- **Nothing a board does.** Requested wait states, a device taking the buses, and
  the clock being stopped are all documented and all absent. The two automatic
  waits are modelled, in an I/O cycle and in an interrupt acknowledge, because the
  part inserts those itself. The rest need a clocked interface rather than a
  stepped one, and all three are recorded as reopening together on that.
- **The seventh state of an acknowledge is placed rather than known.** The cycle
  is seven T states, which the manual gives twice over and never directly, and
  Figure 9 draws six of them. The seventh is spent by the response here, which is
  where a restart already spends the fifth state of its own M1.

## Conventions

| Thing | Rule |
|:------|:-----|
| Language | Python only |
| Comments | None in source. Docstrings carry the reasoning, and say why rather than what |
| Test layout | `<module>.test.py` beside the module it covers |
| Test structure | Arrange, blank line, one act, blank line, assert. No section labels |
| Package manager for tooling | pnpm, never npm |
| Commits | Conventional Commits |
| Artifacts | None. The suite is fetched, never committed, and the manual is cited by digest rather than carried |
