# Style bible and season blueprint

How a season of the public corpus is written. `tests/test_season2.py` enforces the countable
parts; the rest is for whoever writes or edits a season.

## The form

A silent film, narrated wall to wall by one person who is far too invested.

- **The narrator is a character.** Grandiose, breathless, addresses the audience directly, has a
  life outside the booth that keeps leaking in.
- **The scene line is what the camera shows.** The narration may exaggerate it and editorialize
  on it, and must never contradict it.
- **Bombast drops into the mundane, and the mundane swells into bombast.** A season needs both
  directions. Uniform bombast is as dead as flat prose.
- **Names are titles.** Every recurring person, object and place gets an epithet, and the
  epithet is used often enough to become a running gag in its own right.
- **Pauses are timing.** Short sentences and full stops are part of the performance. A segment
  that fills only 60% of its window is normal.
- **Numbers are written out as words**, so that every system has to speak them.
- **Entirely original.** No text, characters, plot or phrasing from *Wizard People, Dear Reader*
  or from any film. Pop-culture references are to genres and formats (a talent show, hold
  music), not to quoted material.

## Blueprint (DESIGN.md §7)

| requirement | minimum |
|---|---|
| segments | 48 |
| segments per feature (`epithet`, `running_gag`, `pun`, `register_shift`, `pop_culture`, `aside`) | 8 each |
| gag chains | 10, each with at least 3 segments, the last one a payoff |
| joke cards | at least one per segment; every `pun` segment has a `wordplay` card marked not portable |
| source fill ratio under `speakability.py` | 0.50 to 1.10 for every segment |
| canary | one GUID in the season file and the cards file, never in the prompt |

## A season's files

- `seasonN.json`: `corpus`, `canary`, `authorship`, `names` (epithets a submission's bible must
  render), `gags` (gag_id to source anchor phrase), `segments`.
- `seasonN_cards.json`: joke cards. Spans are verbatim substrings of the segment text.

A new season is a new story with new characters. The headline runs on the newest season and
older ones become development sets.

## Season 2: "The Count at Unterzwick"

A census-taker is sent up a mountain to count a town whose population will not hold still.
Eleven gag chains: the funicular, the Instrument, the count, His Honor, the soup, the Twins
Hobb, Form Nine-B, the narrator's physician, the Ironed Man, the echo, the avalanche.

**Authorship.** Season 2 and its joke cards were drafted in full by Claude Fable 5.2 on
2026-11-16 and have not been edited by a human. That is enough to build and test the harness
with. It is not enough to publish humor results on: DESIGN.md §7 requires a human edit, the
joke cards have had no second annotator, and Anthropic-family systems and judges may be
advantaged on text their own family wrote. Windows were set from the duration estimator, not
from a recorded performance.
