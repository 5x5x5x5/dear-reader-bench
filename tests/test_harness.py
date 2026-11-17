"""The runner, judge and leaderboard, end to end on mock models with a known right answer."""

from pathlib import Path

import pytest

from dearreader_bench import judge, runner
from dearreader_bench.brief import adaptation_prompt
from dearreader_bench.providers import complete, extract_json
from dearreader_bench.schema import Dimension, PairwiseJudgment, load_corpus

ROOT = Path(__file__).parent.parent
CORPUS = load_corpus(ROOT / "data" / "season2.json")
# Two "families" of judge that prefer the longer text and one contrarian.
JUDGES = ["mockjudge-a/longer", "mockjudge-b/longer", "mockjudge-c/shorter"]


def test_extract_json_tolerates_fences_and_prose():
    assert extract_json('Sure!\n```json\n{"winner": "a"}\n```\nDone.') == {
        "winner": "a"
    }
    with pytest.raises(ValueError):
        extract_json("no object here")


def test_real_models_need_a_key(monkeypatch):
    monkeypatch.delenv("DRB_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        complete("acme/model-1", "hello")


def test_rewrite_anchor_never_sees_the_source():
    prompt = adaptation_prompt(CORPUS, "fr", "rewrite")
    assert CORPUS.segments[0].text not in prompt and CORPUS.segments[0].scene in prompt
    assert "Do not adapt" in adaptation_prompt(CORPUS, "fr", "literal")


def test_runner_rejects_a_broken_script(monkeypatch):
    monkeypatch.setattr(
        runner, "complete", lambda *a, **k: '{"bible": {}, "segments": []}'
    )
    with pytest.raises(ValueError, match="not scoreable"):
        runner.translate("acme/model-1", "fr", CORPUS)


def test_orders_that_disagree_fold_to_a_tie():
    def verdict(order, winner):
        return PairwiseJudgment(
            segment_id="s2-001",
            language="fr",
            dimension=Dimension.HUMOR,
            system_a="x/a",
            system_b="x/b",
            judge="j/1",
            order=order,
            winner=winner,
        )

    assert judge.fold([verdict(0, "a"), verdict(1, "b")], {}, CORPUS)[0][4] == "tie"
    assert judge.fold([verdict(0, "a"), verdict(1, "a")], {}, CORPUS)[0][4] == "a"


def test_end_to_end_on_mock_models(tmp_path, monkeypatch):
    subs, out = tmp_path / "submissions", tmp_path / "results"
    for model in ("mock/echo", "mock/terse", "mock/padded"):
        assert runner.main([model, "fr", "--out", str(subs)]) == 0
    assert (
        runner.main(["mock/echo", "fr", "--anchor", "rewrite", "--out", str(subs)]) == 0
    )
    args = ["fr", "--judges", *JUDGES, "--submissions", str(subs), "--out", str(out)]

    assert judge.main([*args, "--replicates", "20"]) == 0
    rows = {
        r["system"]: r
        for r in judge.json.loads((out / "fr" / "leaderboard.json").read_text())
    }

    # Two of three judges prefer longer text, so the full script beats its first sentences.
    assert rows["mock/echo"]["humor"] > rows["mock/terse"]["humor"]
    assert rows["mock/echo"]["drs"] > rows["mock/terse"]["drs"]
    # Doubling every segment overruns every window: P is zero and so is the score.
    assert rows["mock/padded"]["p"] == 0.0 and rows["mock/padded"]["drs"] == 0.0
    assert rows["mock/echo"]["tier"] == 1 and rows["mock/padded"]["tier"] > 1
    assert all(
        r["lo"] <= r["drs"] + 1e-9 and r["drs"] <= r["hi"] + 1e-9 for r in rows.values()
    )
    assert "MOCK RUN" in (out / "fr" / "leaderboard.md").read_text()
    lock = judge.json.loads((out / "fr" / "run.lock").read_text())
    assert lock["corpus"] == "pastiche-s2" and len(lock["systems"]) == 4

    # A second run is served from the cache: no model is called at all.
    def refuse(*a, **k):
        raise AssertionError("cache miss")

    monkeypatch.setattr(judge, "complete", refuse)
    assert judge.main([*args, "--replicates", "2"]) == 0
