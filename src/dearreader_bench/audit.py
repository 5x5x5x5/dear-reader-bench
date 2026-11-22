"""Automated reliability panel, weight audit, judge heatmap, and anchor validity checks.

Implements the offline diagnostics specified in DESIGN.md §§2.1, 2.2, 2.3, 4, and 6:
- Position-swap consistency & first-position bias per judge
- Krippendorff's alpha per dimension (interval on {-1, 0, +1}, plus nominal);
  dimensions with alpha < 0.5 are flagged tentative and DRS is republished without them
- Split-half reliability of phi / DRS with Spearman-Brown correction
- Leave-one-judge-out (LOJO) rank stability (Kendall's tau, Spearman's rho, max rank shift)
- Judge-deviation heatmap per (judge, system)
- Dirichlet weight-sensitivity audit (1000 draws centered on WEIGHTS)
- Anchor presence and known-groups validity checks (+literal, +rewrite, pinned open-weight)
- Fill-ratio diagnostic distributions vs. the English source

Run standalone on any existing results directory (zero API calls):
    python -m dearreader_bench.audit ja
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import random
import statistics
import sys
from itertools import combinations
from pathlib import Path
from typing import Any

from .brief import LANGUAGES
from .btmodel import composite, fit, tally
from .rubric import WEIGHTS
from .runner import DEFAULT_SUBMISSIONS
from .schema import AdaptationResult, Corpus, Dimension, PairwiseJudgment, load_corpus
from .speakability import fill_ratio
from .submission import DEFAULT_CORPUS, check_submission, performability

log = logging.getLogger(__name__)

# (segment_id, dimension, system_a, system_b, judge, winner) after order-folding.
JudgeOutcome = tuple[str, str, str, str, str, str]

ALPHA_TENTATIVE_THRESHOLD = 0.5
DIRICHLET_CONCENTRATION = 20.0
DIRICHLET_INVARIANCE_THRESHOLD = 0.95


def fold_by_judge(judgments: list[PairwiseJudgment]) -> list[JudgeOutcome]:
    """Fold presentation orders per judge (order disagreement degrades to tie)."""
    by_key: dict[tuple[str, str, str, str, str], list[str]] = {}
    for j in judgments:
        key = (j.segment_id, j.dimension.value, j.system_a, j.system_b, j.judge)
        by_key.setdefault(key, []).append(j.winner)
    return [
        (*key, w[0] if len(set(w)) == 1 else "tie") for key, w in sorted(by_key.items())
    ]


def forfeit_outcomes(
    roster: dict[str, AdaptationResult], corpus: Corpus
) -> list[tuple[str, str, str, str, str]]:
    """Forfeit outcomes where one candidate exceeded 1.50x window and the rival did not."""
    forfeits = {n: set(performability(r, corpus)[1]) for n, r in roster.items()}
    outcomes: list[tuple[str, str, str, str, str]] = []
    for a, b in combinations(sorted(roster), 2):
        for seg_id in sorted(forfeits[a] ^ forfeits[b]):
            winner = "b" if seg_id in forfeits[a] else "a"
            outcomes += [(seg_id, d.value, a, b, winner) for d in Dimension]
    return outcomes


def position_swap_consistency(judgments: list[PairwiseJudgment]) -> dict[str, Any]:
    """Per-judge order-swap agreement and first-position bias (DESIGN.md §6)."""
    pairs: dict[tuple[str, str, str, str, str], dict[int, str]] = {}
    for j in judgments:
        key = (j.segment_id, j.dimension.value, j.system_a, j.system_b, j.judge)
        pairs.setdefault(key, {})[j.order] = j.winner

    per_judge: dict[str, dict[str, Any]] = {}
    by_judge_dim: dict[str, dict[str, list[bool]]] = {}
    for (_, dim, _, _, judge), orders in pairs.items():
        if 0 not in orders or 1 not in orders:
            continue
        w0, w1 = orders[0], orders[1]
        agreed = w0 == w1
        stat = per_judge.setdefault(
            judge,
            {
                "pairs": 0,
                "agree": 0,
                "first_picks": 0,
                "second_picks": 0,
                "ties": 0,
            },
        )
        stat["pairs"] += 1
        stat["agree"] += int(agreed)
        # In order 0, shown-first is 'a'; in order 1, shown-first is 'b'.
        for order, winner in ((0, w0), (1, w1)):
            if winner == "tie":
                stat["ties"] += 1
            elif (order == 0 and winner == "a") or (order == 1 and winner == "b"):
                stat["first_picks"] += 1
            else:
                stat["second_picks"] += 1
        by_judge_dim.setdefault(judge, {}).setdefault(dim, []).append(agreed)

    out: dict[str, Any] = {}
    for judge, s in sorted(per_judge.items()):
        non_tie = s["first_picks"] + s["second_picks"]
        out[judge] = {
            "pairs": s["pairs"],
            "agreement": s["agree"] / s["pairs"] if s["pairs"] else 0.0,
            "first_position_bias": (
                (s["first_picks"] - s["second_picks"]) / non_tie if non_tie else 0.0
            ),
            "tie_rate": s["ties"] / (2 * s["pairs"]) if s["pairs"] else 0.0,
            "by_dimension": {
                d: sum(flags) / len(flags)
                for d, flags in sorted(by_judge_dim.get(judge, {}).items())
            },
        }
    return out


def _krippendorff_interval(units: list[list[float]]) -> float | None:
    """Exact interval-metric Krippendorff's alpha supporting missing raters."""
    valid = [u for u in units if len(u) >= 2]
    n_total = sum(len(u) for u in valid)
    if n_total < 2:
        return None
    do_num = 0.0
    all_vals: list[float] = []
    for u in valid:
        m = len(u)
        sum_v = sum(u)
        sum_v2 = sum(v * v for v in u)
        # sum_{i != j} (v_i - v_j)^2 = 2 * m * sum(v^2) - 2 * (sum(v))^2
        do_num += (2.0 * m * sum_v2 - 2.0 * sum_v * sum_v) / (m - 1)
        all_vals.extend(u)
    d_o = do_num / n_total

    sum_all = sum(all_vals)
    sum_all2 = sum(v * v for v in all_vals)
    d_e = (2.0 * n_total * sum_all2 - 2.0 * sum_all * sum_all) / (
        n_total * (n_total - 1)
    )
    if d_e == 0.0:
        return 1.0 if d_o == 0.0 else 0.0
    return 1.0 - d_o / d_e


def _krippendorff_nominal(units: list[list[str]]) -> float | None:
    """Exact nominal-metric Krippendorff's alpha supporting missing raters."""
    valid = [u for u in units if len(u) >= 2]
    n_total = sum(len(u) for u in valid)
    if n_total < 2:
        return None
    do_num = 0.0
    counts: dict[str, int] = {}
    for u in valid:
        m = len(u)
        u_counts: dict[str, int] = {}
        for v in u:
            u_counts[v] = u_counts.get(v, 0) + 1
            counts[v] = counts.get(v, 0) + 1
        matches = sum(c * (c - 1) for c in u_counts.values())
        disagreements = m * (m - 1) - matches
        do_num += disagreements / (m - 1)
    d_o = do_num / n_total
    total_matches = sum(c * (c - 1) for c in counts.values())
    d_e = (n_total * (n_total - 1) - total_matches) / (n_total * (n_total - 1))
    if d_e == 0.0:
        return 1.0 if d_o == 0.0 else 0.0
    return 1.0 - d_o / d_e


def krippendorff_by_dimension(
    folded: list[JudgeOutcome],
) -> dict[str, dict[str, Any]]:
    """Krippendorff's alpha per dimension over order-folded judge verdicts (DESIGN.md §6)."""
    code = {"a": 1.0, "tie": 0.0, "b": -1.0}
    grouped: dict[str, dict[tuple[str, str, str], list[str]]] = {}
    for seg_id, dim, a, b, _, winner in folded:
        # Canonicalize pair direction so 'a' always means lexicographically smaller system.
        if a <= b:
            unit_key, val = (seg_id, a, b), winner
        else:
            flipped = "b" if winner == "a" else ("a" if winner == "b" else "tie")
            unit_key, val = (seg_id, b, a), flipped
        grouped.setdefault(dim, {}).setdefault(unit_key, []).append(val)

    result: dict[str, dict[str, Any]] = {}
    for dim in (d.value for d in Dimension):
        unit_map = grouped.get(dim, {})
        nom_units = list(unit_map.values())
        int_units = [[code[v] for v in u] for u in nom_units]
        alpha = _krippendorff_interval(int_units)
        alpha_nom = _krippendorff_nominal(nom_units)
        n_units = sum(1 for u in nom_units if len(u) >= 2)
        result[dim] = {
            "units": n_units,
            "alpha": alpha,
            "alpha_nominal": alpha_nom,
            "tentative": alpha is not None and alpha < ALPHA_TENTATIVE_THRESHOLD,
        }
    return result


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    denom = math.sqrt(sum(a * a for a in dx) * sum(b * b for b in dy))
    if denom == 0.0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / denom


def _ranks(values: dict[str, float]) -> dict[str, float]:
    """Average-tie ranks (1 = highest score)."""
    ordered = sorted(values.items(), key=lambda kv: kv[1], reverse=True)
    ranks: dict[str, float] = {}
    i = 0
    while i < len(ordered):
        j = i + 1
        while j < len(ordered) and abs(ordered[j][1] - ordered[i][1]) < 1e-12:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[ordered[k][0]] = avg_rank
        i = j
    return ranks


def _spearman(a: dict[str, float], b: dict[str, float]) -> float | None:
    keys = sorted(set(a) & set(b))
    if len(keys) < 2:
        return None
    ra = _ranks({k: a[k] for k in keys})
    rb = _ranks({k: b[k] for k in keys})
    return _pearson([ra[k] for k in keys], [rb[k] for k in keys])


def _kendall_tau(a: dict[str, float], b: dict[str, float]) -> float | None:
    keys = sorted(set(a) & set(b))
    if len(keys) < 2:
        return None
    concordant = discordant = 0
    for x, y in combinations(keys, 2):
        da = a[x] - a[y]
        db = b[x] - b[y]
        if abs(da) < 1e-12 or abs(db) < 1e-12:
            continue
        if (da > 0) == (db > 0):
            concordant += 1
        else:
            discordant += 1
    total = concordant + discordant
    return (concordant - discordant) / total if total else 1.0


def _score_outcomes(
    outcomes: list[tuple[str, str, str, str, str]],
    p: dict[str, float],
    weights: dict[str, float] | None = None,
    iters: int = 800,
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    w = weights or {d.value: val for d, val in WEIGHTS.items()}
    phi: dict[str, dict[str, float]] = {}
    for d in Dimension:
        rows = [(a, b, win) for _, dim, a, b, win in outcomes if dim == d.value]
        if rows:
            phi[d.value] = fit(tally(rows), iters=iters).phi
    return composite(phi, w, p), phi


def split_half_reliability(
    outcomes: list[tuple[str, str, str, str, str]],
    p: dict[str, float],
    corpus: Corpus,
    splits: int = 20,
    seed: int = 0,
    iters: int = 600,
) -> dict[str, float | None]:
    """Cluster-split-half reliability of phi and DRS with Spearman-Brown (DESIGN.md §6)."""
    cluster_of = {s.id: s.gag_id or s.id for s in corpus.segments}
    by_cluster: dict[str, list[tuple[str, str, str, str, str]]] = {}
    for o in outcomes:
        by_cluster.setdefault(cluster_of[o[0]], []).append(o)
    clusters = sorted(by_cluster)
    if len(clusters) < 4:
        return {k: None for k in ["drs", *(d.value for d in Dimension)]}

    rng = random.Random(seed)
    metrics = ["drs", *(d.value for d in Dimension)]
    sb_values: dict[str, list[float]] = {m: [] for m in metrics}
    half = len(clusters) // 2

    for _ in range(splits):
        shuffled = list(clusters)
        rng.shuffle(shuffled)
        h1 = [o for c in shuffled[:half] for o in by_cluster[c]]
        h2 = [o for c in shuffled[half:] for o in by_cluster[c]]
        drs1, phi1 = _score_outcomes(h1, p, iters=iters)
        drs2, phi2 = _score_outcomes(h2, p, iters=iters)
        series = [("drs", drs1, drs2)] + [
            (d.value, phi1.get(d.value, {}), phi2.get(d.value, {})) for d in Dimension
        ]
        for key, s1, s2 in series:
            common = sorted(set(s1) & set(s2))
            r = _pearson([s1[k] for k in common], [s2[k] for k in common])
            if r is not None and (1.0 + r) > 1e-9:
                sb_values[key].append((2.0 * r) / (1.0 + r))

    return {
        m: (sum(vals) / len(vals) if vals else None) for m, vals in sb_values.items()
    }


def leave_one_judge_out(
    folded: list[JudgeOutcome],
    forfeits: list[tuple[str, str, str, str, str]],
    p: dict[str, float],
    full_drs: dict[str, float],
    iters: int = 800,
) -> dict[str, dict[str, Any]]:
    """Leave-one-judge-out DRS rank stability (DESIGN.md §6)."""
    judges = sorted({o[4] for o in folded})
    if len(judges) < 2:
        return {}
    base_ranks = _ranks(full_drs)
    report: dict[str, dict[str, Any]] = {}
    for dropped in judges:
        kept = [(s, d, a, b, w) for s, d, a, b, j, w in folded if j != dropped] + list(
            forfeits
        )
        drs_loo, _ = _score_outcomes(kept, p, iters=iters)
        loo_ranks = _ranks(drs_loo)
        common = set(base_ranks) & set(loo_ranks)
        max_shift = max(
            (abs(base_ranks[s] - loo_ranks[s]) for s in common), default=0.0
        )
        report[dropped] = {
            "kendall_tau": _kendall_tau(full_drs, drs_loo),
            "spearman_rho": _spearman(full_drs, drs_loo),
            "max_rank_shift": max_shift,
            "drs": drs_loo,
        }
    return report


def judge_deviation_heatmap(
    folded: list[JudgeOutcome],
) -> dict[str, dict[str, float]]:
    """Per-(judge, system) win-rate deviation from ensemble mean on shared comparisons."""
    # Group by (seg_id, dim, a, b) -> {judge: winner}
    by_comp: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for seg_id, dim, a, b, judge, winner in folded:
        by_comp.setdefault((seg_id, dim, a, b), {})[judge] = winner

    deltas: dict[str, dict[str, list[float]]] = {}
    for (_, _, a, b), j_map in by_comp.items():
        if len(j_map) < 2:
            continue
        scores_a = {
            j: (1.0 if w == "a" else (0.5 if w == "tie" else 0.0))
            for j, w in j_map.items()
        }
        mean_a = sum(scores_a.values()) / len(scores_a)
        for j, sa in scores_a.items():
            dev_a = sa - mean_a
            deltas.setdefault(j, {}).setdefault(a, []).append(dev_a)
            deltas.setdefault(j, {}).setdefault(b, []).append(-dev_a)

    return {
        judge: {
            sys_name: sum(vals) / len(vals) for sys_name, vals in sorted(s_map.items())
        }
        for judge, s_map in sorted(deltas.items())
    }


def dirichlet_weight_audit(
    phi: dict[str, dict[str, float]],
    p: dict[str, float],
    base_weights: dict[str, float] | None = None,
    draws: int = 1000,
    concentration: float = DIRICHLET_CONCENTRATION,
    seed: int = 0,
) -> dict[str, Any]:
    """Dirichlet weight-sensitivity audit (DESIGN.md §2.2).

    Draws `draws` weight vectors centered on `base_weights` and reports the
    fraction of pairwise system orderings that remain invariant (>= 95% of draws).
    """
    weights = base_weights or {d.value: w for d, w in WEIGHTS.items()}
    dims = [d for d in weights if d in phi]
    systems = sorted({s for d in dims for s in phi[d]})
    if len(systems) < 2 or not dims:
        return {
            "draws": draws,
            "concentration": concentration,
            "total_pairs": 0,
            "invariant_pairs": 0,
            "invariant_fraction": 1.0,
            "sensitive_pairs": [],
        }

    rng = random.Random(seed)
    pair_wins: dict[tuple[str, str], int] = {
        pair: 0 for pair in combinations(systems, 2)
    }
    alphas = [max(concentration * weights[d], 1e-6) for d in dims]

    for _ in range(draws):
        gammas = [rng.gammavariate(a, 1.0) for a in alphas]
        total = sum(gammas)
        w_draw = {d: g / total for d, g in zip(dims, gammas)}
        drs_draw = composite(phi, w_draw, p)
        for a, b in pair_wins:
            if drs_draw.get(a, 0.0) > drs_draw.get(b, 0.0):
                pair_wins[(a, b)] += 1

    sensitive: list[dict[str, Any]] = []
    invariant = 0
    for (a, b), wins_a in sorted(pair_wins.items()):
        frac = wins_a / draws
        if max(frac, 1.0 - frac) >= DIRICHLET_INVARIANCE_THRESHOLD:
            invariant += 1
        else:
            sensitive.append({"system_a": a, "system_b": b, "p_a_gt_b": frac})

    total_pairs = len(pair_wins)
    return {
        "draws": draws,
        "concentration": concentration,
        "total_pairs": total_pairs,
        "invariant_pairs": invariant,
        "invariant_fraction": invariant / total_pairs if total_pairs else 1.0,
        "sensitive_pairs": sensitive,
    }


def check_anchors_and_validity(
    roster: dict[str, AdaptationResult],
    phi: dict[str, dict[str, float]],
    pinned_anchor: str | None = None,
) -> dict[str, Any]:
    """Check presence of fixed anchors and known-groups validity (DESIGN.md §§2.2, 4)."""
    systems = sorted(roster)
    literals = [s for s in systems if s.endswith("+literal")]
    rewrites = [s for s in systems if s.endswith("+rewrite")]
    non_anchors = [s for s in systems if not s.endswith(("+literal", "+rewrite"))]

    missing: list[str] = []
    if not literals:
        missing.append("forced-literal anchor (+literal)")
    if not rewrites:
        missing.append("unconstrained-rewrite anchor (+rewrite)")
    if pinned_anchor is None:
        missing.append("pinned open-weight mid-tier anchor (not specified)")
    elif pinned_anchor not in roster:
        missing.append(f"pinned open-weight anchor ({pinned_anchor})")

    failures: list[str] = []
    checks: dict[str, Any] = {}

    humor = phi.get(Dimension.HUMOR.value, {})
    gags = phi.get(Dimension.GAGS.value, {})
    fidelity = phi.get(Dimension.FIDELITY.value, {})

    # Known-groups check 1: forced-literal must not win humor (and should lose to its base).
    if literals and humor:
        top_humor = max(humor, key=lambda s: humor[s])
        lit_checks = []
        for lit in literals:
            won_humor = top_humor == lit
            base = lit[: -len("+literal")]
            beat_base = base in humor and humor[lit] >= humor[base]
            lit_checks.append(
                {
                    "anchor": lit,
                    "humor_phi": humor.get(lit),
                    "won_humor": won_humor,
                    "base": base if base in humor else None,
                    "base_humor_phi": humor.get(base),
                    "beat_base": beat_base,
                }
            )
            if won_humor:
                failures.append(f"forced-literal anchor {lit} won humor")
            if beat_base:
                failures.append(
                    f"forced-literal anchor {lit} ({humor[lit]:.3f}) matched or beat "
                    f"its base {base} ({humor[base]:.3f}) on humor"
                )
        checks["literal_humor"] = lit_checks

    # Known-groups check 2: unconstrained-rewrite must land at the bottom on gags + fidelity.
    if rewrites and (gags or fidelity):
        rew_checks = []
        rivals = [s for s in systems if not s.endswith("+rewrite")]
        for rew in rewrites:
            tether_rew = gags.get(rew, 0.0) + fidelity.get(rew, 0.0)
            beaten_rivals = [
                r
                for r in rivals
                if (gags.get(r, 0.0) + fidelity.get(r, 0.0)) <= tether_rew
            ]
            not_bottom_gags = [
                r for r in rivals if gags.get(r, 1.0) <= gags.get(rew, 0.0)
            ]
            not_bottom_fid = [
                r for r in rivals if fidelity.get(r, 1.0) <= fidelity.get(rew, 0.0)
            ]
            rew_checks.append(
                {
                    "anchor": rew,
                    "gags_phi": gags.get(rew),
                    "fidelity_phi": fidelity.get(rew),
                    "bottom_on_gags": not not_bottom_gags,
                    "bottom_on_fidelity": not not_bottom_fid,
                    "bottom_on_tether": not beaten_rivals,
                }
            )
            if beaten_rivals:
                failures.append(
                    f"unconstrained-rewrite anchor {rew} survived tethering battery "
                    f"(gags+fidelity >= {beaten_rivals})"
                )
            elif not_bottom_gags or not_bottom_fid:
                failures.append(
                    f"unconstrained-rewrite anchor {rew} did not place bottom on both "
                    f"gags ({not_bottom_gags}) and fidelity ({not_bottom_fid})"
                )
        checks["rewrite_tethering"] = rew_checks

    if failures:
        status = "invalid"
    elif missing:
        status = "incomplete"
    else:
        status = "valid_automated"

    return {
        "status": status,
        "anchors": {
            "literal": literals,
            "rewrite": rewrites,
            "pinned": pinned_anchor if pinned_anchor in roster else None,
            "non_anchor_count": len(non_anchors),
        },
        "missing_anchors": missing,
        "failures": failures,
        "checks": checks,
    }


def fill_ratio_summary(
    roster: dict[str, AdaptationResult], corpus: Corpus
) -> dict[str, dict[str, Any]]:
    """Fill-ratio distributions per system alongside the English source (DESIGN.md §2.3)."""
    windows = {s.id: s.seconds for s in corpus.segments}
    src_fills = [fill_ratio(s.text, "en", s.seconds) for s in corpus.segments]
    out: dict[str, dict[str, Any]] = {
        "_source_en": {
            "min": min(src_fills),
            "median": statistics.median(src_fills),
            "max": max(src_fills),
            "forfeits": 0,
        }
    }
    for name, result in sorted(roster.items()):
        fills = [
            fill_ratio(s.text, result.language, windows[s.segment_id])
            for s in result.segments
        ]
        _, forfeited = performability(result, corpus)
        out[name] = {
            "min": min(fills),
            "median": statistics.median(fills),
            "max": max(fills),
            "forfeits": len(forfeited),
        }
    return out


def audit_run(
    judgments: list[PairwiseJudgment],
    roster: dict[str, AdaptationResult],
    corpus: Corpus,
    *,
    pinned_anchor: str | None = None,
    dirichlet_draws: int = 1000,
    split_half_splits: int = 20,
    seed: int = 0,
) -> dict[str, Any]:
    """Compute the full automated reliability and validity panel for one run."""
    folded = fold_by_judge(judgments)
    forfeits = forfeit_outcomes(roster, corpus)
    all_outcomes = [(s, d, a, b, w) for s, d, a, b, _, w in folded] + forfeits
    p = {name: performability(res, corpus)[0] for name, res in roster.items()}
    drs, phi = _score_outcomes(all_outcomes, p, iters=2000)

    krip = krippendorff_by_dimension(folded)
    tentative_dims = [d for d, info in krip.items() if info["tentative"]]
    non_tentative_weights = {
        d.value: w for d, w in WEIGHTS.items() if d.value not in tentative_dims
    }
    drs_without_tentative = (
        composite(phi, non_tentative_weights, p)
        if tentative_dims and non_tentative_weights
        else None
    )

    return {
        "validity": check_anchors_and_validity(
            roster, phi, pinned_anchor=pinned_anchor
        ),
        "position_swap": position_swap_consistency(judgments),
        "krippendorff": krip,
        "tentative_dimensions": tentative_dims,
        "drs_without_tentative": drs_without_tentative,
        "split_half": split_half_reliability(
            all_outcomes, p, corpus, splits=split_half_splits, seed=seed
        ),
        "leave_one_judge_out": leave_one_judge_out(folded, forfeits, p, drs),
        "judge_deviation": judge_deviation_heatmap(folded),
        "dirichlet_weights": dirichlet_weight_audit(
            phi, p, draws=dirichlet_draws, seed=seed
        ),
        "fill_ratios": fill_ratio_summary(roster, corpus),
    }


def _fmt(val: float | None, spec: str = ".3f") -> str:
    return "n/a" if val is None else format(val, spec)


def render_audit(report: dict[str, Any], language: str, corpus: Corpus) -> str:
    """Render the audit report as readable Markdown."""
    v = report["validity"]
    lines = [
        f"# Audit panel: {LANGUAGES[language]} on {corpus.corpus}",
        "",
        f"**Automated validity status:** `{v['status']}`",
    ]
    if v["failures"]:
        lines += ["", "### Validity failures"] + [f"- {f}" for f in v["failures"]]
    if v["missing_anchors"]:
        lines += ["", "### Missing anchors"] + [f"- {m}" for m in v["missing_anchors"]]

    lines += [
        "",
        "## Krippendorff's alpha & split-half reliability",
        "",
        "| dimension | units | alpha (interval) | alpha (nominal) | split-half SB | tentative? |",
        "|---|---:|---:|---:|---:|---|",
    ]
    sh = report["split_half"]
    for dim, info in report["krippendorff"].items():
        lines.append(
            f"| {dim} | {info['units']} | {_fmt(info['alpha'])} | "
            f"{_fmt(info['alpha_nominal'])} | {_fmt(sh.get(dim))} | "
            f"{'YES' if info['tentative'] else 'no'} |"
        )
    lines.append(f"| **DRS** | — | — | — | {_fmt(sh.get('drs'))} | — |")

    if report["drs_without_tentative"]:
        tentative_list = ", ".join(report["tentative_dimensions"])
        lines += [
            "",
            f"### DRS excluding tentative dimensions ({tentative_list})",
            "",
            "| system | DRS (non-tentative) |",
            "|---|---:|",
        ]
        for s, score in sorted(
            report["drs_without_tentative"].items(), key=lambda kv: kv[1], reverse=True
        ):
            lines.append(f"| {s} | {score:.3f} |")

    lines += [
        "",
        "## Position-swap consistency",
        "",
        "| judge | pairs | agreement | first-pos bias | tie rate |",
        "|---|---:|---:|---:|---:|",
    ]
    for judge, s in report["position_swap"].items():
        lines.append(
            f"| {judge} | {s['pairs']} | {s['agreement']:.3f} | "
            f"{s['first_position_bias']:+.3f} | {s['tie_rate']:.3f} |"
        )

    if report["leave_one_judge_out"]:
        lines += [
            "",
            "## Leave-one-judge-out rank stability",
            "",
            "| dropped judge | Kendall tau | Spearman rho | max rank shift |",
            "|---|---:|---:|---:|",
        ]
        for judge, s in report["leave_one_judge_out"].items():
            lines.append(
                f"| {judge} | {_fmt(s['kendall_tau'])} | "
                f"{_fmt(s['spearman_rho'])} | {s['max_rank_shift']:.1f} |"
            )

    if report["judge_deviation"]:
        judges = sorted(report["judge_deviation"])
        systems = sorted({s for m in report["judge_deviation"].values() for s in m})
        lines += [
            "",
            "## Judge-deviation heatmap (win rate vs. ensemble mean)",
            "",
            "| system | " + " | ".join(judges) + " |",
            "|---|" + "---:|" * len(judges),
        ]
        for sys_name in systems:
            cells = [
                _fmt(report["judge_deviation"][j].get(sys_name), "+.3f") for j in judges
            ]
            lines.append(f"| {sys_name} | " + " | ".join(cells) + " |")

    dw = report["dirichlet_weights"]
    dw_summary = (
        f"Weight-invariant pairs (>=95% of {dw['draws']} draws, "
        f"concentration={dw['concentration']:.0f}): "
        f"**{dw['invariant_pairs']}/{dw['total_pairs']} ({dw['invariant_fraction']:.1%})**"
    )
    lines += [
        "",
        "## Dirichlet weight-sensitivity audit",
        "",
        dw_summary,
    ]
    if dw["sensitive_pairs"]:
        lines += [
            "",
            "| system A | system B | P(A > B) |",
            "|---|---|---:|",
        ]
        for sp in dw["sensitive_pairs"]:
            lines.append(
                f"| {sp['system_a']} | {sp['system_b']} | {sp['p_a_gt_b']:.3f} |"
            )

    lines += [
        "",
        "## Fill-ratio distribution (diagnostic)",
        "",
        "| system | min | median | max | forfeits |",
        "|---|---:|---:|---:|---:|",
    ]
    for sys_name, fr in report["fill_ratios"].items():
        lines.append(
            f"| {sys_name} | {fr['min']:.2f} | {fr['median']:.2f} | "
            f"{fr['max']:.2f} | {fr['forfeits']} |"
        )
    lines.append("")
    return "\n".join(lines)


def _load_roster(
    submissions: Path, language: str, corpus: Corpus
) -> dict[str, AdaptationResult]:
    roster: dict[str, AdaptationResult] = {}
    for path in sorted(submissions.glob(f"*/{language}.json")):
        result = AdaptationResult.model_validate_json(path.read_text(encoding="utf-8"))
        problems = check_submission(result, corpus)
        if problems:
            raise ValueError(f"{path}: {problems}")
        roster[result.system] = result
    return roster


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("language", choices=sorted(LANGUAGES))
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--submissions", type=Path, default=DEFAULT_SUBMISSIONS)
    parser.add_argument(
        "--results", type=Path, default=DEFAULT_CORPUS.parents[1] / "results"
    )
    parser.add_argument(
        "--pinned-anchor", default=None, help="Pinned open-weight mid-tier system id"
    )
    parser.add_argument("--dirichlet-draws", type=int, default=1000)
    parser.add_argument("--split-half-splits", type=int, default=20)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    corpus = load_corpus(args.corpus)
    roster = _load_roster(args.submissions, args.language, corpus)
    judgments_path = args.results / args.language / "judgments.jsonl"
    if not judgments_path.exists():
        log.error("missing %s", judgments_path)
        return 1
    judgments = [
        PairwiseJudgment.model_validate_json(line)
        for line in judgments_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    report = audit_run(
        judgments,
        roster,
        corpus,
        pinned_anchor=args.pinned_anchor,
        dirichlet_draws=args.dirichlet_draws,
        split_half_splits=args.split_half_splits,
    )
    md = render_audit(report, args.language, corpus)
    out_dir = args.results / args.language
    (out_dir / "audit.json").write_text(
        json.dumps(report, indent=1) + "\n", encoding="utf-8"
    )
    (out_dir / "audit.md").write_text(md, encoding="utf-8")
    sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
