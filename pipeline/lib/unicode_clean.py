# -*- coding: utf-8 -*-
import re

_HOMOGLYPHS = {
    "е": "e",  # CYRILLIC SMALL LETTER IE
}

_REPLACEMENTS = {
    "‌": "",     # ZERO WIDTH NON-JOINER
    "­": "",      # SOFT HYPHEN
    "‑": "-",     # NON-BREAKING HYPHEN
    "‘": "'",     # LEFT SINGLE QUOTATION MARK
    "’": "'",     # RIGHT SINGLE QUOTATION MARK
    "“": '"',     # LEFT DOUBLE QUOTATION MARK
    "”": '"',     # RIGHT DOUBLE QUOTATION MARK
    "„": '"',     # DOUBLE LOW-9 QUOTATION MARK
    "‚": "'",     # SINGLE LOW-9 QUOTATION MARK
    "–": "-",     # EN DASH
    "—": "-",     # EM DASH
    "…": "...",   # HORIZONTAL ELLIPSIS
}


def clean(text):
    if text is None:
        return ""
    for bad, good in _HOMOGLYPHS.items():
        text = text.replace(bad, good)
    for bad, good in _REPLACEMENTS.items():
        text = text.replace(bad, good)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
