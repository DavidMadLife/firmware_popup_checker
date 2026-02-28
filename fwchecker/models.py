from dataclasses import dataclass

@dataclass
class CheckResult:
    input_version: str
    popup_version: str | None  # dùng chung: POPUP version hoặc INLINE version
    result: str
    message: str
    ts: str