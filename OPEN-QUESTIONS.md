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

### What the eight block input and output instructions do to the negate and carry flags.

**The document says.** S is unknown. Z is set if B - 1 = 0; otherwise it is reset. H is unknown. P/V is unknown. N is set. C is not affected.

Source: Zilog UM008011-0816, the INI page and the seven like it.

**What this project follows.** reference

**Why.** The corpus fixes these flags on every one of its cases and this core reproduces it, and the rule the research states independently gives the same answer on all eighty combinations of the counter, the port and the byte that were tried. Two lineages that never consulted each other agree, and the manual disagrees with both.

**What would settle or reopen it.** A program on a real part: clear the carry, run one block input whose sum overflows, and read the flag back.

## Where a document disagrees with itself

One publication saying two things. The reading this project follows is argued in each entry, but only silicon closes it.

### Whether the lowest bit of the byte a device supplies reaches the pointer.

**The document says.** The lower eight bits of the pointer must be supplied by the interrupting device. Only seven bits are required from the interrupting device, because the least-significant bit must be a 0. This process is required, because the pointer must receive two adjacent bytes to form a complete 16-bit service routine starting address; addresses must always start in even locations.

Source: Zilog UM008011-0816, manual page 20.

**What this project follows.** reference

**Why.** The manual's sentence is sound advice to whoever builds the table and is not a description of what the silicon does with the byte. The only party to have tested it reports the opposite, and nothing in the corpus covers it because the corpus contains no interrupt cases.

**What would settle or reopen it.** A program on a real part: point the table at an odd address, raise the line, supply an odd vector, and see where it lands.

## Where nobody wrote it down

Behaviour no manufacturer documented. The recordings agree with independent research, which is two lineages rather than one, and still not a measurement.

### What the address pins hold during the second half of an opcode fetch.

**The document says.** During T3 and T4, the lower seven bits of the address bus contain a memory refresh address and the RFSH signal becomes active, indicating that a refresh read of all dynamic memories must be performed.

Source: Zilog UM008011-0816, manual page 8.

**What this project follows.** reference, in both shapes

**Why.** The manual guarantees only seven bits, so the rest is not a figure it prints. The recording supplies a whole address and this core reproduces it. A model that put something else in the upper nine bits would disagree on every instruction and would have no document behind it either.

**What would settle or reopen it.** A logic capture reading all sixteen address lines during T3 of a fetch.

### Where within a long machine cycle the bus falls idle.

**What this project follows.** reference

**Why.** The two sources are answering different questions rather than contradicting each other. Recorded here so that a reader does not take the whole cycle claim as resting on the manual when half of it rests on the recording.

**What would settle or reopen it.** A logic capture of an instruction with more than one idle state, showing which machine cycle carries them.

### Bits 3 and 5 of the flag register.

**The document says.** Each of these two Flag registers contains 6 bits of status information that are set or cleared by CPU operations; bits 3 and 5 are not used.

Source: Zilog UM008011-0816, manual page 66.

**What this project follows.** reference

**Why.** Saying a bit is not used is a statement about what the designer intended a programmer to read, not a claim that the bit reads as zero. The manual declines to specify rather than specifying something else, so this is an absence rather than a contradiction.

**What would settle or reopen it.** Nothing short of Zilog documenting it, which no revision of this manual has done in eleven revisions over forty years.

### The internal register the recording calls WZ, and the flags latch it calls Q.

**What this project follows.** reference

**What would settle or reopen it.** A die analysis, or Zilog documenting the internal register file.

### The opcodes the manual does not list.

**What this project follows.** reference

**What would settle or reopen it.** Nothing available. These encodings were never specified; they are what the decoder happens to do.

### Which address a halted part puts on the bus.

**The document says.** Each cycle in the HALT state is a normal M1 (fetch) cycle except that the data received from the memory is ignored and an NOP instruction is forced internally to the CPU.

Source: Zilog UM008011-0816, manual page 14.

**What this project follows.** document, for the cycle; neither, for the address

**Why.** The manual says outright that the halted part keeps performing M1 cycles, so emitting none was reporting a machine cycle the part performs as one it does not. It does not say which address those cycles carry: the note under Figure 11 says the halt instruction is repeated, which would put the previous address on the bus, and the counter is where a part that simply stopped advancing would fetch from.

**What would settle or reopen it.** A logic capture of a halted Z80, reading the address lines during any of its M1 cycles.; A recording that steps a machine which is already halted, which this corpus does not.

### The corpus generator has changed its mind about behaviour nobody documented.

**What this project follows.** the pinned corpus

**Why.** The pin exists so a run is reproducible. Following the head instead would be swapping one undocumented opinion for a newer one with nothing to prefer it by.

**What would settle or reopen it.** A real part, for any of the eleven. Nothing else can, because no document speaks to any of them.

### Where the seventh T state of an interrupt acknowledge falls.

**The document says.** This mode of response requires 19 clock periods to complete (seven to fetch the lower eight bits from the interrupting device, six to save the program counter, and six to obtain the jump address).

Source: Zilog UM008011-0816, manual page 20.

**What this project follows.** document

**Why.** Reading the cycle as a four state fetch plus the two added waits gives six, and six makes the printed mode 2 total eighteen against a printed nineteen. The reading that satisfies both printed figures is a five state M1 under the two waits.

**What would settle or reopen it.** A logic capture of a real Z80 answering an interrupt, counting the states of the acknowledge cycle.

### What the internal address register holds once an interrupt has been taken.

**What this project follows.** neither

**Why.** Leaving it alone would be as much of a guess as setting it, and it would be a quieter one. Setting it the way the nearest documented instruction does at least makes the guess a consistent one, and this entry is what stops it reading as a finding.

**What would settle or reopen it.** A recording that takes an interrupt and reports the register afterwards.; A die analysis, or Zilog documenting the internal register file.

### Where the later bytes of a multi byte mode zero response come from.

**The document says.** With Mode 0, the interrupting device can place any instruction on the data bus and the CPU executes it. Consequently, the interrupting device provides the next instruction to be executed. Often this response is a restart instruction because the interrupting device is required to supply only a single-byte instruction. Alternatively, any other instruction such as a 3-byte call to any location in memory could be executed.

Source: Zilog UM008011-0816, manual page 19.

**What this project follows.** document, for the cycles; neither, for the bytes

**Why.** The device sits on the same data bus and answers those reads on real hardware, so the cycles a multi byte response performs are ordinary memory reads either way. What this cannot model is a device that answers them without the memory holding the same bytes, because there is one byte in the call and no pin for a device to drive.

**What would settle or reopen it.** An interface that lets a caller answer each read of a response rather than only the acknowledge, at which point the cycles above are already right.

### Where the two undocumented flag bits come from after a carry instruction, which is not the same answer on every part.

**What this project follows.** reference, and only for the two of the three rules that are not disputed

**Why.** The NEC part was previously another name for the Zilog model, which made this package answer for a part whose measured behaviour it does not reproduce. A part number that resolves to the wrong behaviour is worse than an absent one, because it answers.

**What would settle or reopen it.** A recording taken off each part, which is what the pinned corpus is for the Zilog one and does not exist for the others.

### Whether ST's CMOS part has a carry flag rule of its own.

**What this project follows.** neither

**Why.** Two rung three sources disagree, one of them says the other may have been reading instability rather than a rule, and no recording exists for either. Modelling a rule under those conditions would be picking a side of an open question and calling the result a part.

**What would settle or reopen it.** A recording taken off an ST CMOS part, on a board known to produce stable values for these two bits.

### What a mode zero response does when the byte the device supplies is a prefix.

**The document says.** With Mode 0, the interrupting device can place any instruction on the data bus and the CPU executes it.

Source: Zilog UM008011-0816, manual page 19.

**What this project follows.** document, which is to say neither

**Why.** The interface takes one byte. Producing a second acknowledge cycle would mean asking the caller for a second byte, which is the same interface change the multi byte case needs, and doing half of it would leave the counts right and the pins wrong in a different place.

**What would settle or reopen it.** An interface that lets a caller answer each cycle of a response rather than only the first.

## Where the question is a modelling choice, not a fact

Two defensible ways to record the same silicon. Both are implemented here and the recordings pick one; the part does neither, it does something continuous that both are sampling.

### How many T states a strobe occupies, when a T state is the smallest column there is.

**The document says.** One half clock cycle later, the MREQ signal goes active. At this time, the address to memory has had time to stabilize so that the falling edge of MREQ can be used directly as a chip enable clock to dynamic memories. The RD line also goes active to indicate that the memory read data should be enabled onto the CPU data bus. The CPU samples the data from the memory space on the data bus with the rising edge of the clock of state T3, and this same edge is used by the CPU to turn off the RD and MREQ signals.

Source: Zilog UM008011-0816, manual page 8.

**What this project follows.** document by default, reference in the comparison runner

**Why.** A four character string per T state cannot express a waveform whose edges land between states, so any per-state model applies a rule the manual never states. Calling the recording wrong would be treating one such rule as a fact. Calling it right would be treating a documented simplification as a measurement. Both shapes are kept, named, and produced from the same edge table.

**What would settle or reopen it.** A logic capture of a real Z80, which would give the edges directly rather than through a drawing.; Nothing in the document settles it, because the question is about the model's resolution rather than about the part.

## Where the evidence exists but has not been run here

Not unknown to the world, unverified in this repository.

### The interrupt acknowledge cycle, which is modelled and which nothing verifies.

**The document says.** When the signal is accepted, a special M1 cycle is generated. During this special M1 cycle, the IORQ signal becomes active (instead of the normal MREQ) to indicate that the interrupting device can place an 8-bit vector on the data bus. Two wait states are automatically added to this cycle.

Source: Zilog UM008011-0816, manual page 12.

**What this project follows.** document

**Why.** The generator does emit entries for the interrupt request and for reset, and the published corpus leaves both out. Neither would settle anything if it were published: each case is an ordinary instruction stepped from the given state, with the opcode at the program counter deciding the transcript, so the interrupt entry is not a recording of an acknowledge cycle at all.

**What would settle or reopen it.** A logic capture of a real Z80 answering an interrupt, which would give the pins and the length together.; A corpus that contains acknowledge cycles, which this one does not.

### The one source that could settle most of the entries above, and why it is not being used.

**What this project follows.** neither

**Why.** A port of the netlist's own resolver was written and does not work yet. What is established: the three files parse to the counts the reference expects, the transistors switch, and the chip holds the reset address for the first several half clocks. What is not: the netlist does not come to rest on a falling clock edge, a ring of about eight nets flips forever, and the state degrades over tens of half clocks until the pins read as a chip no silicon could be. The reference has a loop limiter for the same non convergence, so tolerating it is not the difference. Shipping a simulator that does not run the part would be worse than not having one.

**What would settle or reopen it.** Finding what the port does differently on a falling edge. The resolver, the group walk, the queueing, the pull-up parse and the transistor orientation were each checked against the reference and match, so the difference is somewhere finer than those.; Driving the reference application itself, which is a Qt program rather than a library, and reading its waveform export.

## What is not in question

So the boundary is visible rather than implied:

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

- **Wait states.** No slow memory to wait for.
- **Bus request and bus acknowledge.** No second bus master to arbitrate with.
- **Power-down modes.** Nothing here has a power rail.
