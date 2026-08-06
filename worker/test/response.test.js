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

test("buildResponse uses entry.word for a noun (has an article)", () => {
  const body = buildResponse({ ...ENTRY, article: "das", word: "das Mitglied", lemma: "Mitglied" });
  assert.equal(body.word, "das Mitglied");
});

test("buildResponse uses entry.lemma for a non-noun (no article)", () => {
  const body = buildResponse({ ...ENTRY, article: null, word: "Wahrscheinlich", lemma: "wahrscheinlich", pos: "Adjective" });
  assert.equal(body.word, "wahrscheinlich");
});
