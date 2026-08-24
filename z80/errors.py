"""Everything this package raises, in one place.

An exception is named by whoever catches it, so where it is defined decides
whether `except ThatName` written against one module holds against another. They
were spread across five modules here, which is how a sibling package ended up
with two classes under one name and an `except` that caught half the cases it
was written for.

One definition each, and every module that raises one imports it from here. This
module imports nothing from the package, so it can never be the far end of a
cycle.
"""


class UnknownModelError(Exception):
    """A name that is not a part this package knows, nor an alias of one."""


class UnknownCarryRule(Exception):
    """A model asked for a carry flag rule nobody has measured."""


class UnknownShape(Exception):
    """A bus asked for a pin shape that is neither documented nor recorded."""


class Truncated(Exception):
    """The bytes ran out before the instruction did."""


class RunLimit(Exception):
    """A bounded run reached its bound before the caller's condition held.

    Only `run_until` raises this, and only when a caller asked for a bound. A
    part has no such limit: given a program that never satisfies the condition
    it runs until the power goes. The bound is a courtesy to whoever is driving,
    not a property of the silicon.
    """


class ClockClosed(Exception):
    """A clock that has been closed cannot be ticked again."""
