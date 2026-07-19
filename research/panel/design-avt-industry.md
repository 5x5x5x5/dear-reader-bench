# dear-reader-bench v3 — The Recording-Floor Design

*Lens: audiovisual translation practice. This proposal treats the benchmark the way a dubbing studio treats a delivered adaptation script: it is either recordable or it goes back for retakes. v1 was editorial/judge-centric, v2 was run-everything-and-meta-evaluate. v3 is the third pole: practice-anchored, gate-based, artifact-producing.*

---

## 0. Where the current design is naive about performed translation

These are not nitpicks; each one changes the architecture.

1. **There is no spotting.** Segments carry a duration (`seconds: 18`) but no internal cue structure. In AVT, a script is *spotted*: every unit has in/out timecodes and, for comedy, the payoff must land on its visual beat. "His mighty pants surrender at the knee" (mog-008) must coincide with the trousers tearing on screen. A translation that fits the 13-second window but puts the pants line 4 seconds after the shot cuts is a failed take — and the current design cannot see it. Sync-to-picture is *the* defining constraint of AVT and it is entirely absent.

2. **Underrun is unpenalized.** `performability_score` returns 1.0 for any translation at ≤95% of the window — including a 3-second translation of an 18-second window. WPDR is a wall-to-wall voice-over; dead air over a held shot kills the format. No VO studio accepts a take that fills a third of its window. Conversely, the linear decay to 0 at 2× the window is fantasy leniency: a take at 130% is not "65% good," it is unusable. Real tolerance bands are roughly 75–110% of window.

3. **The duration heuristic breaks on real scripts.** The vowel-group regex counts zero-to-few syllables in unvocalized Arabic and Hebrew (vowels are unwritten), and misses Devanagari's inherent vowels — so those languages' estimated durations collapse toward zero and *everything passes*. It also ignores punctuation pauses, which in bombastic narration ("The Wheel that hums. The Wheel that knows.") are a large fraction of the clock. Duration must be *measured*, not estimated (see §6, synthetic table read).

4. **The task model is segment-isolated MT; the industry deliverable is a script plus a bible.** Dubbing adapters receive the whole episode with picture; localization teams maintain KNP sheets (key names and phrases) that lock "Aldo the Cellar-Wretch" to one rendering before line one is adapted. `Translation` has no notion of a script-level job or a term base, so running-gag and name consistency — 30% of what makes this corpus hard — can't be evaluated coherently. The evaluated unit must be a *full-script adaptation job*, not a segment.

5. **"Which is funnier to a native speaker?" is not a question any studio QA asks.** It is unanswerable even between humans, and preference-framing is exactly the surface on which LitEval-style judge bias grows. Humor QA in practice is audit-shaped: *is there a functioning joke at this point, of an appropriate mechanism, in the right place?* Joke loss is detectable; funniness ranking is not.

6. **Compensatory weighted averaging contradicts acceptance logic.** A weighted sum lets 25% voice buy back a broken callback. On a recording floor, any single blocking defect — a name that drifted, a take that doesn't fit, a punchline that missed its beat — triggers a retake regardless of how lovely the register is. Studio quality is conjunctive, not compensatory.

7. **Reference-based metrics presuppose references that will never exist.** Transcreation has no single reference; a commissioned reference joke is one arbitrary point in a large solution space, and commissioning them in M languages breaks the one-person constraint. v2's "run everything, let meta-evaluation decide" neutrality is a cost sink that defers a decision the construct already makes.

---

## 1. Headline metric: First-Pass Acceptance (FPA)

**FPA = the fraction of segments a system delivers that would not be sent back for a retake**, per language, macro-averaged across languages.

A segment passes iff it clears every gate in §2. Alongside FPA, the benchmark publishes the **retake sheet**: per-system counts of retake reasons using a studio-native defect taxonomy (`SYNC-OVER`, `DEAD-AIR`, `BEAT-MISS`, `KNP-BREAK`, `GAG-DROP`, `JOKE-VOID`, `VOICE-FLAT`, `SCENE-CONTRA`). "Model X: 61% FPA in Japanese; dominant retake reason: JOKE-VOID (jokes deleted under time pressure)" is a sentence a dubbing director, a researcher, and a leaderboard reader all understand.

Why this and not a composite score:

- It matches the real acceptance function of the industry the benchmark is simulating. "Good" to a dubbing director means *recordable as delivered*.
- Conjunctive gates are inherently gaming-resistant (§4): every cheap way to pass one gate trips another.
- It is decomposable into retake reasons, which makes failures inspectable without MQM machinery.
- It sidesteps the weighted-priors-pending-recalibration problem entirely: there are no weights, only pre-registered pass bands.

Two headline companions: **min-language FPA** (localization practice: a title ships when *all* locales pass — the chain is its weakest market) and **mean retakes per 10 segments** (the number studios actually track).

## 2. Instrument set (gates + diagnostics), with positions

### Blocking gates — all must pass

| Gate | Retake code | Type | Construct and rationale |
|---|---|---|---|
| **G1 Isochrony** | SYNC-OVER / DEAD-AIR | Computed (TTS-measured) | Measured spoken duration must land in **[0.75, 1.10] × window**. Measured by rendering the take with a locked TTS voice per language at fixed rate (§6), not the syllable heuristic. Over 110% is unrecordable; under 75% is dead air over held picture. The construct is fully specified; no validity question. |
| **G2 Beat sync** | BEAT-MISS | Computed | The payoff must land inside its spotted visual beat window (±max(2.0s, 15% of window)). Payoff position = (payoff onset fraction of the text, by syllable share) × measured total duration. Requires spotting metadata (§6) and the system to quote its own punchline (`payoff_text`) — which adapters do anyway when they mark up scripts. |
| **G3 KNP adherence** | KNP-BREAK | Computed | Every epithet occurrence must match the system's own delivered bible entry (fuzzy token-set ratio ≥ 85 for alphabetic scripts to absorb inflection; NFKC-normalized substring for CJK). Consistency is checked against the system's *own* declared terms, exactly as studio QA checks against the show bible. |
| **G4 Gag anchor recurrence** | GAG-DROP | Computed | For each `gag_id`, the bible's declared anchor phrase must recur (fuzzy) in every segment of the gag group. A running gag with no recurring surface form is not a running gag — this is the mechanical core of callback comedy and it is measurable with string matching. |
| **G5 Joke audit** | JOKE-VOID | Judged (detection, not preference) | For each humor-tagged feature, judges answer: *"Identify the joke at this point in the translation, if any, and name its mechanism (pun / register crash / absurd epithet / adapted reference / literal carry-over of an English joke / none)."* Fail if majority finds no functioning joke or only a literal carry-over where the source has `pun`/`pop_culture`. This is how humor adaptation is actually QA'd: presence and mechanism, not funniness ranking. Detection framing minimizes the LitEval preference-bias surface. |
| **G6 Voice (flattening probe)** | VOICE-FLAT | Judged (signal detection) | A cheap model produces a meaning-matched, register-neutralized rewrite of the candidate ("same content, neutral newsreader prose"). Judges see the pair blind, both orders, and must identify which one is the bombastic narrator. If judges can't reliably pick the candidate (< 4/5 majority across both orders), its voice is indistinguishable from flat prose — fail. Because the comparison is within-system and meaning-matched, fluency bias and length bias have nothing to grab. |
| **G7 Scene fidelity** | SCENE-CONTRA | Judged (entailment-shaped) | *"Does the translation assert anything that contradicts the scene description?"* Contradiction-only, narrow, with quoted evidence required. The comedy may transform freely; the pants must still tear. |

### Diagnostics — reported, never in the headline

- **Director's pick**: one holistic pairwise question — *"Which take would you keep?"* — run as a Bradley–Terry tournament on a 25% segment subsample. Kept small, kept out of the score; used as a convergent-validity check on FPA (§5).
- **COMET-KIWI as a departure gauge, not a score.** Adequacy metrics punish good transcreation by construction; but *reported descriptively* they become interesting: strong systems should show moderate, not maximal, source adequacy. A system at KIWI ceiling is probably translating instead of adapting.
- **Lints (non-scoring)**: digits in the script (dubbing convention: numerals are written out — also a TTS-gaming guard), unbroken runs > ~30 syllables without a clause boundary in segments > 15s (breath planning).

### Excluded, with positions

- **BLEU / chrF++ / COMET-22: cut entirely** (see §7). Not "demoted pending meta-evaluation" — cut. They require references that don't exist and measure surface overlap on a task whose success criterion is *justified departure* from the source surface.
- **CULTURE as a separate judged dimension: cut.** No studio QA sheet has a "culture" line; cultural adaptation failures surface as JOKE-VOID (opaque reference = dead joke) or as lint (explanatory gloss = extra syllables = SYNC-OVER). It remains visible as the `pop_culture` feature breakdown of G5.
- **MQM error spans: cut.** MQM taxonomies are accuracy/fluency-oriented; forcing performed comedy defects into them is category error. The retake-reason taxonomy is the domain-native replacement and is cheaper.

## 3. Statistical aggregation

- **Unit of analysis**: (system, language, segment) → binary all-gates indicator. FPA(system, language) = mean over segments. Headline FPA(system) = unweighted macro-mean over languages; report min-language FPA alongside.
- **Uncertainty**: cluster bootstrap (10,000 resamples). Clusters = gag groups plus singleton segments — segments sharing a `gag_id` are correlated through G3/G4 and must resample together. 95% CIs on every published FPA.
- **System comparisons**: paired exact permutation test on segment-level pass indicators (same segments, same languages, paired by design). Report only differences whose CI excludes zero; the leaderboard shows tiers, not false total orders.
- **Judged gates**: 5-judge ensembles (from the 11-provider registry, no-self-judging rule retained), majority ≥ 3. G6 requires the majority in *both* presentation orders; order-inconsistent verdicts count as fail-safe (no pass). Krippendorff's α reported per gate per release; a pre-registered floor (α ≥ 0.4) demotes a gate to advisory for that release rather than silently counting noise.
- **Feature breakdowns**: per-`Feature` pass rates (the segment tags finally pay rent: "pun segments: 34% FPA; aside segments: 81%").
- **Severity view**: distribution of failed-gate counts per segment (a segment failing five gates is a different animal from one failing G1 by 0.4s), published as the retake sheet.

No learned weights, no regression calibration in the critical path. Pass bands and thresholds are pre-registered constants in the repo.

## 4. Bias, gaming, and contamination resistance

**Gaming — the conjunctive design is the primary defense.** Every single-gate exploit trips a neighbor: pad filler to cure DEAD-AIR → JOKE-VOID/VOICE-FLAT (filler is flat); truncate to cure SYNC-OVER → JOKE-VOID or SCENE-CONTRA; leave every name in English to trivially pass KNP → G5 fails epithet segments (an untranslated "Cellar-Wretch" is not a functioning joke in Japanese); declare a one-word gag anchor that recurs vacuously → G5's mechanism audit on `running_gag` segments. This is not an accident — multi-gate QA exists in studios precisely because each individual constraint is gameable.

**Judge-side bias**: no-self-judging (already in `rubric.py`) retained across the 11-provider registry; all pairwise judgments run in both orders with order-consistency required; candidate texts delimited as data with an instruction-injection scan over them (imperative judge-addressed patterns fail the segment for cause, published as such); rationales capped at two sentences; detection framing (G5/G6/G7) rather than preference framing removes most of the surface where LLM judges are known to over-rate machine-fluent output. G6 is structurally immune to length/fluency bias because both texts are the same system's meaning-matched pair.

**TTS gaming**: text normalization before rendering (numerals expanded per locale — also required of systems by the brief, per dubbing convention), fixed voice and rate per language, audio cached and published so measurements are auditable.

**Contamination**: (a) canary GUID embedded in `segments.json`; (b) **corpus refresh per release** — the pastiche is cheap to extend, so each leaderboard release adds a new *Moon Over Gorganzola* arc and results are tagged with corpus version; published system outputs contaminate only *past* versions. (c) The private track has a useful asymmetry: the English WPDR source is certainly memorized by frontier models, but no published target-language translations of it exist — so *target-side* contamination is naturally near-zero, and public-vs-private FPA divergence is itself a contamination diagnostic worth reporting.

## 5. Validation without blocking on humans

The v2 plan made human calibration load-bearing. Replace it with construct validation a single person can run:

1. **Golden-defect metamorphic tests (the core).** For each gate, construct known-bad variants of a seed set of good translations (best-model output with a manual pass over the 12 public segments) via controlled degradation operators: `register_flatten`, `joke_ablate` (punchline → literal statement), `knp_shuffle` (rename the epithet mid-script), `pad` (+30% filler), `truncate`, `scene_swap` (contradict one visual fact), `beat_slide` (move the punchline off its beat). Each gate must separate seed from its matched degradation with ≥ 0.9 accuracy. These are unit tests for instruments — one person can audit every diff on a 12-segment corpus in an afternoon.
2. **Known-ordering check**: a deliberately weak system (small open model) versus a frontier system must separate on FPA with non-overlapping CIs. If the instrument can't see *that*, nothing downstream matters.
3. **Reliability battery**: judge α per gate, both-order consistency rates, 3-seed self-consistency; all published per release.
4. **Measurement cross-check**: TTS duration vs. heuristic correlation per language (flags languages where the heuristic fallback is unusable — Arabic will fail this, by design); ear-spot-check of five rendered clips per language (minutes, not a study).
5. **Convergent check**: rank-correlate FPA with the director's-pick BT diagnostic. Divergence is a flag to investigate, not a calibration input.
6. Human studies become a *versioned upgrade* — pre-registered, run when resources exist, revising pass bands in a new major version — never a release blocker.

## 6. Novel mechanisms (none exist in any MT benchmark)

1. **Spotted-beat payoff synchrony (flagship).** Extend segments with authored spotting metadata — `beats: [{offset_s, window_s, cue, gag_id?}]` (one-time authoring for the pastiche corpus; e.g. mog-008 gets `{offset_s: 9.0, window_s: 3.0, cue: "trousers tear"}`). Systems must quote their own punchline (`payoff_text`); G2 checks that the punchline's estimated onset, projected onto the measured audio timeline, falls in the beat window. *No MT or literary-translation benchmark scores whether a joke lands while its sight gag is on screen.* This is the defining skill of comedy adaptation for picture, and it is fully computable.
2. **The synthetic table read.** Every system's every take is rendered to audio with a locked TTS voice per language (local Piper where available; one API voice otherwise; heuristic fallback flagged as low-confidence). This (a) replaces the broken duration heuristic with measurement, (b) produces per-system *listenable target-language riff tracks* over the pastiche corpus — an evaluation artifact a human can check in minutes and the single most persuasive leaderboard exhibit imaginable, and (c) is the closest thing to a studio table read that runs on API keys.
3. **The bible deliverable.** The task is a full-script adaptation job: system receives the entire source script, scene descriptions, timings, beats, and a fixed transcreation brief (published as part of the benchmark, like a real client brief: audience, register intent, "write out numerals," "wall-to-wall — fill your windows," "references may be replaced, never glossed"), and must return an `AdaptationResult{bible, segments}` where the bible declares name renderings, gag anchors, and a register note. G3/G4 then hold the system to *its own* bible. This imports the KNP-sheet discipline that separates professional localization from sentence-by-sentence MT, and makes consistency a first-class, computable construct.
4. **The flattening probe (G6).** Register measured as signal detection against a meaning-matched neutralized self, not as preference against a competitor — a judge task with no fluency-bias surface, novel as far as I know in any translation evaluation.

## 7. What I would cut

- **BLEU, chrF++, COMET-22** — and with them the entire obligation to produce reference translations in every language, which is the single largest hidden cost in v2. Not demoted: cut.
- **The meta-evaluation weight-recalibration machinery** (regressing dimension weights on a human sample) — replaced by pre-registered gates; revisit in a major version if human data ever arrives.
- **CULTURE as a scored dimension** and **MQM span annotation** — folded into the joke audit and the retake taxonomy respectively.
- **The full O(n²) six-dimension pairwise tournament** — the gate design needs no tournament; one small holistic BT diagnostic on a subsample survives.
- **Phoneme-level articulability analysis** (tongue-twister detection, stress patterns) — real dubbing directors care, but it's a research project per language; the breath-run lint is the 5% that gives 80%.
- **Human studies as a dependency** — explicitly out of the critical path, per constraint.

## 8. Concrete implementation deltas

- `schema.py`: add `Beat{offset_s, window_s, cue, gag_id?}`; `Segment.beats: list[Beat]`; `Bible{names: dict[str,str], gag_anchors: dict[str,str], register_note: str}`; `AdaptationResult{system, language, bible, segments: list[{id, text, payoff_text?}]}`; `GateResult{segment_id, system, language, gate, passed, evidence}`.
- `speakability.py` → `duration.py`: `measure_seconds(text, lang)` via cached TTS render (Piper first, API fallback, heuristic last with `low_confidence` flag); band scoring [0.75, 1.10]; delete the 2×-window linear decay.
- `rubric.py`: replace the five preference questions with the G5/G6/G7 detection prompts; keep `no_self_judging`; add both-order pairing for G6.
- `data/segments.json`: author beats for all 12 segments; add canary GUID; version the corpus (`mog-v1`).
- New `gates.py` (G1–G4 pure functions, G5–G7 judge harness), `retake_sheet.py` (aggregation + bootstrap), `golden_defects.py` (degradation operators + gate unit tests).

The result is a benchmark whose headline number means what a dubbing director means by good — *this script can go to the floor* — measured by instruments that are either fully computed or framed as detection tasks a biased judge has little room to distort, validated by constructed defects rather than deferred human studies, and producing, as a side effect, the first leaderboard you can *listen to*.