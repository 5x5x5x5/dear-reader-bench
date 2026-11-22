"""Tests for the static site generator (canary safety, honesty gate, assets)."""

from __future__ import annotations

import json
from pathlib import Path

from dearreader_bench.schema import load_corpus
from dearreader_bench.sitegen import build_site

ROOT = Path(__file__).parent.parent
CORPUS_PATH = ROOT / "data" / "season2.json"
CORPUS = load_corpus(CORPUS_PATH)
CANARY_GUID = CORPUS.canary.rsplit(":", 1)[-1]


def test_default_site_build_is_canary_free_and_withholds_unvalidated_scores(tmp_path):
    out = tmp_path / "site"
    index = build_site(out_dir=out, corpus_path=CORPUS_PATH)

    assert index == out / "index.html"
    for name in ("index.html", "styles.css", "app.js", "data.json"):
        assert (out / name).exists(), name
        content = (out / name).read_text(encoding="utf-8")
        # Corpus canary GUID must never appear in any published site artifact.
        assert CANARY_GUID not in content, f"canary leaked into {name}"

    html = index.read_text(encoding="utf-8")
    assert "dear-reader-bench" in html
    assert "The Screening Room" in html
    assert "The Bible Wall" in html
    assert "UNVALIDATED PREVIEW" not in html

    data = json.loads((out / "data.json").read_text(encoding="utf-8"))
    assert data["meta"]["segment_count"] == len(CORPUS.segments)
    assert data["meta"]["gag_chain_count"] == len(CORPUS.gags)
    assert data["meta"]["joke_card_count"] == 71
    assert len(data["submissions"]) >= 8
    assert data["unvalidated_preview"] is None


def test_opt_in_unvalidated_preview_is_quarantined_with_warning(tmp_path):
    fake_results = tmp_path / "results" / "ja"
    fake_results.mkdir(parents=True)
    (fake_results / "leaderboard.json").write_text(
        json.dumps(
            [
                {
                    "tier": 1,
                    "system": "acme/demo",
                    "drs": 0.612,
                    "lo": 0.550,
                    "hi": 0.670,
                    "p": 1.0,
                    "humor": 0.65,
                    "voice": 0.60,
                    "gags": 0.58,
                    "fidelity": 0.61,
                }
            ]
        ),
        encoding="utf-8",
    )
    out = tmp_path / "site"
    index = build_site(
        out_dir=out,
        corpus_path=CORPUS_PATH,
        results_dir=tmp_path / "results",
        include_unvalidated_preview=True,
    )
    html = index.read_text(encoding="utf-8")
    assert "UNVALIDATED PREVIEW" in html
    assert "acme/demo" in html
    assert CANARY_GUID not in html
