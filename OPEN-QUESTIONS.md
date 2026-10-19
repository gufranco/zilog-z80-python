# Open questions

What this project does not know for certain, and what it would take to find out.

Everything here is a place where being faithful to the silicon is still a claim
rather than a measurement. The list is longer than a reader might expect, and
that is the point: the Z80 was documented for people writing programs, not for
people rebuilding it, so a great deal of what a cycle-exact model has to decide
was never printed anywhere.

The settled surface is large. 1,604,000 recorded state cases and 22,005,372
recorded bus cycles agree with this model exactly, every timing figure in the
manual is checked against a run, and 126 of the manual's absolute flag statements
are fuzzed against it. What follows is the residue.

## Why a recording cannot close these

The corpus this project is held to is itself a model. It was made independently,
it is very good, and where it and the manual disagree it has usually been right.
But a recording made by a program is evidence about that program. Where a
document and a recording disagree and no third source exists, the answer is
unknown, and it belongs here rather than being resolved in favour of whichever
source is more convenient.

## What would settle almost all of them

A logic analyser on a real Z80, running short programs written to provoke each
case. The parts are still sold new, and the questions below are mostly a handful
of instructions each.

Two of them need more than that: the flag questions marked as unstable are about
behaviour that differs between manufacturers and between individual chips, so
they need several parts from several makers rather than one.

## Where a document and the recordings disagree

A manufacturer printed one thing and every recorded case shows another. These are the ones a measurement would settle outright.

### Whether the two undocumented flag bits after a carry instruction are deterministic at all.

**What this project follows.** reference

**Why.** A deterministic model has no way to be right about a signal that is not deterministic, and a model that produced random values would fail every case of the corpus while being no closer to any particular part. The rule this package follows is the one every stable part is reported to produce.

**What would settle or reopen it.** Nothing settles it, which is the point of the entry. What would narrow it is a survey of how many parts on how many boards are stable, which the test program named in that document exists to collect.

## Where a document disagrees with itself

One publication saying two things. The reading this project follows is argued in each entry, but only silicon closes it.

### Whether a non-maskable pulse that ends before the part samples it is taken.

**The document says.** NMI. Nonmaskable Interrupt (input, negative edge-triggered). This signal is sampled at the same time as the interrupt line, but this line takes priority over the normal interrupt and it cannot be disabled under software control.

Source: Zilog UM008011-0816, manual pages 6 and 13.

**What this project follows.** document

**Why.** The manual says the line is sampled, which is what the model does, and says it is edge-triggered, which the model honours by taking a held line once. It never says the edge is latched, and the data book's minimum NMI pulse width on printed page 21 bounds how short a pulse the part is guaranteed to see without saying when it is seen. Latching every edge would be choosing the reading that sounds more like hardware, which is the thing this record exists to stop.

**What the die says.** It latches the edge. A pulse one T state long, placed in the second machine cycle of `add hl,bc` and gone six states before the instruction ends, is taken: the next fetch is at 0066h. This package misses the same pulse. The answer is the netlist's, recorded in [`conformance/die.json`](conformance/die.json), written by [`conformance/ask.py`](conformance/ask.py), and it is not adopted as the part's: the member's ladder holds nothing in the package to the netlist, and the die is one photograph of one part.

**What points toward a latch.** The data book's minimum NMI pulse width, parameter 37 on printed pages 21 and 23, is 80, 70, 60 and 60 ns for the four CMOS ratings and 80, 70 and 60 ns for the three NMOS ones, against clock cycle times of 250, 162, 125 and 100 ns and 250, 162 and 125 ns. Every minimum is shorter than one T state, and Figure 9 draws the parameter as the width of a low pulse. It does not settle the question, because no sentence makes that width a condition for recognition, and the paragraph above Figure 9 says "NMI is sampled at the same time as the maskable interrupt input INT".

**What would settle or reopen it.** A logic capture of a real part given an NMI pulse that falls and rises again entirely before the last two states of an instruction, recording whether the next boundary restarts at 0066h.; The same capture with the pulse placed inside an instruction several machine cycles long, which separates a latch from a sample taken once per instruction.

### Whether the lowest bit of the byte a device supplies reaches the pointer.

**The document says.** The lower eight bits of the pointer must be supplied by the interrupting device. Only seven bits are required from the interrupting device, because the least-significant bit must be a 0. This process is required, because the pointer must receive two adjacent bytes to form a complete 16-bit service routine starting address; addresses must always start in even locations.

Source: Zilog UM008011-0816, manual page 20.

**What this project follows.** reference

**Why.** The manual's sentence is sound advice to whoever builds the table and is not a description of what the silicon does with the byte. The only party to have tested it reports the opposite, and nothing in the corpus covers it because the corpus contains no interrupt cases.

**What the die says.** All eight bits. Given 21h with I at 00h, the netlist reads the pointer from 0021h and 0022h, which is what this package does. Recorded in [`conformance/die.json`](conformance/die.json), written by [`conformance/ask.py`](conformance/ask.py).

**What would settle or reopen it.** A program on a real part: point the table at an odd address, raise the line, supply an odd vector, and see where it lands.

## Where nobody wrote it down

Behaviour no manufacturer documented. The recordings agree with independent research, which is two lineages rather than one, and still not a measurement.

### What the address pins hold during the second half of an opcode fetch.

**The document says.** During T3 and T4, the lower seven bits of the address bus contain a memory refresh address and the RFSH signal becomes active, indicating that a refresh read of all dynamic memories must be performed.

Source: Zilog UM008011-0816, manual page 8.

**What this project follows.** reference, in both shapes

**Why.** The manual guarantees only seven bits, so the rest is not a figure it prints. The recording supplies a whole address and this core reproduces it. A model that put something else in the upper nine bits would disagree on every instruction and would have no document behind it either.

**What the die says.** With I at 9Ch and R at F0h, the refresh half of the next fetch puts 9CF0h on all sixteen pins: I above the whole of R, bit 7 included, as this package does. Recorded in [`conformance/die.json`](conformance/die.json), written by [`conformance/ask.py`](conformance/ask.py).

**What would settle or reopen it.** A logic capture reading all sixteen address lines during T3 of a fetch.

### Where within a long machine cycle the bus falls idle.

**What this project follows.** reference

**Why.** The two sources are answering different questions rather than contradicting each other. Recorded here so that a reader does not take the whole cycle claim as resting on the manual when half of it rests on the recording.

**What the die says.** The same. Across all 1135 opcode forms the decoder accepts, `halt` aside, each run once from the die's power-up register state, every machine cycle the netlist runs starts, ends, accesses and addresses exactly as this package's does. One register state takes one side of each conditional instruction. Recorded in [`conformance/die.json`](conformance/die.json), written by [`conformance/ask.py`](conformance/ask.py).

**What would settle or reopen it.** A logic capture of an instruction with more than one idle state, showing which machine cycle carries them.

### Bits 3 and 5 of the flag register.

**The document says.** Each of these two Flag registers contains 6 bits of status information that are set or cleared by CPU operations; bits 3 and 5 are not used.

Source: Zilog UM008011-0816, manual page 66.

**What this project follows.** reference

**Why.** Saying a bit is not used is a statement about what the designer intended a programmer to read, not a claim that the bit reads as zero. The manual declines to specify rather than specifying something else, so this is an absence rather than a contradiction.

**What would settle or reopen it.** Nothing short of Zilog documenting it, which no revision of this manual has done in eleven revisions over forty years.

### The internal register the recording calls WZ, and the flags latch it calls Q.

**What this project follows.** reference

**What the die says.** The netlist names `reg_w` and `reg_z`, and
[`conformance/wz.py`](conformance/wz.py) executes one instruction and reads them.
Eight of the nine cases probed agree with the recording: `ld a,(nn)`,
`ld hl,(nn)` and `ld (nn),hl` leave the address plus one, `jp nn` leaves the
destination, and `in a,(n)` leaves the accumulator over the port plus one. `nop`
and `ld a,n` leave the pair at the pattern the netlist powers up in, which is the
control that makes the rest worth reading.

The ninth disagrees. `ld (nn),a` and `out (n),a` end with the high byte at zero
rather than at the accumulator. A trace of the half cycles shows the pair passing
through the address and then the address plus one before the byte goes to zero,
so the die clears it rather than never loading it, and `ld (nn),hl` keeps it, so
it is not the harness releasing a bus.

**What a real part says.** The recording, on the case the die disputes.
`z80memptr` from the z80test suite, whose CRCs were recorded on a real Zilog Z80,
reads two bits of the register through `bit n,(hl)` after every instruction it
tests, and passes all 156 tests here. A copy of this package that clears the high
byte the way the die does fails exactly `ld (bc),a` and `ld (de),a`, `ld (nn),a`
and `out (n),a`. `z80ccf` reads Q through `scf` and `ccf` after every instruction
it tests and passes all 156 too. Pinned in
[`conformance/z80test.json`](conformance/z80test.json) and run by
[`conformance/z80test.py`](conformance/z80test.py). Its author says the vectors
were not designed to stress the register, which is why this narrows the entry
rather than closing it.

**What would settle or reopen it.** Zilog documenting the internal register file.
A suite or capture that stresses WZ and Q on a real part beyond the z80test
vectors.

### The opcodes the manual does not list.

**What this project follows.** reference

**What would settle or reopen it.** Nothing available. These encodings were never specified; they are what the decoder happens to do.

### Which address a halted part puts on the bus.

**The document says.** Each cycle in the HALT state is a normal M1 (fetch) cycle except that the data received from the memory is ignored and an NOP instruction is forced internally to the CPU.

Source: Zilog UM008011-0816, manual page 14.

**What this project follows.** document, for the cycle; neither, for the address

**Why.** The manual says outright that the halted part keeps performing M1 cycles, so emitting none was reporting a machine cycle the part performs as one it does not. It does not say which address those cycles carry: the note under Figure 11 says the halt instruction is repeated, which would put the previous address on the bus, and the counter is where a part that simply stopped advancing would fetch from.

**What the die says.** The counter. With the halt instruction at 0001h, every M1 cycle the netlist runs while halted carries 0002h, which is the address this package fetches from. Recorded in [`conformance/die.json`](conformance/die.json), written by [`conformance/ask.py`](conformance/ask.py).

**What would settle or reopen it.** A logic capture of a halted Z80, reading the address lines during any of its M1 cycles.; A recording that steps a machine which is already halted, which this corpus does not.

### The corpus generator has changed its mind about behaviour nobody documented.

**What this project follows.** the pinned corpus

**Why.** The pin exists so a run is reproducible. Following the head instead would be swapping one undocumented opinion for a newer one with nothing to prefer it by.

**What the die says.** It splits them. On the seven placement opcodes, `ex (sp),hl` and its two indexed forms, `rrd`, `rld` and the two indexed stores of an immediate, the netlist runs the machine cycles of the pinned corpus, which this package reproduces. On `dd 37`, `dd 3f`, `fd 37` and `fd 3f` run after `cp 28h`, it leaves bits 5 and 3 clear, keeping the flags latch across the index prefix: that is the generator's head, and this package, following the pin, disagrees with the die on those four. Recorded in [`conformance/die.json`](conformance/die.json), written by [`conformance/ask.py`](conformance/ask.py).

**What would settle or reopen it.** A real part, for any of the eleven. Nothing else can, because no document speaks to any of them.

### Where the seventh T state of an interrupt acknowledge falls.

**The document says.** This mode of response requires 19 clock periods to complete (seven to fetch the lower eight bits from the interrupting device, six to save the program counter, and six to obtain the jump address).

Source: Zilog UM008011-0816, manual page 20.

**What this project follows.** document

**Why.** Reading the cycle as a four state fetch plus the two added waits gives six, and six makes the printed mode 2 total eighteen against a printed nineteen. The reading that satisfies both printed figures is a five state M1 under the two waits.

**What the die says.** Seven states: T1, T2, two automatic waits, T3, T4 and a fifth, so the seventh is the last state of the acknowledge cycle, after the refresh half. This package spends it there. Recorded in [`conformance/die.json`](conformance/die.json), written by [`conformance/ask.py`](conformance/ask.py).

**What would settle or reopen it.** A logic capture of a real Z80 answering an interrupt, counting the states of the acknowledge cycle.

### What the internal address register holds once an interrupt has been taken.

**What this project follows.** neither

**Why.** Leaving it alone would be as much of a guess as setting it, and it would be a quieter one. Setting it the way the nearest documented instruction does at least makes the guess a consistent one, and this entry is what stops it reading as a finding.

**What the die says.** The address the response jumps to: 0038h after a mode 1 or mode 0 restart, the address read from the table after mode 2, 0066h after a nonmaskable response. This package sets the same. Recorded in [`conformance/die.json`](conformance/die.json), written by [`conformance/ask.py`](conformance/ask.py).

**What would settle or reopen it.** A recording that takes an interrupt and reports the register afterwards.; A die analysis, or Zilog documenting the internal register file.

### Where the two undocumented flag bits come from after a carry instruction, which is not the same answer on every part.

**What this project follows.** reference, and only for the two of the three rules that are not disputed

**Why.** The NEC part was previously another name for the Zilog model, which made this package answer for a part whose measured behaviour it does not reproduce. A part number that resolves to the wrong behaviour is worse than an absent one, because it answers.

**What would settle or reopen it.** A recording taken off each part, which is what the pinned corpus is for the Zilog one and does not exist for the others.

### Whether ST's CMOS part has a carry flag rule of its own.

**What this project follows.** neither

**Why.** Two rung three sources disagree, one of them says the other may have been reading instability rather than a rule, and no recording exists for either. Modelling a rule under those conditions would be picking a side of an open question and calling the result a part.

**What would settle or reopen it.** A recording taken off an ST CMOS part, on a board known to produce stable values for these two bits.

## Where the question is a modelling choice, not a fact

Two defensible ways to record the same silicon. Both are implemented here and the recordings pick one; the part does neither, it does something continuous that both are sampling.

### How many T states a strobe occupies, when a T state is the smallest column there is.

**The document says.** One half clock cycle later, the MREQ signal goes active. At this time, the address to memory has had time to stabilize so that the falling edge of MREQ can be used directly as a chip enable clock to dynamic memories. The RD line also goes active to indicate that the memory read data should be enabled onto the CPU data bus. The CPU samples the data from the memory space on the data bus with the rising edge of the clock of state T3, and this same edge is used by the CPU to turn off the RD and MREQ signals.

Source: Zilog UM008011-0816, manual page 8.

**What this project follows.** document by default, reference in the comparison runner

**Why.** A four character string per T state cannot express a waveform whose edges land between states, so any per-state model applies a rule the manual never states. Calling the recording wrong would be treating one such rule as a fact. Calling it right would be treating a documented simplification as a measurement. Both shapes are kept, named, and produced from the same edge table.

**Why the die has not been asked.** The netlist resolves half clock cycles, but its clock net does not say which of its two halves is the rising edge the manual's figures are drawn against, and aligning it by the strobe edges would assume the answer.

**What would settle or reopen it.** A logic capture of a real Z80, which would give the edges directly rather than through a drawing.; Nothing in the document settles it, because the question is about the model's resolution rather than about the part.

## Where the evidence exists but has not been run here

Not unknown to the world, unverified in this repository.

### The interrupt acknowledge cycle, which is modelled and which nothing verifies.

**The document says.** When the signal is accepted, a special M1 cycle is generated. During this special M1 cycle, the IORQ signal becomes active (instead of the normal MREQ) to indicate that the interrupting device can place an 8-bit vector on the data bus. Two wait states are automatically added to this cycle.

Source: Zilog UM008011-0816, manual page 12.

**What this project follows.** document

**Why.** The generator does emit entries for the interrupt request and for reset, and the published corpus leaves both out. Neither would settle anything if it were published: each case is an ordinary instruction stepped from the given state, with the opcode at the program counter deciding the transcript, so the interrupt entry is not a recording of an acknowledge cycle at all.

**What the die says.** The cycle this package models. The netlist's acknowledge machine cycle is seven T states with IORQ in place of MREQ, mode 1 and a mode 0 restart reach their destination thirteen states after it begins, mode 2 nineteen, and a nonmaskable response eleven, its first machine cycle five states. Recorded in [`conformance/die.json`](conformance/die.json), written by [`conformance/ask.py`](conformance/ask.py).

**What would settle or reopen it.** A logic capture of a real Z80 answering an interrupt, which would give the pins and the length together.; A corpus that contains acknowledge cycles, which this one does not.

### The one source that could settle most of the entries above, now that it runs.

**What this project follows.** neither

**Why.** conformance/netlist.py runs it. Its resolver follows chipsim.js and wires.js from the same project, which are MIT licensed, and the notice they ask for is in THIRD-PARTY-NOTICES.md. Driven from reset with a program that loads three registers and increments one, it fetches from 0x0000, executes, comes to rest on every edge, and lands on register values that only executing that program produces.

**What it is.** A transistor level netlist of the die exists and is public. Read here on 2026-08-27 it is 6,781 transistors, plus 32 entries that are pull-ups rather than transistors, and 2,059 nets carrying a permanent pull-up. Running it answers the questions a document drawn at half clock resolution and a recording written one column per T state cannot: where a strobe actually falls, how many states an acknowledge takes, what the address pins carry during refresh, and where an internal state sits inside a machine cycle.

**What has changed for the entries above.** [`conformance/ask.py`](conformance/ask.py) asks it twelve questions and records each answer beside what this package does in [`conformance/die.json`](conformance/die.json). Every entry above with a die paragraph has been asked, and [`conformance/wz.py`](conformance/wz.py) asked the one about WZ. Of its twelve answers, the die parts from this package on two: the short nonmaskable pulse and the four prefixed carry instructions. The strobe edges have not been asked, for the reason in that entry. None of the entries is closed by it: an answer is the netlist's, not the part's.

**What had to be measured.** Two things had to be established here rather than taken from anyone, and both were measured. Thirty-two entries in the transistor file carry a flag marking them pull-ups; loading them anyway leaves 36 propagations hitting the limiter over a 130 half cycle run and no register reaches a correct value, and skipping them leaves none. And the doubled net names hold the register set an instruction writes while the single-letter ones hold the shadow set, which is the opposite of what the names suggest; that was settled by executing LD r,n for each of A, B, C, D, E, H and L across all eight bit positions and recording which nets followed the loaded value.

**What would settle or reopen it.** Aligning the netlist's clock phase with the manual's CLK by something other than the strobe edges, after which the strobe question can be asked too.; A logic capture from a real part, which is still what would settle any of them outright, because it would agree or disagree with the extraction.

## What is not in question

So the boundary is visible rather than implied:

- **Everything the z80test suite measures.** Its full, documented, MEMPTR and
  CCF programs, whose CRCs were recorded on a real Zilog Z80, pass all 156 of
  their tests each. That is how the block input and output flags left this file:
  the part sets them the way the recording does, not the way the manual prints.
- **What every opcode does to registers, flags and memory.** Held to the recorded
  corpus across all 1,604,000 cases with no failures, undocumented opcodes and
  undocumented flag bits included.
- **How long each instruction takes and what the bus does.** Held to the same
  corpus cycle for cycle, and separately to every timing table in the manual.
- **The flag rules the manual states absolutely.** 126 of them, fuzzed; 124 hold
  and the two that do not are recorded.
- **Which parts exist and what separates them.** Three, with the differences the
  research establishes.
- **The undefined state at power on.** Not a question but a decision: nothing
  here starts cleared, because no machine does.

## What is deliberately not modelled

Absent rather than unknown, and absent on purpose:

- **M1, RFSH and HALT as pins.** The bus log carries RD, WR, MREQ and IORQ.
  An opcode fetch, a refresh address and the HALT state are all there as
  cycle kinds, addresses and `halted`, but no column reports those three
  levels.
