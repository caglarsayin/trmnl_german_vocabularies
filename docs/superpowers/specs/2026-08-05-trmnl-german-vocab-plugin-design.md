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

| Marker | Section | Rows with marker | Yield a usable block |
|---|---|---|---|
| 🔢 | Noun Forms (singular / plural) | 1,182 | 1,182 (100%) |
| 🔄 | Verb Conjugations | 474 | 473 |
| 📊 | Degrees of Comparison | 406 | 327 |
| — | no marker at all | 130 | 0 |

**These sections are mutually exclusive — 0 rows contain more than one.**
But "has the marker" and "yields a usable block" are not the same thing —
verified by actually running the parser over all 2,192 rows, not just
sampling:

- **79 of the 406 `📊` rows only have a `Positive:` value**, with no
  `Comparative:`/`Superlative:` — these are words like `wohin`, `warum`,
  `schon` that don't inflect for comparison in German. Showing "Positive:
  wohin" would just repeat the headline word, so these correctly yield no
  block, not a malformed one.
- **1 of the 474 `🔄` rows (`möchten`) has no `Partizip II:` at all** — a
  modal verb where the source data simply omitted it.

**Net: 1,982 rows (90.4%) get a real grammar block; 210 (9.6%) get none** —
130 from no marker, 79 from comparison-without-inflection, 1 from
verb-without-partizip. The parser must treat all three as "no block"
outcomes, not errors — the first version of this parser, tested only
against 3 samples per marker type, raised an exception on all 80 of the
non-inflecting/no-partizip cases when run against the full 2,192 rows; it
was corrected before being trusted. The emoji are parse anchors; they must
be stripped from rendered output since they will not render on a 2-bit
grayscale e-ink panel.

### Example cells

8,653 non-empty cells. German and English are concatenated with **no
separator** (`Ich komme sofort.I'm coming right away.`). Splitting on
"sentence-ending punctuation immediately followed by an uppercase letter":

- **93.4%** (8,084) split cleanly into exactly two parts (DE | EN).
- **6.5%** (566) split into 3+ parts on the naive punctuation→uppercase
  rule alone — multiple examples spliced into one cell, with a stray `N.`
  numbering artifact sitting *between* two sentences (not at a cell's
  start, so a simple leading-strip does not fix it). The correct fix
  removes `N. ` wherever it sits between a sentence-ending punctuation mark
  and the next capital letter — e.g. `later?3. Das machen` → `later?Das
  machen`, which then splits cleanly. This is a genuine fix, not an
  estimate: verified by actually running the corrected splitter over every
  example cell in the CSV, not just sampling. A first version that only
  stripped a *leading* `N. ` looked plausible but left all 566 of these
  cells unresolved when checked against the full data — the fix must
  target the artifact's real position.
- After that fix, **7 cells remain genuinely unsplittable** — nested/curly
  quotes containing their own sentence-ending punctuation (e.g. `Er sagte:
  "die" ist der Artikel im Plural.'die' is the article...`), one cell with
  two numbered artifacts plus a parenthetical remark, and one pure-junk
  cell reading `Examples5.` These are logged for visibility, not silently
  dropped, but critically: **every one of the 2,192 rows still has at least
  one other usable example cell** — verified directly, not assumed — so
  these 7 cells never block a row from getting a card. `needs_review.json`
  is informational (which raw cells were discarded) rather than a gate.

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
6. **Examples**: remove `N. ` numbering artifacts wherever they sit between
   a sentence-ending punctuation mark and the next capital letter (not
   just at a cell's start — verified this is where they actually occur);
   *then* split on the punctuation→uppercase boundary. From the resulting
   DE/EN pairs, pick one **by the word's own level** — the deck's own
   example sentences already scale in complexity by level, so picking
   within that band per level is more correct than a single global rule:
   - **A1 → shortest** available pair (median 21 chars, p90 29, max 44)
   - **A2 → median-length** available pair (median 34, p90 43, max 96)
   - **B1 → longest** available pair (median 44, p90 55, max 82)

   Log the 7 genuinely unsplittable cells to `needs_review.json` for
   visibility; every row still has another usable cell, so this never
   blocks a row (verified against all 2,192 rows, not assumed).
7. **Grammar block**: split `Detail` on the 🔢/🔄/📊 marker, parse the block
   into structured lines, tag its type, and **strip the emoji from the
   stored text**. A marker being present does not guarantee a usable block
   — 79 comparison-marked rows have only `Positive:` (no inflection to
   show) and 1 verb-marked row (`möchten`) has no `Partizip II:`; both
   must resolve to `grammar: null`, not an error. Verified: 210 of 2,192
   rows end up with `grammar: null` (130 no-marker + 79 + 1).
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
210 rows — see the grammar-sections breakdown above). `id` is the lowercased
`word` (not `lemma`) with spaces replaced by hyphens — verified unique
across all 2,192 rows. `lemma.lower()` is **not** safe as the id: German
capitalizes nominalized verbs, so the noun "das Hören" (hearing) and the
verb "hören" (to hear) share the lemma "hören" and collide if lowercased
without the article. `word` already carries that distinction (`das Hören`
vs `hören`), which is exactly why it, not the bare lemma, is the identity.

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
| Missing `grammar` (210 rows) or empty `related` | Template omits the section entirely; no empty headings |
| Pass 1 article assertion fails | Hard error — indicates the source sheet's structure changed |
| Pass 3 completeness gate fails | Build fails; v1 requires full related-word coverage |

## Testing

- **Backend**: unit tests for level filtering, exclusion matching
  (case/whitespace), random selection (seeded for determinism), and the
  empty-result fallback.
- **Pipeline**: unit tests on real problem rows captured from this analysis
  — a mid-sentence `N.` numbering artifact that must resolve to a clean
  split (not just get flagged), a genuinely unsplittable quoted-speech
  cell, each of the three grammar markers *and* their no-block edge cases
  (comparison-without-inflection, verb-without-partizip), a noun with an
  article, one of the 106 trailing-column POS-fallback rows, the
  Cyrillic-homoglyph row, and one row per level (A1/A2/B1) to confirm
  shortest/median/longest example selection. Critically: run these parsers
  against the **full 2,192-row CSV**, not just curated samples, before
  trusting them — every parsing bug found during this spec's analysis
  (the comparison/verb no-block cases, the mid-sentence numbering
  artifact) was caught this way, not by sampling.
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
