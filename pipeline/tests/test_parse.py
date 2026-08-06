import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.lib.schema import validate_entry
from pipeline.parse import run

CSV_PATH = Path(__file__).resolve().parents[2] / "GermanWortList - Main.csv"


def test_run_produces_exactly_2192_entries():
    entries, _ = run(CSV_PATH)
    assert len(entries) == 2192


def test_run_drops_b2_and_c1():
    entries, _ = run(CSV_PATH)
    levels = {e["level"] for e in entries}
    assert levels == {"A1", "A2", "B1"}


def test_needs_review_has_exactly_seven_items():
    # 7 genuinely unsplittable example cells (nested quotes, one junk cell) --
    # verified by running the full pipeline, not estimated from a sample.
    _, review = run(CSV_PATH)
    assert len(review) == 7


def test_no_row_is_dropped_for_lack_of_an_example():
    # Every row has at least one other usable example cell even when one
    # is discarded -- this is the invariant that makes needs_review.json
    # informational rather than a gate. If this ever fails, entries will
    # be missing rows that needs_review.json's items reference.
    entries, review = run(CSV_PATH)
    assert len(entries) == 2192
    reviewed_ids = {item["id"] for item in review}
    entry_ids = {e["id"] for e in entries}
    assert reviewed_ids.issubset(entry_ids)


def test_every_entry_passes_schema_minus_related():
    entries, _ = run(CSV_PATH)
    for entry in entries:
        problems = validate_entry(entry, require_related=False)
        assert problems == [], f"{entry['id']}: {problems}"


def test_grammar_null_count_matches_measured_210():
    # 130 rows with no marker at all, 79 comparison-only-Positive, 1
    # verb-with-no-partizip ("möchten") -- see Task 6.
    entries, _ = run(CSV_PATH)
    assert sum(1 for e in entries if e["grammar"] is None) == 210


def test_noun_count_matches_measured_1161():
    entries, _ = run(CSV_PATH)
    assert sum(1 for e in entries if e["pos"] == "Noun") == 1161


def test_no_duplicate_ids():
    # Real collision found by running against the full CSV: the noun "das
    # Hören" (hearing) and the verb "hören" (to hear) share a lemma and
    # would collide if the id were derived from lemma.lower() instead of
    # word.lower() (see make_id() in parse.py).
    entries, _ = run(CSV_PATH)
    ids = [e["id"] for e in entries]
    assert len(ids) == len(set(ids))


def test_id_distinguishes_noun_and_verb_sharing_a_lemma():
    entries, _ = run(CSV_PATH)
    by_id = {e["id"]: e for e in entries}
    assert by_id["das-hören"]["pos"] == "Noun"
    assert by_id["hören"]["pos"] == "Verb"


def test_translation_is_first_sense_only():
    entries, _ = run(CSV_PATH)
    by_id = {e["id"]: e for e in entries}
    assert by_id["wahrscheinlich"]["translation"] == \
        "wahrscheinlich (Adverb): probably, likely, in all likelihood"
    assert max(len(e["translation"]) for e in entries) <= 170
