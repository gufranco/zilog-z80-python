# Third-party notices

Everything in this repository is MIT licensed, as [LICENSE](LICENSE) states. One
part of it follows work published by other people under their own terms, and this
file carries those terms.

## The switch-level resolver

[`conformance/netlist.py`](conformance/netlist.py) runs the part as a net of
transistors. Its resolver, its group walk, its propagation loop and its file
readers follow `chipsim.js` and `wires.js` from the Visual 6502 project, which are
published under the MIT licence. The implementation here is written in Python and
is not a translation of theirs, but the behaviour is deliberately theirs, because
a resolver that settles differently is a different chip.

Read against Visual 6502 at commit
`d8ecc129b34e0eaf320e0400fcf33329475bdb1e`, <https://github.com/trebonian/visual6502>.

```
Copyright (c) 2010 Brian Silverman, Barry Silverman

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

## The netlist itself

The three data files that resolver reads are not in this repository and never
will be. [`conformance/netlist.json`](conformance/netlist.json) names them, says
where they come from and records what each one hashes to, so a copy can be
confirmed before it is trusted. The Visual 6502 repository states that licences
and copyright are per file, and those three carry no header of their own, so this
project reads them and redistributes nothing.

## What is not followed

The bus protocol in `half_cycle`, which decides what a machine cycle is from the
state of the control pins, is taken from Zilog's own manual rather than from any
implementation. Every sentence it rests on is in
[`conformance/hardware.json`](conformance/hardware.json) with its page.
