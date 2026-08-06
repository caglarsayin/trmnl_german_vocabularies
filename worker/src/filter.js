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
