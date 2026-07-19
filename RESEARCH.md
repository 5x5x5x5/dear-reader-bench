# Research Notes

*Compiled July 2026. Literature background for the benchmark. The
authoritative evaluation architecture is `DESIGN.md` (v3, produced by a
four-lens adversarial design panel); §1 below is retained as the v2 instrument
survey it superseded, with the v3 positions noted inline.*

## 1. Instruments: what each one measures

Design principle: **metric validity is an empirical question, not a position.**
Rather than declaring in advance which metrics are adequate for comedic
narration, the benchmark runs every instrument below and includes a
meta-evaluation step — each instrument is correlated against human judgments
on a validation sample, and earns (or loses) its place in the headline score
based on that correlation. This also makes the benchmark useful to the
metrics community: it produces evidence about how automatic metrics behave on
paraphrase-heavy performed comedy, a domain absent from WMT test suites.

| instrument | construct measured | cost | role pending validation |
|---|---|---|---|
| chrF++, BLEU (sacrebleu) | surface overlap with a reference translation | free | reported baselines. Known limitation to test, not assume: overlap metrics are documented to penalize paraphrase, and this corpus is paraphrase-heavy with a single reference |
| COMET-22 / COMET-KIWI | semantic adequacy (learned; validated on WMT domains) | cheap | candidate primary instrument for **scene fidelity**; KIWI (reference-free) covers languages without references |
| speakability (computed, `speakability.py`) | isochrony / fits the time window | free | primary for **performability** — the construct is fully specified, so no validity question arises |
| LLM judge ensemble, anchored pairwise | voice, humor, names, culture | $$ | candidate primary for the four subjective constructs, *pending* the human-agreement check below |
| bilingual human raters (≥10% sample) | all constructs | $$$ | gold standard; calibrates every row above |

Meta-evaluation protocol: report per-instrument correlation (segment-level
Kendall's τ) against the human sample. Instruments below a pre-registered
threshold are demoted to diagnostics; if the judge ensemble itself falls below
threshold, rankings are published as *unvalidated* rather than quietly trusted.

(ROUGE is not in the table: it is a recall-oriented summarization metric, not
part of standard MT evaluation, and measures no construct this benchmark
targets.)

## 2. What the literary-translation-evaluation literature says

- **LitEval-Corpus** (2,000+ paragraphs, MQM-annotated, 4 language pairs) is
  the reference point for metric validation on literary text. Its headline
  finding is our central design warning: **LLM judges (including GEMBA-MQM
  -style approaches) systematically prefer machine translations over
  professional human literary translations** — misaligned with human experts.
  Mitigations adopted here:
  1. **Anchored pairwise comparison** rather than absolute scoring
     (JP-TL-Bench shows anchored pairwise stabilizes LLM judgment).
  2. **Judge ensemble across providers**, with a no-self-judging rule
     (a judge never scores output from its own provider family).
  3. **Rubric decomposition** — six narrow questions instead of one holistic
     "which is better," reducing the fluency-bias surface.
  4. **MQM-style error spans** retained as diagnostics (per GEMBA-MQM /
     Auto-MQM / MQM-APE lineage) so failures are inspectable.
- **LiTransProQA** (EMNLP 2025) operationalizes literary translation QA as
  professional-translator questions answered by an LLM — validation of the
  "narrow questions beat holistic scores" approach; our rubric prompts follow
  this shape.
- Scope note: the LitEval finding is a documented *risk*, not a verdict on
  this domain — it was measured on literary prose, not performed comedy. The
  human-calibration step in §1 is what settles whether it applies here.

## 3. Performability (the "Dear Reader" constraint)

WPDR is a *performed* text: each segment must be speakable in the time the
muted film allows. This is the automatic-dubbing **isochrony** problem.
Research on isometric MT (phoneme/character-count-ratio control, e.g.
PCR-reward RL) shows length control is measurable and optimizable without any
judge. We implement it directly: estimated spoken duration of the translation
÷ segment time window → a computed performability score. Length ratios also
get reported per language, since scripts differ wildly in information density
per syllable.

## 4. Which models to expect on the leaderboard (per-language priors)

From our July-2026 multilingual research (see commentary-track):

- Frontier near-parity at the top overall: Claude Fable 5 / Opus tier (top
  MMMLU-multilingual, 0.927), Gemini 3.x Pro, GPT-5.5.
- **Chinese:** native models (DeepSeek, Qwen, GLM, Kimi) match frontier at a
  fraction of the cost.
- **Japanese/Korean:** Gemini Pro + Claude Opus lead per-language indices;
  Qwen best open-weight CJK.
- **European languages:** Claude repeatedly cited as best for preserving tone,
  humor, and literary style — the core of this benchmark; Mistral the
  European specialist.
- **Lower-resource (ar, hi, id, ...):** Gemini leads.

Hypothesis worth testing: **rankings on this benchmark will diverge from
general multilingual rankings**, because humor reconstruction and register are
closer to creative writing (where Claude leads by a wide margin on EQ-Bench
Creative Writing / arena) than to translation adequacy (where translation
specialists like Qwen-MT and Minimax score highest). If the divergence shows
up, that's the benchmark's headline result.

## 5. Copyright posture

*Wizard People, Dear Reader* is Brad Neely's copyrighted work. This project:

- ships **only** an original pastiche corpus (public track) that imitates the
  *form* — bombastic narrator, epithets, running gags — with original
  characters and story;
- accepts a **user-supplied** transcript for the private track and never
  redistributes, embeds, or caches the real text;
- quotes nothing from the original in code, data, prompts, or docs.

## 6. Sources

- LitEval / literary metric validation: arxiv.org/html/2505.05423 (LiTransProQA, incl. LitEval discussion); aclanthology.org/2025.emnlp-main.1482
- Anchored pairwise LLM judging: arxiv.org/pdf/2601.00223 (JP-TL-Bench)
- MQM-span LLM evaluation lineage: arxiv.org/pdf/2310.13988 (GEMBA-MQM)
- LLM-as-judge long-form limits: arxiv.org/html/2606.01629
- Metric landscape 2026 (COMET-22 primary, chrF secondary; FLORES/WMT suites):
  awesomeagents.ai/leaderboards/translation-benchmarks-leaderboard;
  arxiv.org/pdf/2508.18549 (COMET-poly)
- Isochrony / isometric MT: arxiv.org/pdf/2403.15469
- Multilingual per-language leaders: artificialanalysis.ai/models/multilingual;
  llm-stats.com/benchmarks/mmmlu; benchlm.ai/multilingual
- Creative-writing rankings: EQ-Bench Creative Writing; arena.ai leaderboards

## 7. Roadmap

Superseded — the current roadmap is `DESIGN.md` §9. Two items from the v2
roadmap were explicitly cut by the v3 panel with reasons worth preserving:
weight recalibration by regressing human preference (underpowered at any
affordable sample; replaced by a Dirichlet weight-sensitivity audit) and the
human-gated meta-evaluation as arbiter of the headline (replaced by the lesion
battery + reliability panel, with a scoped human humor sample required before
the first public leaderboard rather than blocking development).
