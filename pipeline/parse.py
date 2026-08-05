import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.lib.examples import collect_pairs, pick_example
from pipeline.lib.fields import ArticleMismatchError, derive_pos, extract_article_lemma
from pipeline.lib.grammar import parse_grammar
from pipeline.lib.translation import first_sense
from pipeline.lib.unicode_clean import clean

KEPT_LEVELS = {"A1", "A2", "B1"}
EXAMPLE_COLUMNS = [f"Example{i}" for i in range(1, 6)]


def make_id(wort):
    # NOT lemma.lower(): German capitalizes nominalized verbs, so the noun
    # "das Hören" (hearing) and the verb "hören" (to hear) share a lemma
    # ("hören") and would collide if the article were dropped before
    # lowercasing. `wort` already carries that distinction -- verified
    # unique across all 2,192 real rows; `lemma.lower()` was not (1 real
    # collision found by testing against the full CSV).
    return wort.lower().replace(" ", "-")


def parse_row(row):
    level = (row.get("Niveau") or "").strip()
    wort = clean(row.get("Wort"))
    klarwort = clean(row.get("Klarwort"))
    ubersetzung = clean(row.get("Übersetzung"))
    detail = row.get("Detail") or ""  # grammar parser needs the raw emoji markers
    trailing = (row.get("") or "").strip()

    entry_id = make_id(wort)
    article, lemma = extract_article_lemma(wort, klarwort)
    pos = derive_pos(wort, ubersetzung, trailing)
    translation = first_sense(ubersetzung)

    cells = [clean(row.get(col)) for col in EXAMPLE_COLUMNS]
    pairs, ambiguous = collect_pairs(cells)
    example = pick_example(pairs, level)

    review_item = None
    if ambiguous:
        review_item = {
            "id": entry_id,
            "wort": wort,
            "issue": "one or more example cells could not be split cleanly and were discarded",
        }

    if example is None:
        # Every real row has another usable cell even when one is discarded
        # (verified) -- this only fires if that invariant is ever violated
        # by a future data change.
        return None, review_item or {
            "id": entry_id,
            "wort": wort,
            "issue": "no usable example available in any column",
        }

    grammar = parse_grammar(detail)

    entry = {
        "id": entry_id,
        "level": level,
        "word": wort,
        "lemma": lemma,
        "article": article,
        "pos": pos,
        "translation": translation,
        "example_de": example[0],
        "example_en": example[1],
        "grammar": grammar,
        "related": [],
    }
    return entry, review_item


def run(csv_path):
    entries = []
    review_items = []
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            level = (row.get("Niveau") or "").strip()
            if level not in KEPT_LEVELS:
                continue
            try:
                entry, review = parse_row(row)
            except ArticleMismatchError as exc:
                raise ArticleMismatchError(f"{row.get('Wort')!r}: {exc}") from exc
            if entry is not None:
                entries.append(entry)
            if review is not None:
                review_items.append(review)
    return entries, review_items


if __name__ == "__main__":
    csv_path = Path(__file__).resolve().parent.parent / "GermanWortList - Main.csv"
    out_dir = Path(__file__).resolve().parent / "out"
    out_dir.mkdir(exist_ok=True)

    entries, review_items = run(csv_path)

    (out_dir / "parsed.json").write_text(json.dumps(entries, ensure_ascii=False, indent=2))
    (out_dir / "needs_review.json").write_text(json.dumps(review_items, ensure_ascii=False, indent=2))

    print(f"Parsed {len(entries)} entries, {len(review_items)} flagged for review.")
