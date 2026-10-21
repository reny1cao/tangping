# Research: finding each letter's source character

These tools reproduce the search behind Tangping's source map: for each Latin letter, find a real Chinese character that, turned a quarter-turn and cut straight across, reads as that letter.

They need **Noto Sans CJK Bold** (SIL OFL 1.1), which is not part of this repository. Point `NOTO_CJK` at the `.ttc` file if it is not at the default path (see `paths.py`). `NOTO_INDEX=2` selects the Simplified Chinese face.

## Method

1. **Verify the reference.** 曼 turned counter-clockwise and cut ~44% from the bottom reads m · A · N (日, 罒, 又).
2. **Broad search** (`find.py`). All 6,763 GB2312 characters, both quarter-turns, split into component bands at blank columns (as 曼 splits into 日 | 罒 | 又), with bottom cuts up to 55% and top cuts up to 50%. Each piece is compared with the Tangping letter (blurred 24×24 correlation, with an aspect penalty).
3. **Finer search** (`find2.py`, `HARD=...`). For letters the broad pass misses: a straight cut on any side, 0–50%, in eighths.
4. **Verify** (`verify.py picks.json out.png`). Each pick is re-rendered at full resolution as a strip (character → turned → cut → piece ≈ letter) with an independent similarity score. This step caught three wrong first guesses: 乙 turns into N, not Z; 巴 came out mirrored; 山 cut for F loses its stem.
5. **Export** (`export_sources.py`). The real outlines, turned and cut with path operations, go to `docs/data/sources.json` for the source map.

`picks.json` holds the final choice per letter: `[character, turn, band start, band end, top cut, bottom cut]`, where turn `1` is counter-clockwise (as in 曼 → MAN) and `3` is clockwise, and every fraction is relative to the turned character's bounding box.

## Results

| Letter | Source | Score | | Letter | Source | Score |
|---|---|---|---|---|---|---|
| A | 曼 (罒) | 0.77 | | N | 曼 (又) | 0.76 |
| B | 巴 | 0.73 | | O | 口 | 0.75 |
| C | 冂 | 0.79 | | P | 节 (卩) | 0.83 |
| D | 巳 | 0.88 | | Q | 坦 | 0.71 |
| E | 山 | 0.82 | | R | 召 (刀) | 0.82 |
| F | 岂 | 0.88 | | S | 凹 | 0.82 |
| G | 町 | 0.78 | | T | 十 | 0.86 |
| H | 工 | 0.72 | | U | 口 | 0.73 |
| I | 日 | 0.90 | | V | 之 | 0.74 |
| J | 冖 | 0.82 | | W | 日 | 0.79 |
| K | 仄 | 0.62 | | X | 艾 (乂) | 0.78 |
| L | 冖 | 0.93 | | Y | 卡 (closest) | 0.58 |
| M | 曼 (日) | 0.88 | | Z | 以 | 0.77 |

1.00 means identical. Scores rose after C, E, F, H, K, R and T were redrawn to follow their sources (mean 0.766 → 0.786).

## Files

| File | Purpose |
|---|---|
| `paths.py` | Font paths, overridable with `NOTO_CJK`, `NOTO_INDEX` |
| `find.py` | Broad search; writes `found.pkl` |
| `find2.py` | Finer search for hard letters; `HARD=BDG OUT=found2.pkl python3 find2.py` |
| `sheet.py` | Candidate sheet from a results file: `FOUND=found2.pkl python3 sheet.py BDG out.png` |
| `explore.py` | Try hand-picked characters with every turn and cut: `python3 explore.py 十丁干 out.png` |
| `verify.py` | Verification strips for a picks file |
| `score_all.py` | Scores for every pick against the current fonts |
| `export_sources.py` | Source map data for the docs page |
