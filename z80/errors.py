class UnknownModelError(Exception): ...


class UnknownCarryRule(Exception): ...


class UnknownShape(Exception): ...


class Truncated(Exception): ...


class RunLimit(Exception): ...


class ClockClosed(Exception): ...


class InsideInstruction(Exception):
    def __init__(self, line: str) -> None:
        super().__init__(
            f"{line}() was called inside an instruction; tick the clock to the instruction "
            f"boundary, or set {line}_line, which the part samples when the instruction completes"
        )
