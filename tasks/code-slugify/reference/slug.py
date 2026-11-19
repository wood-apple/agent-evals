import re
import unicodedata

_SPECIAL = {"ß": "ss", "ø": "o", "Ø": "o", "æ": "ae", "Æ": "ae", "œ": "oe", "đ": "d", "ł": "l"}


def slugify(text: str, max_len: int = 40) -> str:
    s = "".join(_SPECIAL.get(c, c) for c in text)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) > max_len:
        cut = s.rfind("-", 0, max_len + 1)
        s = (s[:cut] if cut > 0 else s[:max_len]).rstrip("-")
    return s
