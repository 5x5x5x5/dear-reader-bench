"""Davidson Bradley-Terry aggregation (DESIGN.md §2.2).

Fits abilities theta_k and a tie parameter nu over pairwise outcomes by
penalized maximum likelihood (light L2, sum-zero identifiability), pure
Python — no scipy. Reports phi = expected win rate vs. the field
(mean over rivals of P(beat) + 0.5 * P(tie)), the bounded quantity that
makes dimensions commensurable in the DRS composite.

Model (Davidson 1970):
    P(i beats j) = pi_i / D,  P(j beats i) = pi_j / D,
    P(tie)       = nu * sqrt(pi_i * pi_j) / D,
    D = pi_i + pi_j + nu * sqrt(pi_i * pi_j),  pi = exp(theta).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class PairData:
    """Aggregated outcomes for one unordered pair."""

    a: str
    b: str
    wins_a: float = 0.0
    wins_b: float = 0.0
    ties: float = 0.0


@dataclass
class BTResult:
    theta: dict[str, float]
    nu: float
    phi: dict[str, float] = field(default_factory=dict)


def tally(outcomes: list[tuple[str, str, str]]) -> list[PairData]:
    """Aggregate (system_a, system_b, winner∈{'a','b','tie'}) records into pair tallies."""
    pairs: dict[tuple[str, str], PairData] = {}
    for a, b, winner in outcomes:
        key = (a, b) if a <= b else (b, a)
        pd = pairs.setdefault(key, PairData(*key))
        flipped = key != (a, b)
        if winner == "tie":
            pd.ties += 1
        elif (winner == "a") != flipped:
            pd.wins_a += 1
        else:
            pd.wins_b += 1
    return list(pairs.values())


def _probs(theta_i: float, theta_j: float, log_nu: float) -> tuple[float, float, float]:
    pi_i, pi_j = math.exp(theta_i), math.exp(theta_j)
    t = math.exp(log_nu) * math.sqrt(pi_i * pi_j)
    d = pi_i + pi_j + t
    return pi_i / d, pi_j / d, t / d


def fit(pairs: list[PairData], l2: float = 0.1, iters: int = 2000, lr: float = 0.1) -> BTResult:
    """Penalized MLE by gradient ascent; sum-zero constraint on theta."""
    systems = sorted({s for p in pairs for s in (p.a, p.b)})
    if not systems:
        return BTResult(theta={}, nu=1.0)
    theta = {s: 0.0 for s in systems}
    log_nu = 0.0
    for it in range(iters):
        grad = {s: -l2 * theta[s] for s in systems}
        grad_nu = -l2 * log_nu
        for p in pairs:
            pa, pb, pt = _probs(theta[p.a], theta[p.b], log_nu)
            n = p.wins_a + p.wins_b + p.ties
            if n == 0:
                continue
            # With log P(a wins) = theta_a - log D and
            # d log D / d theta_a = pa + pt/2 (the sqrt tie coupling):
            #   d logL / d theta_a = wins_a + ties/2 - n * (pa + pt/2)
            grad[p.a] += p.wins_a + p.ties / 2 - n * (pa + pt / 2)
            grad[p.b] += p.wins_b + p.ties / 2 - n * (pb + pt / 2)
            # d logL / d log_nu = ties * (1 - pt) - wins * pt
            grad_nu += p.ties * (1 - pt) - (p.wins_a + p.wins_b) * pt
        step = lr / (1 + it / 500)
        for s in systems:
            theta[s] += step * grad[s] / max(len(pairs), 1)
        log_nu += step * grad_nu / max(len(pairs), 1)
        mean = sum(theta.values()) / len(theta)
        for s in systems:
            theta[s] -= mean
    result = BTResult(theta=theta, nu=math.exp(log_nu))
    result.phi = expected_win_rates(result)
    return result


def expected_win_rates(result: BTResult) -> dict[str, float]:
    """phi_i = mean over rivals of P(i beats j) + 0.5 * P(tie)."""
    systems = sorted(result.theta)
    log_nu = math.log(result.nu) if result.nu > 0 else -30.0
    phi: dict[str, float] = {}
    for i in systems:
        if len(systems) == 1:
            phi[i] = 0.5
            continue
        total = 0.0
        for j in systems:
            if i == j:
                continue
            p_i, _, p_t = _probs(result.theta[i], result.theta[j], log_nu)
            total += p_i + 0.5 * p_t
        phi[i] = total / (len(systems) - 1)
    return phi


def composite(
    phi_by_dimension: dict[str, dict[str, float]],
    weights: dict[str, float],
    performability: dict[str, float] | None = None,
) -> dict[str, float]:
    """DRS = P * sum_d w_d * phi_d (DESIGN.md §2). Missing dimensions renormalize."""
    systems = sorted({s for phis in phi_by_dimension.values() for s in phis})
    scores: dict[str, float] = {}
    for s in systems:
        present = [(d, w) for d, w in weights.items() if d in phi_by_dimension and s in phi_by_dimension[d]]
        wsum = sum(w for _, w in present)
        if wsum == 0:
            continue
        core = sum(w * phi_by_dimension[d][s] for d, w in present) / wsum
        p = performability.get(s, 1.0) if performability else 1.0
        scores[s] = core * p
    return scores
