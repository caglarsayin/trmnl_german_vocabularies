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

## Approach

### Round 1 (during brainstorming): three full-screen options compared

Three genuinely different visual directions were mocked up (matching real
content, not lorem ipsum) and compared side-by-side:

- **A — Centered stack** (the original pre-redesign design): word,
  translation, example, grammar, related, all centered in one vertical
  column. Rejected: with this much content it reads as one undifferentiated
  block, no clear visual entry point.
- **B — Header + two-column body** (chosen initially): word gets a
  dedicated header row (left-aligned, level/POS badge to the right, divider
  beneath). Body splits into two columns: example (wider, left) and
  grammar+related (narrower, right).
- **C — Sidebar + main content**: a slim permanent left sidebar for
  level/POS/grammar, main area for word→translation→example. Not chosen —
  permanently reserves sidebar width even when grammar is absent (130-ish
  rows have no grammar block).

Option B shipped first (Tasks 1-5) and was pushed to the real TRMNL account.
Once viewed for real (both in TRMNL's own web editor preview and via
targeted live re-renders), two real problems emerged that hadn't shown up
in the earlier flat-mockup comparison: the two-column body left roughly
half the screen height empty for most real words (example/grammar content
rarely fills a 328px-tall column), and repeated attempts to fix visual
balance by tweaking individual font sizes weren't addressing the actual
structural issue.

### Round 2 (post-deployment, after seeing it live): Editorial Hero replaces Option B

A second mockup round compared three fresh directions against the deployed
Option B, this time informed by what had actually gone wrong:

- **Editorial Hero (chosen):** hero-sized word up top (level/POS as a
  small muted label above it), translation below, a divider, the example
  sentence given the full width and vertical space that remains, then —
  only when there's content for it — a single compact one-line reference
  strip at the very bottom combining grammar and related info (instead of
  a tall two-column sidebar).
- **Accent Band:** a shaded header band behind word+badge, content
  vertically centered as a group. Not chosen.
- **Stacked Focus:** everything centered as one flowing column, grammar
  detail dropped entirely to keep it minimal. Not chosen — loses
  information Option B had shown.

Editorial Hero fixes both real problems: the compact one-line footer
(instead of a sidebar) eliminates the dead space, and dropping the
two-column split means the example sentence gets the FULL screen width
instead of a fixed ~240px column, which incidentally also fixed a marginal
overflow risk on the longest real example sentences (a ~103-character
example that needed 4 tightly-wrapped lines in the 240px column now fits
in 2, at full width).

This is the current, shipped full-screen design. `half_horizontal.liquid`
and `half_vertical.liquid` use the same stacked pattern (badge, hero word,
translation, example — no grammar/related, no footer strip) they always
did; only `full.liquid` and the three `shared.liquid` partials changed for
this round.

### Content-priority order (confirmed across both rounds)

**Word + translation always shown; example next to drop; grammar +
related are the first two things cut** as space shrinks. This was checked
visually, not just asserted — at quadrant size in particular, keeping
example text present alongside word+translation produced visible
crowding, confirming those should drop together, not independently.

## File structure

```
plugin/
├── settings.yml            (unchanged from the working plugin)
├── shared.liquid            (new — reusable {% template %} partials)
├── full.liquid               (Option B, full detail)
├── half_horizontal.liquid    (stacked: full width, half height)
├── half_vertical.liquid      (side-by-side: half width, full height)
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

**Structural correction found mid-implementation (Task 1/2/3 fix round):**
none of the four size files should wrap their content in `<div class="screen ...">`/`<div class="view ...">` — `trmnlp`'s own dev server (and, by the same mechanism, the real TRMNL renderer) already supplies that wrapper around whatever a size file outputs, sizing it to the correct slot (full screen, or one grid cell of a `mashup--1Tx1B`/`mashup--1Lx1R`/`mashup--2x2` grid for the smaller sizes). Confirmed by running `trmnlp init` in a scratch directory and inspecting its generated scaffold, which starts every size file directly with `<div class="layout ...">` — no screen/view wrapper. Every size file we'd written through Task 3 included that wrapper redundantly; it happened to cause no visible symptom on `full` (the duplicate inner `.screen` renders at the same 800×480 dimensions the outer one already provides, so nothing clips), but on every smaller size it forced the content to lay out as if it had the full screen's width available, then get invisibly clipped down to the actual (narrower) grid-cell width by the outer wrapper's `overflow: hidden` — this was the real cause of text cutting off mid-word in the half sizes, not the `layout--center` vs `layout--stretch-x` choice (that was a real, separate, secondary bug, also fixed).

## Content per layout size

| Layout | Dimensions | Shows |
|---|---|---|
| `full` | 800×480 (OG) | hero word, level/POS badge (small, muted, above the word), translation, example (DE+EN), grammar+related (single compact line at the bottom, only when either has content) |
| `half_horizontal` | full width, half height (stacked) | word, level/POS badge, translation, example (DE+EN) |
| `half_vertical` | half width, full height (side-by-side) | word, level/POS badge, translation, example (DE+EN) |
| `quadrant` | quarter screen | word, translation only |

Both half sizes drop grammar and related entirely (confirmed via the
scale-down mockup). `half_horizontal.liquid` and `half_vertical.liquid`
are intentionally byte-identical — both use the same stacked (badge, word,
translation, example) pattern regardless of their real shape difference
(one is wide/short, the other narrow/tall); a centered vertical stack reads
fine in both, and TRMNL's own chrome (not this markup) is what actually
supplies the different `view--*` sizing per file.

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
