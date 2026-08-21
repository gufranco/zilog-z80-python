# The family standard

These nine repositories are one family and are held to one standard. Where they
differ, the difference must be something the hardware forces, not something
nobody got round to.

| Repository | What it models |
|:--|:--|
| [mos65xx-python](https://github.com/gufranco/mos65xx-python) | The 65xx family, eight parts |
| [nec-upd7725-python](https://github.com/gufranco/nec-upd7725-python) | The DSP the SNES coprocessors are built on |
| [snes-driver-python](https://github.com/gufranco/snes-driver-python) | Reading a cartridge's own coprocessor protocol |
| [snes-dsp-python](https://github.com/gufranco/snes-dsp-python) | The DSP-1 to DSP-4 family |
| [snes-mapper-python](https://github.com/gufranco/snes-mapper-python) | Cartridge headers and address decoding |
| [snes-rom-image-python](https://github.com/gufranco/snes-rom-image-python) | A cartridge image as a file |
| [snes-rtc-python](https://github.com/gufranco/snes-rtc-python) | The two cartridge real-time clocks |
| [star-ocean-nochip-fix](https://github.com/gufranco/star-ocean-nochip-fix) | One header correction, end to end |
| [zilog-z80-python](https://github.com/gufranco/zilog-z80-python) | The Z80 |

## The authority ladder

Every factual question is answered by the highest rung that has an answer, and a
lower rung never overrules a higher one.

1. **Manufacturer documentation.** Anything printed decides. Read it in full
   rather than searching it, because the passages that matter are the ones
   nobody quotes.
2. **The part's own program or the artefact itself.** A cartridge, a firmware
   image, a header. What the silicon was actually asked to do.
3. **A recording from an independent implementation**, for behaviour nobody
   documented.
4. **Nothing else.** An emulator, an FPGA core, a wiki and a forum post are rung
   3 at best and rung 4 for anything printed.

A document that contradicts itself is common. When it does, the cycle table and
the pin descriptions have both times been right and the prose wrong.

## What every repository carries

| Gate | Standard |
|:--|:--|
| Format | `ruff format --check .`, clean |
| Lint | `ruff check .`, zero findings |
| Types | `mypy` at strict plus every optional error class, zero findings |
| Tests | `<module>.test.py` beside the module, run individually |
| Coverage | 100% statement and branch, enforced, on a machine holding no artefacts |
| JSON | `pnpm run format:check`, with every submodule tree exempted |
| CI | lint, types, tests on 3.12/3.13/3.14, plus the project's own conformance job |
| Release | semantic-release from `main`, never tagged by hand |
| Docs | README, AGENTS.md, CLAUDE.md, CONTRIBUTING, SECURITY, CODE_OF_CONDUCT |
| Specs | `specs/current/`, requirements with checkable scenarios |
| Hardware facts | `conformance/hardware.json`, every fact with the sentence it came from |
| Disagreements | `conformance/divergences.json`, both readings and what would settle it |

## Conventions that are not negotiable

| Thing | Rule |
|:--|:--|
| Language | Python only |
| Comments | None in source, ever. Docstrings carry the reasoning |
| Test structure | Arrange, blank line, one act, blank line, assert. No section labels |
| Nothing starts clean | Memory and registers hold what they held, from a seed |
| Artefacts | Never committed: no ROM, no firmware, no fragment of one |
| Only retail dumps | A ROM hack is somebody's edit, not what hardware ran |

## What is not done yet

**Type checking is not started.** `pyproject.toml` carries the strict mypy
configuration the family uses, and `mypy` reports about 1,132 findings, nearly
all of them missing annotations. The CI job that runs mypy is deliberately absent
until the count reaches zero.

**Cycles are not compared.** The sibling `mos65xx-python` holds every one of its
eight parts to the recorded bus activity, cycle by cycle, address by address, and
on the 65816 pin by pin. This project reads the same kind of corpus and compares
only state. The Z80's own data sheet carries the M-cycle and T-state breakdown
for every instruction, and `mos65xx-python/conformance/cycles.py` is the shape to
copy.

**No `conformance/hardware.json`, no `conformance/divergences.json`.** Zilog's
Z80 CPU User Manual is the document, and nothing here quotes it.

**No `specs/current/`, no `AGENTS.md`, no `CLAUDE.md`, no analysis workflow, no
CONTRIBUTING, SECURITY or CODE_OF_CONDUCT.**
