import json
from collections import defaultdict
from pathlib import Path

PREFIX_LENGTHS = (7, 6, 5)


def find_candidates(lemmas):
    lowered = [lemma.lower() for lemma in lemmas]
    by_prefix = defaultdict(set)
    for lemma in lowered:
        for n in PREFIX_LENGTHS:
            if len(lemma) >= n:
                by_prefix[lemma[:n]].add(lemma)

    candidates = {}
    for lemma in lowered:
        related = set()
        for n in PREFIX_LENGTHS:
            if len(lemma) >= n:
                related |= {other for other in by_prefix[lemma[:n]] if other != lemma}
        candidates[lemma] = sorted(related)
    return candidates


def run(parsed_path):
    entries = json.loads(Path(parsed_path).read_text())
    lemmas = [entry["lemma"] for entry in entries]
    candidates = find_candidates(lemmas)

    pairs = []
    for entry in entries:
        lemma = entry["lemma"]
        for candidate_lemma in candidates.get(lemma.lower(), []):
            pairs.append({"lemma": lemma, "candidate_lemma": candidate_lemma})
    return pairs


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent / "out"
    pairs = run(out_dir / "parsed.json")
    (out_dir / "candidates.json").write_text(json.dumps(pairs, ensure_ascii=False, indent=2))
    print(f"Found {len(pairs)} candidate pairs.")
