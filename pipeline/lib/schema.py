REQUIRED_FIELDS = ["id", "level", "word", "lemma", "pos", "translation", "example_de", "example_en"]
VALID_LEVELS = {"A1", "A2", "B1"}
VALID_RELATIONS = {"same_root", "opposite", "verb_form", "noun_form", "synonym"}
VALID_SOURCES = {"mechanical_validated", "generated"}
VALID_GRAMMAR_TYPES = {"noun_forms", "verb_conjugations", "degrees_of_comparison"}


def validate_entry(entry, require_related=True):
    problems = []

    for field in REQUIRED_FIELDS:
        if not entry.get(field):
            problems.append(f"missing or empty required field: {field}")

    if entry.get("level") not in VALID_LEVELS:
        problems.append(f"invalid level: {entry.get('level')!r}")

    grammar = entry.get("grammar")
    if grammar is not None:
        if grammar.get("type") not in VALID_GRAMMAR_TYPES:
            problems.append(f"invalid grammar type: {grammar.get('type')!r}")
        if not grammar.get("lines"):
            problems.append("grammar present but has no lines")

    related = entry.get("related") or []
    for r in related:
        if r.get("relation") not in VALID_RELATIONS:
            problems.append(f"invalid relation type: {r.get('relation')!r}")
        if r.get("source") not in VALID_SOURCES:
            problems.append(f"invalid related source: {r.get('source')!r}")

    if require_related and not related and not entry.get("related_none"):
        problems.append("related is empty and related_none is not set")

    return problems
