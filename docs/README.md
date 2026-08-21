# The documents this package is held to

Nineteen of them, split by what they can settle rather than by subject. Every one
carries a SHA-256 in [`documents.json`](documents.json), so a copy can be checked
rather than trusted, and [`documents.py`](documents.py) brings the whole folder down again
and refuses anything whose digest does not match.

## The ladder

| Rung | What it is | What it settles |
|:--|:--|:--|
| 1 | A Zilog document | What the manufacturer printed about its own part |
| 2 | A recording taken off a real part | Nothing here. That is [`../conformance/suites.json`](../conformance/suites.json) |
| 3 | Independent research | What Zilog did not print, worked out by measuring parts |
| 4 | A bibliography | What exists, not how the part behaves |

**Nothing on rung 3 is ever a citation for a figure a rung 1 document gives.**
Where the two speak to the same thing and disagree, the disagreement goes in
[`../conformance/divergences.json`](../conformance/divergences.json) with what
would settle it, rather than being resolved by preference.

## What is here

`manufacturer/` holds the two Zilog documents. Between them they cover both parts
this package builds: the user manual for behaviour and timing, the product
specification for what the two parts are as products.

`independent/` holds the rest. The three that matter most:

- **Young, The Undocumented Z80 Documented.** The standard account of everything
  Zilog left out, and the document every other one in this folder answers to.
- **Banks, Undocumented Z80 Flags.** The flag changes an interrupted block
  instruction leaves behind, and the finding that the Zilog, NEC and ST parts do
  not agree about what an SCF or CCF produces. That last one is why a model name
  is not enough to pick a flag rule.
- **boo_boo and Kladov, MEMPTR.** What the internal address register holds after
  each instruction, which is the register this package calls WZ.

The rest are the die analyses, the interrupt and reset behaviour nobody
documented, and the threads in which two of the above were worked out.

## Why the files are not in git

They are the publishers' documents rather than this project's, and this
repository is public. One of the nineteen carries a licence that permits
redistribution; the others do not say. What is committed is the identity of each,
which is what makes a copy checkable, and the script that fetches them.

```bash
python3 docs/documents.py          # bring them down and verify every digest
python3 docs/documents.py --check  # verify what is already here, fetch nothing
```
