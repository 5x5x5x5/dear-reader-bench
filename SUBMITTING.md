# Submitting a system

A submission is one model's adaptation of the whole season 2 script into one language. Nothing
is scored yet: the judge harness is not built. Submissions accepted now form the roster the
first run will judge.

## 1. Get the prompt

```sh
uv run --with-editable . python -m dearreader_bench.submission prompt ja > prompt.txt
```

Languages: `ja`, `zh`, `de`, `fr`, `es`, `ar`. The prompt is the same for every system
(`HARNESS_VERSION` in `src/dearreader_bench/brief.py`).

## 2. Run your model once

Send `prompt.txt` as a single user message. No system prompt, no extra instructions, no
examples, no retries chosen by a human, no editing of the output. If the model returns invalid
JSON you may re-run the identical request; say how many attempts it took.

## 3. Save the result

`submissions/<family>__<model>/<language>.json` (any colon in the model name becomes `_`), for example
`submissions/acme__model-1/ja.json`:

```json
{
  "system": "acme/model-1",
  "language": "ja",
  "bible": {
    "names": {"Odalys the Enumerator": "...", "...": "..."},
    "gag_anchors": {"the-funicular": "...", "...": "..."},
    "register_note": "..."
  },
  "segments": [{"segment_id": "s2-001", "text": "..."}]
}
```

`system` is `family/model`, with the exact model version. The family (the part before the
slash) decides which judges may score you, so use the provider that trained the model.

## 4. Check it

```sh
uv run --with-editable . python -m dearreader_bench.submission check submissions/acme__model-1/ja.json
```

It is rejected if a segment is missing or empty, if the bible lacks a name or a gag, if the
language is off the slate, or if the output contains the corpus canary. It also prints the
performability score. Segments estimated at 1.5 times their window or more are forfeited, which
costs score but does not block the submission.

## 5. Open a pull request

One pull request per system. Fill in the template. CI runs the same check.

By submitting you license the translations under CC BY 4.0, as `data/LICENSE` does for the
corpus. Do not submit anything derived from *Wizard People, Dear Reader* itself.

## What a submission is worth

Outputs are self-reported. Before a system appears in a published table the maintainer re-runs
it from the frozen prompt where the model is available, and marks it unverified where it is not.
