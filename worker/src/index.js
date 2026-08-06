import vocab from "./vocab.json" with { type: "json" };
import { filterVocab, parseExclude, parseLevels, pickRandom } from "./filter.js";
import { buildResponse } from "./response.js";

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const levels = parseLevels(url.searchParams.get("levels"));
    const exclude = parseExclude(url.searchParams.get("exclude"));

    const filtered = filterVocab(vocab, { levels, exclude });
    const entry = pickRandom(filtered);
    const body = buildResponse(entry);

    return new Response(JSON.stringify(body), {
      headers: { "content-type": "application/json" },
    });
  },
};
