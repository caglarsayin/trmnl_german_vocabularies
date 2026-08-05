import re

_SENSE_SPLIT_RE = re.compile(r"\s{2,}")


def first_sense(ubersetzung):
    text = (ubersetzung or "").strip()
    if not text:
        return ""
    parts = _SENSE_SPLIT_RE.split(text)
    return parts[0].strip()
