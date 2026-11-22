"""One way to call a model: any OpenAI-compatible chat endpoint, plus mock models.

Defaults to OpenRouter, where a system id like 'family/model' is already the model name and one
key reaches every provider family. Point DRB_BASE_URL at any other compatible server.
The key is read from DRB_API_KEY or OPENROUTER_API_KEY and is never logged.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
_RETRY_STATUS = {408, 429, 500, 502, 503, 504}


def extract_json(reply: str) -> dict:
    """Parse the JSON object in a model reply, tolerating code fences and surrounding prose."""
    start, end = reply.find("{"), reply.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object in model reply")
    return json.loads(reply[start : end + 1])


def complete(
    model: str,
    prompt: str,
    temperature: float | None = None,
    timeout: float = 900,
    reasoning: bool = True,
    meta: dict[str, str] | None = None,
) -> str:
    """Send one user message and return the reply text. A stalled call is retried.

    If `meta` is provided, populates provider-reported metadata such as
    `served_model` and `response_id` so `run.lock` can pin actual snapshots.
    """
    if model.startswith("mock"):
        if meta is not None:
            meta["served_model"] = model
        return _mock(model, prompt)
    key = os.environ.get("DRB_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("set OPENROUTER_API_KEY (or DRB_API_KEY with DRB_BASE_URL)")
    body: dict = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    if temperature is not None:
        body["temperature"] = temperature
    if not reasoning:
        # Hidden reasoning is about 90% of a judge call's cost; models that cannot turn it
        # off answer HTTP 400, which is the caller's cue to pick another judge.
        body["reasoning"] = {"enabled": False}
    request = urllib.request.Request(
        os.environ.get("DRB_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
        + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                # The server sends keep-alive whitespace while a model stalls, which defeats
                # the socket timeout, so enforce a total deadline while reading.
                deadline, chunks = time.monotonic() + timeout, []
                while chunk := response.read1(65536):
                    chunks.append(chunk)
                    if time.monotonic() > deadline:
                        raise TimeoutError(f"{model}: no reply within {timeout:.0f}s")
                payload = json.loads(b"".join(chunks))
                if meta is not None:
                    if isinstance(payload.get("model"), str):
                        meta["served_model"] = payload["model"]
                    if isinstance(payload.get("id"), str):
                        meta["response_id"] = payload["id"]
                reply = payload["choices"][0]["message"]
                return reply.get("content") or ""  # some models return reasoning only
        except urllib.error.HTTPError as error:
            if error.code not in _RETRY_STATUS or attempt == 3:
                raise RuntimeError(
                    f"{model}: HTTP {error.code} {error.read()[:300]!r}"
                ) from error
        except (urllib.error.URLError, TimeoutError):
            if attempt == 3:
                raise
        time.sleep(5 * 2**attempt)
    raise AssertionError("unreachable")


# --- mock models: deterministic, free, and with a known right answer -----------------------


def _mock(model: str, prompt: str) -> str:
    """Deterministic local fakes for translation, judging, and Layer-2 probes."""
    if "\nText A:\n" in prompt:
        a, b = re.search(
            r"\nText A:\n(.*)\n\nText B:\n(.*)\n\nQuestion", prompt, re.DOTALL
        ).groups()
        longer = "tie" if len(a) == len(b) else ("a" if len(a) > len(b) else "b")
        if model.endswith("shorter") and longer != "tie":
            longer = "b" if longer == "a" else "a"
        return json.dumps({"winner": longer, "rationale": "mock: length"})

    if "SOURCE-BLIND COMIC-LOCI PROBE" in prompt:
        text_m = re.search(r"\nTranslation:\n(.*)\n\nReturn", prompt, re.DOTALL)
        text = text_m.group(1).strip() if text_m else ""
        # Short/empty translations yield no detected jokes; longer ones yield one locus.
        jokes = (
            [{"quote": text[:40], "why_funny": "mock: lands aloud"}]
            if len(text) >= 40
            else []
        )
        return json.dumps({"jokes": jokes})

    if "SOURCE-AWARE DETECTION-ASYMMETRY PROBE" in prompt:
        ids = re.findall(r'"joke_id":\s*"([^"]+)"', prompt)
        explained = "this is funny because" in prompt.lower()
        verdicts = [
            {
                "joke_id": jid,
                "status": "explained" if explained else "survived",
                "note": "mock",
            }
            for jid in ids
        ]
        return json.dumps({"verdicts": verdicts})

    if "GAG-LEDGER SOURCE-CORRESPONDENCE PROBE" in prompt:
        return json.dumps(
            {
                "maps_to_source": True,
                "consistent_across_arc": True,
                "rationale": "mock: arc aligns",
            }
        )

    names = json.loads(re.search(r"^Names: (.*)$", prompt, re.MULTILINE).group(1))
    gags = json.loads(
        re.search(r"^Running gags [^:]*:[^:]*: (.*)$", prompt, re.MULTILINE).group(1)
    )
    script = json.loads(prompt.split("\nScript:\n", 1)[1])
    style = {
        "terse": lambda t: re.split(r"(?<=[.!?])\s", t)[0],
        "padded": lambda t: f"{t} {t} {t}",  # 3x overruns every window
    }.get(model.split("/")[-1].split("+")[0], lambda t: t)
    return (
        "```json\n"
        + json.dumps(
            {
                "bible": {
                    "names": {n: n for n in names},
                    "gag_anchors": gags,
                    "register_note": "mock",
                },
                "segments": [
                    {"segment_id": s["id"], "text": style(s.get("text", s["scene"]))}
                    for s in script
                ],
            }
        )
        + "\n```"
    )
