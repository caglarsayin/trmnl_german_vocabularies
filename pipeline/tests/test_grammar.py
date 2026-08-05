import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.lib.grammar import parse_grammar


def test_noun_forms():
    detail = "member (of an organization), participant, member🔢 Noun FormsSingular (Einzahl): das MitgliedPlural (Mehrzahl): Mitglieder"
    result = parse_grammar(detail)
    assert result == {
        "type": "noun_forms",
        "lines": ["Singular: das Mitglied", "Plural: Mitglieder"],
    }


def test_verb_conjugations_extracts_partizip_and_regularity():
    detail = (
        "blitzen (Verb): to flash (lightning), to gleam  das Blitzen (Noun): flashing, flash (of light)"
        "🔄 Verb Conjugationsregelmäßig Partizip II: geblitztPresent (Präsens):ich: blitzedu: blitzt"
        "er/sie/es: blitztwir: blitzenihr: blitztsie: blitzenPast (Präteritum):ich: blitztedu: blitztest"
        "er/sie/es: blitztewir: blitztenihr: blitztetsie: blitzten"
    )
    result = parse_grammar(detail)
    assert result == {"type": "verb_conjugations", "lines": ["Partizip II: geblitzt (regelmäßig)"]}


def test_verb_conjugations_unregelmaessig():
    detail = (
        "das Überweisen (Noun): the transfer"
        "🔄 Verb Conjugationsunregelmäßig Partizip II: überwiesenPresent (Präsens):ich: überweise"
    )
    result = parse_grammar(detail)
    assert result == {"type": "verb_conjugations", "lines": ["Partizip II: überwiesen (unregelmäßig)"]}


def test_verb_with_no_partizip_returns_none():
    # Real case: "möchten" (modal verb) -- no "Partizip II:" in its section at all.
    detail = "🔄 Verb Conjugationsunregelmäßig Present (Präsens):ich: möchtedu: möchtest"
    result = parse_grammar(detail)
    assert result is None


def test_degrees_of_comparison():
    detail = (
        "leer (Adjektiv): empty, vacant, blank, void  das Leer (Noun): the empty (quality/state)"
        "📊 Degrees of ComparisonPositive: leerComparative: leererSuperlative: am leersten"
    )
    result = parse_grammar(detail)
    assert result == {
        "type": "degrees_of_comparison",
        "lines": ["Comparative: leerer", "Superlative: am leersten"],
    }


def test_degrees_of_comparison_positive_only_returns_none():
    # Real case: "wohin" -- doesn't inflect for comparison in German.
    detail = "wohin (Adverb): where to, to what place📊 Degrees of ComparisonPositive: wohin"
    result = parse_grammar(detail)
    assert result is None


def test_no_marker_returns_none():
    assert parse_grammar("oben (Adverb): above, upstairs, at the top") is None


def test_none_input_returns_none():
    assert parse_grammar(None) is None
