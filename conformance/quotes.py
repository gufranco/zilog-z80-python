"""Look for every sentence these records call a quote in the documents they cite.

A record that quotes a document is making a checkable claim, and until this file
existed nothing checked it. Reading the quotes against the documents by hand
found three defects across this family: a Q and A answer that read 8259 where the
page prints 8080, inverting which part generates three acknowledge pulses; a
quote that dropped a parenthetical while labelled verbatim; and, in the sibling
repository, a sentence about a clock divided into phases that appears in none of
the twelve documents that project pins.

The documents are not in the repository and never will be: none is
redistributable. So this reports what it could not check rather than passing
quietly, and a run with no documents on disk checks nothing and says so.

Matching is deliberately loose. Every document here is a photograph of a printed
book, and the text layer a scan carries prints lhe for the and OP for DP, so an
exact search finds nothing and the absence means nothing. A quote is scored on
how many of its five-word windows appear, which survives hyphenation, collapsed
spaces and a misread word, and still fails a sentence that was never printed.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unicodedata
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, NamedTuple

ROOT = Path(__file__).resolve().parent.parent

DOCUMENTS = ROOT / "docs" / "manufacturer"

RECORDS = ROOT / "conformance"

WINDOW = 5
"""Words per window. Short enough to survive a misread word, long enough that
matching one is not a coincidence."""

BAR = 0.4
"""The share of windows a quote must place to count as found.

A scan misreads perhaps a word in twenty, and a quote of thirty words has
twenty-six windows, so a passing quote usually places most of them. The bar sits
low because the question is whether the sentence is on the page at all, not
whether the recogniser read it well.
"""

DASHES = (0x2013, 0x2014, 0x2212)

SINGLES = (0x2018, 0x2019, 0x2032)

DOUBLES = (0x201C, 0x201D)

ELSEWHERE = ("referenceDoes", "independent.json")
"""Trails whose quotes are not the manufacturer speaking.

referenceDoes quotes the recording this project is measured against, and
independent.json quotes research by people who probed parts. Neither is in a
pinned document, and looking for them there would report an absence that means
nothing.
"""


class Verdict(NamedTuple):
    """One quote, and the best any pinned document could do with it."""

    where: str
    quote: str
    document: str | None
    placed: int
    windows: int

    @property
    def found(self) -> bool:
        return bool(self.windows) and self.placed / self.windows >= BAR


def flatten(text: str) -> str:
    """Letters and digits only, so a scan's spacing and punctuation stop mattering."""
    text = unicodedata.normalize("NFKD", text)
    for code in DASHES:
        text = text.replace(chr(code), "-")
    for code in SINGLES:
        text = text.replace(chr(code), "'")
    for code in DOUBLES:
        text = text.replace(chr(code), '"')
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def windows(quote: str) -> list[str]:
    """The overlapping word runs a quote is scored on."""
    words = [one for one in re.split(r"\s+", quote) if one]
    if len(words) <= WINDOW:
        return [flatten(quote)]
    return [flatten(" ".join(words[at : at + WINDOW])) for at in range(len(words) - WINDOW + 1)]


def said(node: Any, trail: str = "") -> list[tuple[str, str]]:
    """Every quoted sentence in a record, with where it sits."""
    found: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{trail}.{key}" if trail else key
            if key.endswith(("quote", "Quote")) and isinstance(value, str):
                if not node.get("assembled"):
                    found.append((here, value))
            elif key == "quotes" and isinstance(value, list):
                found.extend(
                    (f"{here}[{at}]", one) for at, one in enumerate(value) if isinstance(one, str)
                )
            else:
                found.extend(said(value, here))
    elif isinstance(node, list):
        for at, one in enumerate(node):
            found.extend(said(one, f"{trail}[{at}]"))
    return found


def quoted() -> list[tuple[str, str]]:
    """Every quote a pinned document is supposed to carry."""
    found: list[tuple[str, str]] = []
    for path in sorted(RECORDS.glob("*.json")):
        for where, quote in said(json.loads(path.read_text()), path.name):
            if not any(one in where for one in ELSEWHERE):
                found.append((where, quote))
    return found


def readable(path: Path) -> str:
    """The text a document carries, flattened. Empty when nothing can read it."""
    done = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    return flatten(done.stdout)


def library(where: Path | None = None) -> dict[str, str]:
    """Every pinned document on this machine, flattened once."""
    folder = DOCUMENTS if where is None else where
    if not folder.is_dir():
        return {}
    return {path.name: readable(path) for path in sorted(folder.glob("*.pdf"))}


def verify(
    held: Iterable[tuple[str, str]] | None = None,
    books: dict[str, str] | None = None,
) -> list[Verdict]:
    """Every quote, scored against the best document that could place it."""
    books = library() if books is None else books
    found = []
    for where, quote in quoted() if held is None else held:
        parts = windows(quote)
        best, name = 0, None
        for title, body in books.items():
            placed = sum(1 for one in parts if one in body)
            if placed > best:
                best, name = placed, title
        found.append(Verdict(where, quote, name, best, len(parts)))
    return found


def report(found: Sequence[Verdict], books: int) -> str:
    """What was checked, what was not, and anything a person should read."""
    if not books:
        return (
            f"{len(found)} quotes checked against 0 documents: none is on this machine, "
            f"so none was checked. They are not redistributable and are named in the "
            f"References section of README.md"
        )
    missing = [one for one in found if not one.found]
    lines = [
        f"{len(found)} quotes against {books} documents, "
        f"{len(found) - len(missing)} located, {len(missing)} not"
    ]
    lines.extend(
        f"  {one.where}: placed {one.placed} of {one.windows} windows"
        f"{'' if one.document is None else f' (best in {one.document})'}\n"
        f"    {one.quote[:110]}"
        for one in missing
    )
    return "\n".join(lines)


def main(
    books: dict[str, str] | None = None,
    held: Iterable[tuple[str, str]] | None = None,
) -> int:
    books = library() if books is None else books
    found = verify(held, books)
    print(report(found, len(books)))
    if not books:
        return 0
    return 0 if all(one.found for one in found) else 1


if __name__ == "__main__":
    sys.exit(main())
