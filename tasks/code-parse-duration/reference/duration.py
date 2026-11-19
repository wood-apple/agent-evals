import re

_UNITS = {"d": 86400, "h": 3600, "m": 60, "s": 1}
_ORDER = "dhms"


def parse_duration(text: str) -> int:
    s = text.replace(" ", "")
    if not s:
        raise ValueError("empty")
    parts = re.findall(r"(\d+)([a-z])", s)
    if "".join(n + u for n, u in parts) != s:
        raise ValueError(f"bad duration {text!r}")
    total, last = 0, -1
    for n, u in parts:
        if u not in _UNITS:
            raise ValueError(f"unknown unit {u}")
        idx = _ORDER.index(u)
        if idx <= last:
            raise ValueError("units out of order or repeated")
        last = idx
        total += int(n) * _UNITS[u]
    return total
