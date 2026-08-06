# TRMNL Plugin Layout Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single centered-stack `full.liquid` with a proper multi-size TRMNL plugin: a clearer full-screen layout (validated via mockup comparison), real `half_horizontal`/`half_vertical`/`quadrant` layouts, shared markup to avoid duplication, and device-responsive text sizing.

**Architecture:** One `shared.liquid` file defines reusable `{% template %}` partials (header badge, example block, grammar/related block); four size-specific `.liquid` files each `{% render %}` the partials they have room for. No backend/data changes — this only touches `plugin/`.

**Tech Stack:** TRMNL Liquid templating, TRMNL Design Framework CSS classes, `trmnlp` (Ruby gem, already installed from the prior plugin work) for local preview.

## Global Constraints

- Backend/data contract is unchanged: `word`, `article`, `pos`, `level`, `translation`, `example_de`, `example_en`, `grammar_text`, `related_text` are the only fields available (from `worker/src/response.js`'s `buildResponse()`), and they are already flat strings — no nested access needed.
- **CORRECTED mid-execution (Task 2), superseding the line below and the naming used in Tasks 2-3's headers:** `half_horizontal` = **stacked, full width, half height** (split by a horizontal line). `half_vertical` = **side-by-side, half width, full height** (split by a vertical line). Confirmed directly from `trmnlp`'s own `lib/trmnlp/screen.rb` (`HALF_HORIZONTAL` → CSS `mashup--1Tx1B`, "1 top × 1 bottom"; `HALF_VERTICAL` → `mashup--1Lx1R`, "1 left × 1 right") and the framework CSS's grid-row/grid-column rules for those classes, plus a live render. The line below (and Tasks 2/3's original headers/prose) has it backwards — file names below are still correct (`half_horizontal.liquid` really is the file TRMNL expects for the top/bottom slot), only the shape/arrangement description was wrong.
- ~~`half_horizontal` = side-by-side, **half width, full height**. `half_vertical` = stacked, **full width, half height**. This is verified against real TRMNL examples and is the opposite of what the names might suggest — do not swap these.~~ (superseded above)
- Content-priority order across sizes, confirmed via mockup: word + translation always shown; example next to drop; grammar + related are the first two things cut as space shrinks. `full` shows everything; `half_horizontal`/`half_vertical` show word+translation+example (no grammar/related); `quadrant` shows word+translation only.
- Primary verified target is `screen--og` (800×480) — that's the real device. `md:`/`lg:` responsive bumps are best-effort defaults for other devices, not verified on real hardware, and must be described as such.
- Empty `grammar_text`/`related_text` must omit that section entirely (no empty headings) — same rule as the existing template, applied inside the shared partial now instead of duplicated per size.

---

## File Structure

```
plugin/
├── settings.yml            (unchanged)
├── shared.liquid            # Task 1 — reusable partials
├── full.liquid               # Task 1 — Option B: header row + two-column body
├── half_horizontal.liquid    # Task 2 — stacked, full width/half height (corrected)
├── half_vertical.liquid      # Task 3 — side-by-side, half width/full height (corrected)
└── quadrant.liquid           # Task 4 — word + translation only
```

Fixture data for local verification throughout: `pipeline/fixtures/vocab.sample.json` (10 entries, already chosen to include outlier cases — the `ubersetzung` entry has the longest translation/example, `sofort` has a 4-item related list, `oben` has no grammar block).

---

### Task 1: `shared.liquid` partials + `full.liquid` (Option B)

**Files:**
- Create: `plugin/shared.liquid`
- Modify: `plugin/full.liquid` (replace entirely)

**Interfaces:**
- Produces: three `{% template %}` partials in `shared.liquid` — `header_badge` (params: `level`, `pos`), `example_block` (params: `example_de`, `example_en`), `grammar_related_block` (params: `grammar_text`, `related_text`). Tasks 2–4 render the same three partials with the same parameter names.

- [ ] **Step 1: Write `plugin/shared.liquid`**

```liquid
{% template header_badge %}
<div class="label">{{ level }} · {{ pos }}</div>
{% endtemplate %}

{% template example_block %}
<div class="value">{{ example_de }}</div>
<div class="description">{{ example_en }}</div>
{% endtemplate %}

{% template grammar_related_block %}
{% if grammar_text != "" %}
<div class="label">{{ grammar_text }}</div>
{% endif %}
{% if related_text != "" %}
<div class="description">Related: {{ related_text }}</div>
{% endif %}
{% endtemplate %}
```

**Important, verify this before trusting it further:** TRMNL's own documented example of `{% render %}` passes every variable a partial uses as an explicit named parameter (`{% render "say_hello", name: "General Kenobi" %}` for a partial that uses `{{ name }}`) — standard Liquid `render` is scope-isolated, unlike `include`. This plan assumes that model. Step 4 below is where you confirm it actually works that way in TRMNL's implementation specifically — if a partial renders blank/wrong when parameters are passed this way, that assumption is wrong and needs revisiting before Tasks 2–4 build on it.

- [ ] **Step 2: Write `plugin/full.liquid` (Option B — header row + two-column body)**

```liquid
<div class="screen screen--og">
  <div class="view view--full">
    <div class="layout" style="display:flex; flex-direction:column; height:100%; padding:24px 32px; box-sizing:border-box;">
      <div style="display:flex; justify-content:space-between; align-items:baseline; border-bottom:2px solid #000; padding-bottom:12px; margin-bottom:16px;">
        <div class="title">{{ word }}</div>
        {% render "header_badge", level: level, pos: pos %}
      </div>
      <div class="description" style="margin-bottom:16px;">{{ translation }}</div>
      <div style="flex:1; display:flex; gap:24px;">
        <div style="flex:1.4; border-right:1px solid #000; padding-right:24px;">
          <div class="label">Example</div>
          {% render "example_block", example_de: example_de, example_en: example_en %}
        </div>
        <div style="flex:1;">
          {% render "grammar_related_block", grammar_text: grammar_text, related_text: related_text %}
        </div>
      </div>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Install/confirm `trmnlp` is available**

Run: `gem list trmnl_preview` (should already be installed from the earlier plugin task). If not: `gem install trmnl_preview`.

- [ ] **Step 4: Preview locally and confirm the shared-partial mechanism actually works**

From `plugin/`, run `trmnlp serve`, open the local preview, and point it at the deployed Worker (`https://trmnl-german-vocab.caglar-dbd.workers.dev`) or a local fixture so real field values populate.

Expected: the header badge shows `{{ level }} · {{ pos }}` with real values (e.g. "A2 · Noun"), the example block shows both German and English lines, and the grammar/related block shows content when present. **If any `{% render %}`'d section is blank while the surrounding template's own `{{ word }}`/`{{ translation }}` fields populate correctly, the partials are not receiving their parameters** — in that case, try passing all outer-scope variables explicitly at every render call site (already done above) and confirm the parameter names inside `shared.liquid` exactly match what's passed. If it still doesn't work, that means TRMNL's `render` shares scope with the caller after all (unlike standard Liquid) — in that case simplify by removing the explicit parameters (`{% render "header_badge" %}` alone) and confirm the partial can see `level`/`pos` implicitly instead. Do not proceed to Task 2 until one of these two approaches is confirmed working, since Tasks 2–4 depend on it.

- [ ] **Step 5: Visual check against outlier fixture entries**

Using the local preview, cycle through entries and specifically check: the `ubersetzung` entry (longest translation and example) doesn't clip or overflow the two-column body; the `sofort` entry's 4-item related list doesn't overflow its column; the `oben` entry (no grammar block) shows no empty heading where the grammar/related block would be.

- [ ] **Step 6: Commit**

```bash
cd /Users/caglar.sayin/Workbench/trmnl_plugin
git add plugin/shared.liquid plugin/full.liquid
git commit -m "Redesign full.liquid: header row + two-column body, extract shared partials"
```

---

### Task 2: `half_horizontal.liquid` (CORRECTED shape: stacked, full width / half height — see Global Constraints correction note)

**Files:**
- Create: `plugin/half_horizontal.liquid`

**Interfaces:**
- Consumes: `header_badge`, `example_block` partials from `plugin/shared.liquid` (Task 1). Does **not** render `grammar_related_block` — grammar/related are dropped at this size per the Global Constraints content-priority order.

- [ ] **Step 1: Write `plugin/half_horizontal.liquid`**

Half width, full height — narrow and tall, so content stacks vertically (word, badge, translation, example), not side-by-side like `full.liquid`:

```liquid
<div class="screen screen--og">
  <div class="view view--half_horizontal">
    <div class="layout" style="display:flex; flex-direction:column; justify-content:center; height:100%; padding:16px 20px; box-sizing:border-box;">
      {% render "header_badge", level: level, pos: pos %}
      <div class="title" style="margin:6px 0;">{{ word }}</div>
      <div class="description" style="margin-bottom:12px;">{{ translation }}</div>
      <div class="label">Example</div>
      {% render "example_block", example_de: example_de, example_en: example_en %}
    </div>
  </div>
</div>
```

- [ ] **Step 2: Preview locally**

Run `trmnlp serve` from `plugin/`, switch the preview to the `half_horizontal` layout (trmnlp's local dev UI should offer a layout/size selector — if it doesn't expose one directly, check its documentation for how to preview a specific view file, since this is a real gap to resolve before treating this task as verified, not something to skip past).

- [ ] **Step 3: Visual check against outlier fixture entries**

Same outlier entries as Task 1 (`ubersetzung`, `sofort`, `oben`) — confirm the translation/example text doesn't overflow the narrower box, and that no grammar/related content appears (it shouldn't be rendered at all at this size).

- [ ] **Step 4: Commit**

```bash
cd /Users/caglar.sayin/Workbench/trmnl_plugin
git add plugin/half_horizontal.liquid
git commit -m "Add half_horizontal layout: stacked word/badge/translation/example"
```

---

### Task 3: `half_vertical.liquid` (CORRECTED shape: side-by-side, half width / full height — narrow and tall, see Global Constraints correction note)

**Files:**
- Create: `plugin/half_vertical.liquid`

**Interfaces:**
- Consumes: `header_badge`, `example_block` partials from `plugin/shared.liquid` (Task 1). Same content set as Task 2 (word, badge, translation, example — no grammar/related). Same stacked/centered arrangement as Task 2 as well — this box is narrow and tall (half width, full height), which a centered vertical stack suits well (this is the pattern Task 2 already built and visually confirmed working, not the header-row pattern originally drafted here before the shape correction).

- [ ] **Step 1: Write `plugin/half_vertical.liquid`**

Half width, full height — narrow and tall. Use the same `layout--col layout--center` stacked pattern as `half_horizontal.liquid` (Task 2), only the `view--*` class differs:

```liquid
<div class="screen screen--og">
  <div class="view view--half_vertical">
    <div class="layout layout--col layout--center gap--small">
      {% render "header_badge", level: level, pos: pos %}
      <div class="title">{{ word }}</div>
      <div class="description">{{ translation }}</div>
      <div class="label">Example</div>
      {% render "example_block", example_de: example_de, example_en: example_en %}
    </div>
  </div>
</div>
```

- [ ] **Step 2: Render and visually verify**

Use the same `trmnlp build --png` verification approach used for Tasks 1-2 (see their reports/ledger entries for the exact harness setup) — do not attempt `trmnlp serve` and manual browser interaction, static file rendering is sufficient and has proven reliable.

- [ ] **Step 3: Visual check across sampled words**

Render several times against the live backend (it returns a random word each call) and confirm: word/badge/translation/example all fit without clipping in the narrower (half-width) box, and no grammar/related content appears.

- [ ] **Step 4: Commit**

```bash
cd /Users/caglar.sayin/Workbench/trmnl_plugin
git add plugin/half_vertical.liquid
git commit -m "Add half_vertical layout: header row + translation/example, no grammar/related"
```

---

### Task 4: `quadrant.liquid` (word + translation only)

**Files:**
- Create: `plugin/quadrant.liquid`

**Interfaces:**
- Consumes: nothing from `shared.liquid` — at quadrant size, per the confirmed content-priority order, only `word` and `translation` show; no partials are needed since there's no badge/example/grammar/related at this size.

- [ ] **Step 1: Write `plugin/quadrant.liquid`**

```liquid
<div class="screen screen--og">
  <div class="view view--quadrant">
    <div class="layout" style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; text-align:center; padding:10px; box-sizing:border-box;">
      <div class="title">{{ word }}</div>
      <div class="description">{{ translation }}</div>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Preview locally**

Run `trmnlp serve`, switch to the `quadrant` layout view.

- [ ] **Step 3: Visual check against outlier fixture entries**

Confirm the `ubersetzung` entry's long translation doesn't overflow this smallest box (may need to rely on the Worker's existing 120-char truncation — if it still looks cramped, note this as a finding rather than silently accepting overflow).

- [ ] **Step 4: Commit**

```bash
cd /Users/caglar.sayin/Workbench/trmnl_plugin
git add plugin/quadrant.liquid
git commit -m "Add quadrant layout: word and translation only"
```

---

### Task 5: Device-responsive sizing + full cross-size regression check

**Files:**
- Modify: `plugin/full.liquid`, `plugin/half_horizontal.liquid`, `plugin/half_vertical.liquid` (add responsive classes to text elements)

**Interfaces:** none — this task only adds CSS class modifiers to existing markup, no new partials or parameters.

- [ ] **Step 1: Verify the actual responsive modifier class names before using them**

Fetch `https://trmnl.com/framework/docs/v2/responsive` (or the local framework docs if `trmnlp` bundles them) and confirm which typography classes have documented `md:`/`lg:` modifiers. One confirmed example from that page: `<span class="value md:value--large lg:value--xlarge">`. Check specifically whether `.title` has equivalent `--large`/`--xlarge` (or similarly named) modifiers documented. **Do not invent a modifier class name that isn't documented** — if `.title` has no documented size modifier, leave its size as-is at this pass and note that in your report rather than guessing.

- [ ] **Step 2: Apply confirmed responsive classes**

Using only what Step 1 confirmed, add `md:`/`lg:`-prefixed modifier classes to the `.value`/`.description` elements (translation, example) in `full.liquid`, `half_horizontal.liquid`, and `half_vertical.liquid` — e.g., if Step 1 confirms `value md:value--large lg:value--xlarge` is valid, apply that pattern to the `.value`-classed example text in each file. Leave `.title` (the word) at its current explicit inline size unless Step 1 found a confirmed modifier for it too.

- [ ] **Step 3: Full cross-size regression check**

Using `trmnlp serve`, cycle through all four layout views (`full`, `half_horizontal`, `half_vertical`, `quadrant`) with the full outlier set (`ubersetzung`, `sofort`, `oben`, plus at least 3 other fixture entries picked arbitrarily) and confirm nothing clips or overflows at any size. This is the final visual gate before pushing to the real account.

- [ ] **Step 4: Commit**

```bash
cd /Users/caglar.sayin/Workbench/trmnl_plugin
git add plugin/full.liquid plugin/half_horizontal.liquid plugin/half_vertical.liquid
git commit -m "Add device-responsive text sizing using confirmed framework modifier classes"
```

---

### Task 6: Push to the real TRMNL account and confirm on device (human-required)

**This task needs the user's real TRMNL account and physical device — it cannot be completed by an agent alone.**

**Files:** none — this is deployment/verification, not code.

- [ ] **Step 1: Push the updated plugin**

From `plugin/`: `trmnlp login` (if not already authenticated from earlier work), then `trmnlp push`. This updates the existing private plugin (created during the original project) with the new `shared.liquid` and four layout files.

- [ ] **Step 2: Confirm on the physical device (full layout)**

Wait for the configured refresh interval or trigger a manual refresh. Confirm the new header-row-plus-two-column layout renders correctly — no clipping, grammar/related shown when present and absent when not.

- [ ] **Step 3: Confirm the smaller layouts, if a mashup is set up**

If/when this plugin is placed into a mashup slot (half or quadrant), confirm the corresponding layout renders as designed — this may happen later than Step 2 if no mashup is configured yet; note that explicitly rather than claiming it was checked if it wasn't.

- [ ] **Step 4: Commit** (only if any last-minute fixes were needed during device verification; otherwise this task has no commit of its own)

## Self-Review Notes

- **Spec coverage:** Option B full-screen design (Task 1), all three smaller layout sizes with the confirmed `half_horizontal`/`half_vertical` naming (Tasks 2–4), shared partials to avoid duplication (Task 1, consumed by Tasks 2–3), device-responsive sizing scoped to what's actually confirmed rather than invented (Task 5), real-account push and device confirmation (Task 6, explicitly human-gated).
- **Placeholder scan:** no TBD/TODO. The one open technical uncertainty (whether `{% render %}` is scope-isolated or scope-sharing in TRMNL's Liquid) has a concrete two-branch resolution procedure in Task 1 Step 4, not a guess presented as fact — matching how the original plugin plan handled the `{{ }}` vs `##{{ }}` merge-variable uncertainty.
- **Type/name consistency:** the three partial names (`header_badge`, `example_block`, `grammar_related_block`) and their parameter names (`level`, `pos`, `example_de`, `example_en`, `grammar_text`, `related_text`) are identical across Task 1's definition and every `{% render %}` call site in Tasks 2–4.
