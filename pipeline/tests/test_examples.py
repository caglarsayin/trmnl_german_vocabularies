import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.lib.examples import collect_pairs, pick_example, split_examples


def test_splits_clean_two_way_cell():
    cell = "Es ist wahrscheinlich, dass er heute kommt.It is probable that he will come today."
    assert split_examples(cell) == [
        ("Es ist wahrscheinlich, dass er heute kommt.", "It is probable that he will come today.")
    ]


def test_splits_multi_example_cell_with_mid_string_numbering_artifact():
    # The artifact ("3.") sits between "later?" and "Das" -- not at the cell's start.
    cell = (
        "Kommst du später?Are you coming later?"
        "3. Das machen wir später, das andere machen wir am spätesten."
        "We'll do this later, and we'll do the other thing the latest."
    )
    pairs = split_examples(cell)
    assert pairs == [
        ("Kommst du später?", "Are you coming later?"),
        (
            "Das machen wir später, das andere machen wir am spätesten.",
            "We'll do this later, and we'll do the other thing the latest.",
        ),
    ]


def test_splits_cell_with_two_numbering_artifacts():
    cell = (
        "Warum fragst du denn?Why are you asking then?"
        "3. Kommst du denn heute?Are you coming today then?"
        "4. Er blieb zu Hause.He stayed home."
    )
    pairs = split_examples(cell)
    assert len(pairs) == 3
    assert pairs[2] == ("Er blieb zu Hause.", "He stayed home.")


def test_nested_quote_cell_returns_none():
    # Real unsplittable case: the closing quote's period isn't followed directly
    # by an uppercase letter, so no split boundary exists.
    cell = 'Sie sagte: „Hoffentlich klappt alles."She said, "Hopefully everything works out."'
    assert split_examples(cell) is None


def test_junk_cell_returns_none():
    assert split_examples("Examples5.") is None


def test_empty_cell_returns_empty_list():
    assert split_examples("") == []


def test_collect_pairs_flags_unsplittable_but_keeps_good_ones():
    cells = [
        "Ich komme sofort.I'm coming right away.",
        "Examples5.",
    ]
    pairs, ambiguous = collect_pairs(cells)
    assert pairs == [("Ich komme sofort.", "I'm coming right away.")]
    assert ambiguous is True


def test_pick_example_a1_takes_shortest():
    pairs = [("Ein langer Satz mit vielen Woertern hier.", "en"), ("Kurz.", "en")]
    assert pick_example(pairs, "A1") == ("Kurz.", "en")


def test_pick_example_a2_takes_median():
    pairs = [("a", "en"), ("bb", "en"), ("ccc", "en")]
    assert pick_example(pairs, "A2") == ("bb", "en")


def test_pick_example_b1_takes_longest():
    pairs = [("Ein langer Satz mit vielen Woertern hier.", "en"), ("Kurz.", "en")]
    assert pick_example(pairs, "B1") == ("Ein langer Satz mit vielen Woertern hier.", "en")


def test_pick_example_empty_returns_none():
    assert pick_example([], "A1") is None
