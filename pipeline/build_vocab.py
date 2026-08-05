import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.lib.schema import validate_entry


def merge(parsed, enrichment_result):
    by_lemma = {entry["lemma"]: dict(entry) for entry in parsed}
    for entry in by_lemma.values():
        entry["related"] = []
        entry["related_none"] = False

    for item in enrichment_result.get("validated", []):
        if not item.get("valid"):
            continue
        entry = by_lemma.get(item["lemma"])
        if entry is None:
            continue
        entry["related"].append({
            "word": item["candidate_lemma"],
            "relation": item["relation"],
            "source": "mechanical_validated",
        })

    for item in enrichment_result.get("generated", []):
        entry = by_lemma.get(item["lemma"])
        if entry is None:
            continue
        for link in item.get("related", []):
            entry["related"].append({
                "word": link["word"],
                "relation": link["relation"],
                "source": "generated",
            })
        if item.get("related_none"):
            entry["related_none"] = True

    return list(by_lemma.values())


def check_completeness(entries):
    failing = [e["id"] for e in entries if not e.get("related") and not e.get("related_none")]
    if failing:
        raise ValueError(
            f"{len(failing)} entries have neither related links nor related_none=true: {failing}"
        )


def run(parsed_path, result_path, out_path):
    parsed = json.loads(Path(parsed_path).read_text())
    result = json.loads(Path(result_path).read_text())

    merged = merge(parsed, result)
    check_completeness(merged)

    for entry in merged:
        problems = validate_entry(entry, require_related=True)
        if problems:
            raise ValueError(f"{entry['id']}: {problems}")

    Path(out_path).write_text(json.dumps(merged, ensure_ascii=False, indent=2))
    print(f"Wrote {len(merged)} entries to {out_path}")


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent / "out"
    run(out_dir / "parsed.json", out_dir / "enrichment_result.json", out_dir / "vocab.json")
