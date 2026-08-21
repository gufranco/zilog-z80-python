# Contributing

## The short version

Evidence over assertion. A change that claims something is correct carries the
run that shows it, and a claim that cannot be checked is not ready.

## Before you open a pull request

Run every gate, and read the output rather than the exit code:

```bash
uvx ruff@0.16.3 format --check .
uvx ruff@0.16.3 check .
uvx mypy@1.14.1
pnpm install --frozen-lockfile && pnpm run format:check
python3 -m coverage erase
for f in $(find z80 conformance -name '*.test.py' | sort); do
  python3 -m coverage run -a "$f" || echo "FAILED $f"
done
python3 -m coverage report
python3 conformance/fetch.py ~/.cache/conformance-suites
python3 conformance/singlestep.py ~/.cache/conformance-suites/z80/v1
python3 conformance/cycles.py ~/.cache/conformance-suites/z80/v1
```

Coverage is a hard gate at 100% statement and branch. A branch with no test
fails the build rather than lowering the number. Types are a hard gate too:
strict, with every optional error class the checker offers, configured in
[pyproject.toml](pyproject.toml) so a local run and the pipeline agree.

## Where an answer has to come from

This project has an authority ladder, and a change that ignores it will be sent
back however correct it looks.

1. [`conformance/hardware.json`](conformance/hardware.json) is Zilog's user
   manual UM008011-0816, pinned fact by fact with the sentence each figure came
   from, including all 184 of its per-instruction timing rows. It decides
   anything Zilog printed, and
   [`conformance/hardware.test.py`](conformance/hardware.test.py) checks the
   model's constants and its timing against it.
2. The suite pinned in [`conformance/suites.json`](conformance/suites.json)
   decides what the manual does not: the two undocumented flag bits, the internal
   `WZ` register, the `Q` latch, every opcode the manual does not list, and where
   the idle states sit inside a long machine cycle.
3. Nothing else. An emulator, an FPGA core and a wiki are rung 2 at best and
   rung 3 for a printed fact.

Where the two disagree, the manual wins and the disagreement goes in
[`conformance/divergences.json`](conformance/divergences.json) with what would
settle it. **Do not resolve one by changing the model to match the suite.** If
the manual is wrong, say why, with the page.

The manual contradicts itself on three pages. Its own T states breakdown wins
over its M Cycles column, and the reason is written down rather than assumed.

## The workflows

They are checked too, by actionlint, and the archive it comes from is verified
by digest before it runs. If you have it installed already, `actionlint` from the
repository root is the same check.

## Tests

A test file sits beside the module it covers and is named after it. Test bodies
carry no comments: arrange, act and assert are separated by one blank line each,
and the test name says what behaviour is being pinned.

Tests that need a file nobody can distribute are skipped rather than passed when
that file is absent, and they live apart from the rest so the coverage gate stays
meaningful on a runner that has nothing.

## Commits

Conventional Commits, subject under fifty characters, imperative mood. The body
explains what changed and why, wrapped at seventy two columns. Releases are cut
by semantic-release from those subjects, so the type is what decides the version.

## What will be sent back

- A file nobody can legally redistribute, or a digest of one fine enough to
  reconstruct it. Whole-file digests are welcome; per-block ones are not.
- A number in a document that no run produced.
- A behaviour changed to match the suite where Zilog says otherwise.
- A divergence closed without evidence from a rung the ladder recognises.
- A timing figure taken from the manual's tables by reading the extracted text
  rather than the page image. That text layer is unreliable for anything numeric.
- A cycle count changed without the sequence being checked, or the other way
  round. Both runners have to pass.
- A test that asserts what the code does rather than what the hardware does.

## Conduct

The [Code of Conduct](CODE_OF_CONDUCT.md) applies everywhere this project is
discussed. One line of it is specific to this repository and worth reading twice:
never post a copyrighted image, a game, or a link to somewhere either can be
downloaded. A digest identifies a file without carrying it, and a digest is all
anybody needs.

## What is welcome without asking

Measurements. If you have cartridges, patches or hardware this has not been run
against, the most useful contribution is a run and what it found, especially a
disagreement.
