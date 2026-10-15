from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DEFINITION = ROOT / "suites.json"

USAGE = "usage: python3 -m conformance.regenerate <output-directory> [--full] [--clone DIR]"

CLONE_TIMEOUT = 600

RUN_TIMEOUT = 7200

HEAP_MEGABYTES = 20480

FLAG = "let Z80_DO_FULL_MEMCYCLES = false;"

DRIVER = """
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const [root, output, full] = process.argv.slice(2);
fs.mkdirSync(output, { recursive: true });

const sources = %(sources)s;
let code = sources
  .map((name) => fs.readFileSync(path.join(root, name), 'utf8'))
  .join('\\n');

if (full === 'true') {
  const flag = %(flag)s;
  if (!code.includes(flag)) {
    throw new Error('the flag line is not where it was: ' + flag);
  }
  code = code.replace(flag, flag.replace('false', 'true'));
}

// The generator writes each file through JSZip and then hands the finished
// archive to the browser to download. Only the first half has a headless
// equivalent, so the archive is a stub and the download is stubbed out with the
// four browser globals the download reaches for. Letting it run rather than
// catching what it throws keeps the failure of anything else visible.
const elem = { click: () => {} };
const nothing = { appendChild: () => {}, removeChild: () => {}, createElement: () => elem };
const sandbox = {
  console,
  dconsole: { addl: (...parts) => process.stderr.write(parts.join(' ') + '\\n') },
  Blob: function () {},
  document: nothing,
  window: { document: nothing, navigator: {}, URL: { createObjectURL: () => '' } },
  JSZip: function () {
    this.file = (name, body) => fs.writeFileSync(path.join(output, name), body);
    this.generateAsync = async () => Buffer.alloc(0);
  },
};
sandbox.document.body = nothing;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(code + '\\n;generate_Z80_tests(null, false);', sandbox);
"""


def definition(path: Path | str | None = None) -> dict[str, Any]:
    with Path(path or DEFINITION).open() as handle:
        suites: list[dict[str, Any]] = json.load(handle)["suites"]
    generator: dict[str, Any] = suites[0]["generator"]
    return generator


def clone_command(generator: dict[str, Any], directory: Path | str) -> list[list[str]]:
    where = str(directory)
    return [
        ["git", "init", "-q", where],
        ["git", "-C", where, "remote", "add", "origin", generator["repository"]],
        ["git", "-C", where, "fetch", "-q", "--depth=1", "origin", generator["commit"]],
        ["git", "-C", where, "checkout", "-q", "FETCH_HEAD"],
    ]


def driver(generator: dict[str, Any]) -> str:
    sources = [*generator["requires"], generator["entryPoint"].split(",")[0].strip()]
    return DRIVER % {"sources": json.dumps(sources), "flag": json.dumps(FLAG)}


def clone(generator: dict[str, Any], directory: Path | str) -> Path:
    directory = Path(directory)
    if directory.is_dir() and any(directory.iterdir()):
        return directory
    directory.mkdir(parents=True, exist_ok=True)
    for step in clone_command(generator, directory):
        done = subprocess.run(
            step, capture_output=True, text=True, check=False, timeout=CLONE_TIMEOUT
        )
        if done.returncode:
            raise SystemExit(f"cloning the generator failed at {' '.join(step)}\n{done.stderr}")
    return directory


def generate(generator: dict[str, Any], source: Path, output: Path, full: bool) -> int:
    if shutil.which("node") is None:
        raise SystemExit("node is not on the path, and the generator is a JavaScript program")
    output.mkdir(parents=True, exist_ok=True)
    script = output / "driver.js"
    script.write_text(driver(generator))
    done = subprocess.run(
        [
            "node",
            f"--max-old-space-size={HEAP_MEGABYTES}",
            str(script),
            str(source),
            str(output),
            "true" if full else "false",
        ],
        check=False,
        timeout=RUN_TIMEOUT,
    )
    script.unlink()
    return done.returncode


def options(argv: Sequence[str]) -> tuple[Path, bool, Path | None]:
    if not argv:
        raise SystemExit(USAGE)
    output: str | None = None
    clone_into: str | None = None
    full = False
    rest = list(argv)
    while rest:
        item = rest.pop(0)
        if item == "--full":
            full = True
        elif item == "--clone":
            if not rest:
                raise SystemExit(USAGE)
            clone_into = rest.pop(0)
        elif output is None:
            output = item
        else:
            raise SystemExit(USAGE)
    if output is None:
        raise SystemExit(USAGE)
    return Path(output), full, Path(clone_into) if clone_into else None


def main(argv: Sequence[str], held: Path | str | None = None) -> int:
    output, full, clone_into = options(argv)
    generator = definition(held)
    source = clone(generator, clone_into or (Path.home() / ".cache" / "z80-test-generator"))
    code = generate(generator, source, output, full)
    if code:
        print(f"the generator exited {code}")
        return code
    written = len(list(output.glob("*.json")))
    shape = "full memory cycles" if full else "as published"
    print(f"{written} files written to {output}, {shape}, generator {generator['commit'][:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
