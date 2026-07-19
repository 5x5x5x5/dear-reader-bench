import random

from dearreader_bench.btmodel import BTResult, composite, expected_win_rates, fit, tally


def test_tally_folds_orders_and_flips():
    pairs = tally(
        [
            ("x", "y", "a"),   # x wins
            ("y", "x", "a"),   # y wins (flipped pair)
            ("x", "y", "tie"),
        ]
    )
    assert len(pairs) == 1
    p = pairs[0]
    assert (p.a, p.b) == ("x", "y")
    assert p.wins_a == 1 and p.wins_b == 1 and p.ties == 1


def test_fit_recovers_known_ordering():
    # Simulate a clear hierarchy: alpha >> beta >> gamma.
    rng = random.Random(7)
    outcomes = []
    strength = {"alpha": 0.85, "beta": 0.55, "gamma": 0.25}
    names = list(strength)
    for _ in range(400):
        i, j = rng.sample(names, 2)
        p_i = strength[i] / (strength[i] + strength[j])
        r = rng.random()
        if r < 0.1:
            outcomes.append((i, j, "tie"))
        elif rng.random() < p_i:
            outcomes.append((i, j, "a"))
        else:
            outcomes.append((i, j, "b"))
    result = fit(tally(outcomes))
    assert result.theta["alpha"] > result.theta["beta"] > result.theta["gamma"]
    assert abs(sum(result.theta.values())) < 1e-6  # sum-zero identifiability
    assert result.phi["alpha"] > 0.5 > result.phi["gamma"]
    assert all(0.0 < v < 1.0 for v in result.phi.values())


def test_ties_inflate_nu():
    all_ties = tally([("x", "y", "tie")] * 50)
    decisive = tally([("x", "y", "a")] * 25 + [("x", "y", "b")] * 25)
    assert fit(all_ties).nu > fit(decisive).nu


def test_expected_win_rates_single_system():
    assert expected_win_rates(BTResult(theta={"solo": 0.0}, nu=1.0)) == {"solo": 0.5}


def test_composite_applies_weights_and_performability():
    phi = {
        "humor": {"x": 0.8, "y": 0.4},
        "voice": {"x": 0.6, "y": 0.6},
    }
    weights = {"humor": 0.6, "voice": 0.4}
    scores = composite(phi, weights, performability={"x": 1.0, "y": 1.0})
    assert scores["x"] > scores["y"]
    # Performability multiplies: a padding system loses headline score.
    padded = composite(phi, weights, performability={"x": 0.5, "y": 1.0})
    assert padded["x"] < scores["x"]
    assert padded["y"] == scores["y"]


def test_composite_renormalizes_missing_dimensions():
    phi = {"humor": {"x": 0.7}}
    scores = composite(phi, {"humor": 0.35, "voice": 0.30})
    assert abs(scores["x"] - 0.7) < 1e-9
