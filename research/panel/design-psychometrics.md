# dear-reader-bench v3: A Psychometric Design

*Design proposal, measurement-theory lens. Builds on v1 (editorial/judge-centric) and v2 (neutral run-everything-meta-evaluate); supersedes both.*

## 0. Why v1 and v2 both fail as measurement, and the v3 principle

**v1's failure mode** was validity by authority: instruments chosen by taste, weights asserted, no reliability apparatus. A judge-centric benchmark with no evidence that the judge measures anything is an opinion with error bars omitted.

**v2's failure mode** is subtler and worth naming precisely: it treats instrument validity as a *purely* empirical question to be settled by a human meta-evaluation — while the project constraints say human studies cannot be a blocking dependency. The result is a benchmark that, in practice, reports a pile of unendorsed numbers indefinitely. That is not neutrality. Readers anchor on the familiar metric, and the most familiar metric here (BLEU) is the one that construct logic already tells us is *negatively* aligned with the target construct. **Neutrality is false balance when the balanced options are known a priori to differ in validity.** You do not need a human study to know a thermometer is not a barometer; you need one to calibrate the thermometer.

**v3 principle:** validity is an argument, not a vote. The argument has three legs, none of which requires a blocking human study:

1. **Construct logic** decides inclusion/exclusion up front (taking positions, documented).
2. **Reliability and validity evidence collected automatically every release** — position-swap consistency, inter-judge agreement, split-half reliability, a known-groups probe battery, convergent/discriminant checks — bounds how wrong the instruments can be.
3. **Pre-registration** (a frozen, hashed `PREREGISTRATION.md` per release) makes the argument auditable and prevents post-hoc retuning. Human data, if it ever arrives, slots into a pre-registered upgrade protocol; it is a criterion study, not a gate.

---

## 1. The construct, and the headline metric

### 1.1 Construct definition (do this first, everything follows)

The target construct is **performed-comedy translation quality**: *the degree to which a target-language rendition would succeed as this performance — funny, in voice, coherent as a gag structure, and actually deliverable aloud in its time windows — for a native audience of the target language watching the same film.*

Three structural commitments follow directly from this definition, and each has aggregation consequences:

- **The construct is formative, not reflective.** Voice, humor, names, culture, fidelity are *components* that constitute quality; they are not interchangeable indicators of one latent factor. Humor and scene fidelity can trade off. Consequence: Cronbach's alpha *across dimensions* is meaningless and must not be reported as "internal consistency of the benchmark" (a classic formative-construct error). Each component needs its own validity case, and the composite needs a defensible weight source (§3.4). Reliability lives elsewhere: across *replications* of the measurement — segments and judges (§5.1).
- **The construct is non-compensatory in performability.** A rendition that cannot be spoken in its window has zero value as a performance no matter how funny it reads. Additive weighting (v1's 15%) gets this wrong: it lets a brilliant-but-unspeakable rendition outrank a speakable good one. Performability must enter as a **gate**, not a weight. Principled line: **only computed constructs may gate; judged constructs may only weight** — a gate amplifies whatever noise its instrument carries, and only `speakability.py` is fully specified with no validity question.
- **The construct is audience-sided.** The target audience never hears the English. This drives the single biggest instrument-design decision in v3: **source-blind judging** for audience-experience dimensions (§2.2).

### 1.2 Headline metric: DRS (Dear-Reader Score)

**DRS(system, language) = Σ_d w_d · φ_d**, computed over performability-gated pairwise comparisons, where:

- **φ_d** = the system's expected win probability against the field on dimension *d*, derived from a Bradley–Terry–Davidson ability fit to pairwise judge verdicts (§3.3). φ is on [0,1] with a fixed operational meaning across dimensions — this solves the scale-incommensurability problem that sinks naive averaging of per-dimension scores.
- **w** = pre-registered formative weights: voice 0.30, humor 0.30, names 0.15, culture 0.10, fidelity 0.15. (Performability's old 0.15 is redistributed because it is now a gate; mean speakability is still reported as its own leaderboard column.)
- **Gate:** a rendition with estimated-duration ratio ≥ 1.25 of its window **forfeits that segment's comparisons on every dimension** (both sides over → tie). Below 1.25, no penalty inside DRS; the continuous `performability_score` is reported alongside. The 1.25 threshold respects the estimator's stated coarseness ("good enough to flag 20%+ overruns").

**The operational sentence every DRS ships with:** *"DRS 0.62 in Japanese means: on a random segment against a random rival system, this system's rendition is expected to win the composite performed-comedy comparison 62% of the time, after forfeiting unperformable segments."*

Why a gated pairwise win-probability composite and not (a) v1's weighted absolute rubric scores, (b) v2's to-be-determined empirical composite, or (c) a single holistic pairwise question?

- (a) Absolute LLM scoring on literary text is the documented failure mode (LitEval); pairwise judging also makes judge severity/leniency — the largest rater main effect — cancel by construction.
- (b) Is blocked on humans, per above.
- (c) A single holistic question maximizes the fluency-bias and halo surface; narrow questions (LiTransProQA shape, already in `rubric.py`) are the right stimulus. The composite is assembled *after* measurement, transparently, from components whose individual meanings survive.

Cross-language headline: macro-average over a pre-registered slate of 6 core languages spanning scripts and resource levels (de, es, ja, zh, ko, hi). Per-language DRS is primary; the macro-average is a convenience number and is labeled as such.

---

## 2. Instrument set: positions, with construct-validity rationale

| Instrument | Construct it actually measures | Verdict | Rationale |
|---|---|---|---|
| LLM judge ensemble, anchored pairwise, narrow questions, **source-blind** | Predicted target-audience preference on voice/humor/names/culture; scene-match on fidelity | **Primary** for the five judged dimensions | Only instrument whose stimulus can even contain the construct: scene, time window, gag context. Reliability measured every release (§5.1); validity bounded by probe battery (§5.2) |
| `speakability.py` (computed) | Isochrony — fits the window | **Primary** for performability; **gate** on DRS | Fully specified construct, no model opinion; calibrated against TTS criterion (§5.5) |
| **Callback Ledger** (new; computed extraction + within-system contrast) | Gag-arc integrity: referential consistency + payoff lift | **Primary** for the consistency half of names/running-gags | §6. Cross-segment comedy structure is invisible to every per-segment instrument |
| COMET-KIWI (reference-free) | Semantic adequacy, WMT-domain-trained | **Diagnostic only** | Legitimate convergent/discriminant witness for fidelity (§5.3) and an anomaly detector (KIWI floor + judge-fidelity pass → inspect). Never in DRS: its training domain contains no register or humor signal, and adequacy is deliberately violated by good adaptation |
| chrF++ | Surface overlap with a single reference | **Appendix-only, as a discriminant-validity witness** | Pre-registered prediction: chrF++ correlates ≈ 0 or negative with DRS on pun/pop-culture segments. Publishing it *as that prediction's test* converts a misleading number into a validity exhibit |
| BLEU | Surface overlap, worse | **Excluded entirely** | On a paraphrase-*mandatory* construct with one reference, overlap measures imitation of one comedian's solution — negatively aligned with the humor and culture components. Reporting it "as a baseline" is the false-balance trap v2 fell into |
| COMET-22 (reference-based) | Adequacy vs. references we don't have | **Excluded** | Would require commissioning reference translations per language; single-reference paraphrase penalty; KIWI covers the diagnostic need |
| MQM error spans | Adequacy-oriented error taxonomy | **Cut** (§7) | The taxonomy's core categories (accuracy/mistranslation) label as errors exactly what this construct requires (deliberate departure). An instrument whose ontology contradicts the construct produces confidently wrong diagnostics |
| Bilingual human raters | The criterion | **Optional upgrade path, never a gate** | Pre-registered slot-in protocol (§5.6) |

### 2.2 Position: source-blind judging for audience-experience dimensions

The current `pairwise_prompt` shows the judge the English source. For voice, humor, names, and culture, this is a **contaminated stimulus**: the audience-experience construct is defined over the target text alone, and showing the source (a) anchors judges on the source's specific solutions, rewarding literal proximity — the documented direction of LLM-judge bias, (b) lets "funny if you back-translate" leak in through the judge itself, the exact failure the humor question tries to penalize.

v3 judges voice/humor/names/culture on: target text A, target text B, scene description, time window, target-language gag context from earlier segments, and a genre brief ("bombastic alternate-audio narration performance") — **no English source**. Fidelity needs no source either: the rubric already defines it against the *scene*, which `schema.py` carries independently. The humor question drops its back-translation clause (the judge can't back-translate what it can't see) and instead penalizes "wordplay that reads as residue of another language."

Acknowledged limitation, accepted deliberately: source-blind judges cannot detect *omission* of source material. That is the correct trade — the construct is performance quality, not completeness, and scene fidelity plus the window gate bound how much a system can get away with by cutting. A source-aware "adaptation audit" remains available as an offline diagnostic, outside DRS.

---

## 3. Statistical aggregation

### 3.1 Comparison design and budget

With ~11 systems, full round-robin is 55 pairs. Per language: 55 pairs × 12 segments × 3 judges × 2 presentation orders = **3,960 judge calls**, using one composite call per (pair, segment, judge, order) that asks all five narrow questions in randomized order and returns five winners. At 60 segments (§3.5) this is ~20k calls/language — still one-person-runnable; if budget binds, drop to an incomplete design (each segment gets a random connected subset of ~25 pairs) and let the BT model interpolate, which is precisely what BT is for.

The multi-question single call trades cost against halo (common-method variance across dimensions). We take the trade and **quantify the halo**: a pre-registered 5% subsample is re-judged with isolated single-dimension calls; the inter-dimension correlation inflation between conditions is reported as a method-effect statistic each release.

### 3.2 Verdict aggregation

Per (pair, segment, judge): the two presentation orders must agree per dimension, else that judge's verdict for that dimension is recorded as a tie (position-inconsistency is measured noise, not signal). Per (pair, segment, dimension): majority across the 3 judges; ties propagate as ties.

Judge slate per pair: 3 provider families drawn from the registry, excluding both candidates' families (`no_self_judging` generalized to the pair). With 11 families this always has slack.

### 3.3 Model

Per (language, dimension): fit a **Bradley–Terry–Davidson** model (BT with a tie parameter) by penalized MLE (light L2, sum-zero identifiability) on the aggregated pair-segment outcomes, after applying the performability forfeit rule. Report each system's ability as **φ_d = mean over rivals of P(beat rival)** — the "win probability vs. the field," a bounded, interpretable quantity commensurable across dimensions.

**Uncertainty:** cluster bootstrap, B = 1000, resampling **segments** (the dominant variance facet) and judges jointly; refit BT per replicate; report 95% CIs on φ_d and on DRS. The leaderboard displays **rank ranges**, not point ranks; two systems are "separated" only when paired-bootstrap DRS differences exclude zero. With 12 segments the CIs will be honest and wide — that is a feature, and the argument for §3.5.

### 3.4 Weights: pre-registered, sensitivity-analyzed, never regressed

v2's plan to recalibrate weights by regressing human preference on dimension scores is cut: at any affordable human sample (10% of 12 segments!) the regression is hopelessly underpowered and would launder noise as calibration. Instead: weights are pre-registered priors, and every release reports a **weight-sensitivity analysis** — draw 1000 weight vectors from a Dirichlet centered on the registered weights (concentration chosen so components vary roughly ±50% relative), recompute DRS, report the fraction of leaderboard pairs whose ordering is invariant. If rankings are robust (historically likely, since dimension scores correlate positively across systems), the weight debate is empirically moot and the report says so with a number. If a specific pair flips under plausible weights, the leaderboard flags it as weight-sensitive rather than pretending to a precision the composite doesn't have.

### 3.5 Generalizability theory: how big must the corpus be?

Run a **G-study** each release: variance decomposition of pair outcomes into system, segment, judge, and interaction components (mixed model). Then a **D-study** projects the generalizability coefficient Eρ² of DRS as a function of segment count. Release criterion: Eρ² ≥ 0.80 for the headline. Twelve segments will not reach it; the D-study turns "we should write more pastiche" into a quantified target (expect ~40–60 segments, i.e. 3–5 pastiche films). Corpus expansion follows a **content-validity blueprint**: every `Feature` appears in ≥ 8 segments, every gag arc has ≥ 3 segments including a payoff, register shifts appear in both directions. This is test-blueprint construction, standard psychometrics, absent from every MT benchmark.

---

## 4. Bias, gaming, and contamination resistance

- **Position bias:** both orders always run; disagreement degrades to tie (§3.2). Position-swap consistency is a published per-judge reliability stat, and a judge model falling below 60% consistency on any dimension is dropped from the slate (pre-registered rule).
- **Self-preference and family-style preference:** no-self-judging is kept; additionally publish a **judge-deviation heatmap** — each judge's per-system win-rate delta vs. the ensemble consensus. A judge that systematically favors one family (even not its own — stylistic kinship is real) is visible, and a pre-registered deviation threshold triggers exclusion for that (judge, system-family) cell.
- **Verbosity/length bias:** the performability gate structurally punishes padding — the classic LLM-judge exploit is made self-defeating by the construct itself. Residual check: per-dimension correlation of wins with character length among *gate-passing* renditions, reported as a bias audit.
- **Style-token stuffing (gaming the rubric):** the judge prompts are public; a system could stuff bombast markers. Defenses: (a) the probe battery (§5.2) includes a stuffed-but-hollow probe (P-FLAT's inverse: bombast markers pasted onto flat content) once per release to verify judges aren't fooled; (b) corpus rotation (below) invalidates memorized solutions; (c) narrow questions mean gaming must succeed on five orthogonal fronts plus a computed gate.
- **Contamination:** the public pastiche corpus will enter pretraining the moment it's on GitHub. Mitigations: (a) a **canary GUID** embedded in the corpus file (BIG-bench convention) so training-set membership is detectable; (b) **corpus versioning** — each major release adds a new pastiche film; the headline is reported on the newest corpus, older ones become practice tracks; (c) the contamination asymmetry is documented honestly: for *translation* benchmarks, source-side memorization matters far less than target-side — and no target-language solutions for the pastiche exist anywhere until systems produce them. Note the inversion on the private track: real WPDR's *English* is thoroughly in pretraining (fan transcripts), but published translations of it essentially don't exist, so the private track is target-side clean too.
- **Protocol standardization (a gaming surface people miss):** systems receive the full segment sequence in order with scene descriptions and windows — document-level translation, pre-registered as *the* condition. No per-system prompt tuning; the harness prompt is versioned and frozen per release. No glossary side-channel (letting systems emit a name glossary would change the construct and invite output-formatting games).

---

## 5. Validation without blocking on humans

This is the heart of the psychometric case: a standing, automated **instrument health panel**, re-run and published with every release.

### 5.1 Reliability (necessary for validity, fully measurable for free)

- **Position-swap consistency** per judge per dimension (already have both orders; zero extra cost).
- **Inter-judge agreement:** Krippendorff's α over the 3-judge verdicts per dimension. Pre-registered floor: α ≥ 0.35 (pairwise comedy judgments are noisy; the composite's reliability comes from aggregation, and the G-study quantifies exactly how much). A dimension below floor is flagged "unreliable this release" and reported outside DRS with DRS recomputed both ways.
- **Split-half reliability of system scores:** random segment halves, correlate per-dimension φ across halves, Spearman-Brown correct. This answers "does a system's voice advantage replicate across material?" — the *correct* internal-consistency question for this design (across replications, not across formative components; see §1.1).
- **Judge test-retest:** re-run a 5% subsample at the same settings; verdict self-agreement per judge.

### 5.2 Known-groups validity: the probe battery (the workhorse)

Construct **validity probes** — deliberately degraded renditions with known, labeled defects, generated by template edits and LLM rewrites of a strong system's translations, entered into pairwise comparison against their unedited parents:

| Probe | Injected defect | Must lose on | Must NOT lose on |
|---|---|---|---|
| P-LIT | puns rendered word-for-word | humor | fidelity, voice |
| P-FLAT | register flattened to neutral prose | voice | fidelity, names |
| P-LONG | padded to ~1.5× window | (caught by computed gate — tests the estimator end-to-end) | — |
| P-INCON | gag/epithet renderings swapped mid-corpus | names + Callback Ledger | humor per-segment |
| P-GLOSS | references footnote-explained | culture | fidelity |
| P-WRONG | described events altered | fidelity | voice, humor |

Publish the resulting **sensitivity/specificity matrix** (probe × dimension) each release. Pre-registered pass bar: ≥ 80% loss rate on the target dimension, ≤ chance + 10 points off-target. A dimension failing sensitivity is demoted from DRS *by its own pre-registered rule* — this is the non-human replacement for v2's human meta-evaluation gate, and it doubles as a regression test whenever judge models rotate. No human ever touches it.

### 5.3 Convergent/discriminant matrix (mini-MTMM)

Pre-registered predictions, tested on every full run: fidelity-judge ↔ COMET-KIWI moderately positive (convergent — both see adequacy); humor-judge ↔ chrF++ ≈ 0 or negative on pun-tagged segments (discriminant — the construct mandates divergence); humor winners are *less* lexically overlapping with source on pun segments (direction-of-effect check); performability ↔ length trivially high (sanity). Deviations are findings, not embarrassments — e.g., humor ↔ chrF++ strongly positive would indicate judges rewarding literalness and trigger investigation.

### 5.4 Internal structure

Inter-dimension correlations of φ across systems, per language. Pre-registered collapse rule: if culture ↔ humor r > 0.9 across two consecutive releases, culture folds into humor (its weight transfers) — discriminant validity between subscales is an empirical property we test, not an org chart we defend.

### 5.5 Criterion validity for speakability, via TTS

The one instrument that gates DRS gets a criterion study that costs a few dollars: synthesize ~100 translated segments per script family with a neural TTS API, measure audio durations, correlate with `estimate_seconds`. Target Pearson r ≥ 0.9 within script family; below that, refit the rate constants (`_CJK_RATES`, `_SYLLABLES_PER_SECOND`) on the TTS data. TTS pace is not performance pace, but the gate needs correct *ordering and ratios*, which this validates. One person, one afternoon, no humans.

### 5.6 Humans as upgrade, never as gate

`PREREGISTRATION.md` carries a frozen protocol for the day human data exists: bilingual raters, ≥10% segment sample, same pairwise instrument, segment-level Kendall's τ per instrument against human verdicts, pre-registered demotion thresholds — v2's meta-evaluation, verbatim, minus its blocking role. Until then the validity case is §5.1–5.5, stated plainly in the report: *"DRS is validated by reliability, known-groups, and convergent/discriminant evidence; human criterion validity is pending."* That sentence is honest and shippable. v2's alternative — no headline until humans arrive — is neither.

---

## 6. Novel mechanism: the Callback Ledger

No existing MT benchmark measures **cross-segment comedic structure** — WMT is sentence/paragraph scoped; document-level MT work checks pronoun and lexical cohesion, not whether a *gag arc* survives translation. WPDR-style narration lives on running gags: an epithet coined in segment 1 must recur, mutate deliberately, and pay off. The corpus already encodes this (`gag_id`, `running_gag`); nothing yet measures it. The Callback Ledger has two halves, chosen so their error structures are independent:

**(a) Referential consistency — computed.** For each `gag_id`, an extractor model performs a narrow, high-reliability task: identify the target-language rendering of the tagged gag token in each of its segments (extraction, not judgment — validated by double extraction with two provider families, agreement reported as a reliability stat). Consistency score = mean pairwise normalized edit similarity of renderings within the arc, with a pre-registered allowance for grammatically forced variation (case marking, particles). Being computed, it may enter mechanically: it contributes 40% of the names dimension score (judged naturalness/comedy of names is the other 60%), and P-INCON in the probe battery verifies its sensitivity end-to-end.

**(b) Payoff lift — a judge-bias-cancelling difference score.** The final segment of each gag arc (e.g., mog-011's "it is a wheel. It has always been a wheel.") is judged for humor twice: once with the system's *own translated setup segments* as context, once standalone. **Payoff lift = P(win | context) − P(win | no context)**, estimated within-system. A translation whose gag pays off gains from context; one that translated each segment locally, however fluently, shows no lift. The psychometric point is the design: as a within-system, within-judge difference score, every judge main effect — severity, fluency bias, family preference — subtracts out. It is the closest thing to a randomized experiment this benchmark contains, and it operationally defines "the running gag works in translation," a construct no per-segment instrument can see. Payoff lift is reported as its own leaderboard column (not folded into DRS in v3.0; folding in is a pre-registered candidate change for v3.1 once its split-half reliability is known).

---

## 7. What I would cut

1. **BLEU** — entirely, including "as a baseline." Negatively aligned with the construct; its only function is to mislead the skimming reader. (chrF++ survives only in the appendix, reframed as a discriminant-validity witness with a pre-registered null/negative prediction.)
2. **COMET-22 reference-based** — requires commissioning references per language for a paraphrase-mandatory corpus; KIWI covers the diagnostic role.
3. **MQM error spans** — an adequacy ontology applied to a construct that rewards deliberate inadequacy; produces confidently wrong diagnostics at real cost.
4. **The human-gated meta-evaluation as the arbiter of the headline** — replaced by the probe battery + reliability panel (automated) with humans as a pre-registered upgrade (§5.6).
5. **Weight recalibration by regressing human preference** (old roadmap step 6) — underpowered at any plausible sample; replaced by the Dirichlet weight-sensitivity analysis, which answers the question people actually have (do the weights matter?) with data we can afford.
6. **Judge rationale mining at scale** — keep the one-sentence rationale field for spot-audits; any systematic analysis of rationales measures judge rhetoric, not translation quality.
7. **Live/continuous leaderboard updates** — batch releases only, each with frozen judges, frozen prompts, frozen corpus version, and its own health panel. An Elo that drifts as judges silently update is a reliability disaster.
8. **A sixth judged dimension for performability nuance** (prosody, breath placement) — tempting, unspecifiable, and the duration gate captures the load-bearing part. Revisit only if TTS-based phrasing analysis becomes trivially cheap.

---

## 8. Implementation map

New modules under `src/dearreader_bench/`: `pairs.py` (comparison scheduler: round-robin or connected random subset, judge-slate assignment with pair-family exclusion, order duplication); `btmodel.py` (Davidson BT, penalized MLE, φ computation, cluster bootstrap); `ledger.py` (gag extraction, double-extraction agreement, consistency scoring, payoff-lift contrast scheduling); `probes.py` (battery generation from templates + LLM edits, expectation matrix, sensitivity/specificity report); `health.py` (position-swap, Krippendorff α, split-half/Spearman-Brown, G-study variance components, D-study projection, judge-deviation heatmap); `report.py` (leaderboard with rank ranges, operational sentences, health panel, weight-sensitivity).

Changes to existing files: `rubric.py` — source-blind prompt variant (drop `segment.text` from audience-side dimensions; genre brief added; humor question's back-translation clause replaced), multi-question composite call with randomized question order; `schema.py` — `JudgeCall` (order, judge, per-dimension winners), `ProbeSpec`, `GagRendering`; `speakability.py` — unchanged logic, plus a `calibrate/` script implementing the TTS criterion fit. Corpus: add canary GUID; expand per the content blueprint (§3.5).

New top-level file: `PREREGISTRATION.md`, hashed and referenced from every release report, containing: judge model IDs and prompt hashes; weights; gate threshold (1.25); tie rules; reliability floors (position-swap 60%, α 0.35, probe sensitivity 80%/specificity chance+10); collapse rule (r > 0.9 twice); language slate; the human-study slot-in protocol; and the rule that any change to any of these bumps the major version.

**Release checklist:** freeze → translate (document-level protocol) → gate → judge (both orders) → fit BT → health panel → probe battery → publish DRS with CIs, rank ranges, operational sentences, and the validity appendix. If the health panel fails a pre-registered floor, the release ships with the affected dimension quarantined — the benchmark's willingness to demote its own instruments in public is what makes its headline number worth trusting.