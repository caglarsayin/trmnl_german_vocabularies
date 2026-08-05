import re

_ARTIFACT_RE = re.compile(r"(?<=[.!?])\s*\d+\.\s+(?=[A-ZÄÖÜ])")
_SPLIT_RE = re.compile(r"(?<=[.!?])(?=[A-ZÄÖÜ])")
_LEADING_NUM_RE = re.compile(r"^\s*\d+\.\s*")


def split_examples(cell):
    text = (cell or "").strip()
    if not text:
        return []
    text = _ARTIFACT_RE.sub("", text)
    parts = _SPLIT_RE.split(text)
    parts = [_LEADING_NUM_RE.sub("", p).strip() for p in parts]
    if len(parts) % 2 != 0:
        return None
    return [(parts[i], parts[i + 1]) for i in range(0, len(parts), 2)]


def collect_pairs(cells):
    all_pairs = []
    ambiguous = False
    for cell in cells:
        if not (cell or "").strip():
            continue
        result = split_examples(cell)
        if result is None:
            ambiguous = True
            continue
        all_pairs.extend(result)
    return all_pairs, ambiguous


def pick_example(pairs, level):
    if not pairs:
        return None
    ordered = sorted(pairs, key=lambda pair: len(pair[0]))
    if level == "A1":
        return ordered[0]
    if level == "A2":
        return ordered[len(ordered) // 2]
    return ordered[-1]
