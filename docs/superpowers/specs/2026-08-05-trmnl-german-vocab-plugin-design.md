# TRMNL German Vocabulary Flashcard Plugin — Design

## Overview

A TRMNL private plugin that shows one German vocabulary flashcard at a time
(word, translation, article/part of speech, example sentence, related words),
sourced from the user's existing vocabulary list (`GermanWortList - Main.csv`,
~2,304 entries across CEFR levels A1/A2/B1). Word selection is random per
poll, filtered by per-installation settings (levels to include, words to
exclude). Built for personal use first, with the settings mechanism (TRMNL
Custom Fields) already supporting multiple independent installations, so it
can be shared with others later without rework.

## Goals

- Show one flashcard per screen refresh: German word, article/part of
  speech, English translation, an example sentence, and related words
  (opposites, noun/verb pairs, root forms) worth learning together.
- Let each installation filter which levels/words are eligible, without
  requiring a backend user database.
- Keep the live request path fast, deterministic-cost, and LLM-free — all
  language understanding happens once, offline, during data preparation.

## Non-goals (for this iteration)

- Progress tracking / spaced repetition (avoiding repeats, marking words as
  learned). Explicitly deferred; the backend design should not preclude
  adding it later (see Future Work).
- Publishing to the TRMNL Marketplace. Start as a private plugin; revisit
  once the private version is validated.
- Live LLM calls at request time. All enrichment is precomputed.

## Source data reality check

The source CSV is messier than a simple word/translation/level table:

- Columns: `Niveau` (level), `Wort`, `Klarwort`, `Übersetzung`, `Detail`,
  `Example1`–`Example5`, plus a mostly-unused trailing column.
- `Übersetzung` and `Detail` each pack **multiple senses per word** into one
  text blob (e.g. `wahrscheinlich (Adverb): probably... wahrscheinlich
  (Adjektiv): probable...`), and the two columns disagree on capitalization
  for the same sense.
- Example cells concatenate the **German sentence and its English
  translation with no separator** (`Es ist wahrscheinlich, dass er heute
  kommt.It is probable that he will come today.`), and some cells splice
  **two examples together** with a stray numbering artifact (`3.`).
- No dedicated article/part-of-speech column (embedded as `(Adverb)` /
  `(Noun)` text inside the blob) and no related-words column.

This shapes the data pipeline below into two distinct passes rather than one.

## Architecture

```
TRMNL device --(scheduled wake)--> TRMNL cloud --(poll, per Custom Field
settings)--> Cloudflare Worker --(reads static enriched dataset)--> picks
one random word matching filters --> returns JSON --> TRMNL renders Liquid
template --> pushes static image to device
```

- **TRMNL Private Plugin**, strategy = **Polling**. TRMNL calls our Worker
  URL on a schedule (`refresh_interval`), which must be one of TRMNL's fixed
  values: **15, 60, 360, 720, or 1440 minutes** — not an arbitrary number.
- **Custom Fields** (defined on the plugin) give each installation its own
  settings form — levels to include (a `select` field with `multiple:
  true`, constrained to A1/A2/B1) and words to exclude (a `multi_string`
  field, free-form comma-separated). We author the Polling URL itself as a
  template referencing each field by keyname (e.g. `.../poll?levels={{
  levels }}&exclude={{ exclude }}`); TRMNL interpolates the installation's
  saved values into that URL before calling it. So per-installation
  settings reach our Worker as query params via our own URL templating —
  not an automatic passthrough — and still without any auth or per-user
  database on our side. (Source: [Private Plugins](https://help.trmnl.com/en/articles/9510536-private-plugins),
  [Custom Plugin Form Builder](https://help.trmnl.com/en/articles/10513740-custom-plugin-form-builder),
  [Dynamic Polling URLs](https://help.trmnl.com/en/articles/12689499-dynamic-polling-urls).)
- **Backend runtime: Cloudflare Workers.** Chosen for a generous free tier
  at this traffic volume, Workers KV available if progress-tracking is
  added later, and simple CLI deploy (Wrangler).
- Webhook strategy and full Marketplace submission were considered and
  rejected for now — see "Approaches considered" below.

### Approaches considered

- **Private Plugin + Webhook** (push-based): would require us to run our
  own scheduler and track every installation's webhook URL ourselves.
  Rejected — Polling gives us this for free since TRMNL initiates the
  fetch.
- **Full Marketplace plugin from day one**: real upfront overhead (manifest
  schema, TRMNL review, genericizing away from this specific vocab deck)
  before the private version is even validated. Deferred to a later phase.

## Data pipeline (offline, one-time per sheet update)

Two passes, run manually whenever the source sheet changes:

1. **Mechanical parser** (a small script, not LLM-driven — this is
   pattern-based cleanup): splits the concatenated example+translation
   cells, separates multi-example cells, and extracts the `(Adverb)` /
   `(Noun)`-style tags into a structured part-of-speech field per sense.
   Cases the parser can't confidently resolve are written to a separate
   "needs review" list rather than guessed, for the batch pass below to
   resolve.
2. **Claude Code batch pass** (interactive, no separate API token needed):
   run in batches over the parser's output to validate translations, fix
   entries the parser flagged, and generate the missing **related words**
   field (opposites for adjectives, noun/verb pairs, root forms) using
   linguistic judgment the mechanical parser can't provide. Given the
   ~2,300-row volume, this runs across multiple batches, possibly multiple
   sessions.

**Output**: a single clean JSON dataset — the source of truth deployed with
the Worker (or stored in Workers KV). The live backend only ever reads this
static file; it never calls an LLM at request time.

**Re-running**: whenever the source sheet changes, re-run both passes and
redeploy the dataset.

## Backend API contract

- `GET /` (the polling endpoint), query params populated by TRMNL from
  Custom Fields:
  - `levels` — comma-separated levels to include (default: all)
  - `exclude` — comma-separated German words to exclude, matched against
    the dataset's word field case-insensitively after trimming whitespace
    (default: none)
- Behavior: filter the dataset by the above, pick one random entry, return
  it as JSON shaped for the Liquid template (word, article/POS,
  translation, example sentence, related words).
- Response must be **flat JSON at the root level** (TRMNL's merge-variable
  access expects root-level fields as `##{{ field_name }}`; nested objects
  would need explicit dot-path syntax) — keep the shape flat to avoid that
  extra complexity in the template.
- Unrecognized/malformed params are ignored and fall back to defaults
  rather than erroring.

## Display / template

- **Layout: full screen.** The content (word + translation + example +
  related words) needs the space; a half/quadrant layout would cramp it.
- Flashcard style: German word large and centered, article/POS as a small
  badge, English translation below, example sentence, related words as a
  smaller secondary list.
- Built with TRMNL's Liquid templating and design-system CSS classes.

## Error handling

- Filtered set ends up empty (e.g. all words excluded) → Worker returns a
  friendly fallback card ("no words match your filters") instead of
  erroring.
- Dataset fails to load → Worker returns an HTTP error; TRMNL shows its own
  stale/error state on that poll; failure is logged.
- Enrichment: spot-check a sample of Claude's output before treating a
  batch as final; ambiguous existing entries are flagged, not silently
  overwritten.

## Testing

- Backend: unit tests for filter + random-selection logic (seeded random
  for determinism); manual checks hitting the deployed Worker URL with
  different query params.
- Template: use TRMNL's private-plugin preview/simulator to verify the
  flashcard layout before relying on the physical device.
- End-to-end: on the real device, confirm polling returns a new word and
  that Custom Fields settings actually filter what shows up.

## Future work (explicitly out of scope now)

- Progress tracking / spaced repetition, using Workers KV keyed by
  installation.
- Publishing as a public Marketplace plugin.
- Supporting datasets other than this specific German vocabulary list.
