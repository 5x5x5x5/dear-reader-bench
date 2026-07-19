from pathlib import Path

import pytest

from dearreader_bench.rubric import (
    JUDGE_QUESTIONS,
    SOURCE_BLIND,
    WEIGHTS,
    no_self_judging,
    pairwise_prompt,
)
from dearreader_bench.schema import Dimension, Feature, load_segments
from dearreader_bench.speakability import (
    FORFEIT_RATIO,
    estimate_seconds,
    fill_ratio,
    is_forfeit,
    performability_score,
)

DATA = Path(__file__).parent.parent / "data" / "segments.json"


def test_corpus_loads_and_is_coherent():
    segments = load_segments(DATA)
    assert len(segments) >= 10
    for s in segments:
        assert s.seconds > 0 and s.text and s.scene
    wheel = [s for s in segments if s.gag_id == "the-wheel"]
    assert len(wheel) >= 3
    exercised = {f for s in segments for f in s.features}
    assert exercised == set(Feature)


def test_weights_sum_to_one_over_judged_dimensions():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9
    assert set(WEIGHTS) == set(Dimension)
    assert set(JUDGE_QUESTIONS) == set(Dimension)


def test_source_blind_split():
    # Humor and voice are audience-side; gags and fidelity are the tether.
    assert SOURCE_BLIND == {Dimension.VOICE, Dimension.HUMOR}


def test_pairwise_prompt_visibility_conditions():
    seg = load_segments(DATA)[0]
    blind = pairwise_prompt(seg, "ja", Dimension.HUMOR, "訳A", "訳B")
    assert seg.text not in blind  # source never shown for audience-side dimensions
    assert seg.scene in blind and "訳A" in blind and "訳B" in blind

    aware = pairwise_prompt(seg, "ja", Dimension.FIDELITY, "訳A", "訳B")
    assert seg.text in aware  # the tether: source shown for relation dimensions
    assert seg.scene in aware


def test_prompt_treats_candidates_as_untrusted():
    seg = load_segments(DATA)[0]
    prompt = pairwise_prompt(seg, "de", Dimension.VOICE, "A", "B")
    assert "untrusted" in prompt


def test_no_self_judging():
    assert no_self_judging("google/gemini-2.5-pro", "anthropic/claude-opus-4-8", "openai/gpt-5.4")
    assert not no_self_judging("anthropic/claude-sonnet-5", "anthropic/claude-opus-4-8")


# --- duration model -------------------------------------------------------


def test_estimate_seconds_scripts():
    latin = estimate_seconds("Behold the village of Gorganzola, a smear of chimneys.", "fr")
    assert 1.5 < latin < 6
    zh = estimate_seconds("看哪，戈尔贡佐拉村，一抹烟囱。", "zh")
    assert 2 < zh < 5
    ja = estimate_seconds("見よ、ゴルゴンゾーラの村を。", "ja")
    assert 1 < ja < 4
    ko = estimate_seconds("보라, 고르곤졸라 마을을.", "ko")
    assert 1 < ko < 4
    assert estimate_seconds("", "fr") == 0.0


def test_digits_and_acronyms_cost_duration():
    # Closed exploit: "2000" and "USSR" used to be duration-free.
    assert estimate_seconds("In 1987 the USSR", "en") > estimate_seconds("In the year", "en")
    assert estimate_seconds("2000", "en") > 0.5


def test_unvocalized_and_abugida_scripts_counted():
    # Closed exploit: Arabic/Hebrew/Devanagari collapsed to ~1 syllable per word.
    arabic = estimate_seconds("انظر إلى قرية غورغونزولا", "ar")
    assert arabic > 2.0
    hindi = estimate_seconds("गोर्गोन्ज़ोला गाँव को देखो", "hi")
    assert hindi > 1.5


def test_latin_inside_cjk_costs_duration():
    # Closed exploit: romaji salted into Japanese was invisible to the estimator.
    plain = estimate_seconds("見よ、村を。", "ja")
    salted = estimate_seconds("見よ、village of Gorganzola の村を。", "ja")
    assert salted > plain + 0.5


def test_punctuation_pauses_count():
    flat = estimate_seconds("the wheel hums and knows", "en")
    paused = estimate_seconds("The wheel hums. The wheel knows.", "en")
    assert paused > flat


def test_performability_shape():
    # Comfortably within window: fine.
    assert performability_score("Une phrase courte.", "fr", 10) == 1.0
    # Underrun is NOT penalized (dead air is a diagnostic; the source runs 54-89% fill).
    assert performability_score("Court.", "fr", 30) == 1.0
    assert fill_ratio("Court.", "fr", 30) < 0.2
    # No safe harbor above 1.10: penalty starts immediately.
    words_20s = "parole " * 90  # ~90 syllables ≈ 20s
    assert performability_score(words_20s, "fr", 15) < 1.0
    # Egregious overrun forfeits.
    assert is_forfeit("mot " * 400, "fr", 5)
    assert performability_score("mot " * 400, "fr", 5) == 0.0
    with pytest.raises(ValueError):
        performability_score("x", "fr", 0)


def test_source_segments_do_not_forfeit():
    # The English source performance must be eligible under its own gate.
    for s in load_segments(DATA):
        assert not is_forfeit(s.text, "en", s.seconds), s.id
        assert fill_ratio(s.text, "en", s.seconds) < FORFEIT_RATIO
