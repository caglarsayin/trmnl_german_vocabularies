# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.lib.unicode_clean import clean


def test_strips_zero_width_non_joiner():
    assert clean("nearby‌ (next door)") == "nearby (next door)"


def test_strips_soft_and_nonbreaking_hyphen():
    assert clean("wieder­holen") == "wiederholen"
    assert clean("nicht‑öffentlich") == "nicht-öffentlich"


def test_normalizes_curly_quotes_and_dashes():
    assert clean("„Hallo“ – sagte er ’mal‘") == '"Hallo" - sagte er \'mal\''


def test_fixes_cyrillic_homoglyph():
    # U+0435 CYRILLIC SMALL LETTER IE looks identical to Latin 'e'
    contaminated = "spеrrt"
    assert clean(contaminated) == "sperrt"


def test_collapses_whitespace_and_strips():
    assert clean("  a   b  ") == "a b"


def test_handles_none():
    assert clean(None) == ""
