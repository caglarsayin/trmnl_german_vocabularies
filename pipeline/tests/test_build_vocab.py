import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.build_vocab import merge

PARSED = [
    {"id": "argern", "lemma": "ärgern", "level": "B1", "word": "ärgern", "article": None,
     "pos": "Verb", "translation": "to annoy", "example_de": "x.", "example_en": "y.",
     "grammar": None, "related": []},
    {"id": "katze", "lemma": "Katze", "level": "A1", "word": "die Katze", "article": "die",
     "pos": "Noun", "translation": "cat", "example_de": "x.", "example_en": "y.",
     "grammar": None, "related": []},
]


def test_merge_applies_validated_pairs_and_generated_links():
    result = {
        "validated": [
            {"lemma": "ärgern", "candidate_lemma": "ärgerlich", "valid": True, "relation": "same_root"},
        ],
        "generated": [
            {"lemma": "Katze", "related": [{"word": "der Kater", "relation": "opposite"}], "related_none": False},
        ],
        "needs_review_resolved": [],
    }
    merged = merge(PARSED, result)
    by_id = {e["id"]: e for e in merged}
    assert by_id["argern"]["related"] == [
        {"word": "ärgerlich", "relation": "same_root", "source": "mechanical_validated"}
    ]
    assert by_id["katze"]["related"] == [
        {"word": "der Kater", "relation": "opposite", "source": "generated"}
    ]


def test_merge_skips_invalid_candidate_pairs():
    result = {
        "validated": [
            {"lemma": "ärgern", "candidate_lemma": "ärgerlich", "valid": False, "relation": "none"},
        ],
        "generated": [{"lemma": "Katze", "related": [], "related_none": True}],
        "needs_review_resolved": [],
    }
    merged = merge(PARSED, result)
    by_id = {e["id"]: e for e in merged}
    assert by_id["argern"]["related"] == []
    assert by_id["argern"]["related_none"] is False  # still ungated -- see gate test below


def test_gate_fails_loudly_when_a_word_has_neither_related_nor_related_none():
    from pipeline.build_vocab import check_completeness

    incomplete = [
        {"id": "argern", "related": [], "related_none": False},
        {"id": "katze", "related": [{"word": "x", "relation": "opposite", "source": "generated"}]},
    ]
    with pytest.raises(ValueError, match="argern"):
        check_completeness(incomplete)


def test_gate_passes_when_every_word_has_related_or_related_none():
    from pipeline.build_vocab import check_completeness

    complete = [
        {"id": "argern", "related": [], "related_none": True},
        {"id": "katze", "related": [{"word": "x", "relation": "opposite", "source": "generated"}]},
    ]
    check_completeness(complete)  # should not raise
