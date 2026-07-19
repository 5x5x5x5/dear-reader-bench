# dear-reader-bench — v3 Design (authoritative)

*This document supersedes the evaluation sections of earlier iterations. v1 was
editorial (judge-centric, weights asserted); v2 was maximally neutral
(run-everything, human-gated meta-evaluation). v3 was produced by a four-lens
design panel (measurement theory, benchmark engineering, audiovisual-translation
practice, humor science), each proposal adversarially critiqued, then
synthesized. Where v3 takes a position, the position survived attack; where it
hedges, the hedge is load-bearing.*

## 0. Principles (what survived the panel)

1. **Validity is an argument, not a vote.** Construct logic decides instrument
   inclusion up front; automated reliability/validity evidence bounds how wrong
   the instruments can be; pre-registration makes it auditable. (No instrument
   earns headline status merely by being familiar; none is excluded merely by
   taste.)
2. **The construct is performed-comedy *translation*.** Two failure poles must
   both be excluded by design: *adequacy-tethered* scoring (rewards literalism,
   kills jokes) and *untethered* scoring (rewards abandoning the source and
   free-writing scene-conditioned comedy — the fatal hole two critiques found
   in pure source-blind judging).
3. **Only measured constructs may gate; judged constructs may only weight —
   and only *validated* measurements may gate hard.** Cliffs sitting inside an
   estimator's error band are noise amplifiers.
4. **The corpus is the binding constraint, and honesty about power is
   mandatory.** Twelve segments cannot separate frontier systems. Until the
   corpus reaches its blueprint size, the leaderboard reports tiers with the
   statement that most systems are indistinguishable.
5. **Humans are non-blocking for development, required for claims.** Dev
   releases run fully automated. The first *public* leaderboard that makes
   humor claims requires a small bilingual pairwise sample (~100 comparisons,
   humor dimension only) — affordable, scheduled, and the only defense against
   ecosystem-shared judge taste, the domain's best-documented failure mode.

## 1. Task definition: the adaptation job

The evaluated unit is a **full-script adaptation job**, not per-segment MT
(the panel's unanimous structural fix). A system receives the entire source
script — segments with timings, scene descriptions, feature tags — plus a
fixed, published transcreation brief (audience, register intent, "references
may be replaced, never glossed", "write out numerals"). It must return an
`AdaptationResult`:

- `bible` — its own key-names-and-phrases sheet: the chosen rendering for every
  epithet and gag anchor, plus a register note (the KNP-sheet discipline of
  professional localization);
- `segments` — the translated segments.

Consistency is then checked against the system's *own* bible (as studio QA
does), with an independent comedic-function check so a vacuous bible entry
(e.g. the plain word for "wheel") cannot pass by necessity.

One harness prompt, versioned and frozen per release; no per-system tuning; no
glossary side-channels beyond the bible the task itself demands.

## 2. Headline: DRS (Dear-Reader Score)

**DRS(system, language) = P(system, language) · Σ_d w_d · φ_d(system, language)**

### 2.1 The judged core

Four dimensions (culture folds into humor until the corpus has ≥6
pop-culture segments — it currently has one, and a BT fit over one segment is
a coin flip wearing a leaderboard column):

| dimension | weight | judge condition | question focus |
|---|---|---|---|
| humor | 0.35 | **source-blind** | is it funny *in the target language* (incl. adapted references) |
| voice | 0.30 | **source-blind** | bombastic narrator register survives |
| gags | 0.20 | **source-aware** | names/epithets/running gags: derived from the source's, consistent with the bible, comically alive |
| fidelity | 0.15 | **source-aware** | describes the same events; no contradiction of scene or source |

- **Anchored pairwise, both presentation orders, narrow questions** (JP-TL-Bench
  / LiTransProQA shape). Order-disagreement degrades to a tie. Absolute scoring
  is never used for judged constructs (LitEval).
- **Split-visibility is two calls by necessity** (one cannot both show and hide
  the source; the cost model below prices this honestly). Source-blind judging
  of humor/voice removes source-anchoring bias and enforces
  "funny-without-back-translation" behaviorally; source-aware gags+fidelity at
  0.35 combined weight, plus the tethering battery (§4), closes the
  untethered-generation hole.
- **Judge ensemble:** 3 provider families per pair, `no_self_judging`
  generalized to exclude both candidates' families; every slate includes one
  **pinned open-weight judge** (reproducibility core — hosted judges retire;
  open weights are immortal). Judge-deviation heatmap published; raw judgment
  JSONL archived every release; content-addressed judgment cache.

### 2.2 Aggregation

- Per (language, dimension): **Davidson Bradley–Terry** (explicit tie
  parameter), light L2, fit on order-folded verdicts after forfeits.
- Report **φ_d = mean over rivals of [P(beat rival) + ½P(tie)]** — expected win
  rate vs. the field. φ is bounded, commensurable across dimensions (this is
  what makes the weighted sum legitimate — summing raw BT logits across
  separately-fit cells lets judge decisiveness set the effective weights).
- **Fixed anchors in every roster,** which is what makes φ comparable across
  releases despite roster churn: (a) a forced-literal baseline ("translate
  preserving wording, do not adapt"), (b) a pinned open-weight mid-tier system,
  (c) an unconstrained-rewrite baseline (scene only, source withheld). The
  anchors are the field's fixed reference points, and (a)/(c) double as
  known-groups validity checks: a run where forced-literal wins humor, or
  where unconstrained-rewrite survives the tethering battery, is invalid and
  says so.
- **Uncertainty:** cluster bootstrap resampling **gag-chains** (segments
  sharing a `gag_id` are correlated and must resample together), BT refit per
  replicate, 95% CIs on φ and DRS. Leaderboard shows **tiers** (overlapping
  rank intervals), never bare ranks. With the current 12-segment corpus the
  honest output is one or two tiers — published as such.
- **Weights:** pre-registered priors with a **Dirichlet weight-sensitivity
  audit** every release (1000 draws centered on the registered weights; report
  the fraction of pairwise orderings that are weight-invariant; flag
  weight-sensitive pairs). Never recalibrated by regressing tiny human samples
  — that launders noise as calibration.

### 2.3 The performability term P

Performability is **measured, not judged**, and enters two ways:

- **Continuous penalty (the default):** per segment,
  `m = 1.0` if estimated-duration ratio ≤ 1.10; linear to 0 at 1.50.
  `P` = mean m over segments. No safe harbor: padding past 110% of the window
  starts costing immediately (a cliff-only gate *shelters* padding below the
  cliff — the exact inversion one critique proved).
- **Forfeit only at ≥ 1.50×** — far enough outside the estimator's error band
  that misclassification can't flip it. Forfeited segments score as losses
  against eligible opponents in the BT fit.
- **Underrun (dead air) is a reported diagnostic, never a gate.** The panel's
  AVT critique ran the original estimator on the then-current English source
  and found 7 of 12 segments at 54–89% fill; under the shipping estimator
  (which adds pause time) the current corpus spans 59–107% — *the pauses are
  the comic timing*. Any
  floor that flunks the source performance measures speech density, not
  performance fit. We publish fill-ratio distributions per system next to the
  source's own, and a regression test asserts the source never forfeits its
  own gate.
- **Duration is estimated by a mixed-script model** (see `speakability.py`):
  per-script syllable/mora/character units including Arabic/Hebrew/Devanagari
  branches, spoken-digit and acronym expansion, Latin-in-CJK counting, and
  punctuation pause time — the concrete exploit surface a critique identified
  (digits/acronyms/romaji counted as zero duration) is closed. Roadmap: TTS
  (eSpeak-NG/Piper) measurement as the oracle with the heuristic as cross-check,
  calibrated on the source segments' own fill ratios; TTS version pinned in
  `run.lock`. A language-ID/script-composition check flags code-switching
  salting.

## 3. Layer 2: behavioral instruments (columns + validity network)

These are reported columns and diagnostics — none is folded into DRS until its
reliability is measured (pre-registered candidate promotions in minor
releases). They exist because judged preference alone cannot see cross-segment
structure, and because behavioral probes with checkable answers are the right
complement to preference judging (not, as one proposal had it, a replacement —
mechanical gates alone invite gate-shaped unfunny text).

- **Joke Cards** (annotation substrate, one-time): per joke — setup/punchline
  spans, GTVH-style mechanism from a closed taxonomy, script opposition,
  portability flag, gag link. Second annotator on a sample; agreement
  reported. Non-portable jokes (puns): *any* functioning joke at segment scope
  counts (Delabastita's substitution norms) — survival is **segment-scoped and
  compensation-aware**, never locus-pinned (locus-pinning punishes the
  displacement strategies the AVT literature calls best practice).
- **Detection asymmetry** (the panel's consensus best single idea): probe
  models read the translation source-blind and mark/explain comic loci; then
  again with the source attached. Jokes explicable **only with the source
  attached** are certified translationese. Scored on the asymmetry, not blind
  detection alone (blind detection measures recognizability, and LLMs
  recognize intent through translationese).
- **Gag Ledger:** computed. (a) consistency of each gag's rendering across its
  arc, checked against the bible with inflection tolerance; (b) a
  **source-correspondence term** — the target arc must map to the *source's*
  arc (this term is part of the tethering battery); (c) presence across the
  arc. Double extraction by two provider families; agreement reported.
- **Payoff lift:** the final segment of each gag arc judged for humor twice —
  with the system's own translated setup as context vs. standalone. Lift =
  P(win|context) − P(win|no context). As a within-system, within-judge
  difference score, judge main effects cancel; it operationalizes "the running
  gag works in translation," which no per-segment instrument can see. Reported
  column; promotion to DRS gated on measured split-half reliability.
- **Punchline placement (ordinal) and laugh room:** the source-final punchline
  must be target-final (position-in-text, not fabricated timecodes against
  imaginary picture); trailing matter after the final punchline beyond the
  source's own is reported as dead-air-after-laugh.
- **Flattening probe (graded diagnostic):** judges pick the candidate out of a
  candidate/register-neutralized-rewrite pair, blind, both orders, with
  length-matched controls. A voice signal with no fluency-bias surface.
- **Autopsy taxonomy** (replaces MQM, whose accuracy/fluency ontology labels
  deliberate adaptation as error): every failure gets a cause —
  died-by-literalism (detection asymmetry), died-by-explanation,
  died-by-flattening, died-by-timing, died-by-inconsistency (ledger),
  died-by-untethering. Failure decomposition without category error.

**Convergence reporting:** Layer-2 columns are rank-correlated against the
judged dimensions every release. Divergence is a flagged finding — either a
probe failure or the paper's most interesting result — not silently absorbed.

## 4. Tethering battery (anti-untethered-generation)

A "translation" that discards the source and free-writes scene-conditioned
bombast must lose. Three independent defenses, all mandatory:

1. **Source-aware gags + fidelity** carry 0.35 of DRS weight;
2. **The unconstrained-rewrite anchor** is in every run and must land at the
   bottom on gags + fidelity + detection-asymmetry, else the run is invalid;
3. **Gag Ledger source-correspondence** fails arcs with no mapping to the
   source's arcs.

## 5. Excluded instruments (positions)

- **BLEU: excluded entirely**, including "as a baseline." Single-reference
  n-gram overlap on paraphrase-*mandatory* text is an anti-signal (rewards
  imitation of one comedian's solution), and any number in the results table
  will be sorted by. Raw translations are published; anyone can compute it.
- **COMET-22 (reference-based): excluded** — requires commissioning references
  for a corpus whose construct forbids a canonical reference.
- **chrF++: appendix-only, reframed as a discriminant-validity witness** with
  a pre-registered prediction (≈0 or negative correlation with humor-φ on
  pun-tagged segments) and as a contamination tripwire against the unpublished
  reference set. Its number is published *as that prediction's test*.
- **COMET-KIWI: catastrophe floor only** — empty/wrong-language/refusal/
  hallucination detection routing segments to recheck. Never in DRS: its
  training domain contains no register or humor signal, and good adaptation
  deliberately violates the adequacy it measures.
- **MQM spans: cut** (ontology contradicts the construct; autopsy taxonomy is
  the domain-native replacement).
- **Direct funniness ratings (1–10): never** (poor human inter-rater
  reliability + LitEval bias on top).

## 6. Validation program (runnable by one person)

- **Lesion battery** (instrument unit tests, necessary-but-not-sufficient —
  never sold as a validity warrant): controlled degradations
  (explain-the-joke, literalize-pun, flatten-register, gag-shuffle, pad,
  truncate, scene-contradict) must be caught by their target dimension
  (pre-registered sensitivity) and *not* by others (specificity), **plus a
  false-rejection arm**: diverse legitimate translations of the same segment
  must not be systematically rejected. Includes a fluency-bias probe class
  (polished-but-flat vs. inspired-but-rougher) targeting the LitEval failure
  mode, which pairwise judging does *not* cancel (it cancels severity main
  effects, not preference-direction bias — a confusion two proposals made and
  both critiques caught).
- **Null calibration:** two same-system generations (nonzero temperature)
  enter as pseudo-distinct entrants; their BT gap must straddle zero.
- **Reliability panel, published every release:** position-swap consistency
  per judge; Krippendorff's α per dimension (α < 0.5 ⇒ dimension flagged
  *tentative* and DRS republished both ways — no silent counting of noise);
  split-half (segment-halves) reliability of φ with Spearman–Brown; leave-one-
  judge-out rank stability.
- **TTS criterion study for the duration model:** synthesize translated
  segments per script family, correlate measured vs. estimated durations,
  refit rate constants on failure. The only instrument allowed to forfeit gets
  the cheapest real criterion validity available.
- **Human sample (scheduled, scoped, non-blocking for dev):** ~100 bilingual
  anchored-pairwise comparisons on the humor dimension before the first public
  leaderboard. Pre-registered agreement analysis; a judge ensemble that
  disagrees with bilingual humans on humor demotes humor to *tentative* until
  judges or prompts are revised.

## 7. Contamination and reproducibility

- **Canary GUID** in the corpus; presence checked in outputs each run.
- **Season protocol:** the corpus is defined by a style bible + blueprint
  (feature quotas ≥8 per feature, ≥10 gag chains, register shifts both
  directions, ≥6 pop-culture segments); each release adds a season; the
  headline runs on the newest; old seasons demote to dev sets. **Corpus
  authorship is the project's real cost and is budgeted as such** (target:
  48+ segments before any confident tiering; LLM-drafted pastiche requires
  human edit + a note on authoring-family homophily risk).
- **Seeded surface-variant corpora:** because ground truth lives at mechanism
  level (Joke Cards), a deterministic renamer produces variants with unchanged
  cards; canonical-vs-variant score gaps beyond CI flag memorization.
- **Public/private divergence** as a free contamination diagnostic. The private
  (real-WPDR) track is declared **source-side contaminated by default** (the
  transcript has circulated since 2004); its target-side cleanliness is a
  checkable claim (fan translations must be searched per language, not
  assumed). The private track is a demo and diagnostic; the pastiche track is
  the scientific instrument.
- **`run.lock`** pins judge/candidate snapshots, harness prompts (hashed), TTS
  and estimator versions, corpus version. Temperature-0 judging is *not*
  determinism on modern serving stacks; reproducibility rests on the archived
  judgment JSONL + cache, and the release says so.
- **PREREGISTRATION.md** per release: weights, thresholds, floors, collapse
  and demotion rules, language slate, human-study slot-in protocol. Hashed;
  any change bumps the major version. Batch releases only — no live Elo.

## 8. Cost model (honest arithmetic)

Per language at the current corpus (11 systems + 3 anchors = 14 → 91 pairs;
two visibility conditions ⇒ 2 calls × 2 orders × 3 judges):
91 × 12 × 12 = ~13k judge calls ≈ **$130–180/language** at mid-tier judge
pricing; six languages ≈ **$1k/run** all-in with probes, ledger extraction,
and lesion battery. At the 48-segment blueprint corpus: ~4× that. Solo-runnable;
the scarce resource is corpus authorship, not API spend — stated in §7.

## 9. Roadmap (ordered by leverage)

1. **Corpus season 2** to the blueprint (highest leverage; nothing else
   matters until n supports tiers) + Joke Cards with second-annotator sample.
2. Harness: adaptation-job protocol (bible deliverable), translation runner
   over the provider registry, judgment cache, `run.lock`.
3. Judge layer: two-condition pairwise prompts, order duplication, Davidson BT
   + φ + gag-chain bootstrap (implemented in `btmodel.py`), tiers.
4. Layer-2 instruments: gag ledger, detection asymmetry, payoff lift,
   flattening probe, autopsies.
5. Validation: lesion battery + null calibration + reliability panel; TTS
   criterion study; anchors wired into every run.
6. Human humor sample (~100 pairs) → first public leaderboard.
