"""Performability: can the translation be spoken in the segment's time window?

This is the automatic-dubbing isochrony problem (see RESEARCH.md §3). We
estimate spoken duration from script-appropriate speech-rate norms and score
the ratio of estimated duration to the available window. No model judgment
involved.

Duration heuristics (broadcast/dubbing rules of thumb):
- Latin/Cyrillic/etc. scripts: syllables at ~4.5 syllables/sec, syllables
  estimated from vowel groups.
- CJK: characters approximate morae/syllables — Chinese ~3.3 chars/sec
  (each hanzi a syllable), Japanese ~7 morae/sec (kana ≈ mora; kanji ≈ 1.6),
  Korean ~4.5 hangul syllable-blocks/sec.
These are deliberately coarse — good enough to flag translations that are
20%+ over their window, which is what the score cares about.
"""

from __future__ import annotations

import re
import unicodedata

_VOWEL_GROUP = re.compile(r"[aeiouyáéíóúàèìòùâêîôûäëïöüåøæœãõαεηιουωаеёиоуыэюя]+", re.IGNORECASE)

_CJK_RATES = {
    "zh": 3.3,   # hanzi / sec
    "ja": 7.0,   # morae / sec
    "ko": 4.5,   # syllable blocks / sec
}
_SYLLABLES_PER_SECOND = 4.5


def _is_han(ch: str) -> bool:
    return "CJK UNIFIED" in unicodedata.name(ch, "")


def estimate_seconds(text: str, language: str) -> float:
    """Rough spoken duration of `text` in `language` (code, e.g. 'ja')."""
    text = text.strip()
    if not text:
        return 0.0
    lang = language.lower()
    if lang == "zh":
        units = sum(1 for ch in text if _is_han(ch))
        return max(units, 1) / _CJK_RATES["zh"]
    if lang == "ja":
        kana = sum(1 for ch in text if "HIRAGANA" in unicodedata.name(ch, "") or "KATAKANA" in unicodedata.name(ch, ""))
        kanji = sum(1 for ch in text if _is_han(ch))
        morae = kana + kanji * 1.6
        return max(morae, 1) / _CJK_RATES["ja"]
    if lang == "ko":
        blocks = sum(1 for ch in text if "HANGUL SYLLABLE" in unicodedata.name(ch, ""))
        return max(blocks, 1) / _CJK_RATES["ko"]
    syllables = 0
    for word in re.findall(r"[^\W\d_]+", text, re.UNICODE):
        groups = len(_VOWEL_GROUP.findall(word))
        syllables += max(groups, 1)
    return max(syllables, 1) / _SYLLABLES_PER_SECOND


def performability_score(text: str, language: str, window_seconds: float) -> float:
    """1.0 when the estimate fits the window comfortably, decaying toward 0 as it overruns.

    Fits at <= 95% of the window score 1.0 (a breath is part of the performance).
    Overruns are penalized linearly; 2x the window scores 0.
    """
    if window_seconds <= 0:
        raise ValueError("window_seconds must be positive")
    ratio = estimate_seconds(text, language) / window_seconds
    if ratio <= 0.95:
        return 1.0
    return max(0.0, 1.0 - (ratio - 0.95) / 1.05)
