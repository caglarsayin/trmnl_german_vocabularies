# TRMNL Plugin Layout Redesign — Design

## Overview

Redesign the German vocabulary flashcard's visual layout (currently a single
centered-stack `full.liquid`) into a proper multi-size TRMNL plugin: a
better full-screen design, plus genuine support for the three smaller
mashup layout sizes (half two ways, quadrant), plus reasonable adaptation
across TRMNL device models. The Worker/backend and data pipeline are
unaffected — this is purely the `plugin/` presentation layer.

## Goals

- Replace the current full-screen layout with a clearer visual hierarchy
  (validated via mockup comparison — see Approach below).
- Build real `half_horizontal.liquid`, `half_vertical.liquid`, and
  `quadrant.liquid` layouts, not just `full.liquid`, so the plugin works
  correctly if placed in a mashup alongside other plugins.
- Share common markup across the four size files via `shared.liquid`
  rather than duplicating it four times.
- Apply TRMNL's device-width responsive classes (`sm:`/`md:`/`lg:`) as
  reasonable defaults for non-OG devices, without needing hardware that
  isn't owned to validate precisely.

## Non-goals (this iteration)

- Pixel-perfect verification on any device other than the OG (800×480) —
  other devices get sensible responsive defaults, explicitly flagged as
  unverified rather than tested.
- Changing the underlying data/response contract (`word`, `translation`,
  `example_de`/`example_en`, `grammar_text`, `related_text`, etc.) — this
  redesign only changes how those existing fields are arranged and which
  ones show at which size.
- Portrait-orientation-specific tuning beyond what the framework's
  `portrait:` prefix gives for free.

## Approach: three full-screen options compared, then validated for scale-down

Three genuinely different visual directions were mocked up (matching real
content, not lorem ipsum) and compared side-by-side:

- **A — Centered stack** (the current design): word, translation, example,
  grammar, related, all centered in one vertical column. Rejected: with
  this much content it reads as one undifferentiated block, no clear
  visual entry point.
- **B — Header + two-column body** (chosen): word gets a dedicated header
  row (left-aligned, level/POS badge to the right, divider beneath).
  Body splits into two columns: example (wider, left) and
  grammar+related (narrower, right). Uses the full screen width instead
  of wasting it on centered whitespace, and gives each category of
  information its own visual zone.
- **C — Sidebar + main content**: a slim permanent left sidebar for
  level/POS/grammar, main area for word→translation→example. Considered,
  not chosen — reads well but permanently reserves sidebar width even
  when grammar is absent for a given word (130-ish rows have no grammar
  block), wasting space more often than B does.

Once B was chosen for full-screen, its scale-down behavior across the three
smaller sizes was validated with the same real content, confirming a
content-priority order: **word + translation always shown; example next
to drop; grammar + related are the first two things cut** as space
shrinks. This was checked visually, not just asserted — at quadrant size
in particular, keeping example text present alongside word+translation
produced visible crowding, confirming those should drop together, not
independently.

## File structure

```
plugin/
├── settings.yml            (unchanged from the working plugin)
├── shared.liquid            (new — reusable {% template %} partials)
├── full.liquid               (Option B, full detail)
├── half_horizontal.liquid    (side-by-side: half width, full height)
├── half_vertical.liquid      (stacked: full width, half height)
└── quadrant.liquid           (quarter screen)
```

**Naming note, corrected against the authoritative source (the `trmnlp`
gem's own `Screen` definitions and the TRMNL framework's mashup CSS grid
rules — not a secondary example repo, which is what an earlier draft of
this spec relied on and got backwards):** `half_horizontal` means the
plugin is split from its mashup partner by a **horizontal** line — i.e.
**stacked, full width, half height** (`trmnlp`'s `HALF_HORIZONTAL` maps to
CSS class `mashup--1Tx1B`, "1 top × 1 bottom", each spanning the full grid
width). `half_vertical` means split by a **vertical** line — i.e.
**side-by-side, half width, full height** (`HALF_VERTICAL` maps to
`mashup--1Lx1R`, "1 left × 1 right", each spanning the full grid height).
This matches the more literal reading of the names (a "horizontal split"
cuts along a horizontal line) and was confirmed two ways: reading
`trmnlp`'s `lib/trmnlp/screen.rb` source directly, and rendering both
views against live data and visually inspecting the output shape.

`shared.liquid` defines `{% template %}` blocks for the pieces reused
across sizes — a header-badge partial (level/POS), an example-block
partial, and a grammar/related-block partial — and each size file
`{% render %}`s only the ones it has room for.

## Content per layout size

| Layout | Dimensions | Shows |
|---|---|---|
| `full` | 800×480 (OG) | word, article, level/POS badge, translation, example (DE+EN), grammar block, related words |
| `half_horizontal` | full width, half height (stacked) | word, level/POS badge, translation, example (DE+EN) |
| `half_vertical` | half width, full height (side-by-side) | word, level/POS badge, translation, example (DE+EN) |
| `quadrant` | quarter screen | word, translation only |

Both half sizes drop grammar and related entirely (confirmed via the
scale-down mockup) — the distinction between them is arrangement (stacked
badge above content vs. side-by-side) as space allows, not which fields
show.

## Device responsiveness

Primary target remains `screen--og` (the real, owned device) — every
layout is built and verified against it first via `trmnlp serve` with real
fixture data. On top of that baseline, `md:`/`lg:` breakpoint-prefixed
classes bump text size on the word/translation/example elements for wider
devices (`screen--v2` and similar), so the layout doesn't look
undersized on hardware not currently owned. This is explicitly a
best-effort default, not something verified on real hardware — call this
out rather than imply it was tested.

## Testing

- `trmnlp serve` locally against all four layout files, using the same
  real fixture data from `pipeline/fixtures/vocab.sample.json` (10
  entries, chosen originally to include outlier cases: the longest
  translation, an entry with no grammar block, an entry with a 4-item
  related list) — confirm no clipping/overlap at any of the four sizes.
- If `trmnlp`'s local preview supports switching device/size, spot-check
  the `md:`/`lg:` responsive classes visually; if it doesn't support that,
  say so explicitly rather than claim it was checked.
- Manual visual check on the real device for `full` (the layout actually
  in daily use) as the final confirmation, same as before.

## Error handling

Unchanged from the existing design: `grammar_text`/`related_text` being
empty strings (already handled via `{% if grammar_text != "" %}` /
`{% if related_text != "" %}` in the current template) continues to work
the same way in `shared.liquid`'s partials — an empty field means that
partial isn't rendered, at any size, rather than showing an empty
heading.
