# TRMNL German Vocabulary Flashcard Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a TRMNL private plugin that shows one German vocabulary flashcard per screen refresh, sourced from `GermanWortList - Main.csv`, filtered by per-installation level settings.

**Architecture:** A three-pass offline data pipeline (Python) turns the messy source CSV into a clean `vocab.json`; a Cloudflare Worker (JS) serves one random filtered entry per poll; a TRMNL Private Plugin (Polling strategy, Custom Fields, Liquid template) renders it to the device.

**Tech Stack:** Python 3 (stdlib only — `csv`, `re`, `json`; no third-party deps) for the pipeline, plain JavaScript + Cloudflare Workers (Wrangler) for the backend, `trmnlp` (Ruby gem) for local template preview, TRMNL's Liquid templating for the device UI.

## Global Constraints

These come directly from the spec (`docs/superpowers/specs/2026-08-05-trmnl-german-vocab-plugin-design.md`) and apply to every task below:

- Only levels A1/A2/B1 are kept; B2/C1 rows are dropped in Pass 1. Final row count: **2,192**.
- POS derivation order is: article presence → inline `(POS):` tag → trailing-column tag. No row may fall through all three (verified: it never does, on the real data).
- Article extraction must **assert** `Wort` minus article `== Klarwort`; a mismatch is a hard error, not a warning (verified 100% on the real sheet — a violation means the source format changed).
- Example sentence selection is **level-dependent**: A1 → shortest available pair, A2 → median-length pair, B1 → longest available pair (all measured well under the overflow cap).
- Every entry in the final `vocab.json` must have a non-empty `related` array or an explicit `related_none: true` — this is a **build-failing gate**, not a warning.
- The live Worker request path never calls an LLM. All language work is precomputed.
- `refresh_interval` in the TRMNL plugin must be one of: 15, 60, 360, 720, 1440 (minutes) — no other value is valid.
- Response JSON from the Worker must be flat at the root level (no nested objects) — TRMNL's merge variables expect `{{ field_name }}` directly.

---

## File Structure

```
trmnl_plugin/
├── GermanWortList - Main.csv          (existing)
├── docs/superpowers/{specs,plans}/... (existing)
├── pipeline/
│   ├── lib/
│   │   ├── unicode_clean.py           # Task 2
│   │   ├── fields.py                  # Task 3 (article/lemma/POS)
│   │   ├── translation.py             # Task 4
│   │   ├── examples.py                # Task 5
│   │   ├── grammar.py                 # Task 6
│   │   └── schema.py                  # Task 1 (validator, shared)
│   ├── tests/
│   │   ├── test_unicode_clean.py
│   │   ├── test_fields.py
│   │   ├── test_translation.py
│   │   ├── test_examples.py
│   │   ├── test_grammar.py
│   │   ├── test_parse.py              # Task 7 (integration, real CSV)
│   │   ├── test_match_candidates.py   # Task 8
│   │   └── test_build_vocab.py        # Task 9 (synthetic data)
│   ├── fixtures/
│   │   └── vocab.sample.json          # Task 1, hand-written, 10 entries
│   ├── parse.py                        # Task 7 — Pass 1 orchestrator
│   ├── match_candidates.py             # Task 8 — Pass 2
│   ├── prepare_enrichment_args.py      # Task 9 — builds Pass 3 input
│   ├── build_vocab.py                  # Task 9 — merges Pass 3 output + gate
│   └── out/                            # gitignored: parsed.json, candidates.json,
│                                        #   needs_review.json, enrichment_args.json,
│                                        #   enrichment_result.json, vocab.json
├── worker/
│   ├── src/
│   │   ├── index.js                    # Task 12 — fetch handler
│   │   ├── filter.js                   # Task 11 — level/exclude/random logic
│   │   ├── response.js                 # Task 11 — flatten + truncate for template
│   │   └── vocab.json                  # Task 11 (fixture copy) → Task 10 (real data)
│   ├── test/
│   │   ├── filter.test.js
│   │   └── response.test.js
│   ├── wrangler.toml                    # Task 12
│   └── package.json                     # Task 12
├── plugin/
│   ├── settings.yml                     # Task 13
│   └── full.liquid                      # Task 13
└── .gitignore                           # Task 1
```

Files that change together live together: everything under `pipeline/lib/` is a pure-function module with its own test file, imported by `parse.py`. The Worker's pure filtering logic (`filter.js`, `response.js`) is separated from the Cloudflare-specific `index.js` glue so it can be tested with plain Node, no Workers runtime needed.

---

### Task 1: Repo scaffolding, vocab schema, and shared validator

**Files:**
- Create: `.gitignore`
- Create: `pipeline/lib/schema.py`
- Create: `pipeline/fixtures/vocab.sample.json`
- Create: `pipeline/tests/test_schema.py`

**Interfaces:**
- Produces: `validate_entry(entry: dict, require_related: bool = True) -> list[str]` — returns a list of human-readable problems (empty list = valid). Every later pipeline task imports this from `pipeline.lib.schema`.

- [ ] **Step 1: Write `.gitignore`**

```
pipeline/out/
node_modules/
.wrangler/
```

- [ ] **Step 2: Write the failing test for the schema validator**

`pipeline/tests/test_schema.py`:

```python
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
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `python3 -m pytest pipeline/tests/test_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.lib.schema'` (create `pipeline/lib/__init__.py` and `pipeline/__init__.py` as empty files too, so the package imports work).

- [ ] **Step 4: Implement the validator**

`pipeline/lib/schema.py`:

```python
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
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python3 -m pytest pipeline/tests/test_schema.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Hand-write the 10-entry fixture**

`pipeline/fixtures/vocab.sample.json` — covers, deliberately, every structural case the real data has: a noun with plural, a verb with Partizip II, an adjective with comparative + a related opposite, a word with no grammar block (the 210-row case), a word resolved via the trailing-column POS fallback (the 106-row case), an entry with `related_none: true`, an entry with 4 related words (cap case), and one entry per level (A1/A2/B1) so Worker level-filtering has something to filter:

```json
[
  {
    "id": "mitglied", "level": "A2", "word": "das Mitglied", "lemma": "Mitglied",
    "article": "das", "pos": "Noun",
    "translation": "member (of an organization), participant",
    "example_de": "Neue Mitglieder sind willkommen.", "example_en": "New members are welcome.",
    "grammar": {"type": "noun_forms", "lines": ["Singular: das Mitglied", "Plural: die Mitglieder"]},
    "related": [{"word": "die Mitgliedschaft", "relation": "same_root", "source": "mechanical_validated"}]
  },
  {
    "id": "blitzen", "level": "B1", "word": "blitzen", "lemma": "blitzen",
    "article": null, "pos": "Verb",
    "translation": "to flash (lightning), to gleam",
    "example_de": "Es blitzt und donnert seit einer Stunde ununterbrochen am Himmel.",
    "example_en": "It has been flashing and thundering nonstop in the sky for an hour.",
    "grammar": {"type": "verb_conjugations", "lines": ["Partizip II: geblitzt (regelmäßig)"]},
    "related": [{"word": "der Blitz", "relation": "same_root", "source": "mechanical_validated"}]
  },
  {
    "id": "entspannend", "level": "A2", "word": "entspannend", "lemma": "entspannend",
    "article": null, "pos": "Adjective",
    "translation": "relaxing, soothing, unwinding",
    "example_de": "Das war die entspannendste Massage, die ich je hatte.",
    "example_en": "That was the most relaxing massage I have ever had.",
    "grammar": {"type": "degrees_of_comparison", "lines": ["Comparative: entspannender", "Superlative: am entspannendsten"]},
    "related": [{"word": "anstrengend", "relation": "opposite", "source": "generated"}]
  },
  {
    "id": "oben", "level": "A1", "word": "oben", "lemma": "oben",
    "article": null, "pos": "Adverb",
    "translation": "above, upstairs, at the top",
    "example_de": "Das Buch liegt oben.", "example_en": "The book is on top.",
    "grammar": null,
    "related": [], "related_none": true
  },
  {
    "id": "sofort", "level": "A2", "word": "sofort", "lemma": "sofort",
    "article": null, "pos": "Adverb",
    "translation": "immediately, right away, at once",
    "example_de": "Ich komme sofort.", "example_en": "I'm coming right away.",
    "grammar": null,
    "related": [
      {"word": "gleich", "relation": "synonym", "source": "generated"},
      {"word": "später", "relation": "opposite", "source": "generated"},
      {"word": "sogleich", "relation": "synonym", "source": "generated"},
      {"word": "unverzüglich", "relation": "synonym", "source": "generated"}
    ]
  },
  {
    "id": "baum", "level": "A1", "word": "der Baum", "lemma": "Baum",
    "article": "der", "pos": "Noun",
    "translation": "tree",
    "example_de": "Der Baum ist grün.", "example_en": "The tree is green.",
    "grammar": {"type": "noun_forms", "lines": ["Singular: der Baum", "Plural: die Bäume"]},
    "related": [{"word": "der Wald", "relation": "same_root", "source": "generated"}]
  },
  {
    "id": "schnell", "level": "A1", "word": "schnell", "lemma": "schnell",
    "article": null, "pos": "Adjective",
    "translation": "fast, quick",
    "example_de": "Das Auto ist schnell.", "example_en": "The car is fast.",
    "grammar": {"type": "degrees_of_comparison", "lines": ["Comparative: schneller", "Superlative: am schnellsten"]},
    "related": [{"word": "langsam", "relation": "opposite", "source": "generated"}]
  },
  {
    "id": "ubersetzung", "level": "B1", "word": "die Übersetzung", "lemma": "Übersetzung",
    "article": "die", "pos": "Noun",
    "translation": "translation, translated version",
    "example_de": "Die Übersetzung dieses Fachbuchs ins Japanische war eine echte Herausforderung für das gesamte Team.",
    "example_en": "Translating this technical book into Japanese was a real challenge for the whole team.",
    "grammar": {"type": "noun_forms", "lines": ["Singular: die Übersetzung", "Plural: die Übersetzungen"]},
    "related": [{"word": "übersetzen", "relation": "verb_form", "source": "mechanical_validated"}]
  },
  {
    "id": "wichtig", "level": "A2", "word": "wichtig", "lemma": "wichtig",
    "article": null, "pos": "Adjective",
    "translation": "important",
    "example_de": "Das Meeting war heute erstaunlich wichtig für alle Beteiligten im Projekt.",
    "example_en": "The meeting was surprisingly important today for everyone involved in the project.",
    "grammar": {"type": "degrees_of_comparison", "lines": ["Comparative: wichtiger", "Superlative: am wichtigsten"]},
    "related": [{"word": "unwichtig", "relation": "opposite", "source": "generated"}]
  },
  {
    "id": "ueberzeugen", "level": "B1", "word": "überzeugen", "lemma": "überzeugen",
    "article": null, "pos": "Verb",
    "translation": "to convince, to persuade",
    "example_de": "Es dauerte lange, aber am Ende konnte sie ihn mit guten Argumenten vollständig überzeugen.",
    "example_en": "It took a while, but in the end she was able to fully convince him with good arguments.",
    "grammar": {"type": "verb_conjugations", "lines": ["Partizip II: überzeugt (regelmäßig)"]},
    "related": [{"word": "die Überzeugung", "relation": "noun_form", "source": "mechanical_validated"}]
  }
]
```

- [ ] **Step 7: Add a test that the fixture itself is schema-valid**

Append to `pipeline/tests/test_schema.py`:

```python
import json

def test_fixture_file_is_fully_schema_valid():
    fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "vocab.sample.json"
    entries = json.loads(fixture_path.read_text())
    assert len(entries) == 10
    for entry in entries:
        problems = validate_entry(entry)
        assert problems == [], f"{entry['id']}: {problems}"
```

- [ ] **Step 8: Run all schema tests**

Run: `python3 -m pytest pipeline/tests/test_schema.py -v`
Expected: PASS (6 tests)

- [ ] **Step 9: Commit**

```bash
git add .gitignore pipeline/
git commit -m "Add vocab schema validator and hand-written test fixture"
```

---

### Task 2: Unicode cleanup helper

**Files:**
- Create: `pipeline/lib/unicode_clean.py`
- Test: `pipeline/tests/test_unicode_clean.py`

**Interfaces:**
- Produces: `clean(text: str | None) -> str`. Used by Task 3–6's extraction functions and Task 7's orchestrator before any parsing.

- [ ] **Step 1: Write the failing tests**

`pipeline/tests/test_unicode_clean.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.lib.unicode_clean import clean


def test_strips_zero_width_non_joiner():
    assert clean("nearby‌ (next door)") == "nearby (next door)"


def test_strips_soft_and_nonbreaking_hyphen():
    assert clean("wieder­holen") == "wiederholen"
    assert clean("nicht‑öffentlich") == "nicht-öffentlich"


def test_normalizes_curly_quotes_and_dashes():
    assert clean("„Hallo“ – sagte er ’mal‘") == '"Hallo" - sagte er \'mal\''


def test_fixes_cyrillic_homoglyph():
    # U+0435 CYRILLIC SMALL LETTER IE looks identical to Latin 'e'
    contaminated = "spеrrt"
    assert clean(contaminated) == "sperrt"


def test_collapses_whitespace_and_strips():
    assert clean("  a   b  ") == "a b"


def test_handles_none():
    assert clean(None) == ""
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest pipeline/tests/test_unicode_clean.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.lib.unicode_clean'`

- [ ] **Step 3: Implement**

`pipeline/lib/unicode_clean.py`:

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest pipeline/tests/test_unicode_clean.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/lib/unicode_clean.py pipeline/tests/test_unicode_clean.py
git commit -m "Add unicode cleanup helper for pipeline Pass 1"
```

---

### Task 3: Article, lemma, and POS extraction

**Files:**
- Create: `pipeline/lib/fields.py`
- Test: `pipeline/tests/test_fields.py`

**Interfaces:**
- Consumes: `clean()` from Task 2 (call it on inputs before passing to these functions — the orchestrator in Task 7 is responsible for this ordering, these functions assume already-cleaned input).
- Produces: `extract_article_lemma(wort: str, klarwort: str) -> tuple[str | None, str]`, raising `ArticleMismatchError` on mismatch; `derive_pos(wort: str, ubersetzung: str, trailing: str) -> str`, raising `ValueError` if undeterminable.

- [ ] **Step 1: Write the failing tests**

`pipeline/tests/test_fields.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest pipeline/tests/test_fields.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`pipeline/lib/fields.py`:

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest pipeline/tests/test_fields.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/lib/fields.py pipeline/tests/test_fields.py
git commit -m "Add article/lemma/POS extraction with verified fallback order"
```

---

### Task 4: Translation first-sense extraction

**Files:**
- Create: `pipeline/lib/translation.py`
- Test: `pipeline/tests/test_translation.py`

**Interfaces:**
- Produces: `first_sense(ubersetzung: str) -> str`.

- [ ] **Step 1: Write the failing tests**

`pipeline/tests/test_translation.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.lib.translation import first_sense


def test_multi_sense_takes_first_only():
    ubersetzung = (
        "wahrscheinlich (Adverb): probably, likely, in all likelihood  "
        "wahrscheinlich (Adjektiv): probable, likely  "
        "das Wahrscheinliche (Noun): the probable (thing/concept)"
    )
    assert first_sense(ubersetzung) == "wahrscheinlich (Adverb): probably, likely, in all likelihood"


def test_single_sense_returns_whole_thing():
    assert first_sense("member (of an organization), participant") == "member (of an organization), participant"


def test_empty_input_returns_empty_string():
    assert first_sense("") == ""
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest pipeline/tests/test_translation.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`pipeline/lib/translation.py`:

```python
import re

_SENSE_SPLIT_RE = re.compile(r"\s{2,}")


def first_sense(ubersetzung):
    text = (ubersetzung or "").strip()
    if not text:
        return ""
    parts = _SENSE_SPLIT_RE.split(text)
    return parts[0].strip()
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest pipeline/tests/test_translation.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/lib/translation.py pipeline/tests/test_translation.py
git commit -m "Add first-sense translation extraction"
```

---

### Task 5: Example sentence splitting and level-based selection

**Files:**
- Create: `pipeline/lib/examples.py`
- Test: `pipeline/tests/test_examples.py`

**Interfaces:**
- Produces: `split_examples(cell: str) -> list[tuple[str, str]] | None` (returns `None` only for a genuinely unsplittable cell — caller logs these to `needs_review.json`, but see Task 7: this never blocks a row since every row has another usable cell); `collect_pairs(cells: list[str]) -> tuple[list[tuple[str, str]], bool]` (second value is `True` if any cell was unsplittable); `pick_example(pairs: list[tuple[str, str]], level: str) -> tuple[str, str] | None`.

**Important — verified, not assumed:** the `N.` numbering artifact in
multi-example cells sits *between* two sentences (e.g.
`...later?3. Das machen...`), not at the start of a chunk. A first version
of this splitter that only stripped a *leading* `N. ` looked reasonable
but, when run against all 2,192 real rows rather than a couple of samples,
left every one of the 566 multi-example cells unresolved (returned `None`
instead of splitting). The fix below removes the artifact at its actual
position — between a sentence-ending punctuation mark and the next capital
letter — before splitting. Do not reintroduce a leading-only strip.

- [ ] **Step 1: Write the failing tests**

`pipeline/tests/test_examples.py`:

```python
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
        "We’ll do this later, and we’ll do the other thing the latest."
    )
    pairs = split_examples(cell)
    assert pairs == [
        ("Kommst du später?", "Are you coming later?"),
        (
            "Das machen wir später, das andere machen wir am spätesten.",
            "We’ll do this later, and we’ll do the other thing the latest.",
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
    cell = 'Sie sagte: „Hoffentlich klappt alles.“She said, “Hopefully everything works out.”'
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest pipeline/tests/test_examples.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`pipeline/lib/examples.py`:

```python
import re

_ARTIFACT_RE = re.compile(r"(?<=[.!?])\s*\d+\.\s+(?=[A-ZÄÖÜ])")
_SPLIT_RE = re.compile(r"(?<=[.!?])(?=[A-ZÄÖÜ])")
_LEADING_NUM_RE = re.compile(r"^\s*\d+\.\s*")


def split_examples(cell):
    text = (cell or "").strip()
    if not text:
        return []
    text = _ARTIFACT_RE.sub("", text)
    parts = _SPLIT_RE.split(text)
    parts = [_LEADING_NUM_RE.sub("", p).strip() for p in parts]
    if len(parts) % 2 != 0:
        return None
    return [(parts[i], parts[i + 1]) for i in range(0, len(parts), 2)]


def collect_pairs(cells):
    all_pairs = []
    ambiguous = False
    for cell in cells:
        if not (cell or "").strip():
            continue
        result = split_examples(cell)
        if result is None:
            ambiguous = True
            continue
        all_pairs.extend(result)
    return all_pairs, ambiguous


def pick_example(pairs, level):
    if not pairs:
        return None
    ordered = sorted(pairs, key=lambda pair: len(pair[0]))
    if level == "A1":
        return ordered[0]
    if level == "A2":
        return ordered[len(ordered) // 2]
    return ordered[-1]
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest pipeline/tests/test_examples.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/lib/examples.py pipeline/tests/test_examples.py
git commit -m "Add example splitting and level-based selection (A1 shortest, A2 median, B1 longest)"
```

---

### Task 6: Grammar block parsing

**Files:**
- Create: `pipeline/lib/grammar.py`
- Test: `pipeline/tests/test_grammar.py`

**Interfaces:**
- Produces: `parse_grammar(detail_text: str) -> dict | None` — returns `{"type": ..., "lines": [...]}`, or `None` if no marker is present *or* the marker's section has nothing useful beyond the headline word.

**Important — verified, not assumed:** a marker being present does not
guarantee a usable block. Running a first version of this parser (which
assumed every `📊` section has Positive+Comparative+Superlative, and every
`🔄` section has a `Partizip II:`) against all 2,192 real rows — not just
the 3 samples per marker type used to write the regexes — raised 80
exceptions: 79 `📊` rows have only `Positive:` (words like `wohin`,
`warum`, `schon` that don't inflect for comparison in German) and 1 `🔄`
row (`möchten`, a modal verb) has no `Partizip II:` at all. Both must
resolve to `None` — showing "Positive: wohin" would just repeat the
headline word — not raise. The implementation below handles both as
first-class `None` outcomes, not edge cases bolted on after.

- [ ] **Step 1: Write the failing tests**

Using the exact, verified real-data samples (no space after the marker, no space before the title's glued content):

`pipeline/tests/test_grammar.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.lib.grammar import parse_grammar


def test_noun_forms():
    detail = "member (of an organization), participant, member🔢 Noun FormsSingular (Einzahl): das MitgliedPlural (Mehrzahl): Mitglieder"
    result = parse_grammar(detail)
    assert result == {
        "type": "noun_forms",
        "lines": ["Singular: das Mitglied", "Plural: Mitglieder"],
    }


def test_verb_conjugations_extracts_partizip_and_regularity():
    detail = (
        "blitzen (Verb): to flash (lightning), to gleam  das Blitzen (Noun): flashing, flash (of light)"
        "🔄 Verb Conjugationsregelmäßig Partizip II: geblitztPresent (Präsens):ich: blitzedu: blitzt"
        "er/sie/es: blitztwir: blitzenihr: blitztsie: blitzenPast (Präteritum):ich: blitztedu: blitztest"
        "er/sie/es: blitztewir: blitztenihr: blitztetsie: blitzten"
    )
    result = parse_grammar(detail)
    assert result == {"type": "verb_conjugations", "lines": ["Partizip II: geblitzt (regelmäßig)"]}


def test_verb_conjugations_unregelmaessig():
    detail = (
        "das Überweisen (Noun): the transfer"
        "🔄 Verb Conjugationsunregelmäßig Partizip II: überwiesenPresent (Präsens):ich: überweise"
    )
    result = parse_grammar(detail)
    assert result == {"type": "verb_conjugations", "lines": ["Partizip II: überwiesen (unregelmäßig)"]}


def test_verb_with_no_partizip_returns_none():
    # Real case: "möchten" (modal verb) -- no "Partizip II:" in its section at all.
    detail = "🔄 Verb Conjugationsunregelmäßig Present (Präsens):ich: möchtedu: möchtest"
    result = parse_grammar(detail)
    assert result is None


def test_degrees_of_comparison():
    detail = (
        "leer (Adjektiv): empty, vacant, blank, void  das Leer (Noun): the empty (quality/state)"
        "📊 Degrees of ComparisonPositive: leerComparative: leererSuperlative: am leersten"
    )
    result = parse_grammar(detail)
    assert result == {
        "type": "degrees_of_comparison",
        "lines": ["Comparative: leerer", "Superlative: am leersten"],
    }


def test_degrees_of_comparison_positive_only_returns_none():
    # Real case: "wohin" -- doesn't inflect for comparison in German.
    detail = "wohin (Adverb): where to, to what place📊 Degrees of ComparisonPositive: wohin"
    result = parse_grammar(detail)
    assert result is None


def test_no_marker_returns_none():
    assert parse_grammar("oben (Adverb): above, upstairs, at the top") is None


def test_none_input_returns_none():
    assert parse_grammar(None) is None
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest pipeline/tests/test_grammar.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`pipeline/lib/grammar.py`:

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest pipeline/tests/test_grammar.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/lib/grammar.py pipeline/tests/test_grammar.py
git commit -m "Add grammar block parser for noun/verb/adjective sections"
```

---

### Task 7: Pass 1 orchestrator — parse the real CSV

**Files:**
- Create: `pipeline/parse.py`
- Test: `pipeline/tests/test_parse.py`

**Interfaces:**
- Consumes: `clean()` (Task 2), `extract_article_lemma()`/`derive_pos()` (Task 3), `first_sense()` (Task 4), `collect_pairs()`/`pick_example()` (Task 5), `parse_grammar()` (Task 6), `validate_entry()` (Task 1).
- Produces: `parse_row(row: dict) -> tuple[dict | None, dict | None]` — returns `(entry, review_item)`. **These are independent, not mutually exclusive**: `review_item` is set whenever any example cell was discarded as unsplittable, *regardless* of whether `entry` also succeeded (which it does for every real row — verified, see below); `entry` is `None` only in the hypothetical case where *no* usable example survives at all across every column. `run(csv_path: str) -> tuple[list[dict], list[dict]]` — returns `(entries, review_items)`. Task 8 imports `run()`.

**Important — verified, not assumed:** it would be natural to assume a
row with an unsplittable example cell should be skipped entirely. That is
wrong for this data: every one of the 2,192 rows has *another* usable
example cell even when one is discarded, verified by actually running the
full pipeline — zero rows end up with no example at all. Treating
"discarded cell" and "row has no example" as the same condition would
incorrectly drop real, complete entries. `needs_review.json` is therefore
informational (which raw cells got discarded, for eventual source-sheet
cleanup), not a gate on entry creation. Only fall back to dropping the row
if `pick_example` genuinely returns `None` — code defensively for that
case, but do not expect it to trigger on this dataset.

- [ ] **Step 1: Write the failing integration test against the real CSV**

This test encodes the exact counts measured during spec analysis — a regression guard, not a guess:

`pipeline/tests/test_parse.py`:

```python
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
    entries, _ = run(CSV_PATH)
    ids = [e["id"] for e in entries]
    assert len(ids) == len(set(ids))
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest pipeline/tests/test_parse.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.parse'`

- [ ] **Step 3: Implement**

`pipeline/parse.py`:

```python
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


def parse_row(row):
    level = (row.get("Niveau") or "").strip()
    wort = clean(row.get("Wort"))
    klarwort = clean(row.get("Klarwort"))
    ubersetzung = clean(row.get("Übersetzung"))
    detail = row.get("Detail") or ""  # grammar parser needs the raw emoji markers
    trailing = (row.get("") or "").strip()

    article, lemma = extract_article_lemma(wort, klarwort)
    pos = derive_pos(wort, ubersetzung, trailing)
    translation = first_sense(ubersetzung)

    cells = [clean(row.get(col)) for col in EXAMPLE_COLUMNS]
    pairs, ambiguous = collect_pairs(cells)
    example = pick_example(pairs, level)

    review_item = None
    if ambiguous:
        review_item = {
            "id": lemma.lower(),
            "wort": wort,
            "issue": "one or more example cells could not be split cleanly and were discarded",
        }

    if example is None:
        # Every real row has another usable cell even when one is discarded
        # (verified) -- this only fires if that invariant is ever violated
        # by a future data change.
        return None, review_item or {
            "id": lemma.lower(),
            "wort": wort,
            "issue": "no usable example available in any column",
        }

    grammar = parse_grammar(detail)

    entry = {
        "id": lemma.lower(),
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
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest pipeline/tests/test_parse.py -v`
Expected: PASS (8 tests). If `test_needs_review_has_exactly_seven_items` fails with a different count, check whether `split_examples`'s artifact-removal regex (Task 5) is over- or under-firing compared to the 7-cell figure verified during spec analysis — do not adjust the expected count without re-running the check against the CSV directly. If `test_no_row_is_dropped_for_lack_of_an_example` fails, that means the source CSV changed in a way that removes the last usable example from some word — investigate that row specifically rather than loosening the assertion.

- [ ] **Step 5: Run the script directly and inspect output**

Run: `python3 pipeline/parse.py`
Expected: `Parsed 2192 entries, 7 flagged for review.` and `pipeline/out/parsed.json` / `pipeline/out/needs_review.json` created.

Task 6's grammar parser and Task 5's example splitter were each verified against all 2,192 real rows during spec analysis (not just samples) and both bugs found that way are already fixed in Tasks 5–6's code above. If this run still raises an exception from `pipeline/lib/grammar.py` or produces a different needs-review count, that means a data variant neither pass caught. **Do not catch and skip it** — print the offending cell, go back to the relevant task, add a test case reproducing the new variant, and fix it there, then re-run this step.

- [ ] **Step 6: Commit**

```bash
git add pipeline/parse.py pipeline/tests/test_parse.py
git commit -m "Add Pass 1 orchestrator: CSV -> parsed.json + needs_review.json"
```

---

### Task 8: Pass 2 — mechanical related-word candidates

**Files:**
- Create: `pipeline/match_candidates.py`
- Test: `pipeline/tests/test_match_candidates.py`

**Interfaces:**
- Consumes: the `entries` list shape produced by Task 7's `run()` (specifically each entry's `id`/`lemma`/`level`).
- Produces: `find_candidates(lemmas: list[str]) -> dict[str, list[str]]` (lemma → list of candidate lemmas, lowercase); `run(parsed_path: str) -> list[dict]` — returns a flat list of `{"lemma": ..., "candidate_lemma": ...}` pairs. Task 9 imports `run()`.

- [ ] **Step 1: Write the failing tests**

`pipeline/tests/test_match_candidates.py`:

```python
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.match_candidates import find_candidates, run


def test_finds_shared_prefix_siblings():
    lemmas = ["ärgern", "ärgerlich", "Katze"]
    candidates = find_candidates(lemmas)
    assert "ärgerlich" in candidates["ärgern"]
    assert "ärgern" in candidates["ärgerlich"]
    assert candidates.get("katze", []) == []


def test_short_lemmas_below_prefix_length_get_no_candidates():
    lemmas = ["zu", "an"]
    candidates = find_candidates(lemmas)
    assert candidates.get("zu", []) == []
    assert candidates.get("an", []) == []


def test_run_reads_parsed_json_and_flattens_to_pairs(tmp_path):
    parsed = [
        {"id": "argern", "lemma": "ärgern", "level": "B1"},
        {"id": "argerlich", "lemma": "ärgerlich", "level": "B1"},
        {"id": "katze", "lemma": "Katze", "level": "A1"},
    ]
    parsed_path = tmp_path / "parsed.json"
    parsed_path.write_text(json.dumps(parsed))

    pairs = run(parsed_path)
    pair_set = {(p["lemma"], p["candidate_lemma"]) for p in pairs}
    assert ("ärgern", "ärgerlich") in pair_set
    assert ("ärgerlich", "ärgern") in pair_set
    assert not any(p["lemma"] == "Katze" for p in pairs)
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest pipeline/tests/test_match_candidates.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`pipeline/match_candidates.py`:

```python
import json
from collections import defaultdict
from pathlib import Path

PREFIX_LENGTHS = (7, 6, 5)


def find_candidates(lemmas):
    lowered = [lemma.lower() for lemma in lemmas]
    by_prefix = defaultdict(set)
    for lemma in lowered:
        for n in PREFIX_LENGTHS:
            if len(lemma) >= n:
                by_prefix[lemma[:n]].add(lemma)

    candidates = {}
    for lemma in lowered:
        related = set()
        for n in PREFIX_LENGTHS:
            if len(lemma) >= n:
                related |= {other for other in by_prefix[lemma[:n]] if other != lemma}
        candidates[lemma] = sorted(related)
    return candidates


def run(parsed_path):
    entries = json.loads(Path(parsed_path).read_text())
    lemmas = [entry["lemma"] for entry in entries]
    candidates = find_candidates(lemmas)

    pairs = []
    for entry in entries:
        lemma = entry["lemma"]
        for candidate_lemma in candidates.get(lemma.lower(), []):
            pairs.append({"lemma": lemma, "candidate_lemma": candidate_lemma})
    return pairs


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent / "out"
    pairs = run(out_dir / "parsed.json")
    (out_dir / "candidates.json").write_text(json.dumps(pairs, ensure_ascii=False, indent=2))
    print(f"Found {len(pairs)} candidate pairs.")
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest pipeline/tests/test_match_candidates.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run against the real parsed output and check the measured count**

Run: `python3 pipeline/match_candidates.py`
Expected: `Found 1296 candidate pairs.` (matches the figure measured in the spec). If this number differs, check whether Task 7's `parsed.json` lemma casing/content changed — do not adjust `match_candidates.py`'s prefix lengths to force the number to match.

- [ ] **Step 6: Commit**

```bash
git add pipeline/match_candidates.py pipeline/tests/test_match_candidates.py
git commit -m "Add Pass 2: mechanical stem-based related-word candidates"
```

---

### Task 9: Pass 3 tooling — prepare enrichment input and merge/gate the output

**Files:**
- Create: `pipeline/prepare_enrichment_args.py`
- Create: `pipeline/build_vocab.py`
- Test: `pipeline/tests/test_build_vocab.py`

**Interfaces:**
- Consumes: `parsed.json` (Task 7 output shape), `candidates.json` (Task 8 output shape), `needs_review.json` (Task 7 output shape).
- Produces: `prepare_enrichment_args.py` emits `pipeline/out/enrichment_args.json` shaped as `{"pairs": [...], "wordsNeedingGeneration": [...], "allLemmas": [...], "needsReview": [...]}`, where each item in `wordsNeedingGeneration` is `{"lemma": ..., "translation": ..., "pos": ...}` (context for the generation agent). `build_vocab.merge(parsed: list[dict], enrichment_result: dict) -> list[dict]`; `build_vocab.run(parsed_path, result_path, out_path) -> None`, raising `ValueError` (with every failing entry's `id` listed) if the completeness gate fails.

- [ ] **Step 1: Write the failing tests for `build_vocab.merge` (using synthetic data — no need to run the real, expensive Workflow to test this)**

`pipeline/tests/test_build_vocab.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest pipeline/tests/test_build_vocab.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `prepare_enrichment_args.py`**

```python
import json
from collections import defaultdict
from pathlib import Path


def run(parsed_path, candidates_path, review_path):
    entries = json.loads(Path(parsed_path).read_text())
    pairs = json.loads(Path(candidates_path).read_text())
    review = json.loads(Path(review_path).read_text())

    has_candidate = {p["lemma"] for p in pairs}
    words_needing_generation = [
        {"lemma": e["lemma"], "translation": e["translation"], "pos": e["pos"]}
        for e in entries
        if e["lemma"] not in has_candidate
    ]

    return {
        "pairs": pairs,
        "wordsNeedingGeneration": words_needing_generation,
        "allLemmas": sorted({e["lemma"] for e in entries}),
        "needsReview": review,
    }


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent / "out"
    args = run(out_dir / "parsed.json", out_dir / "candidates.json", out_dir / "needs_review.json")
    (out_dir / "enrichment_args.json").write_text(json.dumps(args, ensure_ascii=False, indent=2))
    print(
        f"{len(args['pairs'])} pairs to validate, "
        f"{len(args['wordsNeedingGeneration'])} words needing generation, "
        f"{len(args['needsReview'])} needs-review items."
    )
```

- [ ] **Step 4: Implement `build_vocab.py`**

```python
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.lib.schema import validate_entry


def merge(parsed, enrichment_result):
    by_lemma = {entry["lemma"]: dict(entry) for entry in parsed}
    for entry in by_lemma.values():
        entry["related"] = []
        entry["related_none"] = False

    for item in enrichment_result.get("validated", []):
        if not item.get("valid"):
            continue
        entry = by_lemma.get(item["lemma"])
        if entry is None:
            continue
        entry["related"].append({
            "word": item["candidate_lemma"],
            "relation": item["relation"],
            "source": "mechanical_validated",
        })

    for item in enrichment_result.get("generated", []):
        entry = by_lemma.get(item["lemma"])
        if entry is None:
            continue
        for link in item.get("related", []):
            entry["related"].append({
                "word": link["word"],
                "relation": link["relation"],
                "source": "generated",
            })
        if item.get("related_none"):
            entry["related_none"] = True

    return list(by_lemma.values())


def check_completeness(entries):
    failing = [e["id"] for e in entries if not e.get("related") and not e.get("related_none")]
    if failing:
        raise ValueError(
            f"{len(failing)} entries have neither related links nor related_none=true: {failing}"
        )


def run(parsed_path, result_path, out_path):
    parsed = json.loads(Path(parsed_path).read_text())
    result = json.loads(Path(result_path).read_text())

    merged = merge(parsed, result)
    check_completeness(merged)

    for entry in merged:
        problems = validate_entry(entry, require_related=True)
        if problems:
            raise ValueError(f"{entry['id']}: {problems}")

    Path(out_path).write_text(json.dumps(merged, ensure_ascii=False, indent=2))
    print(f"Wrote {len(merged)} entries to {out_path}")


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent / "out"
    run(out_dir / "parsed.json", out_dir / "enrichment_result.json", out_dir / "vocab.json")
```

- [ ] **Step 5: Run to verify pass**

Run: `python3 -m pytest pipeline/tests/test_build_vocab.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add pipeline/prepare_enrichment_args.py pipeline/build_vocab.py pipeline/tests/test_build_vocab.py
git commit -m "Add Pass 3 tooling: enrichment args prep, merge, and completeness gate"
```

---

### Task 10: Pass 3 execution — run the tiered subagent Workflow (real cost, requires confirmation)

**This task spends real tokens across ~51 subagent calls.** Do not run it as a routine step in a subagent-driven-development loop without a human confirming first — stop and ask before invoking the Workflow tool below.

**Files:**
- Modifies: `pipeline/out/enrichment_args.json` (generated), `pipeline/out/enrichment_result.json` (generated), `pipeline/out/vocab.json` (generated), `worker/src/vocab.json` (overwritten with real data — see Task 11, which this task depends on for that final destination existing).

**Interfaces:**
- Consumes: `prepare_enrichment_args.run()` and `build_vocab.run()` from Task 9.

- [ ] **Step 1: Generate the enrichment args file**

Run: `python3 pipeline/prepare_enrichment_args.py`
Expected: prints pair/word/review counts (1,296 / 1,507 / 4 if Tasks 7–8 ran against the unmodified CSV) and writes `pipeline/out/enrichment_args.json`.

- [ ] **Step 2: STOP — confirm with the user before proceeding**

State plainly: "This will spawn approximately 51 subagents (13 Haiku validation batches, 38 Sonnet generation batches, plus 1 needs-review resolution call) and consume real tokens. Proceed?" Do not continue past this step without an explicit go-ahead.

- [ ] **Step 3: Read the prepared args**

Read `pipeline/out/enrichment_args.json` and pass its parsed JSON content as the `args` parameter to the Workflow tool call in the next step — do not re-derive or summarize it, pass it through as-is.

- [ ] **Step 4: Invoke the Workflow tool with this script**

```javascript
export const meta = {
  name: 'german-vocab-enrichment',
  description: 'Validate mechanical candidate pairs and generate related-word links for the German vocab deck',
  phases: [
    { title: 'Validate', detail: 'Haiku judges mechanical stem-match candidate pairs' },
    { title: 'Generate', detail: 'Sonnet generates related words for words with no candidate' },
    { title: 'Review', detail: 'Sonnet resolves the 4 needs_review items' },
  ],
}

function chunk(items, size) {
  const out = []
  for (let i = 0; i < items.length; i += size) out.push(items.slice(i, i + size))
  return out
}

const VALIDATE_SCHEMA = {
  type: 'object',
  properties: {
    results: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          lemma: { type: 'string' },
          candidate_lemma: { type: 'string' },
          valid: { type: 'boolean' },
          relation: { type: 'string', enum: ['same_root', 'opposite', 'verb_form', 'noun_form', 'synonym', 'none'] },
        },
        required: ['lemma', 'candidate_lemma', 'valid', 'relation'],
      },
    },
  },
  required: ['results'],
}

const GENERATE_SCHEMA = {
  type: 'object',
  properties: {
    results: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          lemma: { type: 'string' },
          related: {
            type: 'array',
            maxItems: 4,
            items: {
              type: 'object',
              properties: {
                word: { type: 'string' },
                relation: { type: 'string', enum: ['same_root', 'opposite', 'verb_form', 'noun_form', 'synonym'] },
              },
              required: ['word', 'relation'],
            },
          },
          related_none: { type: 'boolean' },
        },
        required: ['lemma', 'related', 'related_none'],
      },
    },
  },
  required: ['results'],
}

const REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    results: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          resolution: { type: 'string' },
          example_de: { type: 'string' },
          example_en: { type: 'string' },
        },
        required: ['id', 'resolution'],
      },
    },
  },
  required: ['results'],
}

phase('Validate')
const pairBatches = chunk(args.pairs, 100)
const validateResults = await pipeline(
  pairBatches,
  (batch, _item, index) =>
    agent(
      `You are judging German vocabulary relatedness. For each pair below, decide if the two words ` +
        `are genuinely worth learning together (same root, opposite, verb/noun form of each other, or close synonym) ` +
        `versus a coincidental shared prefix with no real relation. Default to valid=false when unsure. ` +
        `Pairs:\n${JSON.stringify(batch)}`,
      { label: `validate-${index}`, phase: 'Validate', model: 'haiku', schema: VALIDATE_SCHEMA }
    )
)

phase('Generate')
const wordBatches = chunk(args.wordsNeedingGeneration, 40)
const generateResults = await pipeline(
  wordBatches,
  (batch, _item, index) =>
    agent(
      `You are a German language expert building flashcard related-word links. The full vocabulary deck's ` +
        `lemmas (prefer linking to these when possible, since the goal is learning them together) are:\n` +
        `${JSON.stringify(args.allLemmas)}\n\n` +
        `For each word below, provide up to 4 related words (opposites, verb/noun pairs, root forms, or close ` +
        `synonyms), labelled with a relation type. If a word genuinely has no useful related word even outside ` +
        `the deck, set related_none=true and leave related empty. While you're at it, if you notice the given ` +
        `translation is wrong or misleading for the word, you may ignore it -- do not fabricate a fix field, ` +
        `just make sure your related-word choices are correct regardless.\n\n` +
        `Words:\n${JSON.stringify(batch)}`,
      { label: `generate-${index}`, phase: 'Generate', model: 'sonnet', schema: GENERATE_SCHEMA }
    )
)

phase('Review')
let reviewResult = { results: [] }
if (args.needsReview.length > 0) {
  reviewResult = await agent(
    `These German vocabulary rows had example sentences that couldn't be mechanically split into clean ` +
      `German/English pairs (ambiguous punctuation or junk data). For each, provide a corrected example_de ` +
      `and example_en, or set resolution to "drop" if the row's example data is unsalvageable.\n\n` +
      `Rows:\n${JSON.stringify(args.needsReview)}`,
    { label: 'resolve-needs-review', phase: 'Review', model: 'sonnet', schema: REVIEW_SCHEMA }
  )
}

const validated = validateResults.filter(Boolean).flatMap((r) => r.results)
const generated = generateResults.filter(Boolean).flatMap((r) => r.results)

return {
  validated,
  generated,
  needs_review_resolved: reviewResult.results,
}
```

- [ ] **Step 5: Save the Workflow's result**

Write the Workflow tool's returned object to `pipeline/out/enrichment_result.json` (use the Write tool — this is the orchestrating agent's job, not something the Workflow script itself can do, since Workflow scripts have no filesystem access).

- [ ] **Step 6: Merge and gate**

Run: `python3 pipeline/build_vocab.py`
Expected: `Wrote 2192 entries to .../vocab.json`. If it instead raises `ValueError` listing entries with neither `related` nor `related_none`, that means some lemma in `parsed.json` didn't appear in either the validation or generation batches (a bug in Task 9's batching, not something to patch around in `build_vocab.py`) — go back and check `prepare_enrichment_args.py`'s partitioning logic.

- [ ] **Step 7: Spot-check a sample**

Read 10 random entries from `pipeline/out/vocab.json` and manually confirm the related words make sense (e.g. `schnell` should not be linked to an unrelated word that merely shares a prefix). If quality looks systematically off for either the validation or generation tier, do not proceed to Task 11 — revisit the relevant agent prompt in Step 4 and re-run this task before trusting the dataset.

- [ ] **Step 8: Commit the pipeline outputs that should be tracked**

`pipeline/out/` is gitignored (Task 1) since it's regenerable, but the final `vocab.json` is the one artifact worth tracking outside `pipeline/out/` once it exists — that happens when it's copied into the Worker in Task 11/12. No commit here; this task's job is producing `pipeline/out/vocab.json` for Task 11 to consume.

---

### Task 11: Worker filtering, random selection, and response shaping

**Files:**
- Create: `worker/package.json`
- Create: `worker/src/filter.js`
- Create: `worker/src/response.js`
- Create: `worker/src/vocab.json` (copy of `pipeline/fixtures/vocab.sample.json` for now — Task 10's real output replaces this once it exists)
- Test: `worker/test/filter.test.js`
- Test: `worker/test/response.test.js`

**Interfaces:**
- Produces: `parseLevels(param: string | null) -> string[]`, `parseExclude(param: string | null) -> Set<string>`, `filterVocab(vocab: object[], {levels, exclude}) -> object[]`, `pickRandom(array: any[], rng?: () => number) -> any | null` from `filter.js`; `buildResponse(entry: object | null) -> object` from `response.js`. Task 12's `index.js` imports all of these.

- [ ] **Step 1: Scaffold the worker package**

`worker/package.json`:

```json
{
  "name": "trmnl-german-vocab-worker",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "node --test test/",
    "dev": "wrangler dev",
    "deploy": "wrangler deploy"
  },
  "devDependencies": {
    "wrangler": "^3.90.0"
  }
}
```

Run: `cd worker && npm install`

- [ ] **Step 2: Copy the fixture as the initial bundled dataset**

Run: `cp "../pipeline/fixtures/vocab.sample.json" src/vocab.json` (from inside `worker/`)

- [ ] **Step 3: Write the failing tests for `filter.js`**

`worker/test/filter.test.js`:

```javascript
import { test } from "node:test";
import assert from "node:assert/strict";
import { filterVocab, parseExclude, parseLevels, pickRandom } from "../src/filter.js";

const SAMPLE = [
  { word: "das Mitglied", lemma: "Mitglied", level: "A2" },
  { word: "der Baum", lemma: "Baum", level: "A1" },
  { word: "die Übersetzung", lemma: "Übersetzung", level: "B1" },
];

test("parseLevels defaults to all levels when empty", () => {
  assert.deepEqual(parseLevels(""), ["A1", "A2", "B1"]);
  assert.deepEqual(parseLevels(null), ["A1", "A2", "B1"]);
});

test("parseLevels filters unknown values and normalizes case", () => {
  assert.deepEqual(parseLevels("a1,C1,b1"), ["A1", "B1"]);
});

test("parseLevels falls back to all levels if nothing valid survives", () => {
  assert.deepEqual(parseLevels("C1,X9"), ["A1", "A2", "B1"]);
});

test("parseExclude lowercases and trims", () => {
  const excl = parseExclude(" Baum , MITGLIED ");
  assert.ok(excl.has("baum"));
  assert.ok(excl.has("mitglied"));
});

test("parseExclude handles empty input", () => {
  assert.equal(parseExclude(null).size, 0);
});

test("filterVocab respects level and exclude together", () => {
  const result = filterVocab(SAMPLE, { levels: ["A1", "A2"], exclude: new Set(["baum"]) });
  assert.deepEqual(result.map((e) => e.lemma), ["Mitglied"]);
});

test("filterVocab excludes by word or lemma", () => {
  const result = filterVocab(SAMPLE, { levels: ["A1", "A2", "B1"], exclude: new Set(["übersetzung"]) });
  assert.deepEqual(result.map((e) => e.lemma), ["Mitglied", "Baum"]);
});

test("filterVocab returns empty array when everything is excluded", () => {
  const result = filterVocab(SAMPLE, {
    levels: ["A1", "A2", "B1"],
    exclude: new Set(["mitglied", "baum", "übersetzung"]),
  });
  assert.deepEqual(result, []);
});

test("pickRandom is deterministic with an injected rng", () => {
  assert.equal(pickRandom(SAMPLE, () => 0), SAMPLE[0]);
  assert.equal(pickRandom(SAMPLE, () => 0.999), SAMPLE[2]);
});

test("pickRandom returns null for an empty array", () => {
  assert.equal(pickRandom([], () => 0), null);
});
```

- [ ] **Step 4: Run to verify failure**

Run: `cd worker && npm test`
Expected: FAIL — `Cannot find module '../src/filter.js'`

- [ ] **Step 5: Implement `filter.js`**

```javascript
const VALID_LEVELS = ["A1", "A2", "B1"];

export function parseLevels(param) {
  if (!param) return [...VALID_LEVELS];
  const requested = param
    .split(",")
    .map((s) => s.trim().toUpperCase())
    .filter((level) => VALID_LEVELS.includes(level));
  return requested.length > 0 ? requested : [...VALID_LEVELS];
}

export function parseExclude(param) {
  if (!param) return new Set();
  return new Set(
    param
      .split(",")
      .map((s) => s.trim().toLowerCase())
      .filter(Boolean)
  );
}

export function filterVocab(vocab, { levels, exclude }) {
  return vocab.filter((entry) => {
    if (!levels.includes(entry.level)) return false;
    if (exclude.has(entry.word.toLowerCase())) return false;
    if (exclude.has(entry.lemma.toLowerCase())) return false;
    return true;
  });
}

export function pickRandom(array, rng = Math.random) {
  if (array.length === 0) return null;
  const index = Math.min(array.length - 1, Math.floor(rng() * array.length));
  return array[index];
}
```

- [ ] **Step 6: Run to verify `filter.test.js` passes**

Run: `cd worker && node --test test/filter.test.js`
Expected: PASS (10 tests)

- [ ] **Step 7: Write the failing tests for `response.js`**

`worker/test/response.test.js`:

```javascript
import { test } from "node:test";
import assert from "node:assert/strict";
import { buildResponse } from "../src/response.js";

const ENTRY = {
  word: "das Mitglied",
  article: "das",
  pos: "Noun",
  level: "A2",
  translation: "member (of an organization), participant",
  example_de: "Neue Mitglieder sind willkommen.",
  example_en: "New members are welcome.",
  grammar: { type: "noun_forms", lines: ["Singular: das Mitglied", "Plural: Mitglieder"] },
  related: [
    { word: "die Mitgliedschaft", relation: "same_root", source: "mechanical_validated" },
    { word: "der Verein", relation: "synonym", source: "generated" },
  ],
};

test("buildResponse flattens grammar lines and related words into strings", () => {
  const body = buildResponse(ENTRY);
  assert.equal(body.grammar_type, "noun_forms");
  assert.equal(body.grammar_text, "Singular: das Mitglied · Plural: Mitglieder");
  assert.equal(body.related_text, "die Mitgliedschaft, der Verein");
});

test("buildResponse caps related words at 4", () => {
  const manyRelated = { ...ENTRY, related: Array.from({ length: 6 }, (_, i) => ({ word: `w${i}`, relation: "synonym", source: "generated" })) };
  const body = buildResponse(manyRelated);
  assert.equal(body.related_text.split(", ").length, 4);
});

test("buildResponse handles missing grammar", () => {
  const body = buildResponse({ ...ENTRY, grammar: null });
  assert.equal(body.grammar_type, "");
  assert.equal(body.grammar_text, "");
});

test("buildResponse truncates a long translation with an ellipsis, keeping it at 120 chars", () => {
  const body = buildResponse({ ...ENTRY, translation: "a".repeat(200) });
  assert.equal(body.translation.length, 120);
  assert.ok(body.translation.endsWith("…"));
});

test("buildResponse truncates a long example at 100 chars", () => {
  const body = buildResponse({ ...ENTRY, example_de: "a".repeat(200) });
  assert.equal(body.example_de.length, 100);
});

test("buildResponse leaves short fields untouched", () => {
  const body = buildResponse(ENTRY);
  assert.equal(body.translation, ENTRY.translation);
});

test("buildResponse returns a friendly fallback card for a null entry", () => {
  const body = buildResponse(null);
  assert.equal(body.word, "No words match your filters");
  assert.equal(body.grammar_text, "");
  assert.equal(body.related_text, "");
});
```

- [ ] **Step 8: Run to verify failure**

Run: `cd worker && node --test test/response.test.js`
Expected: FAIL — `Cannot find module '../src/response.js'`

- [ ] **Step 9: Implement `response.js`**

```javascript
function truncate(text, max) {
  const value = text || "";
  if (value.length <= max) return value;
  return value.slice(0, max - 1).trimEnd() + "…";
}

export function buildResponse(entry) {
  if (!entry) {
    return {
      word: "No words match your filters",
      article: "",
      pos: "",
      level: "",
      translation: "Adjust your plugin settings to include more levels or fewer exclusions.",
      example_de: "",
      example_en: "",
      grammar_type: "",
      grammar_text: "",
      related_text: "",
    };
  }

  const related = (entry.related || []).slice(0, 4);

  return {
    word: entry.word,
    article: entry.article || "",
    pos: entry.pos,
    level: entry.level,
    translation: truncate(entry.translation, 120),
    example_de: truncate(entry.example_de, 100),
    example_en: truncate(entry.example_en, 100),
    grammar_type: entry.grammar ? entry.grammar.type : "",
    grammar_text: entry.grammar ? entry.grammar.lines.join(" · ") : "",
    related_text: related.map((r) => r.word).join(", "),
  };
}
```

- [ ] **Step 10: Run all worker tests**

Run: `cd worker && npm test`
Expected: PASS (17 tests total)

- [ ] **Step 11: Commit**

```bash
git add worker/package.json worker/src/filter.js worker/src/response.js worker/src/vocab.json worker/test/
git commit -m "Add Worker filtering, random selection, and response shaping with tests"
```

---

### Task 12: Worker fetch handler, Wrangler config, and deploy

**Files:**
- Create: `worker/src/index.js`
- Create: `worker/wrangler.toml`

**Interfaces:**
- Consumes: `parseLevels`, `parseExclude`, `filterVocab`, `pickRandom` (Task 11 `filter.js`), `buildResponse` (Task 11 `response.js`).

- [ ] **Step 1: Write `wrangler.toml`**

```toml
name = "trmnl-german-vocab"
main = "src/index.js"
compatibility_date = "2024-09-01"
```

- [ ] **Step 2: Implement `index.js`**

```javascript
import vocab from "./vocab.json" with { type: "json" };
import { filterVocab, parseExclude, parseLevels, pickRandom } from "./filter.js";
import { buildResponse } from "./response.js";

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const levels = parseLevels(url.searchParams.get("levels"));
    const exclude = parseExclude(url.searchParams.get("exclude"));

    const filtered = filterVocab(vocab, { levels, exclude });
    const entry = pickRandom(filtered);
    const body = buildResponse(entry);

    return new Response(JSON.stringify(body), {
      headers: { "content-type": "application/json" },
    });
  },
};
```

- [ ] **Step 3: Run it locally with `wrangler dev`**

Run: `cd worker && npx wrangler dev`
Expected: starts a local dev server, typically at `http://localhost:8787`.

- [ ] **Step 4: Manually verify with curl (in another terminal)**

```bash
curl "http://localhost:8787/?levels=A1"
curl "http://localhost:8787/?levels=A1,A2&exclude=Baum"
curl "http://localhost:8787/?levels=A1&exclude=Baum,Katze,Mitglied,Schnell,Wichtig,Oben,Sofort"
```

Expected: first two calls return one word's flattened JSON matching the requested level filter; the third (excluding every A1 word in the 10-entry fixture) returns the fallback card (`"word": "No words match your filters"`).

- [ ] **Step 5: Deploy to Cloudflare**

Run: `cd worker && npx wrangler login` (opens a browser to authenticate — this creates a real, publicly reachable Cloudflare resource; confirm with the user before running `deploy` if they haven't used Wrangler before), then `npx wrangler deploy`.
Expected: prints a deployed URL like `https://trmnl-german-vocab.<subdomain>.workers.dev`. Record this URL — Task 13 needs it for the Polling URL.

- [ ] **Step 6: Verify the deployed URL with curl**

```bash
curl "https://trmnl-german-vocab.<subdomain>.workers.dev/?levels=A1"
```

Expected: same JSON shape as the local dev server.

- [ ] **Step 7: Commit**

```bash
git add worker/src/index.js worker/wrangler.toml
git commit -m "Add Worker fetch handler and deploy configuration"
```

---

### Task 13: TRMNL plugin — settings and Liquid template

**Files:**
- Create: `plugin/settings.yml`
- Create: `plugin/full.liquid`

**Interfaces:**
- Consumes: the flat JSON fields produced by Task 11's `buildResponse` — `word`, `article`, `pos`, `level`, `translation`, `example_de`, `example_en`, `grammar_type`, `grammar_text`, `related_text`.

- [ ] **Step 1: Install `trmnlp` and scaffold a preview project**

Run: `gem install trmnl_preview` (if Ruby isn't available, use the Docker alternative: `docker run --rm -it -v "$PWD/plugin:/plugin" -p 4567:4567 trmnl/trmnlp serve`, run from the `plugin/` directory).

Run: `cd plugin && trmnlp init .` (or into a temp dir and copy the generated `.trmnlp.yml` in, if `init` refuses to scaffold into a non-empty directory) — this generates the exact expected file layout `trmnlp serve` reads. Compare its generated `src/settings.yml` structure against what's written below before trusting the field names — the exact YAML keys for `custom_fields` are inferred from TRMNL's Help Center article, not independently re-verified here.

- [ ] **Step 2: Write `plugin/settings.yml`**

```yaml
name: German Vocabulary Flashcard
strategy: polling
polling_verb: GET
polling_url: "https://trmnl-german-vocab.<your-subdomain>.workers.dev/?levels={{ levels }}&exclude={{ exclude }}"
refresh_interval: 60
custom_fields:
  - keyname: levels
    field_type: select
    name: "Levels to include"
    multiple: true
    options:
      - "A1"
      - "A2"
      - "B1"
  - keyname: exclude
    field_type: multi_string
    name: "Words to exclude"
```

Replace `<your-subdomain>` with the real deployed Worker's subdomain from Task 12, Step 5.

- [ ] **Step 3: Write `plugin/full.liquid`**

Start with plain `{{ }}` interpolation (per docs.trmnl.com); the Open Question below covers what to do if fields don't populate.

```html
<div class="screen screen--og">
  <div class="view view--full">
    <div class="layout">
      <div class="label">{{ level }} · {{ pos }}</div>
      <div class="title">{{ article }} {{ word }}</div>
      <div class="description">{{ translation }}</div>
      <div class="value">{{ example_de }}</div>
      <div class="description">{{ example_en }}</div>
      {% if grammar_text != "" %}
      <div class="label">{{ grammar_text }}</div>
      {% endif %}
      {% if related_text != "" %}
      <div class="description">Related: {{ related_text }}</div>
      {% endif %}
    </div>
  </div>
</div>
```

- [ ] **Step 4: Preview locally and resolve the merge-variable syntax question**

Run: `trmnlp serve` (from `plugin/`), open `http://localhost:4567`, and point its Polling URL config at the deployed Worker URL from Task 12.

Expected: the rendered preview shows real field values (a German word, translation, etc.), not literal `{{ word }}` text. **If fields show up empty or literal**, switch every `{{ field }}` in `full.liquid` to `##{{ field }}` (the help.trmnl.com syntax) and reload — do not guess; use whichever one actually renders data in this preview.

- [ ] **Step 5: Iterate on layout visually**

Using the framework's documented classes (`screen`, `screen--og`, `view`, `view--full`, `layout`, `title`, `value`, `label`, `description`) as a starting point, adjust `full.liquid` until the card is legible on the 800×480 preview — centering, spacing, and font sizing aren't fully specified by the docs fetched during planning, so this is a look-and-adjust loop in the live preview, not a fixed spec. Test with the fixture's outlier entries (`ubersetzung`'s long translation, `sofort`'s 4-item related list) to confirm nothing clips.

- [ ] **Step 6: Commit**

```bash
git add plugin/settings.yml plugin/full.liquid
git commit -m "Add TRMNL plugin settings and Liquid flashcard template"
```

---

### Task 14: Wire up the real dataset and verify end-to-end on the device

**Files:**
- Modifies: `worker/src/vocab.json` (replaced with Task 10's real output)

**Interfaces:** none — this is verification, not new code.

- [ ] **Step 1: Replace the fixture with the real dataset**

Run: `cp pipeline/out/vocab.json worker/src/vocab.json` (requires Task 10 to have been run for real — do not proceed if `pipeline/out/vocab.json` doesn't exist yet).

- [ ] **Step 2: Re-run Worker tests against the real data shape**

Run: `cd worker && npm test`
Expected: still PASS — the tests use their own inline fixtures, not `src/vocab.json` directly, so this just confirms nothing broke.

- [ ] **Step 3: Redeploy**

Run: `cd worker && npx wrangler deploy`

- [ ] **Step 4: Verify variety and filtering against the real dataset**

```bash
curl "https://trmnl-german-vocab.<your-subdomain>.workers.dev/?levels=A1"
curl "https://trmnl-german-vocab.<your-subdomain>.workers.dev/?levels=A1"
curl "https://trmnl-german-vocab.<your-subdomain>.workers.dev/?levels=B1"
```

Expected: the two A1 calls return different words most of the time (random selection over ~700 A1 entries), and the B1 call returns a B1-level word.

- [ ] **Step 5: Install the plugin on the real TRMNL device/account**

Using TRMNL's web UI (or `trmnlp push`, if authenticated via `trmnlp login`), create the Private Plugin from `plugin/settings.yml` / `plugin/full.liquid`, set the Custom Field values (e.g. levels = A1, A2, B1), and add it to a playlist/screen on the actual device.

- [ ] **Step 6: Confirm on the physical device**

Wait for the configured `refresh_interval` (or trigger a manual refresh if TRMNL's UI supports it) and confirm the device shows a real flashcard — word, translation, example, grammar block, related words all rendering without clipping. Change the Custom Field's level filter to just `B1` and confirm subsequent refreshes only show B1 words.

- [ ] **Step 7: Commit**

```bash
git add worker/src/vocab.json
git commit -m "Wire up the real enriched vocabulary dataset"
```

---

## Self-Review Notes

- **Spec coverage**: every spec section maps to a task — source data cleanup (Tasks 2–6), Pass 1/2/3 (Tasks 7–10), backend contract (Task 11–12), display/template (Task 13), error handling (fallback card in Task 11, article-mismatch hard error in Task 7, completeness gate in Task 9), testing (every task has its own), the open merge-variable-syntax question (Task 13 Step 4).
- **Placeholder scan**: no TBD/TODO; the one deliberately unresolved item (merge-variable syntax) has a concrete resolution procedure, not a guess.
- **Type/name consistency checked**: `filter.js`'s `filterVocab`/`pickRandom`/`parseLevels`/`parseExclude` names match between Task 11's implementation and Task 12's `index.js` import; `response.js`'s `buildResponse` likewise; `pipeline.parse.run()`'s return shape `(entries, review_items)` matches what Task 8's `match_candidates.run()` and Task 9's `prepare_enrichment_args.run()` consume; the `related[].source` field (`mechanical_validated` / `generated`) is consistent across the schema validator (Task 1), the fixture (Task 1), `build_vocab.merge()` (Task 9), and `response.js` (Task 11, where it's dropped since the template doesn't need it).
- **Full-dataset verification, not sample-based trust**: Tasks 5 and 6's regex logic were each actually run against all 2,192 real rows (not just the samples used to write them) before being written into this plan, and two real bugs surfaced and were fixed as a result — a naive leading-anchor numbering-artifact strip that silently failed on all 566 multi-example cells (Task 5), and a grammar-section parser that raised on the 80 rows where a marker is present but the section has no useful content beyond the headline word (Task 6). Both fixes are reflected in the code above, not left as follow-up work. The corresponding counts in Task 7's tests (`210` null-grammar rows, `7` needs-review items) are the verified figures, not the earlier estimates the spec first shipped with.
