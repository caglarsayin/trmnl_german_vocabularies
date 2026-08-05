import re

_NOUN_RE = re.compile(r"Singular \(Einzahl\):\s*(?P<singular>.+?)Plural \(Mehrzahl\):\s*(?P<plural>.+)$")
_VERB_REGULARITY_RE = re.compile(r"(?P<regularity>regelmäßig|unregelmäßig)")
_VERB_PARTIZIP_RE = re.compile(r"Partizip II:\s*(?P<partizip>.+?)Present\s*\(Präsens\)")
_COMPARISON_PART_RE = re.compile(
    r"(?P<label>Positive|Comparative|Superlative):\s*(?P<value>.+?)(?=(?:Positive|Comparative|Superlative):|$)"
)

_MARKERS = {"🔢": "noun_forms", "🔄": "verb_conjugations", "📊": "degrees_of_comparison"}
_TITLES = {
    "noun_forms": "Noun Forms",
    "verb_conjugations": "Verb Conjugations",
    "degrees_of_comparison": "Degrees of Comparison",
}


def parse_grammar(detail_text):
    text = detail_text or ""
    for marker, gtype in _MARKERS.items():
        idx = text.find(marker)
        if idx == -1:
            continue
        section = text[idx + len(marker):].lstrip()
        title = _TITLES[gtype]
        if section.startswith(title):
            section = section[len(title):]
        if gtype == "noun_forms":
            return _parse_noun(section)
        if gtype == "verb_conjugations":
            return _parse_verb(section)
        return _parse_comparison(section)
    return None


def _parse_noun(section):
    match = _NOUN_RE.search(section)
    if not match:
        raise ValueError(f"Could not parse noun_forms section: {section!r}")
    plural = re.sub(r"^(der|die|das)\s+", "", match["plural"].strip())
    return {"type": "noun_forms", "lines": [f"Singular: {match['singular'].strip()}", f"Plural: {plural}"]}


def _parse_verb(section):
    partizip_match = _VERB_PARTIZIP_RE.search(section)
    if not partizip_match:
        # e.g. "möchten" -- no Partizip II given; nothing useful to show.
        return None
    regularity_match = _VERB_REGULARITY_RE.search(section)
    line = f"Partizip II: {partizip_match['partizip'].strip()}"
    if regularity_match:
        line += f" ({regularity_match['regularity']})"
    return {"type": "verb_conjugations", "lines": [line]}


def _parse_comparison(section):
    parts = {m["label"]: m["value"].strip() for m in _COMPARISON_PART_RE.finditer(section)}
    if not parts:
        raise ValueError(f"Could not parse degrees_of_comparison section: {section!r}")
    lines = []
    if "Comparative" in parts:
        lines.append(f"Comparative: {parts['Comparative']}")
    if "Superlative" in parts:
        lines.append(f"Superlative: {parts['Superlative']}")
    if not lines:
        # Only Positive was present -- word doesn't inflect for comparison.
        return None
    return {"type": "degrees_of_comparison", "lines": lines}
