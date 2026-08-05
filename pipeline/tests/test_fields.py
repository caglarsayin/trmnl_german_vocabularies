import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.lib.fields import ArticleMismatchError, derive_pos, extract_article_lemma


def test_noun_with_article_extracts_cleanly():
    article, lemma = extract_article_lemma("das Mitglied", "Mitglied")
    assert article == "das"
    assert lemma == "Mitglied"


def test_non_noun_has_no_article():
    article, lemma = extract_article_lemma("schnell", "schnell")
    assert article is None
    assert lemma == "schnell"


def test_mismatch_raises():
    with pytest.raises(ArticleMismatchError):
        extract_article_lemma("das Mitglied", "Mitgleid")  # typo'd Klarwort


def test_case_mismatch_in_remainder_raises():
    # Important: case-sensitive comparison catches casing discrepancies
    # Real CSV has only 1 such row ("das All"/"all"), dropped elsewhere
    with pytest.raises(ArticleMismatchError):
        extract_article_lemma("das All", "all")


def test_pos_from_article_is_noun():
    assert derive_pos("das Mitglied", "member (of an organization)", "German Noun (A2)") == "Noun"


def test_pos_from_inline_tag_when_no_article():
    ubersetzung = "wahrscheinlich (Adverb): probably, likely  wahrscheinlich (Adjektiv): probable"
    assert derive_pos("Wahrscheinlich", ubersetzung, "German Word (A2)") == "Adverb"


def test_pos_from_trailing_column_when_no_article_and_no_tag():
    # One of the 106 real rows with neither an article nor an inline tag.
    assert derive_pos("Oben", "above, upstairs, at the top", "German Adverb (A1)") == "Adverb"


def test_pos_raises_when_undeterminable():
    with pytest.raises(ValueError):
        derive_pos("Mystery", "a mysterious thing", "")


def test_pos_raises_when_trailing_is_german_word():
    # Minor 1: "German Word" exclusion should raise (guards against future data changes)
    with pytest.raises(ValueError):
        derive_pos("Unknown", "unknown thing", "German Word (A1)")


def test_pos_falls_through_when_inline_tag_not_in_mapping():
    # Minor 2: unrecognized inline tag falls through to trailing column
    ubersetzung = "something (UnknownTag): definition"
    assert derive_pos("Word", ubersetzung, "German Adverb (A2)") == "Adverb"
