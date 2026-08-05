import json
from collections import defaultdict
from pathlib import Path


def run(parsed_path, candidates_path, review_path):
    entries = json.loads(Path(parsed_path).read_text())
    pairs = json.loads(Path(candidates_path).read_text())
    review = json.loads(Path(review_path).read_text())

    has_candidate = {p["lemma"] for p in pairs}
    words_needing_generation = [
        {"lemma": e["lemma"], "translation": e["translation"], "pos": e["pos"]}
        for e in entries
        if e["lemma"] not in has_candidate
    ]

    return {
        "pairs": pairs,
        "wordsNeedingGeneration": words_needing_generation,
        "allLemmas": sorted({e["lemma"] for e in entries}),
        "needsReview": review,
    }


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent / "out"
    args = run(out_dir / "parsed.json", out_dir / "candidates.json", out_dir / "needs_review.json")
    (out_dir / "enrichment_args.json").write_text(json.dumps(args, ensure_ascii=False, indent=2))
    print(
        f"{len(args['pairs'])} pairs to validate, "
        f"{len(args['wordsNeedingGeneration'])} words needing generation, "
        f"{len(args['needsReview'])} needs-review items."
    )
