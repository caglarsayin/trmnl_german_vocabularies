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
    word: entry.article ? entry.word : entry.lemma,
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
