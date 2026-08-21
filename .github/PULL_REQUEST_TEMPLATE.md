## What this changes

One or two sentences. What is different afterwards, and why it needed to be.

## How it was checked

Paste the output rather than describing it. A claim that the tests pass is not
evidence that they did.

```text
```

- [ ] `ruff format --check .` and `ruff check .` are clean
- [ ] `mypy` reports nothing
- [ ] Every test file runs, and coverage is 100% of statements and branches
- [ ] `conformance/hardware.test.py` still holds every figure to the manual

## If this changes what the processor does

The state comparison is not enough on its own. A push writing the low half of a
register pair before the high half touches the same two addresses and leaves
identical final state, and it passed the state comparison for as long as it
existed. Run the cycle comparison and paste its last two lines:

```bash
python3 conformance/cycles.py
```

Every T state is compared, not the count: the address, the value, and the four
control pins. A change that leaves the totals equal and moves any one of those
is still a change to what the part does.

## If this changes a number the manual prints

Say which page. `conformance/hardware.json` carries the page for every one of
the 184 timing rows, and `conformance/hardware.test.py` reads the figure from
there rather than repeating it, so a citation is a check that can fail.

The manual contradicts itself on three pages. All three are recorded, and the
breakdown wins over the M Cycles column. A fourth would need the same treatment:
found by arithmetic, then confirmed against the rendered page.

## What it does not carry

- [ ] No firmware, no ROM, and no fragment of either
- [ ] Nothing that says where to obtain them
