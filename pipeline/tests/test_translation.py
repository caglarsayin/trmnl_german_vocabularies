import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.lib.translation import first_sense


def test_multi_sense_takes_first_only():
    ubersetzung = (
        "wahrscheinlich (Adverb): probably, likely, in all likelihood  "
        "wahrscheinlich (Adjektiv): probable, likely  "
        "das Wahrscheinliche (Noun): the probable (thing/concept)"
    )
    assert first_sense(ubersetzung) == "wahrscheinlich (Adverb): probably, likely, in all likelihood"


def test_single_sense_returns_whole_thing():
    assert first_sense("member (of an organization), participant") == "member (of an organization), participant"


def test_empty_input_returns_empty_string():
    assert first_sense("") == ""
