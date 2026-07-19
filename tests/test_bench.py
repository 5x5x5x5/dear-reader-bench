from pathlib import Path

import pytest

from dearreader_bench.rubric import JUDGE_QUESTIONS, WEIGHTS, no_self_judging, pairwise_prompt
from dearreader_bench.schema import Dimension, Feature, load_segments
from dearreader_bench.speakability import estimate_seconds, performability_score

DATA = Path(__file__).parent.parent / "data" / "segments.json"


def test_corpus_loads_and_is_coherent():
    segments = load_segments(DATA)
    assert len(segments) >= 10
    for s in segments:
        assert s.seconds > 0 and s.text and s.scene
    # Running gags span multiple segments
    wheel = [s for s in segments if s.gag_id == "the-wheel"]
    assert len(wheel) >= 3
    # Every feature category is exercised somewhere
    exercised = {f for s in segments for f in s.features}
    assert exercised == set(Feature)


def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9
    assert set(WEIGHTS) == set(Dimension)


def test_judged_dimensions_have_questions():
    judged = set(Dimension) - {Dimension.PERFORMABILITY}
    assert set(JUDGE_QUESTIONS) == judged


def test_pairwise_prompt_contents():
    seg = load_segments(DATA)[0]
    prompt = pairwise_prompt(seg, "ja", Dimension.HUMOR, "訳A", "訳B")
    assert seg.text in prompt and "訳A" in prompt and "訳B" in prompt
    assert "ja" in prompt
    with pytest.raises(ValueError):
        pairwise_prompt(seg, "ja", Dimension.PERFORMABILITY, "a", "b")


def test_no_self_judging():
    assert no_self_judging("google/gemini-2.5-pro", "anthropic/claude-opus-4-8", "openai/gpt-5.4")
    assert not no_self_judging("anthropic/claude-sonnet-5", "anthropic/claude-opus-4-8")


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


def test_performability_score_shape():
    # Comfortably within window
    assert performability_score("Une phrase courte.", "fr", 10) == 1.0
    # Massive overrun scores 0
    assert performability_score("mot " * 400, "fr", 5) == 0.0
    # Between: monotonic penalty
    mid = performability_score("mot " * 40, "fr", 8)
    assert 0.0 < mid < 1.0
    with pytest.raises(ValueError):
        performability_score("x", "fr", 0)
