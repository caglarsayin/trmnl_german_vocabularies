import re

_ARTICLE_RE = re.compile(r"^(der|die|das)\s+(.+)$", re.IGNORECASE)
_TAG_RE = re.compile(r"\(([^)]{2,30})\)\s*:")
_TRAILING_RE = re.compile(r"^German\s+(\w+)")

_TAG_TO_POS = {
    "noun": "Noun", "verb": "Verb", "adjektiv": "Adjective", "adjective": "Adjective",
    "adverb": "Adverb", "partikel": "Particle", "präposition": "Preposition",
    "pronomen": "Pronoun", "konjunktion": "Conjunction", "kontraktion": "Contraction",
    "numerale": "Numeral", "artikel": "Article", "interjektion": "Interjection",
}


class ArticleMismatchError(ValueError):
    pass


def extract_article_lemma(wort, klarwort):
    wort = wort.strip()
    klarwort = klarwort.strip()
    match = _ARTICLE_RE.match(wort)
    if not match:
        return None, klarwort
    article, remainder = match.group(1).lower(), match.group(2)
    if remainder.lower() != klarwort.lower():
        raise ArticleMismatchError(
            f"Wort={wort!r} minus article={remainder!r} != Klarwort={klarwort!r}"
        )
    return article, klarwort


def derive_pos(wort, ubersetzung, trailing):
    if _ARTICLE_RE.match(wort.strip()):
        return "Noun"

    tag_match = _TAG_RE.search(ubersetzung or "")
    if tag_match:
        key = tag_match.group(1).strip().lower()
        if key in _TAG_TO_POS:
            return _TAG_TO_POS[key]

    trailing_match = _TRAILING_RE.match((trailing or "").strip())
    if trailing_match and trailing_match.group(1) != "Word":
        return trailing_match.group(1)

    raise ValueError(f"Could not derive POS for Wort={wort!r}")
