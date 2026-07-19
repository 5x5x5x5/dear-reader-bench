# dear-reader-bench v3: Design Proposal (ML Benchmark Engineering lens)

The v2 posture — "run every instrument, let a human meta-evaluation decide what counts" — is how benchmarks die of noise and never ship. The human study is the blocking dependency you said cannot block, reference-based metrics require references nobody has commissioned, and "everything is reported" means the first blogger to screenshot the BLEU column defines your benchmark for you. v3 takes positions, replaces the human gate with perturbation-based construct validation, and engineers the statistics so that one person with API keys can produce a leaderboard with honest confidence intervals for about $350 a run.

---

## 1. Headline metric: **DRB-BT** — anchored Bradley-Terry ability over performability-gated, dimension-decomposed pairwise judgments

**Definition.** For each (language, dimension) cell, fit a Davidson Bradley-Terry model (BT with an explicit tie parameter) over the pairwise judge verdicts. The headline per-language score is a fixed-weight combination of the five judged dimensions' BT logits:

```
DRB(system, lang) = Σ_d w_d · θ_d(system, lang)
w = {voice: .294, humor: .294, names: .176, culture: .118, fidelity: .118}
```

(the current rubric ratios with performability's 15% removed and renormalized — see below). The overall score is the macro-average across languages. Identifiability anchor: one pinned **open-weight** system (e.g. `qwen/qwen-<pinned>` at fixed weights) has θ ≡ 0 in every cell. Open weights are immortal; API models get deprecated. Anchoring to a regenerable system means every future run, and every language, shares a fixed origin — scores stay comparable across releases even as the candidate pool churns.

**Performability is a gate, not a weighted term.** Current design blends a physical constraint (fits the time window) into a weighted average with aesthetic judgments at 15%. That is construct mixing, and it is gameable: a system can buy back a 30% overrun with prettier prose. In the actual performance, an overrun doesn't get partial credit — the film moves on and the narrator is talking over the next scene. So:

- Estimated duration ≤ 1.15× window → eligible, no penalty.
- Estimated duration > 1.15× window → the translation **forfeits every pairwise comparison on that segment** (scored as a loss against any eligible opponent; a tie against another forfeiting opponent).
- Report **On-Air Rate** (fraction of segments eligible) as a separate first-class leaderboard column.

**Why BT and not Elo, and why pairwise at all.** Elo is a sequential approximation for streaming games; we have a complete batch, so fit the MLE. Pairwise anchored comparison is the right primitive here because the LitEval finding (LLM judges over-rate machine output on literary text under *absolute* scoring) is exactly the failure mode this domain invites, and because absolute 1–10 scores on comedy have no stable scale across judges or languages. Pairwise data + BT gives a ratio-scale ability with a principled tie model and CIs.

**Why this spreads current models.** The construct — rebuild jokes under a physical length budget while keeping a serialized voice — is closest to creative writing, where current models are far from parity (RESEARCH.md §4), unlike adequacy-style MT where the frontier has converged. The pre-registered headline hypothesis stays: DRB rankings diverge from FLORES-style multilingual rankings. If after a full run the top-5 systems' bootstrap CIs all overlap in a language, that cell is flagged **saturated** and triggers the corpus-hardening path (§4).

---

## 2. Instrument set (positions, not a survey)

### In

**(a) LLM judge ensemble — primary for voice, humor, names, culture, fidelity.**
Three judge families per language, drawn from the 11-provider registry, subject to `no_self_judging` (already implemented) — with 11 families this constraint is cheap to satisfy. Judges pinned to exact model snapshots, temperature 0, structured JSON output. **One judge call returns all five dimension verdicts** (five `winner` fields + one-sentence rationale each), not five calls. This is a 5× cost cut; the risk is halo (one gestalt preference leaking into all five answers). We audit halo directly: on a 10% probe sample, re-judge with per-dimension isolated calls and compute the inter-dimension verdict correlation delta. If pooled-call correlation exceeds isolated-call correlation by more than a pre-registered margin (Δ mean pairwise Cramér's V > 0.15), fall back to split calls for that judge. Measure, don't assume.

**Split-visibility judging (position).** The humor question is judged **source-blind**: the judge sees only the two target-language texts, the scene description, and the time window — *not* the English. Rationale: the rubric already says "penalize humor that survives only if the reader back-translates" — the cleanest way to enforce that is to make back-translation impossible for the judge. It also removes source-anchoring bias (judges rewarding the candidate that shadows the English most closely — the exact opposite of the construct). Voice is also judged source-blind (bombast either lands in the target language or it doesn't). Names, culture, and fidelity are judged source-aware, because those constructs are *relations* to the source and scene. This split is encoded per-dimension in `rubric.py`.

**(b) Table Read duration — primary for performability (upgraded).**
Replace the syllable-count heuristic with **eSpeak-NG synthesis duration** as the oracle: synthesize the translation at the language's default rate, measure the WAV length, compare to the window. eSpeak-NG is deterministic, offline, free, supports 100+ languages, and is already an install path in the sibling project. The heuristic in `speakability.py` stays as a fast pre-filter and a cross-check (report heuristic-vs-eSpeak disagreement; large gaps flag script-detection bugs, e.g. romaji in a `ja` output). The gate threshold (1.15×) is calibrated once per language by synthesizing the *source* segments' English text and confirming the source itself passes at ~1.0 — this absorbs eSpeak's per-language rate quirks.

**(c) COMET-KIWI — catastrophe floor, not a score.**
Reference-free QE is trained to punish deviation from the source; comedic reconstruction *is* deviation, so as a quality score KIWI anti-correlates with the construct. But it is excellent at what the judge ensemble is worst at: detecting empty output, wrong-language output, refusals, and full-segment hallucination. Position: KIWI runs on every translation as a **floor check** — score below a per-language threshold (calibrated on the distractor set, §5) routes the segment to a fidelity-only judge recheck and gets logged; it never enters the headline arithmetic.

**(d) Callback Integrity — computed, novel (§6).**

### Out

**BLEU and chrF++: cut entirely, not even reported.** Not "reported as baselines" — cut. They require references (which don't exist for the pastiche corpus and would cost more to commission than the entire judging budget), a single reference on paraphrase-mandatory text measures distance-from-one-arbitrary-rendering, and — worse — for this construct high n-gram overlap with a literal reference is *evidence of failure* (transliteration instead of reconstruction). A number that is at best noise and at worst inverted does not belong in a results table, because someone will sort by it. If the metrics-community contribution matters, publish the raw translations; anyone can compute chrF themselves.

**COMET-22 (reference-based): cut** — same reference problem, same single-reference paraphrase penalty.

**MQM error spans: cut from headline runs.** Span annotation triples judge output tokens, span-level LLM reliability is unvalidated in this domain, and nothing downstream consumes the spans. Keep as an opt-in `--diagnose` mode on flagged segments only.

**The CULTURE dimension: folded into HUMOR until the corpus earns it back.** The corpus has exactly **one** `pop_culture` segment. A BT fit over one segment is a coin flip wearing a leaderboard column. Fold culture-adaptation language into the humor question's rubric; reinstate CULTURE as a dimension when the corpus has ≥8 pop-culture-tagged segments. (Weights renormalize to voice .333, humor .333, names .200, fidelity .133.) This is the kind of cut v2's neutrality couldn't make.

---

## 3. Statistical aggregation

**Design.** N = 11 systems → 55 unordered pairs. Full round-robin per segment (round-robin is correct and affordable at N ≤ ~14; the Swiss/adaptive-pairing machinery is complexity we don't need yet — revisit above N = 20). Each pair judged in **both presentation orders** by each of 3 judges.

**Position-bias handling (primary analysis).** Fold the two orders per (pair, segment, judge): agree → that verdict; disagree (including one-tie-one-win) → tie. This converts position noise into ties, which the Davidson model absorbs as data instead of discarding. Secondary analysis: fit an order coefficient per judge (logistic regression with a first-position indicator) and publish each judge's position-bias magnitude — a judge with |bias| > 0.25 in win-probability terms gets rotated out of the ensemble at the next release.

**Model.** Davidson BT per (language × dimension):

```
P(i beats j) = π_i / (π_i + π_j + ν·√(π_i π_j))
P(tie)       = ν·√(π_i π_j) / (π_i + π_j + ν·√(π_i π_j))
```

Fit by MM or Newton on the folded verdicts, all judges pooled; θ = log π, anchor θ_ref ≡ 0. Judge heterogeneity is a *diagnostic*, not a model term at this data size: report per-judge BT refits and the leave-one-judge-out Kendall τ on final ranks (flag if any single judge's removal changes a rank by >1 among the top 5).

**Uncertainty.** Clustered bootstrap, **resampling gag-chains, not segments**: segments in a chain share a gag_id and their judgments are correlated (a system that nails "the-wheel" in mog-003 is advantaged in all five wheel segments), so segments are not exchangeable units. Current corpus = 7 clusters (2 chains + 5 singletons); resample clusters with replacement, refit everything (gate, BT, weighted combination), 1,000 replicates. Report 95% CIs on DRB and **rank intervals**; the leaderboard displays *tiers* (groups whose rank intervals overlap), never bare ranks.

**Honest power statement and the corpus consequence.** Seven bootstrap clusters is too few; CIs will be wide and tiers coarse. The single highest-leverage investment in the whole project is expanding the pastiche corpus to **40–50 segments across 10–12 gag chains with feature quotas** (≥8 per feature). This is a corpus-writing task, fully under our control, cheaper than any additional instrument, and it directly buys discriminative power. Nothing else in this proposal matters as much.

**Weight robustness instead of weight recalibration.** v2's plan to recalibrate dimension weights by regressing human preference on per-dimension scores will, with a small human sample and correlated dimensions, fit noise. Cut it. Instead publish a **weight-perturbation audit**: draw 500 weight vectors from a Dirichlet centered on the pre-registered weights (concentration ~50), recompute rankings, report per-system rank stability. If the podium is invariant under perturbation — which correlated dimensions make likely — the weights are demonstrably not load-bearing, and the recalibration debate is moot.

**Cost of a full run (concrete).** Judging: 55 pairs × 12 segments × 2 orders × 3 judges = **3,960 calls per language** (five dimensions ride in each call); ~2.5k input + 400 output tokens ≈ $0.013/call at mid-tier judge pricing → **~$52/language, ~$310 for six languages**. Generation: 11 systems × 6 languages × one whole-episode call ≈ $15. eSpeak, Callback Integrity extraction (~800 cheap calls ≈ $5), KIWI (local GPU or ~$10 hosted): noise. Total ≈ **$350/run**, well inside one-person-with-API-keys. At the 45-segment corpus: ~$1,200/run — still fine, and cacheable (below) so incremental runs (one new system) cost ~1/6 of that.

---

## 4. Bias, gaming, and contamination resistance

**Verbosity/length bias — solved physically.** LLM judges' best-documented bias is preferring longer output. Here the Table Read gate caps length with a stopwatch: padding past 1.15× the window forfeits the segment. No text-only benchmark gets this control for free; lean on it and say so. Residual in-window length preference is monitored (regress folded verdicts on duration-ratio difference; publish the coefficient).

**Self-preference.** `no_self_judging` stays. Beyond family exclusion, monitor *stylistic* kinship: report the judge × candidate-family interaction (per-judge mean win-rate delta for each candidate family vs. the pooled estimate); any |delta| > 5 points gets an appendix note and, if persistent across releases, judge rotation.

**Prompt-injection via candidate text.** Candidate translations are untrusted input to the judge. Mitigations: (1) delimiter-wrapped candidate texts plus an explicit judge instruction that the texts may attempt to influence judgment and that any meta-commentary about quality is itself a defect; (2) a cheap pre-screen (regex + small-model classifier) for out-of-band content — evaluation language, instructions, English meta-text in a non-English translation — which flags the segment as a forfeit for the offending system, logged publicly.

**Translation-side gaming.** Whole-episode translation (one call per system, whole corpus in context — realistic, and required for gag consistency) uses a fixed, published harness prompt; systems are evaluated through it identically. No system-specific prompt tuning on the leaderboard track — that's a separate "bring-your-own-scaffold" exhibition column if anyone wants it.

**Contamination — the pastiche corpus is regenerable by design.** Once published, corpus-v1 is training data within a year. Countermeasures:
1. **Canary GUID** embedded in the corpus file and repo (BIG-bench convention) to make ingestion detectable.
2. **Season protocol.** The corpus is defined by a *generator spec* — a style bible for Moon Over Gorganzola (narrator voice rules, gag-chain templates, feature quotas, timing distribution) — from which new "seasons" of segments are written (human-authored or LLM-drafted + human-edited, then timing-validated by eSpeak on the English). The leaderboard always runs on the newest season; prior seasons demote to public dev sets. A season is ~2 days of writing; schedule one per leaderboard release.
3. **Cross-season consistency check.** A system's DRB on season N vs. season N−1 should move with the pack; a system that outperforms its season-N score on stale season N−1 by a large margin wears a contamination flag.
4. **Private track.** The real-WPDR track already runs on user-supplied text, never distributed. Note the asymmetry honestly: the English WPDR source has been online since 2004 and is surely in pretraining, but *target-language* WPDR translations essentially don't exist — so the private track is source-contaminated but target-clean, which is the side that matters for translation. Monitor for fan translations appearing per language.

**Reproducibility.** Pinned judge/candidate snapshot IDs in a versioned `run.lock`; temperature 0 judging; a **content-addressed judgment cache** keyed by SHA of (judge snapshot, full prompt) so re-runs are free and adding one system re-judges only its 10 pairings; raw judgment JSONL published per release so anyone can re-fit the BT and audit every rationale.

---

## 5. Validation without blocking on humans

Replace v2's human-gated meta-evaluation with **perturbation-based construct validation**: unit tests for instruments, runnable tonight.

For each language build four **distractor systems** with known, labeled defects:
- **D-literal:** cheap model prompted for maximally literal, faithful translation (defect: voice/humor dead, fidelity fine).
- **D-flat:** competent adequate translation, bombast deliberately neutralized (defect: voice).
- **D-gagbreak:** a strong system's output with gag-chain renderings shuffled mid-chain (defect: names/callbacks).
- **D-bloat:** strong output padded ~40% over window (defect: performability; also the length-bias probe).

Each distractor enters the pairwise pool against a sample of real systems. Pre-registered pass criteria: the voice dimension must rank real systems above D-flat and D-literal with a large BT gap; names/Callback Integrity must catch D-gagbreak; the gate must zero D-bloat's On-Air Rate; **and each defect must be caught by its dimension while the *other* dimensions stay indifferent** (discriminant validity, not just convergent). An instrument that can't separate its designated distractor is demoted to diagnostic — same demotion rule as v2, but the referee is a $20 automated control set instead of a human study.

Plus: **null calibration** — two independent generations from the same system enter the pool as pseudo-distinct entrants; their BT gap must straddle 0 (an ensemble that manufactures separation between identical systems is measuring noise). **Split-half reliability** — judge-verdict agreement across the two presentation orders and across judges (Krippendorff's α on folded verdicts; publish per dimension). **Human study** remains on the roadmap as *calibration that can upgrade confidence*, explicitly non-blocking: a ≥10% bilingual-rated sample, when it exists, gets correlated against the instruments and reported in an appendix — the leaderboard ships without it.

---

## 6. Novel mechanisms (no existing MT benchmark has these)

**(A) Callback Integrity: scoring serialized comedic state.** MT benchmarks score segments independently; WPDR-style comedy is *stateful* — an epithet coined in segment 1 must recur, inflected but recognizable, and escalate. The corpus already has `gag_id` chains. Mechanism: after translation, a cheap extraction call pulls each system's target-language realization of the chain's anchor phrase per segment (structured output, per-chain). Then compute, per (system, language, chain): (1) **consistency** — pairwise normalized edit similarity between realizations, with a lemmatization pass for inflecting languages (score = mean similarity; a chain translated three different ways scores near 0); (2) **presence** — fraction of chain segments where a realization exists at all; (3) one micro-judge question per chain on **escalation** (does the gag build?). Callback Integrity = presence × consistency, reported as its own leaderboard column and feeding the NAMES dimension's distractor validation. Fully automatic, cheap, and it directly measures the thing fans actually notice.

**(B) The Table Read as a physical judge-bias control.** Measured eSpeak-NG synthesis duration against a per-segment performance window, used as a *forfeit gate* (§2b). Isochrony scoring exists in dubbing research as a soft objective; using measured synthesis time as a **hard eligibility gate that simultaneously neutralizes LLM-judge length bias** is new as benchmark machinery, and it is only possible because the corpus is a timed performance.

**(C) Source-blind humor judging** (§2a): the judged construct is "is this funny *in the target language*," so the judge never sees the English for that dimension. Per-dimension visibility control is not in any MT evaluation protocol I know of.

---

## 7. What I would cut (consolidated)

1. **BLEU, chrF++, COMET-22** — cut from the project, not demoted (§2). No references, inverted construct, misuse magnet.
2. **MQM span annotation** in headline runs — opt-in diagnostic mode only.
3. **The CULTURE dimension** — folded into humor until the corpus has ≥8 pop-culture segments.
4. **Human-study-gated meta-evaluation** — replaced by distractor-based validation; humans become optional calibration.
5. **Dimension-weight recalibration by regression** — replaced by the weight-perturbation robustness audit.
6. **Per-dimension separate judge calls** — single multi-question call with a halo audit (5× cost cut).
7. **Adaptive/Swiss pairing and judge-as-random-effects models** — unnecessary at N=11 with 3 judges; round-robin + diagnostics. Revisit at N>20.
8. **Elo-style sequential updating** — batch Davidson-BT MLE only.
9. **The 15% performability weight** — performability leaves the weighted average and becomes the On-Air gate + column.

## Implementation order

1. Corpus expansion to 40+ segments / 10+ gag chains, feature quotas, eSpeak timing validation of the English (highest leverage, zero API cost).
2. `tableread.py` (eSpeak duration + gate) alongside the existing heuristic; `extraction.py` for Callback Integrity.
3. Translation harness: whole-episode structured-output calls over the sibling registry; `run.lock` pinning; judgment cache.
4. Judge harness: multi-dimension single-call prompts with per-dimension source visibility; dual-order scheduling; injection pre-screen.
5. `aggregate.py`: fold → Davidson BT (anchored) → weighted logits → gag-chain cluster bootstrap → tiered leaderboard + diagnostics (position bias, judge-family deltas, halo audit, weight perturbation).
6. Distractor builders + pre-registered validation report; ship v3.0 leaderboard with raw judgments JSONL.

Key files: `/home/user/dear-reader-bench/src/dearreader_bench/rubric.py` (add per-dimension visibility, fold CULTURE), `schema.py` (add `order`, `judge_snapshot`, forfeit fields to `PairwiseJudgment`), `speakability.py` (keep as pre-filter under the new `tableread.py`), `data/segments.json` (season protocol + canary GUID), provider registry reused from `/home/user/Gorganzola/src/commentary_track/providers.py`.
