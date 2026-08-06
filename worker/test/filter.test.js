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
