# dear-reader-bench v3 — Joke Survival, Measured Behaviorally

**Lens:** humor research + computational humor. A joke is not a sentence with a "funny" property; it is a small machine with parts — a script opposition, a logical mechanism, a punchline placed at a moment, a register contrast that powers it. Translation either rebuilds that machine in the target language or it doesn't. The benchmark's job is to test whether the machine *runs*, and it can do that without ever asking a model "is this funny?" — a question LLM judges answer badly (LitEval's machine-preference bias) and that humans answer only in aggregate. v1 asked judges for opinions; v2 deferred every validity question to a human study that the constraints say cannot block. v3's move: **replace opinion with behavior.** Every core instrument is a probe whose pass/fail condition is defined before any model opines.

---

## 1. Headline metric: Joke Survival Rate (JSR)

**JSR = the fraction of source-annotated comic units that survive translation as functional objects**, where survival is a conjunction of four behavioral gates (defined in §2): the joke is *findable* by a source-blind native-language probe at the mapped position, *functional* (incongruous yet resolvable — the incongruity-resolution signature is intact), *mechanically legitimate* (same comic mechanism, or a sanctioned substitution for non-portable jokes), and *deliverable* (lands inside the segment's time window with the punchline where a performer needs it).

Headline: **JSR@strict per (system, language)** — e.g. "GPT-5.6 preserves 71% of jokes into Japanese; Claude Opus preserves 84%."

Why this and not a weighted composite:

1. **It is the construct.** The benchmark's premise is "can a model move a *performance*." The unit of a comedic performance is the laugh. Voice, names, culture, timing are *means*; the laugh landing is the *end*. A headline metric should measure the end.
2. **It is interpretable and decomposable.** A percentage of jokes that survive is legible to outsiders in a way "0.73 composite" never is, and every dead joke has an autopsy (§2.7): died-by-literalism, died-by-explanation, died-by-flattening, died-by-timing, died-by-inconsistency. The leaderboard tells you not just who wins but *how jokes die per language* — that is a research contribution, not just a ranking.
3. **It dodges the judge-bias trap.** No probe is ever asked for a preference or a funniness score. Probes do detection, explanation, prediction, and classification — tasks with checkable answers against pre-registered joke annotations. LitEval's finding (judges prefer machine output on literary text) attacks preference judgments; it has no purchase on "mark the spans where the audience laughs, then explain the joke in your own language."
4. **It is binary at the joke level on purpose.** Partial credit hides deaths. A joke that is 60% intact is dead — nobody half-laughs on schedule. Graded sub-scores exist as diagnostics; the headline is strict.

JSR is reported alongside two mandatory context numbers so it cannot be gamed in isolation: **Spurious Joke Rate** (comic loci detected in the translation with no source counterpart — anti-stuffing, §4) and **Fidelity Floor** (scene-fidelity pass rate — the narration must still describe the film).

---

## 2. Instrument set

### 2.0 The annotation layer: Joke Cards (one-time, human, cheap)

Every instrument below keys off a per-joke annotation the maintainer writes once. Extend `schema.py`:

```python
class Mechanism(str, Enum):
    EXAGGERATION = "exaggeration"          # "destiny is enormous"
    ANTICLIMAX = "anticlimax"              # pattern-break list: "unasked, total, and carrying a lantern"
    PERSONIFICATION = "personification"    # "stands in it like a government"
    LITERALIZATION = "literalization"      # metaphor taken literally
    REGISTER_CRASH = "register_crash"      # bombast → mundane or reverse
    FALSE_PRECISION = "false_precision"    # "a low B-flat ... the note of unfinished business"
    PSEUDO_AUTHORITY = "pseudo_authority"  # "as any scholar will tell you"
    CALLBACK = "callback"                  # running-gag reactivation
    WORDPLAY = "wordplay"                  # pun; NON-PORTABLE by definition
    CATEGORY_ERROR = "category_error"      # "buried three husbands, two of them deceased"
    UNDERSTATEMENT = "understatement"
    ABSURD_SIMILE = "absurd_simile"        # "like an avalanche apologizing"

class JokeCard(BaseModel):
    joke_id: str
    segment_id: str
    setup_span: str          # verbatim source span
    punchline_span: str      # verbatim source span — the laugh trigger
    locus_ratio: float       # punchline end as fraction of segment's estimated spoken time
    mechanism: Mechanism
    script_opposition: tuple[str, str]   # e.g. ("NATURAL_DISASTER", "AUNT")
    portable: bool           # can the mechanism be rebuilt without language-specific material?
    gag_id: str | None
```

The 12-segment corpus yields ~30 joke cards; a day of work. GTVH (Attardo & Raskin) is the theoretical warrant: of the six Knowledge Resources, translation should preserve the top of the hierarchy — script opposition and logical mechanism — while language and narrative strategy are free to change. That is exactly what the cards encode and what the probes test. `locus_ratio` is computed with the existing `speakability.estimate_seconds` applied clause-by-clause — position is measured in *performed seconds*, not characters, which is what makes loci comparable across scripts and word orders.

### 2.1 Cold-Open Comprehension Probe (Gate F — findable) — INCLUDE

A probe model receives **only the target-language text** — no English source, no mention that it is a translation. System prompt: "You are a native speaker of {lang} reading the transcript of a comedic spoken performance. Mark every span where the audience is expected to laugh, and for each, explain the joke — in {lang}." Output: JSON spans + explanations.

Scoring is mechanical: a source joke is *found* if the probe marks a span whose performed-time position (via `estimate_seconds`) falls within ±15% of the card's `locus_ratio`. Run with 3 probe models from distinct provider families (no-self-probing, reusing `no_self_judging`); found = majority.

**Construct validity:** this operationalizes the rubric's best line — "penalize humor that survives only if the reader back-translates to English" — as a behavioral test instead of an instruction to a judge. A joke that exists only in English is invisible to a source-blind reader; the probe *is* that reader, imperfectly but checkably. The **detection asymmetry corollary** is a free second signal: re-run the probe *with* the English source attached; jokes explicable only with the source attached are certified dead-on-arrival translationese.

### 2.2 Mechanism-Equivalence Probe (Gate M — mechanically legitimate) — INCLUDE

For each found joke, a second source-blind call: the probe classifies the target-language span into the closed `Mechanism` taxonomy and names the two clashing scripts. Match rules:

- `portable=True` jokes: probe's mechanism must equal the card's mechanism (or an adjacency-listed neighbor — e.g. EXAGGERATION↔FALSE_PRECISION), and script opposition must match semantically (multilingual embedding cosine ≥ 0.6 against the card's opposition labels, adjudicated by a third cheap model only on the embedding gray zone 0.5–0.7).
- `portable=False` jokes (puns): **any** legal mechanism passes. The survival criterion for a pun is "a joke exists at that locus," not "the same pun exists" — this is the professional norm in humor translation (Delabastita's pun-translation strategies: pun→pun, pun→other-rhetorical-device are both success; pun→literal-gloss is failure). The substitution *rate* is reported as a diagnostic per language.

**Construct validity:** closed-set classification against a pre-registered answer is a task LLMs do reliably and that is auditable joke-by-joke. It directly measures the GTVH claim that mechanism, not wording, is what translation must carry. No existing MT metric even has a slot for this.

### 2.3 Setup–Punchline Predictability Contrast (Gate I — incongruity intact) — INCLUDE. **This is the flagship novel mechanism (§6).**

Incongruity-resolution theory (Suls; Attardo) says a punchline must be (a) *unpredictable* from the setup and (b) *coherent in hindsight*. Both halves are measurable without opinions:

- **Unpredictability:** truncate the translation at the last clause boundary before the punchline locus. Sample n=8 continuations at temperature 1.0 from 2 probe models. Embed continuations and the actual punchline with a locally-run multilingual embedder (BGE-M3 — free, offline, provider-neutral). `predictability = mean(top-3 cosine similarities)`. A live joke scores low. A joke that has been *explained* — the classic translator failure, and the classic way to fool a comprehension probe — becomes predictable and scores high. Gate: `predictability_target ≤ predictability_source + 0.10` (source predictability computed once, same procedure, English).
- **Hindsight coherence:** show the full segment, ask 3 probes (source-blind, in-language): "is the marked span interpretable as intentional within this text — yes/no?" Majority yes required. This filters the failure mode unpredictability alone would reward: word salad. High surprise + no resolution is noise, not comedy.

**Construct validity:** this is the incongruity-resolution signature measured directly — the first MT instrument I know of that tests a joke's *information structure* rather than its wording or its judged quality. It is also the anti-explanation weapon: explanation kills unpredictability, literalism kills hindsight coherence, and neither can be prompted around because the test is the model-population's actual predictive behavior.

### 2.4 Delivery suite (Gate D — deliverable) — INCLUDE, extending `speakability.py`

Three computed sub-checks, no model judgment beyond locus detection already done:

1. **Isochrony** — existing `performability_score`, gate at ≥ 0.8.
2. **Punchline placement** — performed-seconds position of the translated punchline vs the card's `locus_ratio`, tolerance ±15% of the window. Verb-final syntax (ja, ko, de subordinate clauses) genuinely displaces punchlines; measuring it per language is a publishable finding, not noise.
3. **Laugh room** — estimated spoken material *after* the final punchline ≤ 2.0s beyond what the source carries. Trailing matter after the laugh is dead air in performance; no MT benchmark has ever measured it.

**Construct validity:** timing is constitutive of performed comedy, not decoration. All three are fully specified constructs — the "no validity question arises" property RESEARCH.md correctly claims for isochrony now covers *where the funny lands*, not just whether the text fits.

### 2.5 Register Trajectory & Flattening Index — INCLUDE (diagnostic axis, feeds autopsies)

WPDR's engine is register whiplash. Split source and translation into clauses; one cheap model tags each clause 1–7 on a fixed-anchor register scale (7 = liturgical/epic … 1 = vulgar/mundane), three repetitions, median. Compute per-segment: dynamic range, shift count (|Δ|≥3), and DTW alignment of the two trajectories. **Flattening Index = 1 − (target range / source range)**, clipped to [0,1]. Segments tagged `register_shift` must show a shift within ±15% performed-time of the source shift, or any joke whose mechanism is REGISTER_CRASH fails Gate M.

**Construct validity:** register humor (Attardo 1994) is incongruity between *styles*, and style level is a taggable property of each clause independent of humor judgment. This instrument replaces the VOICE pairwise judge: "grandiose bombast survives" ≈ "sustained high register with intact crash amplitude," measured, not opined. What it loses vs a judge (idiolect, rhythm) is real but small next to what it gains (auditability, no preference bias).

### 2.6 Gag Ledger — INCLUDE (corpus-level, mostly deterministic)

Per `gag_id`, extract each segment's rendering of the gag token (the Wheel, the pants, Grandmother-the-knife) — one extraction call per segment — then deterministic checks: (a) **consistency**: same lemma/rendering across all instances (edit-distance tolerance for inflection); (b) **callback integrity**: CALLBACK-mechanism jokes fail Gate M automatically if the referenced rendering differs from its antecedent. Document-level referential coherence across timed segments is invisible to every sentence-level MT metric; here it is three string comparisons.

### 2.7 Joke autopsy — INCLUDE (replaces MQM spans)

Every dead joke gets a cause from a closed taxonomy, assigned mechanically from which gate failed and how: **died-by-literalism** (found w/ source attached only), **died-by-explanation** (predictability spike), **died-by-flattening** (register range collapse on a REGISTER_CRASH joke), **died-by-timing** (Gate D), **died-by-inconsistency** (Gag Ledger). MQM's error categories (accuracy/fluency/terminology) were built for adequacy failures and have no cell for "the punchline arrived early"; the autopsy taxonomy is the domain-correct replacement.

### 2.8 Retained diagnostics outside the headline

- **COMET-KIWI** (reference-free), as the **Fidelity Floor** only: segment-level adequacy against `segment.scene`+`segment.text`, pass/fail at a fixed threshold. It exists to catch the degenerate winner — a system that writes brilliant original comedy about the wrong movie. It contributes nothing to humor scoring because it was trained to reward exactly the literal adequacy this benchmark punishes.
- **Translationese probe**: source-blind, "was this originally written in {lang}, or translated? one word." A known-task naturalness check, reported per system as a diagnostic.

### Excluded — positions, not hedges

- **BLEU: out entirely.** N-gram overlap against a single reference of paraphrase-mandatory text measures distance from *one* solution to a problem with thousands. It is not a weak signal here; it is an anti-signal (rewards literalism).
- **chrF++: out as a metric, retained as a tripwire** (§4) — suspicious overlap with the *unpublished* reference set indicates contamination, which is the one thing overlap is genuinely good at detecting.
- **COMET-22 (reference-based): out.** Same single-reference problem, plus WMT-domain training. KIWI survives only in the demoted floor role above.
- **Pairwise LLM preference judging: out of the headline entirely.** This is v3's sharpest break with v1/v2. Every construct the six-dimension pairwise rubric targeted is now covered by a behavioral probe with a checkable answer (voice→2.5, humor→2.1–2.3, names/gags→2.6, timing→2.4, fidelity→COMET-KIWI floor; culture is *absorbed into JSR* — a well-adapted reference is precisely one whose joke survives the Cold-Open probe, and a footnoted one is one that dies by explanation). Preference judging can live in an appendix for people who want it; it earns no weight.
- **Direct funniness ratings ("rate 1–10 how funny"): never.** Twenty years of computational-humor literature says inter-rater reliability on decontextualized funniness is poor even for humans; for LLMs it adds the LitEval bias on top. The whole design exists to avoid this question.

---

## 3. Statistical aggregation

- **Unit of analysis: the joke** (n≈30 now; corpus roadmap to 60–80 segments / ~150–200 jokes — one author-month of pastiche writing, the single highest-value expansion).
- **Per (system, language): JSR = surviving jokes / total jokes**, with a 95% CI from a **cluster bootstrap resampling segments** (jokes within a segment share fate; gags correlate across segments — resample at the segment level, keep gag structure intact, 2,000 replicates).
- **System comparisons: paired.** Every system translates the same jokes, so use an **exact paired permutation test on joke-level survival outcomes** (flip labels within joke, 10⁵ permutations). Paired designs on ~200 Bernoulli trials detect ~10-point JSR differences at conventional power; ranking claims below the significance threshold are printed as ties.
- **Breakdowns: mixed-effects logistic regression** — `survive ~ system + language + mechanism + portable + (1|segment) + (1|gag_id)` (statsmodels/`pymer4`; one function). This yields per-mechanism and per-language survival odds with correct uncertainty, and is the machinery for the nomological-validity predictions in §5.
- **Probe uncertainty is propagated, not hidden:** each gate that uses a probe ensemble records the vote split; a *sensitivity JSR* is recomputed under leave-one-probe-out (§4), and the headline table prints JSR ± bootstrap CI ± max leave-one-probe-out shift.
- **No weighted composite. No dimension weights.** The 25/25/15/10/15/10 vector is deleted, not recalibrated — there is nothing to weight when the headline is one rate and everything else is a labeled diagnostic. Spurious Joke Rate and Fidelity Floor are reported beside JSR, never folded in.

---

## 4. Bias, gaming, and contamination resistance

**Judge/probe bias.**
- **Source-blind by construction:** the core probes never see English, so English-fluency halo effects and back-translation shortcuts are structurally excluded, not instructed away.
- **No-self-probing:** reuse `no_self_judging` — a provider's models never probe its own translations. With 11 registry providers, three disjoint probe families per language is easy.
- **Leave-one-probe-out sensitivity:** recompute all rankings dropping each probe model; report the max rank shift. A benchmark whose ranking depends on which probe you drop says so on the front page.
- **Probe competence confound:** a probe weak in Yoruba under-detects everyone's jokes in Yoruba equally. Consequence: **within-language rankings are the product; cross-language JSR comparisons ship labeled *diagnostic only*.** This is a scoping position, stated up front.

**Gaming by benchmarked systems.**
- **Joke stuffing** (add extra gags to boost detection): JSR counts only source-carded loci; extra material inflates **Spurious Joke Rate** (published beside JSR) and burns the isochrony budget.
- **Explanation smuggling** ("he said, hilariously"; glosses): the predictability contrast (2.3) punishes it mechanically — explained punchlines become predictable — and a regex+probe pass flags explicit humor markers and translator's-note constructions as an automatic died-by-explanation.
- **Length gaming:** Gate D is a hard conjunct; you cannot buy comprehension-probe hits with text that no longer fits the window.
- **Reference chasing:** impossible — reference translations are unpublished (below) and no headline instrument uses them.

**Contamination.**
- **Canary GUID** in `segments.json`; presence in a model's output is checked each run.
- **Seeded surface-variant corpora:** because the ground truth lives at mechanism level (Joke Cards), a deterministic renamer (names, village, cheese, B-flat→other note; seeded table swap) produces variant corpora whose cards are *unchanged*. Each leaderboard run scores canonical + one fresh variant; a canonical−variant JSR gap > CI width is flagged as memorization. This is cheap *because* the benchmark measures mechanisms, not strings — the design's theory choice is also its contamination defense.
- **chrF++ tripwire** against the private, never-published reference set: overlap above a calibrated ceiling flags reference leakage.
- **The private (real-WPDR) track is declared contaminated by default** — the transcript has circulated online since 2004 and must be assumed memorized by every frontier model. Position: the private track is a demo and a debugging aid; the public pastiche track is the scientific instrument. Print this on the leaderboard.

---

## 5. Validation without blocking on humans

The v2 stance ("instruments earn their place via human correlation") made human studies load-bearing, violating the constraints. v3 validates instruments the way psychometrics does when criterion data is scarce: **known-item, known-group, and nomological validity** — all runnable by one person with API keys.

1. **Lesion battery (the workhorse).** Take strong translations (best available model, hand-spot-checked) and apply six controlled lesions per joke: explain-the-joke, literalize-the-pun, flatten-register, break-gag-consistency, pad-past-window, shuffle-punchline-position. Generate with one model, hand-verify a sample (~1 hr/language). Every instrument must **detect its target lesion (AUC ≥ 0.85, pre-registered) and not fire on non-target lesions (specificity ≥ 0.8)**. Instruments failing their battery are demoted to unscored diagnostics *by rule, before any leaderboard is published*. Cost: 6 lesions × 30 jokes × 3 languages ≈ a few hundred cheap-tier calls plus probe runs — tens of dollars.
2. **Known-groups anchors in every run:** (a) a forced-literal baseline ("translate preserving wording; do not adapt jokes"); (b) a frontier system; (c) an unconstrained-rewrite baseline ("write funny narration in {lang} for this scene", source discarded). Required orderings: JSR(literal) ≪ JSR(frontier); rewrite must be *killed by the Fidelity Floor and Spurious Joke Rate* despite high probe hits. A run violating the orderings is invalid and says so.
3. **Reliability:** probe-ensemble agreement (Fleiss' κ per gate; κ < 0.4 flags the gate), and test–retest (two seeds; JSR shift beyond CI flags instability).
4. **Nomological network:** the theory makes falsifiable predictions the instruments must reproduce if they measure what they claim: WORDPLAY jokes survive least and substitute most; portable mechanisms (ABSURD_SIMILE, CATEGORY_ERROR) survive most; punchline displacement is worst in verb-final languages; register range compresses toward the middle in all systems (regression-to-register is the translationese signature). Confirmed patterns are construct-validity evidence *and* the paper's findings section.
5. **Humans as enhancement, never gate:** an always-open, low-friction protocol — bilingual volunteers rate 20 disagreement-zone jokes (probe split votes) — accumulates criterion data opportunistically. Pre-register that human data can *retire* an instrument but the benchmark publishes without it.

---

## 6. The novel mechanism (claim to novelty)

**The Cold-Open Survival Protocol** — specifically instrument 2.3, the **Setup–Punchline Predictability Contrast**: measuring whether a translated joke preserves the *incongruity-resolution information signature* (punchline unpredictable from setup under target-language model sampling, yet coherent in hindsight), with all probes source-blind, and punchline *position* scored in performed seconds against a timed window (2.4).

No existing MT benchmark, WMT test suite, or literary-MT evaluation measures any of: (a) a joke's predictability structure rather than its wording or judged quality; (b) source-blind functional comprehension as the survival criterion; (c) punchline placement and laugh room inside a hard time window. Each is individually new to MT evaluation; the conjunction is the benchmark's contribution, and it generalizes beyond WPDR to dubbing, subtitling, and stand-up translation — which is what makes this a computational-humor result and not only a leaderboard.

---

## 7. Cut list

1. **The six-dimension weighted composite and its weights** — deleted, not recalibrated. Dimensions survive as diagnostic facets of JSR breakdowns.
2. **Pairwise preference judging as a scored instrument** — the O(N²) tournament, the anchoring machinery, position-bias mitigation, tie calibration: all complexity purchased to stabilize a kind of judgment the design no longer needs. Optional appendix at most.
3. **BLEU and COMET-22** — anti-signals on paraphrase-mandatory text (chrF++ survives only as the contamination tripwire; COMET-KIWI only as the Fidelity Floor).
4. **MQM error spans** — wrong ontology for comedy death; replaced by the autopsy taxonomy.
5. **v2's run-everything meta-evaluation** — its honesty was admirable and its dependency structure broken: it made a human study the arbiter of every instrument while the constraints forbid human studies from blocking. The lesion battery is the non-blocking replacement.
6. **Cross-language headline comparisons** — scoped out (probe-competence confound, §4); within-language rankings only.
7. **Precision speech-duration modeling** (TTS-based timing, phoneme-level rates) — the coarse estimator's job is gating and locus mapping; ±15% tolerances absorb its error. Revisit only if lesion battery shows Gate D misfiring.

## Implementation sketch

```
src/dearreader_bench/
  jokecards.py      # JokeCard model, mechanism taxonomy, locus computation (reuses speakability)
  probes/
    coldopen.py     # Gate F: laugh-locus detection + explanation (source-blind)
    mechanism.py    # Gate M: closed-set classification + script-opposition match
    incongruity.py  # Gate I: truncate → sample n=8 → BGE-M3 cosine; hindsight-coherence vote
    delivery.py     # Gate D: isochrony + punchline placement + laugh room
    register.py     # clause tagging, trajectory DTW, Flattening Index
    gagledger.py    # extraction + deterministic consistency checks
  survival.py       # gate conjunction, autopsy assignment, JSR
  stats.py          # cluster bootstrap, paired permutation, mixed-effects logistic
  lesions.py        # lesion generation + battery scoring (validation harness)
  providers.py      # thin adapter over commentary-track PROVIDERS registry
data/
  segments.json     # + joke_cards.json, variants/seed-*.json (generated)
```

Cost envelope per full run (12 segments, ~30 jokes, 8 systems, 3 languages, 3 probes): translation ~300 calls; probes ~30 jokes × 3 langs × 8 systems × (3 F + 1 M + 16 I-samples + 3 coherence) ≈ 17k mostly cheap-tier calls — order $50–150 on registry budget tiers. One person, API keys, an afternoon of compute. The expensive asset is the one that should be expensive: writing more jokes.
