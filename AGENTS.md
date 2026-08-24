# Working in this repository

This file is for a coding agent. A person reading it will not be harmed, but
[README.md](README.md) is the document written for them.

## What this project is, in one paragraph

A Zilog Z80: a decoder, a disassembler and an execution core that emits every bus
cycle, covering three parts of the family. It is held to a pinned conformance
corpus of 1,604,000 cases and, separately, to every timing and flag table the
manufacturer printed. It is a model of a processor, not an emulator that is
pleasant to use, and where those two pull apart the processor wins.

## The interface a caller drives

The part is powered and not reset when it is built. `reset()` is the caller's to
call, because no board hands over a processor that has reset itself.

Three ways to run it, sharing one place where a T state is spent:

- `step()` runs one instruction and returns the T states it cost.
- `run_for(cycles)` spends a budget of them and overshoots, because an
  instruction cannot be cut in half.
- `Clock(cpu).tick()` advances exactly one T state and stops, on a thread,
  because Python cannot suspend a call stack. Fifty times slower and the only
  way to change what a read answers mid-instruction.

Three inputs are lines rather than events, each read where a document says the
part reads it: `irq_line` at the final T state, `nmi_line` on its transition,
`wait_line` after T2 of every machine cycle. `on_cycle` is called once per T
state, after that state's activity.

Every cycle passes through `spend()` and nowhere else. A counter kept in one
method and a hook called from another drift the first time somebody adds a cycle
to only one of them, and nothing catches it. Keep it that way.

## The authority ladder

Every factual question is answered by the highest rung that has an answer, and a
lower rung never overrules a higher one.

1. **Manufacturer documentation.** What Zilog and NEC printed. Every document is
   listed in the README's References section with its page count and digest, and
   every fact taken from one is in
   [`conformance/hardware.json`](conformance/hardware.json) with the sentence it
   came from and the page it was on.
2. **The part itself.** A measurement on real silicon. Nothing here rests on one,
   which is why [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) is as long as it is.
3. **A recording from an independent implementation.** The SingleStepTests
   corpus, pinned by commit in
   [`conformance/suites.json`](conformance/suites.json), and the independent
   research recorded in
   [`conformance/independent.json`](conformance/independent.json). Two lineages
   that never consulted each other, which is worth more than either alone and is
   still not a measurement.
4. **Anything else.** A source with no measurement behind it is not cited.

Where rung one and rung three disagree and rung two is silent, the answer is
**unknown**. Record it in
[`conformance/divergences.json`](conformance/divergences.json) with what would
settle it. Do not pick the more convenient source and move on.

## What is settled and what is not

**Settled: every opcode's effect on state.** 1,604,000 recorded cases, no
failures, undocumented opcodes and the two undocumented flag bits included.

**Settled: cycles.** [`conformance/cycles.py`](conformance/cycles.py) compares
22,005,372 T states against the recording, pin by pin. The bus shape is also held
to the manual's own figures by
[`conformance/hardware.test.py`](conformance/hardware.test.py), which needs no
corpus on the machine.

**Settled: the flag rules the manual states absolutely.** 126 of them, extracted
from the Condition Bits Affected block of all 131 instruction pages and fuzzed.
124 hold; the two that do not are recorded.

**Not settled: nineteen things**, each in [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md)
with what would close it. Most are behaviour Zilog documented for programmers
rather than for people rebuilding the part. Do not close one by argument.

## The two pin shapes

The manual's control-pin edges fall on half-T-state boundaries and a model whose
smallest column is a whole T state has to pick a rule. Both are implemented:
`manual` reads each pin at the clock edge ending the state, `recording` matches
what the corpus carries. The default is `manual`; the corpus runner asks for
`recording`. This is a modelling choice, not a fact about silicon, and it is
recorded as one.

## Every gate, in the order to run them

```bash
ruff format --check .
ruff check .
mypy
pnpm run format:check
for f in $(find z80 conformance -name '*.test.py' | sort); do python3 "$f"; done
python3 -m coverage report
```

The conformance run needs the corpus, which is fetched rather than vendored:

```bash
python3 -m conformance.fetch ~/.cache/conformance-suites
python3 -m conformance.singlestep ~/.cache/conformance-suites/z80/v1
python3 -m conformance.cycles ~/.cache/conformance-suites/z80/v1
```

## Conventions that are not negotiable

| Thing | Rule |
|:------|:-----|
| Language | Python only |
| Comments | None in source. Docstrings carry the reasoning |
| Test layout | `<module>.test.py` beside the module it covers |
| Test shape | Arrange, blank line, one act, blank line, assert. No section labels |
| Coverage | 100% statements and branches, enforced |
| Types | `mypy` at strict, plus every optional error class |
| Commits | Conventional Commits, subject under 50 characters |
| Corpus | Fetched and pinned by commit, never vendored |
| Documents | Read, quoted and pinned by digest. Never committed: none is redistributable |
| Undefined state | Nothing starts cleared and nothing can be asked to. There is no fill parameter and there will not be one |
| Fidelity | Where the part and convenience disagree, the part wins. A behaviour that exists only to make a test easier is a defect |
| Public API | This and the 65xx package present the same surface. See [FAMILY.md](FAMILY.md) |

## Layout

```
z80/
  core.py        the execution core, which emits every bus cycle
  bus.py         the shape of every machine cycle, and the only place that knows it
  opcodes.py     the decoder and disassembler, built from one decomposition
  registers.py   the register file, including WZ and the Q latch
  flags.py       the eight bits, including the two the datasheet leaves blank
  memory.py      flat and sparse memories that start filled, never cleared
  models.py      the three parts, by name and alias
conformance/
  suites.json    which corpus, at which commit
  fetch.py       getting it
  singlestep.py  running it, state by state
  cycles.py      running it, T state by T state
  regenerate.py  rebuilding it from the generator that made it
  hardware.json  what Zilog printed, with the sentence
  independent.json  what the research outside Zilog establishes
  divergences.json  where sources part, with a status and a severity
  links.py       the weekly check that every cited address still answers
```

## Things that will bite you

**A figure taken from a document is read twice.** Almost every document behind
these projects is a photograph of a printed book. Its text layer, where it has
one, was produced by somebody else's recogniser and prints `lhe` for `the`; the
page read as an image now is cleaner but drops a lone digit and misses a faint
line outright. Read it both ways and record what both agree on. `FAMILY.md`, under
"Reading a document that is a photograph", carries the traps and what the record
has to hold. Skipping this is how a timing table came to name forty three of its
rows after the text sitting next to them.

- **The manual's opcode maps have no usable text layer.** Read the rendered page.
  Extracting them produces characters that are not in the printed table.
- **The corpus and the manual disagree about pin shape.** That is the two-shape
  question above, not a defect.
- **`docs/` is not in the repository.** It holds copyrighted documents that
  cannot be redistributed. Nothing tracked may read from it: a test that does
  passes here and fails everywhere else.

## Before calling anything finished

[`FAMILY.md`](FAMILY.md) carries a checklist under "What a new repository has to
have before it is a member". Every line on it was a defect found in one of these
repositories and fixed in all of them, so it is the list of things that have
actually gone wrong here rather than a list of good intentions. Read it before
adding a surface, and read it again before saying a change is done.

Two rules from that file are worth repeating because they are the ones skipped
most often, and skipping them is how the rest of the list got written:

**A check nobody has seen fail is not known to work.** Drive it, once,
deliberately, against input that should fail it. Three checks in this family
reported clean while the thing they guarded was broken, and each was believed
because the run stayed green.

**Silence and success produce the same output.** A check that found no files, no
documents or no records exits zero exactly like one that examined everything.
Print what was examined, and say so when the answer is nothing.

## What a change is expected to leave behind

A gate that would have caught the bug. A change to instruction behaviour also
runs the corpus, because that is the only thing here that can tell you whether it
is right.
