# Security

## Reporting

Report anything you believe is a security problem through
[GitHub's private vulnerability reporting](https://docs.github.com/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability)
on this repository, rather than in a public issue. There is no service behind
this and no user data, so the realistic reports are about the supply chain and
about what a malformed input can make the code do.

## What is in scope

| Class | Example |
|-------|---------|
| Supply chain | A dependency or a pinned action that has been compromised |
| Malformed input | A crafted suite file that makes a runner allocate without bound or loop without end |
| Path handling | An input that causes a write outside the directory the caller named |
| Pin handling | Anything that makes a fetch resolve to something other than the pinned commit |

## What is not

A conformance disagreement is a correctness bug and belongs in a normal issue.
So does a model that disagrees with real hardware. Neither is a security matter,
and filing them privately only slows the fix.

## What this repository does fetch, and when

The conformance suite is large and is not carried here, so `conformance/fetch.py`
clones it. That is the one thing in this project that reaches the network, it
runs only when a person or a workflow asks it to, and it clones the commit named
in `conformance/suites.json` rather than whatever a branch points at today. A
report that the fetch path can be made to clone somewhere else, or to run a
command out of that file, is in scope and is the most interesting thing here.

Nothing is fetched while the core is running. Any file the model reads is one
already on the machine because somebody put it there.
