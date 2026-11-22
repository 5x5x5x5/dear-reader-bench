"""Static site generator for dear-reader-bench.5x5x5x5.dev.

Builds a self-contained static site into `site/` from the public corpus,
Joke Cards, and committed submissions (never leaking the corpus canary GUID,
and never publishing unvalidated judged numbers by default per CLAUDE.md and
DESIGN.md §6).

Usage:
    uv run build_site.py
    python -m dearreader_bench.sitegen --out site
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import shutil
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from .brief import HARNESS_VERSION, LANGUAGES
from .layer2 import gag_ledger_deterministic, load_joke_cards
from .rubric import WEIGHTS
from .schema import AdaptationResult, Corpus, Dimension, load_corpus
from .speakability import (
    FORFEIT_RATIO,
    PENALTY_START_RATIO,
    estimate_seconds,
    fill_ratio,
)
from .submission import DEFAULT_CORPUS, check_submission, performability

log = logging.getLogger(__name__)

REPO_URL = "https://github.com/5x5x5x5/dear-reader-bench"
ASSETS_DIR = Path(__file__).parent / "site_assets"


def _safe_inline_json(obj: Any) -> str:
    """Serialize JSON safe to embed inside a <script type="application/json"> tag."""
    return (
        json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def _load_submissions(
    submissions_dir: Path, corpus: Corpus, language: str = "ja"
) -> list[AdaptationResult]:
    out: list[AdaptationResult] = []
    if not submissions_dir.exists():
        return out
    for path in sorted(submissions_dir.glob(f"*/{language}.json")):
        res = AdaptationResult.model_validate_json(path.read_text(encoding="utf-8"))
        if not check_submission(res, corpus):
            out.append(res)
    return out


def collect_site_data(
    *,
    corpus_path: Path,
    cards_path: Path,
    submissions_dir: Path,
    language: str = "ja",
    results_dir: Path | None = None,
    include_unvalidated_preview: bool = False,
) -> dict[str, Any]:
    """Assemble public, canary-free site data from repo artifacts."""
    corpus = load_corpus(corpus_path)
    cards = load_joke_cards(cards_path)
    subs = _load_submissions(submissions_dir, corpus, language=language)

    windows = {s.id: s.seconds for s in corpus.segments}
    src_fills = [fill_ratio(s.text, "en", s.seconds) for s in corpus.segments]
    total_seconds = sum(s.seconds for s in corpus.segments)

    segments_data = [
        {
            "id": s.id,
            "seconds": s.seconds,
            "text": s.text,
            "scene": s.scene,
            "features": [f.value for f in s.features],
            "gag_id": s.gag_id,
            "source_fill_ratio": round(fill_ratio(s.text, "en", s.seconds), 3),
        }
        for s in corpus.segments
    ]
    cards_data = [
        {
            "joke_id": c.joke_id,
            "segment_id": c.segment_id,
            "setup_span": c.setup_span,
            "punchline_span": c.punchline_span,
            "mechanism": c.mechanism.value,
            "script_opposition": list(c.script_opposition),
            "portable": c.portable,
            "gag_id": c.gag_id,
        }
        for c in cards
    ]

    submissions_data: list[dict[str, Any]] = []
    for sub in subs:
        p_score, forfeits = performability(sub, corpus)
        ledger = gag_ledger_deterministic(sub, corpus)
        fills = [
            fill_ratio(s.text, sub.language, windows[s.segment_id])
            for s in sub.segments
        ]
        submissions_data.append(
            {
                "system": sub.system,
                "language": sub.language,
                "role": (
                    "literal"
                    if sub.system.endswith("+literal")
                    else ("rewrite" if sub.system.endswith("+rewrite") else "system")
                ),
                "bible": sub.bible.model_dump(mode="json"),
                "measured": {
                    "performability": round(p_score, 4),
                    "forfeits": len(forfeits),
                    "fill_min": round(min(fills), 3),
                    "fill_median": round(statistics.median(fills), 3),
                    "fill_max": round(max(fills), 3),
                    "name_consistency": round(ledger["name_consistency"], 4),
                    "gag_consistency": round(ledger["gag_consistency"], 4),
                    "overall_consistency": round(ledger["overall_consistency"], 4),
                    "inflected_matches": ledger["inflected_matches"],
                    "missed_count": ledger["missed_count"],
                    "arc_recurrence_rate": round(ledger["arc_recurrence_rate"], 4),
                    "vacuous_count": len(ledger["vacuous_entries"]),
                },
                "segments": {
                    s.segment_id: {
                        "text": s.text,
                        "est_seconds": round(estimate_seconds(s.text, sub.language), 2),
                        "fill_ratio": round(
                            fill_ratio(s.text, sub.language, windows[s.segment_id]), 3
                        ),
                    }
                    for s in sub.segments
                },
            }
        )

    feature_counts = Counter(f.value for s in corpus.segments for f in s.features)
    mech_counts = Counter(c.mechanism.value for c in cards)

    payload: dict[str, Any] = {
        "meta": {
            "corpus": corpus.corpus,
            "harness_version": HARNESS_VERSION,
            "language": language,
            "language_name": LANGUAGES[language],
            "slate": LANGUAGES,
            "segment_count": len(corpus.segments),
            "gag_chain_count": len(corpus.gags),
            "joke_card_count": len(cards),
            "non_portable_count": sum(1 for c in cards if not c.portable),
            "total_seconds": total_seconds,
            "source_fill": {
                "min": round(min(src_fills), 3),
                "median": round(statistics.median(src_fills), 3),
                "max": round(max(src_fills), 3),
            },
            "feature_counts": dict(feature_counts.most_common()),
            "mechanism_counts": dict(mech_counts.most_common()),
        },
        "corpus": {
            "names": list(corpus.names),
            "gags": dict(corpus.gags),
        },
        "segments": segments_data,
        "cards": cards_data,
        "submissions": submissions_data,
        "unvalidated_preview": None,
    }

    # Opt-in local preview only: never included in default public builds (CLAUDE.md rule).
    if include_unvalidated_preview and results_dir is not None:
        lang_dir = results_dir / language
        lb_path = lang_dir / "leaderboard.json"
        audit_path = lang_dir / "audit.json"
        if lb_path.exists():
            payload["unvalidated_preview"] = {
                "leaderboard": json.loads(lb_path.read_text(encoding="utf-8")),
                "audit": (
                    json.loads(audit_path.read_text(encoding="utf-8"))
                    if audit_path.exists()
                    else None
                ),
            }

    return payload


def _render_performability_svg(data: dict[str, Any]) -> str:
    """Render an SVG showing the 1.10x->1.50x performability curve + real fill ranges."""
    w, h = 640, 290
    left, right, top, bottom = 52, 616, 24, 210
    x_max = 1.65

    def sx(ratio: float) -> float:
        return left + (min(ratio, x_max) / x_max) * (right - left)

    def sy(score: float) -> float:
        return bottom - score * (bottom - top)

    # Curve points: (0, 1) -> (1.10, 1) -> (1.50, 0) -> (1.65, 0)
    pts = [
        (0.0, 1.0),
        (PENALTY_START_RATIO, 1.0),
        (FORFEIT_RATIO, 0.0),
        (x_max, 0.0),
    ]
    poly = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in pts)
    area = f"{sx(0):.1f},{sy(0):.1f} " + poly + f" {sx(x_max):.1f},{sy(0):.1f}"

    # Plot source + submission median/range whiskers neatly below the curve axis.
    entries = [
        (
            "English source",
            data["meta"]["source_fill"]["min"],
            data["meta"]["source_fill"]["median"],
            data["meta"]["source_fill"]["max"],
            "var(--brass)",
        )
    ] + [
        (
            sub["system"].split("/")[-1].replace(":free", ""),
            sub["measured"]["fill_min"],
            sub["measured"]["fill_median"],
            sub["measured"]["fill_max"],
            "var(--vermilion)" if sub["role"] != "system" else "var(--emerald)",
        )
        for sub in data["submissions"][:6]
    ]

    whiskers: list[str] = []
    for idx, (label, lo, med, hi, color) in enumerate(entries):
        y = 224 + idx * 9
        if y > h - 6:
            break
        whiskers.append(
            f'<line x1="{sx(lo):.1f}" y1="{y}" x2="{sx(hi):.1f}" y2="{y}" '
            f'stroke="{color}" stroke-width="2" stroke-opacity="0.7" />'
            f'<circle cx="{sx(med):.1f}" cy="{y}" r="3.2" fill="{color}">'
            f"<title>{html.escape(label)}: min {lo:.2f}x, median {med:.2f}x, max {hi:.2f}x</title>"
            f"</circle>"
        )

    ticks = [0.0, 0.5, 1.0, 1.1, 1.5]
    tick_svg = "".join(
        f'<line x1="{sx(t):.1f}" y1="{top}" x2="{sx(t):.1f}" y2="{bottom}" '
        f'stroke="var(--border)" stroke-dasharray="3 4" />'
        f'<text x="{sx(t):.1f}" y="{bottom + 14}" text-anchor="middle" '
        f'fill="var(--ink-muted)" font-family="var(--font-mono)" font-size="10">{t:.1f}×</text>'
        for t in ticks
    )

    return f"""
    <svg viewBox="0 0 {w} {h}" role="img" aria-label="Performability score curve and system fill ratios">
      <defs>
        <linearGradient id="perfGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="var(--emerald)" stop-opacity="0.26" />
          <stop offset="100%" stop-color="var(--emerald)" stop-opacity="0.0" />
        </linearGradient>
      </defs>
      {tick_svg}
      <rect x="{sx(FORFEIT_RATIO):.1f}" y="{top}" width="{sx(x_max) - sx(FORFEIT_RATIO):.1f}" height="{bottom - top}" fill="var(--vermilion)" fill-opacity="0.10" />
      <polygon points="{area}" fill="url(#perfGrad)" />
      <polyline points="{poly}" fill="none" stroke="var(--emerald)" stroke-width="2.8" />
      <line x1="{sx(PENALTY_START_RATIO):.1f}" y1="{top}" x2="{sx(PENALTY_START_RATIO):.1f}" y2="{bottom}" stroke="var(--brass)" stroke-width="1.3" stroke-dasharray="4 3" />
      <line x1="{sx(FORFEIT_RATIO):.1f}" y1="{top}" x2="{sx(FORFEIT_RATIO):.1f}" y2="{bottom}" stroke="var(--vermilion)" stroke-width="1.5" stroke-dasharray="4 3" />
      <text x="{sx(0.55):.1f}" y="{top + 18}" text-anchor="middle" fill="var(--emerald)" font-family="var(--font-mono)" font-size="11">No underrun gate (pauses = timing)</text>
      <text x="{sx(1.29):.1f}" y="{top + 48}" text-anchor="middle" fill="var(--brass)" font-family="var(--font-mono)" font-size="10">Linear penalty</text>
      <text x="{sx(1.575):.1f}" y="{top + 18}" text-anchor="middle" fill="var(--vermilion)" font-family="var(--font-mono)" font-size="10">Forfeit</text>
      <text x="{left - 8}" y="{sy(1.0) + 4:.1f}" text-anchor="end" fill="var(--ink-muted)" font-family="var(--font-mono)" font-size="10">1.0</text>
      <text x="{left - 8}" y="{sy(0.5) + 4:.1f}" text-anchor="end" fill="var(--ink-muted)" font-family="var(--font-mono)" font-size="10">0.5</text>
      <text x="{left - 8}" y="{sy(0.0) + 4:.1f}" text-anchor="end" fill="var(--ink-muted)" font-family="var(--font-mono)" font-size="10">0.0</text>
      <line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="var(--border-strong)" />
      {"".join(whiskers)}
    </svg>
    """


def _render_roster_rows(submissions: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for sub in submissions:
        m = sub["measured"]
        role_badge = (
            '<span class="badge badge-blind">literal</span>'
            if sub["role"] == "literal"
            else (
                '<span class="badge badge-aware">rewrite</span>'
                if sub["role"] == "rewrite"
                else '<span class="badge badge-ok">system</span>'
            )
        )
        rows.append(
            "<tr>"
            f'<td class="mono">{html.escape(sub["system"])}</td>'
            f"<td>{role_badge}</td>"
            f'<td class="num">{m["performability"]:.3f}</td>'
            f'<td class="num">{m["fill_min"]:.2f}–{m["fill_median"]:.2f}–{m["fill_max"]:.2f}×</td>'
            f'<td class="num">{m["overall_consistency"]:.3f}</td>'
            f'<td class="num">{m["inflected_matches"]}</td>'
            f'<td class="num">{m["missed_count"]}</td>'
            f'<td class="num">{m["forfeits"]}</td>'
            "</tr>"
        )
    return "\n".join(rows)


def _render_mechanism_bars(mech_counts: dict[str, int]) -> str:
    top_val = max(mech_counts.values(), default=1)
    items: list[str] = []
    for mech, count in list(mech_counts.items())[:10]:
        pct = (count / top_val) * 100
        items.append(
            '<div class="bar-row">'
            f'<span class="bar-label">{html.escape(mech.replace("_", " "))}</span>'
            f'<div class="bar-track"><div class="bar-inner" style="width:{pct:.1f}%"></div></div>'
            f'<span class="bar-num">{count}</span>'
            "</div>"
        )
    return "\n".join(items)


def _render_unvalidated_preview(preview: dict[str, Any] | None) -> str:
    if not preview or not preview.get("leaderboard"):
        return ""
    rows = preview["leaderboard"]
    audit = preview.get("audit") or {}
    tentative = audit.get("tentative_dimensions") or []
    trs = "".join(
        "<tr>"
        f'<td class="num">{r["tier"]}</td>'
        f'<td class="mono">{html.escape(r["system"])}</td>'
        f'<td class="num">{r["drs"]:.3f}</td>'
        f'<td class="num">{r["lo"]:.3f}–{r["hi"]:.3f}</td>'
        f'<td class="num">{r["p"]:.3f}</td>'
        f'<td class="num">{r.get("humor", 0.0):.3f}</td>'
        f'<td class="num">{r.get("voice", 0.0):.3f}</td>'
        f'<td class="num">{r.get("gags", 0.0):.3f}</td>'
        f'<td class="num">{r.get("fidelity", 0.0):.3f}</td>'
        "</tr>"
        for r in rows
    )
    tent_note = (
        f" Tentative dimensions (Krippendorff's α &lt; 0.5): <strong>{html.escape(', '.join(tentative))}</strong>."
        if tentative
        else ""
    )
    return f"""
    <section id="preview">
      <div class="wrap">
        <div class="sec-head">
          <div>
            <div class="sec-kicker">Local Diagnostic Preview Only</div>
            <h2>Unvalidated Seed Run</h2>
          </div>
        </div>
        <div class="preview-warning">
          <strong>UNVALIDATED PREVIEW (not for publication):</strong> Built with
          <code>--include-unvalidated-preview</code>. Season 2 has not had its human edit and the
          DESIGN.md §6 validation program / human humor sample has not been completed.{tent_note}
        </div>
        <div class="table-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th class="num">Tier</th>
                <th>System</th>
                <th class="num">DRS</th>
                <th class="num">95% CI</th>
                <th class="num">P</th>
                <th class="num">Humor</th>
                <th class="num">Voice</th>
                <th class="num">Gags</th>
                <th class="num">Fidelity</th>
              </tr>
            </thead>
            <tbody>{trs}</tbody>
          </table>
        </div>
      </div>
    </section>
    """


def render_html(data: dict[str, Any]) -> str:
    """Render the complete HTML page from collected public data."""
    meta = data["meta"]
    spot = next(
        (s for s in data["segments"] if s["id"] == "s2-005"), data["segments"][0]
    )
    total_sec = round(meta["total_seconds"])
    total_mins, total_rem = divmod(total_sec, 60)
    dims = [
        (
            "Humor",
            int(WEIGHTS[Dimension.HUMOR] * 100),
            "source-blind",
            "badge-blind",
            "Rebuilt to land for native speakers who never hear the English. Cultural refs adapted, never glossed.",
        ),
        (
            "Voice",
            int(WEIGHTS[Dimension.VOICE] * 100),
            "source-blind",
            "badge-blind",
            "Grandiose, wheezing, overwrought narrator momentum with sharp drops into the mundane.",
        ),
        (
            "Gags",
            int(WEIGHTS[Dimension.GAGS] * 100),
            "source-aware",
            "badge-aware",
            "Invented epithets and running gags derived from the source and consistent with the system's own bible.",
        ),
        (
            "Fidelity",
            int(WEIGHTS[Dimension.FIDELITY] * 100),
            "source-aware",
            "badge-aware",
            "Still narrates this scene and source events—the tether that blocks free-written comedy.",
        ),
    ]
    dim_cards = "".join(
        f"""
        <div class="dim-card">
          <div class="dim-top">
            <span class="dim-name">{name}</span>
            <span class="dim-weight">{weight}%</span>
          </div>
          <span class="badge {cls}">{cond}</span>
          <p class="dim-desc">{desc}</p>
        </div>
        """
        for name, weight, cond, cls, desc in dims
    )

    cmd_prompt = "uv run --with-editable . python -m dearreader_bench.submission prompt ja > prompt.txt"
    cmd_check = "uv run --with-editable . python -m dearreader_bench.submission check submissions/acme__model-1/ja.json"
    cmd_mock = (
        "uv run --no-project --with pytest --with pydantic --with-editable . pytest -q"
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>dear-reader-bench — Comedic Film-Narration Translation Benchmark</title>
  <meta name="description" content="An AI benchmark for translating Wizard People, Dear Reader-style bombastic comedic narration across languages: humor, voice, running gags, and timed speakability.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,500;0,9..144,600;1,9..144,500&family=JetBrains+Mono:wght@400;600&family=Noto+Serif+JP:wght@400;600&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header class="topbar">
    <div class="wrap topbar-inner">
      <a href="#" class="brand">
        <span class="brand-mark">dear-reader-bench</span>
        <span class="brand-tag">{html.escape(meta["corpus"])}</span>
      </a>
      <nav class="nav" aria-label="Primary">
        <a href="#screening">Screening Room</a>
        <a href="#bible-wall">Bible Wall</a>
        <a href="#methodology">Methodology</a>
        <a href="#roster">Roster &amp; Gate</a>
        <a href="#submit">Submit</a>
      </nav>
      <div class="nav-actions">
        <button id="theme-toggle" class="btn btn-icon" type="button">Archival Paper</button>
        <a class="btn btn-primary" href="{REPO_URL}" target="_blank" rel="noopener">GitHub</a>
      </div>
    </div>
  </header>

  <main>
    <section class="hero">
      <div class="wrap hero-grid">
        <div>
          <div class="eyebrow">
            <span class="eyebrow-dot"></span>
            <span>Full-Script Comedic Adaptation Benchmark · v3 Design</span>
          </div>
          <h1>Not meaning.<br><em>Performance.</em></h1>
          <p class="hero-lead">
            Most translation benchmarks check whether a model moved propositions between languages.
            <strong>dear-reader-bench</strong> tests whether wall-to-wall bombastic narration—invented
            epithets, multi-scene running gags, register whiplash, and timed aloud delivery—survives
            crossing into another language.
          </p>
          <div class="hero-cta">
            <a class="btn btn-primary" href="#screening">Enter the Screening Room</a>
            <a class="btn" href="{REPO_URL}/blob/main/DESIGN.md" target="_blank" rel="noopener">Read DESIGN.md (v3)</a>
            <a class="btn" href="#submit">Submit a Model</a>
          </div>
          <div class="stat-strip">
            <div>
              <div class="stat-val">{meta["segment_count"]}</div>
              <div class="stat-lbl">Timed Segments</div>
            </div>
            <div>
              <div class="stat-val">{meta["joke_card_count"]}</div>
              <div class="stat-lbl">Joke Cards</div>
            </div>
            <div>
              <div class="stat-val">{meta["gag_chain_count"]}</div>
              <div class="stat-lbl">Running Gag Arcs</div>
            </div>
            <div>
              <div class="stat-val">{total_mins}:{total_rem:02d}</div>
              <div class="stat-lbl">Runtime ({len(meta["slate"])} langs)</div>
            </div>
          </div>
        </div>

        <aside class="spotlight" aria-label="Live translation excerpt">
          <div class="spotlight-head">
            <span>EXCERPT · {html.escape(spot["id"].upper())} · THE COUNT AT UNTERZWICK</span>
            <span class="timecode">{spot["seconds"]}s WINDOW</span>
          </div>
          <p class="spotlight-scene">{html.escape(spot["scene"])}</p>
          <p class="spotlight-quote">“{html.escape(spot["text"])}”</p>
          <div id="spotlight-tabs" class="spotlight-tabs"></div>
          <div id="spotlight-tr" class="spotlight-tr"></div>
          <div class="meter-row">
            <div class="meter-track"><div id="spotlight-meter-fill" class="meter-fill" style="width:50%"></div></div>
            <span id="spotlight-meter-text"></span>
          </div>
        </aside>
      </div>
    </section>

    <section id="screening">
      <div class="wrap">
        <div class="sec-head">
          <div>
            <div class="sec-kicker">Interactive Corpus &amp; Adaptation Explorer</div>
            <h2>The Screening Room</h2>
            <p class="sec-sub">
              Scrub through all {meta["segment_count"]} segments of <em>The Count at Unterzwick</em>
              (original CC BY 4.0 test fiction), click any Joke Card to highlight its setup &amp; punchline
              spans, and inspect how submitted Japanese adaptations handle bible consistency and spoken timing.
            </p>
          </div>
        </div>

        <div class="filmstrip-controls">
          <div class="filter-group">
            <select id="filter-gag" class="control" aria-label="Filter by running gag arc">
              <option value="">All running-gag arcs ({meta["gag_chain_count"]})</option>
            </select>
            <select id="filter-feature" class="control" aria-label="Filter by comedy feature">
              <option value="">All comedy features</option>
            </select>
          </div>
          <span class="mono" style="font-size:0.76rem;color:var(--ink-muted)">
            <span class="hl-setup">setup</span> · <span class="hl-punch">punchline</span> · <span class="hl-bible">bible term</span>
          </span>
        </div>

        <div id="filmstrip" class="filmstrip" role="listbox" aria-label="Segments"></div>

        <div class="stage-grid">
          <div class="panel">
            <div id="stage-source"></div>
            <div id="stage-cards" class="cards-stack"></div>
          </div>
          <div class="panel">
            <div class="panel-title">
              <h3>Side-by-Side Adaptations ({html.escape(meta["language_name"])})</h3>
              <span class="mono" style="font-size:0.74rem;color:var(--ink-muted)">CC BY 4.0</span>
            </div>
            <div class="compare-controls">
              <select id="select-sys-a" class="control" aria-label="Candidate A"></select>
              <select id="select-sys-b" class="control" aria-label="Candidate B"></select>
            </div>
            <div id="stage-compare"></div>
          </div>
        </div>
      </div>
    </section>

    <section id="bible-wall">
      <div class="wrap">
        <div class="sec-head">
          <div>
            <div class="sec-kicker">Full-Script Adaptation Protocol · DESIGN.md §1</div>
            <h2>The Bible Wall</h2>
            <p class="sec-sub">
              Every system adapts the whole script in one shot and delivers a studio-style KNP bible:
              its chosen rendering for every character epithet, running-gag anchor, and narrator voice note.
            </p>
          </div>
          <div id="bible-tabs" class="bible-tabs">
            <button class="chip active" data-tab="names" type="button">Epithets ({len(data["corpus"]["names"])})</button>
            <button class="chip" data-tab="gags" type="button">Running Gags ({len(data["corpus"]["gags"])})</button>
            <button class="chip" data-tab="notes" type="button">Narrator Register Notes</button>
          </div>
        </div>
        <div id="bible-content"></div>
      </div>
    </section>

    <section id="methodology">
      <div class="wrap">
        <div class="sec-head">
          <div>
            <div class="sec-kicker">Measurement Architecture · DESIGN.md §§2–4</div>
            <h2>How DRS Works</h2>
            <p class="sec-sub">
              Two failure poles are excluded by construction: adequacy-tethered literalism (which kills jokes)
              and untethered free-writing (which abandons the source). Only measured constructs may gate;
              judged constructs may only weight.
            </p>
          </div>
        </div>

        <div class="equation-card">
          <div class="equation">
            DRS(s, L) = <span class="sym-p">P(s, L)</span> · Σ<sub>d</sub> <span class="sym-w">w<sub>d</sub></span> · <span class="sym-phi">φ<sub>d</sub>(s, L)</span>
          </div>
          <div class="eq-legend">
            <span><strong style="color:var(--emerald)">P</strong> = measured speakability</span>
            <span><strong style="color:var(--brass)">w<sub>d</sub></strong> = pre-registered weights</span>
            <span><strong style="color:var(--vermilion)">φ<sub>d</sub></strong> = Davidson BT expected win rate</span>
          </div>
        </div>

        <div class="dims-grid" style="margin-bottom:24px">{dim_cards}</div>

        <div class="two-col">
          <div class="panel">
            <div class="panel-title">
              <h3>Performability Curve &amp; Fill Ratios</h3>
              <span class="mono" style="font-size:0.74rem;color:var(--ink-muted)">mixed-script model</span>
            </div>
            <p style="margin:0 0 12px;font-size:0.86rem;color:var(--ink-dim)">
              Continuous decay from 1.10× to forfeit at 1.50×. Underrun is never penalized—the English source
              runs {meta["source_fill"]["min"]:.2f}×–{meta["source_fill"]["max"]:.2f}× because pauses are comic timing.
              Whiskers below the axis plot real min/median/max fill ratios (hover dots for values).
            </p>
            <div class="svg-wrap">{_render_performability_svg(data)}</div>
          </div>

          <div class="panel">
            <div class="panel-title">
              <h3>Season 2 Joke Card Taxonomy</h3>
              <span class="mono" style="font-size:0.74rem;color:var(--ink-muted)">{meta["non_portable_count"]} non-portable puns</span>
            </div>
            <p style="margin:0 0 14px;font-size:0.86rem;color:var(--ink-dim)">
              Every segment is annotated with GTVH-style mechanisms so Layer-2 Detection Asymmetry
              and compensation-aware survival scoring separate genuine adaptation from translationese.
            </p>
            <div class="bar-list">{_render_mechanism_bars(meta["mechanism_counts"])}</div>
          </div>
        </div>
      </div>
    </section>

    <section id="roster">
      <div class="wrap">
        <div class="sec-head">
          <div>
            <div class="sec-kicker">Honest Status · Computed Diagnostics Only</div>
            <h2>Submitted Roster &amp; Validation Gate</h2>
            <p class="sec-sub">
              Judged humor scores are deliberately withheld until Season 2 receives its human edit and the
              DESIGN.md §6 validation program passes. Below are strictly deterministic, judge-free measurements
              for the {len(data["submissions"])} committed {html.escape(meta["language_name"])} submissions.
            </p>
          </div>
        </div>

        <div class="honesty-banner">
          <div>
            <strong>Why no public DRS leaderboard yet?</strong> Season 2 was LLM-drafted for harness
            construction and has not yet had its human editorial pass, second Joke Card annotator, or the
            ~100-pair bilingual human humor sample required before publishing humor claims (DESIGN.md §§0, 6, 7).
          </div>
          <span class="badge badge-warn">Harness {html.escape(meta["harness_version"])}</span>
        </div>

        <div class="table-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th>System</th>
                <th>Role</th>
                <th class="num">Performability P</th>
                <th class="num">Fill (min–med–max)</th>
                <th class="num">Gag Ledger</th>
                <th class="num">Inflected</th>
                <th class="num">Missed</th>
                <th class="num">Forfeits</th>
              </tr>
            </thead>
            <tbody>{_render_roster_rows(data["submissions"])}</tbody>
          </table>
        </div>

        <div class="gate-grid">
          <div class="gate-item">
            <div class="gate-item-head"><span>Harness &amp; Two-Condition Judge</span><span class="badge badge-ok">Built</span></div>
            <p>Full-script bible intake, gag-bible judge context, order folding, Davidson BT + cluster bootstrap, run.lock snapshots.</p>
          </div>
          <div class="gate-item">
            <div class="gate-item-head"><span>Audit &amp; Layer-2 Instruments</span><span class="badge badge-ok">Built</span></div>
            <p>Krippendorff's α, position-swap bias, Dirichlet audit, Gag Ledger, Detection Asymmetry, Payoff Lift, offline lesions.</p>
          </div>
          <div class="gate-item">
            <div class="gate-item-head"><span>Corpus Human Edit &amp; 2nd Annotator</span><span class="badge badge-warn">Owed</span></div>
            <p>Human editorial pass on Season 2 (eliminating authoring-family homophily) and Joke Card inter-annotator agreement.</p>
          </div>
          <div class="gate-item">
            <div class="gate-item-head"><span>Bilingual Human Humor Sample</span><span class="badge badge-warn">Owed</span></div>
            <p>~100 anchored pairwise comparisons on humor before the first public judged leaderboard ships.</p>
          </div>
        </div>
      </div>
    </section>

    {_render_unvalidated_preview(data.get("unvalidated_preview"))}

    <section id="submit">
      <div class="wrap">
        <div class="sec-head">
          <div>
            <div class="sec-kicker">Open Intake · Six-Language Draft Slate</div>
            <h2>Submit a System</h2>
            <p class="sec-sub">
              One prompt, frozen per release, across <code>ja</code>, <code>zh</code>, <code>de</code>,
              <code>fr</code>, <code>es</code>, and <code>ar</code>. Translations are licensed CC BY 4.0;
              code and docs are Apache-2.0.
            </p>
          </div>
        </div>

        <div class="steps-grid">
          <div class="step-card">
            <span class="step-num">STEP 01</span>
            <h3>Print the Frozen Prompt</h3>
            <p style="margin:0;font-size:0.86rem;color:var(--ink-dim)">
              Send as one user message with no system prompt, extra glossary, or human edits.
            </p>
            <div class="code-box">
              <button class="copy-btn" type="button" data-copy="{html.escape(cmd_prompt)}">Copy</button>
              <code>{html.escape(cmd_prompt)}</code>
            </div>
          </div>

          <div class="step-card">
            <span class="step-num">STEP 02</span>
            <h3>Validate Locally</h3>
            <p style="margin:0;font-size:0.86rem;color:var(--ink-dim)">
              Checks all 48 segments, bible completeness, canary cleanliness, and speakability.
            </p>
            <div class="code-box">
              <button class="copy-btn" type="button" data-copy="{html.escape(cmd_check)}">Copy</button>
              <code>{html.escape(cmd_check)}</code>
            </div>
          </div>

          <div class="step-card">
            <span class="step-num">STEP 03</span>
            <h3>Test &amp; Open a PR</h3>
            <p style="margin:0;font-size:0.86rem;color:var(--ink-dim)">
              Run the offline test suite (zero API keys required) and submit via pull request.
            </p>
            <div class="code-box">
              <button class="copy-btn" type="button" data-copy="{html.escape(cmd_mock)}">Copy</button>
              <code>{html.escape(cmd_mock)}</code>
            </div>
          </div>
        </div>
      </div>
    </section>
  </main>

  <footer>
    <div class="wrap footer-inner">
      <div>
        <strong>dear-reader-bench</strong> · Code &amp; docs Apache-2.0 · Synthetic corpus &amp; translations CC BY 4.0.
        No copyrighted film transcripts are distributed here.
      </div>
      <div class="footer-links">
        <a href="{REPO_URL}" target="_blank" rel="noopener">Repository</a>
        <a href="{REPO_URL}/blob/main/DESIGN.md" target="_blank" rel="noopener">DESIGN.md</a>
        <a href="{REPO_URL}/blob/main/SUBMITTING.md" target="_blank" rel="noopener">SUBMITTING.md</a>
        <a href="data.json">data.json</a>
      </div>
    </div>
  </footer>

  <script id="drb-data" type="application/json">{_safe_inline_json(data)}</script>
  <script src="app.js" defer></script>
</body>
</html>
"""


def build_site(
    *,
    out_dir: Path,
    corpus_path: Path = DEFAULT_CORPUS,
    cards_path: Path | None = None,
    submissions_dir: Path | None = None,
    language: str = "ja",
    results_dir: Path | None = None,
    include_unvalidated_preview: bool = False,
) -> Path:
    """Build the complete static site into `out_dir` and return `out_dir / 'index.html'`."""
    root = corpus_path.parents[1]
    cards = cards_path or corpus_path.with_name("season2_cards.json")
    subs = submissions_dir or (root / "submissions")
    results = results_dir or (root / "results")

    data = collect_site_data(
        corpus_path=corpus_path,
        cards_path=cards,
        submissions_dir=subs,
        language=language,
        results_dir=results,
        include_unvalidated_preview=include_unvalidated_preview,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    for asset in ("styles.css", "app.js"):
        shutil.copy2(ASSETS_DIR / asset, out_dir / asset)

    (out_dir / "data.json").write_text(
        json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    index = out_dir / "index.html"
    index.write_text(render_html(data), encoding="utf-8")
    return index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_CORPUS.parents[1] / "site")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--cards", type=Path, default=None)
    parser.add_argument("--submissions", type=Path, default=None)
    parser.add_argument("--language", choices=sorted(LANGUAGES), default="ja")
    parser.add_argument(
        "--include-unvalidated-preview",
        action="store_true",
        help="Include local unvalidated seed-run table (for local review only, not public deploy)",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    out = build_site(
        out_dir=args.out,
        corpus_path=args.corpus,
        cards_path=args.cards,
        submissions_dir=args.submissions,
        language=args.language,
        include_unvalidated_preview=args.include_unvalidated_preview,
    )
    log.info("built static site at %s", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
