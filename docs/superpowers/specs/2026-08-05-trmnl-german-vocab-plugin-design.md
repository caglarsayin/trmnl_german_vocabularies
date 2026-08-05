# TRMNL German Vocabulary Flashcard Plugin — Design

## Overview

A TRMNL private plugin that shows one German vocabulary flashcard per screen
refresh — word, article, part of speech, English translation, an example
sentence with its translation, a grammar block (plural / conjugation /
comparative), and related words drawn from the same deck. Data comes from the
user's existing list (`GermanWortList - Main.csv`). Word selection is random
per poll, filtered by per-installation settings. Built for personal use
first, using TRMNL Custom Fields so multiple independent installations work
from day one and it can be shared later without rework.

All figures in this document were measured directly from the source CSV, not
estimated.

## Goals

- One flashcard per refresh, showing: German word (with article for nouns),
  part of speech, English translation, **exactly one** example sentence +
  translation selected to match the word's own level (simple for A1,
  longer/more complex for B1), the applicable grammar block, and related
  words from the deck.
- Per-installation filtering by CEFR level, without a backend user database.
- Keep the live request path LLM-free and fast — all language work happens
  once, offline, during data preparation.
- Every card has related words (complete coverage is a v1 requirement).

## Non-goals (this iteration)

- Progress tracking / spaced repetition. Deferred, but the backend must not
  preclude it (see Future work).
- TRMNL Marketplace publication. Private plugin first.
- Live LLM calls at request time.
- Levels beyond A1/A2/B1 — B2 (110 rows) and C1 (3 rows) are **dropped
  during the pipeline** by decision, leaving 2,192 rows.

## Source data: measured profile

Source: `GermanWortList - Main.csv`, 2,305 data rows, all with non-empty
`Wort` / `Klarwort` / `Übersetzung` / `Detail`, and **no duplicate words**
(2,305 distinct — so the word itself is a safe unique key).

Columns: `Niveau`, `Wort`, `Klarwort`, `Übersetzung`, `Detail`,
`Example1`–`Example5`, plus one unnamed trailing column.

| Level | Rows | Kept? |
|---|---|---|
| A1 | 705 | yes |
| A2 | 928 | yes |
| B1 | 559 | yes |
| B2 | 110 | **dropped** |
| C1 | 3 | **dropped** |
| **Kept total** | **2,192** | |

Everything below refers to the 2,192 kept rows unless noted.

### What each column actually contains

- **`Wort` already carries the article for nouns** ("das Mitglied"), and
  `Klarwort` is the same word with the article stripped ("Mitglied").
  Verified across the full sheet: where `Wort` starts with der/die/das,
  `Wort` minus the article equals `Klarwort` in **100% of cases (0
  mismatches)**. So article extraction is exact and needs no LLM and no blob
  parsing. 1,161 nouns (53.0%): die 494, der 412, das 255.
- **`Übersetzung`** packs 1–4 senses into one blob, sense boundaries marked
  by runs of 2+ spaces, each optionally tagged `(Noun):` / `(Verb):` /
  `(Adjektiv):` / `(Adverb):` etc. **54.8% of rows have no such tag**, so
  tags alone are an insufficient POS source.
- **The trailing unnamed column carries a full POS tag**, not just
  Noun-vs-Word: `Noun` (1,159, agreeing with the article-derived count of
  1,161 to within 2), `Word` (926 — a placeholder meaning "see the inline
  `(POS):` tags instead," used exactly on rows that have them), and,
  critically, specific tags — `Adverb` (76), `Pronoun` (9), `Conjunction`
  (6), `Preposition` (5), `Adjective` (4), `Interjection` (2), `Verb` (2),
  `Contraction` (1), `Particle` (1), `Numeral` (1) — for **exactly the 106
  rows that have neither an article nor an inline tag**. Verified by
  isolating that no-article/no-tag set and confirming its trailing values
  are exactly this specific-tag set (not `Noun`/`Word`). **Net result: POS
  is resolvable for all 2,192 rows with zero manual disambiguation** —
  article when present, else inline tag when present, else this trailing
  tag.
- **`Detail` is not a near-duplicate of `Übersetzung`** — only 5.9% match
  after normalization. It contains the sense blob **plus an emoji-delimited
  grammar section**.

### `Detail`'s grammar sections (the emoji are delimiters, not noise)

| Marker | Section | Rows | Share |
|---|---|---|---|
| 🔢 | Noun Forms (singular / plural) | 1,182 | 53.9% |
| 🔄 | Verb Conjugations | 474 | 21.6% |
| 📊 | Degrees of Comparison | 406 | 18.5% |
| — | no grammar section | 130 | 5.9% |

**These sections are mutually exclusive — 0 rows contain more than one.**
That means the card needs exactly one grammar slot, populated for 94.1% of
words and absent for 130. The emoji are parse anchors; they must be stripped
from rendered output since they will not render on a 2-bit grayscale e-ink
panel.

### Example cells

8,653 non-empty cells. German and English are concatenated with **no
separator** (`Ich komme sofort.I'm coming right away.`). Splitting on
"sentence-ending punctuation immediately followed by an uppercase letter":

- **93.4%** (8,084) split cleanly into exactly two parts (DE | EN).
- **6.5%** (566) split into 3+ parts — these are multiple examples spliced
  into one cell, usually with a stray `N.` numbering artifact (580 cells
  contain one).
- **3 cells** are genuinely ambiguous (quoted speech whose quotes contain
  sentence-ending punctuation), plus one junk cell literally reading
  `Examples5.` These go to manual review.

### Character-level contamination

- **2,221 zero-width non-joiners (U+200C)** in `Übersetzung` — invisible.
- Soft hyphen (U+00AD), non-breaking hyphen (U+2011), curly quotes, en/em
  dashes, and **one Cyrillic `е` (U+0435) homoglyph** typo.
- Emoji as described above.

All of this is stripped or normalized in Pass 1.

## Architecture

```
TRMNL device --(scheduled wake)--> TRMNL cloud
    --(GET poll, URL templated with this installation's settings)-->
Cloudflare Worker --(reads bundled static vocab.json)-->
    filter by level --> pick one at random --> flat JSON response -->
TRMNL renders Liquid template --> static image pushed to device
```

- **TRMNL Private Plugin**, strategy = **Polling**. `refresh_interval` must
  be one of TRMNL's fixed values: **15, 60, 360, 720, or 1440 minutes**.
- **Custom Fields** define the per-installation settings form. We author the
  Polling URL as a template referencing field keynames (e.g.
  `.../poll?levels={{ levels }}&exclude={{ exclude }}`); TRMNL interpolates
  each installation's saved values before calling it. Per-installation
  settings therefore arrive as query params **via our own URL templating —
  not an automatic passthrough** — and need no auth or per-user database.
  - `levels`: `select` field with `multiple: true`, options A1/A2/B1.
  - `exclude`: `multi_string` field, comma-separated words.
- **Runtime: Cloudflare Workers** — generous free tier at this volume,
  Workers KV available if progress tracking is added later, simple Wrangler
  deploy.
- `vocab.json` for 2,192 rows is small enough to bundle with the Worker;
  no KV or external storage needed for v1.

Sources: [Private Plugins](https://help.trmnl.com/en/articles/9510536-private-plugins),
[Custom Plugin Form Builder](https://help.trmnl.com/en/articles/10513740-custom-plugin-form-builder),
[Dynamic Polling URLs](https://help.trmnl.com/en/articles/12689499-dynamic-polling-urls),
[Screen Templating](https://docs.trmnl.com/go/private-plugins/templates),
[Framework: Screen](https://trmnl.com/framework/docs/2.3/screen).

### Approaches considered and rejected

- **Webhook strategy** (push): we would have to run our own scheduler and
  track every installation's webhook URL. Polling gives both for free since
  TRMNL initiates the fetch.
- **Marketplace plugin from day one**: manifest schema, TRMNL review, and
  genericizing away from this specific deck, all before the private version
  is validated. Deferred.
- **Live LLM enrichment per request**: per-poll latency and cost, and
  non-reproducible cards. Rejected in favour of precomputation.

## Data pipeline (offline, re-run when the sheet changes)

Three passes. Passes 1–2 are deterministic scripts; Pass 3 is interactive.

### Pass 1 — Mechanical parse (deterministic)

1. Drop B2/C1 → 2,192 rows.
2. Unicode cleanup: strip U+200C / U+00AD / U+2011, normalize curly quotes
   and dashes, repair the Cyrillic `е` homoglyph.
3. **Article + lemma**: regex `^(der|die|das)\s+` on `Wort`; assert the
   remainder equals `Klarwort` (held 100% on the full sheet — treat any
   violation as a hard error, not a warning).
4. **POS**: article presence → `Noun`; else inline `(POS):` tag on the first
   sense where present; else the trailing column's specific tag (covers
   exactly the 106 rows with neither). No row falls through all three.
5. **Translation**: take the **first sense only** (split on runs of 2+
   spaces). This is the primary overflow control — see budget below.
6. **Examples**: split on the punctuation→uppercase boundary; strip `N.`
   numbering artifacts; from the resulting DE/EN pairs, pick one **by the
   word's own level** — the deck's own example sentences already scale in
   complexity by level, so picking within that band per level is more
   correct than a single global rule:
   - **A1 → shortest** available pair (median 21 chars, p90 29, max 44)
   - **A2 → median-length** available pair (median 34, p90 43, max 96)
   - **B1 → longest** available pair (median 44, p90 55, max 82)

   Route the 3 ambiguous cells and the `Examples5.` junk cell to
   `needs_review.json`.
7. **Grammar block**: split `Detail` on the 🔢/🔄/📊 marker, parse the block
   into structured lines, tag its type, and **strip the emoji from the
   stored text**. Exactly one block per row where present.
8. Emit `parsed.json` + `needs_review.json`.

### Pass 2 — Mechanical related-word candidates (deterministic)

Prefix-stem matching (5/6/7-char prefixes) across all 2,192 lemmas, since
the requirement is links to **other words in this deck**.

- **685 words (31.2%)** get ≥1 candidate; median 1, p90 4, max 9.
- **1,296 candidate pairs** total to validate.
- **1,507 words get no mechanical candidate** and need generation.

The method produces true positives (`übersetzen→übersetzung`,
`ärgern→ärgerlich`, `bedeuten→bedeutend`, `blitzen→blitz`,
`öffentlich→öffentlichkeit`) and clear false positives
(`schwanger→schwach`, `komplett→kompliziert`), so its output is a
**candidate list, never final**.

Emit `candidates.json`.

### Pass 3 — Claude Code batch enrichment (no API token; tiered subagent fleet)

No standalone script — orchestrated as a Workflow (subagent fleet) from
inside a Claude Code session, tiered by task difficulty rather than one
model for everything:

1. **Validate** the 1,296 candidate pairs — a bounded yes/no + relation-type
   judgment per pair, cheap enough for a smaller model. **Haiku**, batched
   ~100 pairs/agent → **~13 agent calls**.
2. **Generate** links for the 1,507 words with no mechanical candidate —
   opposites, verb↔noun pairs, root forms, near-synonyms, **preferring
   words that exist in this deck**. This is real linguistic judgment where
   a weaker model's mistakes are more likely and costlier to catch later.
   **Sonnet**, batched ~40 words/agent (each agent gets the full lemma list
   for grounding) → **~38 agent calls**.
3. Label every link with a relation type: `same_root`, `opposite`,
   `verb_form`, `noun_form`, `synonym`. Tag `related[].source` as
   `"mechanical_validated"` (step 1) or `"generated"` (step 2) — cheap
   provenance for auditing either tier later without re-running anything.
4. Resolve `needs_review.json` (Sonnet — same reasoning as step 2).
5. Validate translations opportunistically while passing over each batch.

Both stages use `schema` on the agent calls so output is structured, not
prose to parse. **~51 agent calls total** — above this session's default
"medium" workflow guideline (under 15 agents); appropriate here since it's
a one-time bulk data job with a natural per-batch structure, not a case of
open-ended fan-out. Confirm before running.

Because complete coverage is a v1 requirement, Pass 3 ends with a
**completeness gate**, not a spot check: every row must have either a
non-empty `related[]` or an explicit `related_none: true` marker justifying
why no useful link exists. The build fails if any row has neither.

**Output**: `vocab.json` — the single source of truth, bundled with the
Worker. Re-running means re-running all three passes and redeploying.

## Dataset schema (`vocab.json`)

One flat array of entries:

```json
{
  "id": "mitglied",
  "level": "A2",
  "word": "das Mitglied",
  "lemma": "Mitglied",
  "article": "das",
  "pos": "Noun",
  "translation": "member (of an organization), participant",
  "example_de": "Neue Mitglieder sind willkommen.",
  "example_en": "New members are welcome.",
  "grammar": {
    "type": "noun_forms",
    "lines": ["Singular: das Mitglied", "Plural: die Mitglieder"]
  },
  "related": [
    { "word": "die Mitgliedschaft", "relation": "same_root", "source": "mechanical_validated" }
  ]
}
```

`article` and `grammar` are `null` where not applicable (`grammar` null for
130 rows). `id` is the lowercased lemma, unique because the deck has no
duplicate words.

## Backend API contract

`GET /poll`

| Param | Source | Default | Behavior |
|---|---|---|---|
| `levels` | `select` (multiple) | all of A1/A2/B1 | comma-separated; unknown values ignored |
| `exclude` | `multi_string` | none | comma-separated words, matched against `word` and `lemma` case-insensitively after trimming |

Response: **flat JSON at the root level** — TRMNL exposes root-level fields
directly to the template, whereas nested objects require explicit dot-path
Liquid syntax. `grammar.lines` and `related` are unavoidably nested/array;
these are pre-flattened into template-ready strings by the Worker
(`grammar_lines` as a list of strings, `related_display` as a preformatted
string) so the template stays simple.

Malformed or unknown params fall back to defaults rather than erroring.

## Display / template

**Device**: 800×480, 2-bit grayscale e-ink. Markup nests
`screen → view view--full → layout`, using the TRMNL framework's typography
and layout utilities. Full-screen view — the content genuinely needs it.

Card structure, top to bottom:

1. German word, large, centered (article included for nouns).
2. Small badge line: article + part of speech + level.
3. English translation (first sense only).
4. Example sentence (German), with its English translation beneath.
5. Grammar block, when present — labelled by type.
6. Related words, as a compact secondary line.

### Overflow budget (measured, filtered subset)

| Field | median | p90 | p99 | max |
|---|---|---|---|---|
| `Wort` | 9 | 13 | 17 | 32 |
| `Übersetzung`, all senses | 57 | 162 | 214 | **315** |
| `Übersetzung`, **first sense only** | 46 | 77 | 118 | **163** |
| example DE, **level-selected** (see above) | 33 | 47 | 62 | 96 |
| example EN, **level-selected** | 32 | 47 | 63 | 84 |

(The example figures are measured on the properly split, per-level-selected
sentence — not the raw unsplit cell, which mixes DE+EN+multiple examples
and would misleadingly show a max of 297.)

Taking the first sense cuts the worst case from 315 → 163 characters. The
level-aware example selection keeps examples well-bounded on its own — max
96 chars — with no observed case needing truncation. On top of these two
primary defences:

- Hard-cap translation at 120 chars (covers p99 = 118) with ellipsis.
- Hard-cap the example at 100 chars (covers the measured max of 96) as a
  safety margin, not because truncation is expected.
- Cap `related` at 4 items.
- Strip all emoji before rendering.
- Verify against the framework's overflow-management utilities rather than
  assuming CSS truncation behaves as on a normal browser.

## Error handling

| Condition | Behavior |
|---|---|
| Filtered set empty (everything excluded) | Worker returns a friendly fallback card ("no words match your filters"), not an error — the display must never show a broken plugin |
| `vocab.json` fails to load | Worker returns HTTP 5xx; TRMNL falls back to its own stale/error state; failure logged |
| Malformed / unknown query params | Ignored, defaults applied |
| Missing `grammar` (130 rows) or empty `related` | Template omits the section entirely; no empty headings |
| Pass 1 article assertion fails | Hard error — indicates the source sheet's structure changed |
| Pass 3 completeness gate fails | Build fails; v1 requires full related-word coverage |

## Testing

- **Backend**: unit tests for level filtering, exclusion matching
  (case/whitespace), random selection (seeded for determinism), and the
  empty-result fallback.
- **Pipeline**: unit tests on real problem rows captured from this analysis —
  a 3+-split example cell, a `N.` numbering artifact, each of the three
  grammar markers, a noun with an article, one of the 106 trailing-column
  POS-fallback rows, the Cyrillic-homoglyph row, and one row per level
  (A1/A2/B1) to confirm shortest/median/longest example selection.
- **Template**: use the **`trmnlp` local CLI** with `settings.yml` and
  `.liquid` files to preview locally — no physical device needed for layout
  iteration. Then confirm in TRMNL's hosted previewer.
- **Overflow**: render the measured worst-case rows (longest word, longest
  first-sense translation, 297-char example, 4 related words, each grammar
  type) and confirm nothing clips.
- **End-to-end**: on the device, confirm polling yields a new word and that
  changing Custom Fields actually changes what appears.

## Open question to resolve during implementation

TRMNL's own docs disagree on merge-variable syntax: the help center shows
`##{{ field_name }}` for polling payloads, while
[docs.trmnl.com](https://docs.trmnl.com/go/private-plugins/templates) shows
plain `{{ variable }}`. Determine the correct form empirically in the
previewer before writing the template; do not assume either.

## Future work

- Progress tracking / spaced repetition via Workers KV keyed by
  installation.
- Reinstating B2/C1 (113 rows) if the user's level advances.
- Showing multiple senses, or cycling senses across refreshes.
- Marketplace publication.
- A better exclusion UX — hand-typing comma-separated words does not scale
  to 2,192 entries, so level filtering is the practical filter in v1 and
  `exclude` is for a handful of specific annoyances.
