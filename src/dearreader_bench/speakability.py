"""Performability: can the translation be spoken in the segment's time window?

Duration is estimated by a mixed-script model: text is scanned once and every
run of characters contributes syllable-equivalent units under its own script's
rules, then units convert to seconds at the language's speech rate, plus pause
time for punctuation (in this genre the pauses are part of the clock).

Design rules from DESIGN.md §2.3:
- Overrun: continuous penalty from 1.10x the window, forfeit at >= 1.50x
  (far enough outside the estimator's error band that misclassification
  cannot flip it).
- Underrun (dead air) is a reported diagnostic (`fill_ratio`), never a gate:
  the English source itself sits at 54-89% fill — the pauses are the timing.

Known-exploit coverage (per adversarial review): digits and acronyms count as
spoken syllables; Arabic/Hebrew and Devanagari have their own branches
(unvocalized/abugida scripts defeat vowel-group counting); Latin material
embedded in CJK text is counted, not free.

Roadmap: TTS-measured duration (eSpeak-NG/Piper) as the oracle with this
estimator as cross-check, calibrated on the source segments' fill ratios.
"""

from __future__ import annotations

import re
import unicodedata

_VOWEL_GROUP = re.compile(r"[aeiouyáéíóúàèìòùâêîôûäëïöüåøæœãõαεηιουωаеёиоуыэюя]+", re.IGNORECASE)
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_DIGIT_RUN = re.compile(r"\d+")
_ACRONYM = re.compile(r"\b[A-Z]{2,}\b")
_SENTENCE_PUNCT = re.compile(r"[.!?…]+")
_CLAUSE_PUNCT = re.compile(r"[,;:—–]|--")

# Syllable-equivalent units per second, by language code.
_UNIT_RATES = {"zh": 3.3, "ja": 7.0, "ko": 4.5}
_DEFAULT_RATE = 4.5

# Pause time contributed by punctuation (seconds).
_SENTENCE_PAUSE = 0.30
_CLAUSE_PAUSE = 0.15

# Performability shape (DESIGN.md §2.3).
PENALTY_START_RATIO = 1.10
FORFEIT_RATIO = 1.50


def _char_class(ch: str) -> str:
    code = ord(ch)
    if 0x0600 <= code <= 0x06FF or 0x0750 <= code <= 0x077F or 0x0590 <= code <= 0x05FF:
        return "arabic_hebrew"
    if 0x0900 <= code <= 0x097F:
        return "devanagari"
    name = unicodedata.name(ch, "")
    if "CJK UNIFIED" in name:
        return "han"
    if "HIRAGANA" in name or "KATAKANA" in name:
        return "kana"
    if "HANGUL SYLLABLE" in name:
        return "hangul"
    return "other"


def _latin_word_syllables(word: str) -> float:
    return max(len(_VOWEL_GROUP.findall(word)), 1)


def _syllable_units(text: str, language: str) -> float:
    """Syllable-equivalent units for mixed-script text."""
    lang = language.lower()
    units = 0.0
    consumed = [False] * len(text)

    # Digits: read aloud (~1.5 syllables per digit across languages, coarse).
    for m in _DIGIT_RUN.finditer(text):
        units += 1.5 * len(m.group())
        for i in range(m.start(), m.end()):
            consumed[i] = True
    # Acronyms: one syllable-ish per letter ("USSR" is four, not one).
    for m in _ACRONYM.finditer(text):
        units += 1.2 * len(m.group())
        for i in range(m.start(), m.end()):
            consumed[i] = True

    # Per-character scripts.
    for i, ch in enumerate(text):
        if consumed[i]:
            continue
        cls = _char_class(ch)
        if cls == "han":
            units += 1.6 if lang == "ja" else 1.0  # kanji ~1.6 morae; hanzi = 1 syllable
            consumed[i] = True
        elif cls == "kana":
            units += 1.0
            consumed[i] = True
        elif cls == "hangul":
            units += 1.0
            consumed[i] = True
        elif cls == "arabic_hebrew":
            units += 0.7  # unvocalized letters; ~0.7 syllables per letter
            consumed[i] = True
        elif cls == "devanagari":
            if unicodedata.category(ch) not in ("Mn", "Mc"):  # combining marks ride free
                units += 0.8
            consumed[i] = True

    # Remaining Latin/Cyrillic/Greek words (also covers Latin embedded in CJK).
    remaining = "".join(ch if not consumed[i] else " " for i, ch in enumerate(text))
    for word in _WORD.findall(remaining):
        units += _latin_word_syllables(word)
    return units


def estimate_seconds(text: str, language: str) -> float:
    """Rough spoken duration of `text` in `language` (code, e.g. 'ja')."""
    text = text.strip()
    if not text:
        return 0.0
    rate = _UNIT_RATES.get(language.lower(), _DEFAULT_RATE)
    speech = max(_syllable_units(text, language), 1.0) / rate
    pauses = _SENTENCE_PAUSE * len(_SENTENCE_PUNCT.findall(text)) + _CLAUSE_PAUSE * len(
        _CLAUSE_PUNCT.findall(text)
    )
    return speech + pauses


def fill_ratio(text: str, language: str, window_seconds: float) -> float:
    """Estimated duration / window. Reported diagnostic; the source itself runs 0.54-0.89."""
    if window_seconds <= 0:
        raise ValueError("window_seconds must be positive")
    return estimate_seconds(text, language) / window_seconds


def is_forfeit(text: str, language: str, window_seconds: float) -> bool:
    """Egregious overrun: the segment forfeits its comparisons (DESIGN.md §2.3)."""
    return fill_ratio(text, language, window_seconds) >= FORFEIT_RATIO


def performability_score(text: str, language: str, window_seconds: float) -> float:
    """1.0 up to 110% of the window, decaying linearly to 0.0 at the 150% forfeit line.

    No safe harbor above 1.10 (a cliff-only gate shelters padding) and no
    underrun penalty (dead air is a diagnostic, not a defect — see fill_ratio).
    """
    ratio = fill_ratio(text, language, window_seconds)
    if ratio <= PENALTY_START_RATIO:
        return 1.0
    if ratio >= FORFEIT_RATIO:
        return 0.0
    return (FORFEIT_RATIO - ratio) / (FORFEIT_RATIO - PENALTY_START_RATIO)
