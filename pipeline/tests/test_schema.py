import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.lib.schema import validate_entry

VALID_NOUN = {
    "id": "mitglied",
    "level": "A2",
    "word": "das Mitglied",
    "lemma": "Mitglied",
    "article": "das",
    "pos": "Noun",
    "translation": "member (of an organization), participant",
    "example_de": "Neue Mitglieder sind willkommen.",
    "example_en": "New members are welcome.",
    "grammar": {"type": "noun_forms", "lines": ["Singular: das Mitglied", "Plural: die Mitglieder"]},
    "related": [{"word": "die Mitgliedschaft", "relation": "same_root", "source": "mechanical_validated"}],
}


def test_valid_entry_has_no_problems():
    assert validate_entry(VALID_NOUN) == []


def test_missing_required_field_is_reported():
    entry = dict(VALID_NOUN)
    del entry["translation"]
    problems = validate_entry(entry)
    assert any("translation" in p for p in problems)


def test_grammar_and_article_may_be_none():
    entry = dict(VALID_NOUN)
    entry["grammar"] = None
    entry["article"] = None
    entry["pos"] = "Adverb"
    assert validate_entry(entry) == []


def test_related_must_be_nonempty_or_related_none_true():
    entry = dict(VALID_NOUN)
    entry["related"] = []
    problems = validate_entry(entry)
    assert any("related" in p for p in problems)

    entry["related_none"] = True
    assert validate_entry(entry) == []


def test_require_related_false_skips_that_check():
    entry = dict(VALID_NOUN)
    entry["related"] = []
    assert validate_entry(entry, require_related=False) == []


import json

def test_fixture_file_is_fully_schema_valid():
    fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "vocab.sample.json"
    entries = json.loads(fixture_path.read_text())
    assert len(entries) == 10
    for entry in entries:
        problems = validate_entry(entry)
        assert problems == [], f"{entry['id']}: {problems}"
