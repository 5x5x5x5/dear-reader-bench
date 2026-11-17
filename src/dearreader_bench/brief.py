"""The adaptation job prompt (DESIGN.md §1): one prompt, the same for every system.

Any change to BRIEF or to the prompt layout must bump HARNESS_VERSION, because
submissions made under different prompts are not comparable.
"""

from __future__ import annotations

import json

from .schema import Corpus

HARNESS_VERSION = "s2-draft-2"

# Draft slate, one per script family the duration model has a branch for.
# Not yet pre-registered (DESIGN.md §7).
LANGUAGES = {
    "ja": "Japanese",
    "zh": "Mandarin Chinese (simplified)",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "ar": "Arabic (Modern Standard)",
}

BRIEF = """\
You are adapting the complete narration script of a comedic film into {language}.
The film is silent; a single bombastic narrator talks over all of it, and your
script will be performed aloud by a narrator in {language}.

The brief:
- Audience: adult native speakers of {language} who will never hear the English.
- It must be funny in {language}. Rebuild jokes and wordplay so they land; do not
  carry them over literally.
- Cultural references may be replaced with ones this audience knows. Never gloss
  or explain a reference or a joke.
- Keep the narrator: grandiose and overwrought, with deliberate drops into the
  mundane. Keep the events of each segment and never contradict its scene.
- Each segment has a time window in seconds. Your text must be speakable in it.
- Write out numerals as words.
- Names, epithets and running gags must be rendered the same way every time they
  recur, unless the source itself varies them for comic effect.

Return one JSON object and nothing else:
{{"bible": {{"names": {{<source name>: <your rendering>, ...}},
            "gag_anchors": {{<gag_id>: <your rendering of its anchor phrase>, ...}},
            "register_note": <one or two sentences on the voice you chose>}},
 "segments": [{{"segment_id": <id>, "text": <your adaptation>}}, ...]}}
The bible needs an entry for every name and every gag_id listed below, and
"segments" needs every segment, in order.
"""


# The two prompt-variant anchors every roster carries (DESIGN.md §2.2). They are fixed reference
# points and validity checks: literal should lose humor, rewrite should lose gags and fidelity.
ANCHORS = {
    "literal": (
        "\nOverride for this run: translate preserving the wording as closely as the language "
        "allows. Do not adapt, rebuild or replace any joke or reference.\n"
    ),
    "rewrite": (
        "\nFor this run the English narration is withheld. Write the narration from the scene "
        "descriptions alone.\n"
    ),
}


def adaptation_prompt(corpus: Corpus, language: str, anchor: str | None = None) -> str:
    """Build the full-script adaptation prompt for a slate language code. The canary is left out."""
    hidden = {"text"} if anchor == "rewrite" else set()
    segments = [
        s.model_dump(mode="json", exclude_none=True, exclude=hidden)
        for s in corpus.segments
    ]
    return (
        BRIEF.format(language=LANGUAGES[language])
        + (ANCHORS[anchor] if anchor else "")
        + f"\nNames: {json.dumps(corpus.names, ensure_ascii=False)}\n"
        + f"Running gags (gag_id: source anchor phrase): {json.dumps(corpus.gags, ensure_ascii=False)}\n"
        + f"\nScript:\n{json.dumps(segments, ensure_ascii=False, indent=1)}\n"
    )
