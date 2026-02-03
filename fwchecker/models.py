from dataclasses import dataclass

@dataclass
class CheckResult:
    input_version: str
    popup_version: str | None
    result: str
    message: str
    ts: str
