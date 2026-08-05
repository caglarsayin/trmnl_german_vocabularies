import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.match_candidates import find_candidates, run


def test_finds_shared_prefix_siblings():
    lemmas = ["ärgern", "ärgerlich", "Katze"]
    candidates = find_candidates(lemmas)
    assert "ärgerlich" in candidates["ärgern"]
    assert "ärgern" in candidates["ärgerlich"]
    assert candidates.get("katze", []) == []


def test_short_lemmas_below_prefix_length_get_no_candidates():
    lemmas = ["zu", "an"]
    candidates = find_candidates(lemmas)
    assert candidates.get("zu", []) == []
    assert candidates.get("an", []) == []


def test_run_reads_parsed_json_and_flattens_to_pairs(tmp_path):
    parsed = [
        {"id": "argern", "lemma": "ärgern", "level": "B1"},
        {"id": "argerlich", "lemma": "ärgerlich", "level": "B1"},
        {"id": "katze", "lemma": "Katze", "level": "A1"},
    ]
    parsed_path = tmp_path / "parsed.json"
    parsed_path.write_text(json.dumps(parsed))

    pairs = run(parsed_path)
    pair_set = {(p["lemma"], p["candidate_lemma"]) for p in pairs}
    assert ("ärgern", "ärgerlich") in pair_set
    assert ("ärgerlich", "ärgern") in pair_set
    assert not any(p["lemma"] == "Katze" for p in pairs)
