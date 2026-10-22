# Changelog

## 3.200 — 2026-10-22
Fixes from the design audit (`scripts/audit.py`).
- **Legibility:** D gets cut corners (not O), 8 a narrower top bowl (not B), 5 a cut bowl (not S), 6 and 9 open terminals, 1 a 撇 flag (not I), 0 a dot (not O), Q a longer tail.
- **Case:** lowercase is narrower and lighter, so Regular's M N V W X Y Z capitals no longer match their lowercase; i and j have dots, with dotless ı and ȷ. `ss01` swaps tall and short M N V W X Y Z.
- **Spacing:** sidebearings set from each letter's shape instead of one fixed value; automatic class kerning by closest approach (LT, Ta, T., L’ …), with accented forms kerned separately so accents never collide.
- **Colour and weight:** crossbars 112 (A keeps the reference's full bar); symbol and accent strokes brought up to at least 88 units; lighter X.
- **Coverage:** full Google Fonts Latin Core (319 characters) with combining marks, `mark`/`mkmk` positioning and `ccmp` dotless i/j; ẞ Ł Ħ Ŧ ª º.
- **Technical:** tabular figures; points at extrema and no colinear points; hinted with otfautohint; canonical OFL text; copyright with the repository URL.
- Typing **MAN** in Regular now reproduces the original image (5% pixel difference, previously 10%).

## 3.100 — 2026-10-21
- Motion piece re-cut to a 96 BPM grid (27.5 s) with an original soundtrack synthesized in code (`scripts/bgm.py`); the end card's 躺 lies down on the final note.
- New sample text throughout: "LIE FLAT. STAND TALL.", "TURN · CUT · READ" and the lazy-dog pangram.
- README images rendered by `scripts/make_images.py`.
- C, E, F, H, K, R and T redrawn to follow their source characters (冂's hook, 山's long middle arm, 工's short stroke, 仄's curved arms, 刀's curved leg, 十's wide bar).
- Kerning for the wide T and the R/K legs; Æ, Œ and ¢ updated to match.
- Distribution metadata: OFL in the name table, typographic family for Even, code pages, fsType 0.
- Source map: a real Hei source character, turned and cut, for every letter.

## 3.000
- Lowercase as the short form of every letter; accented Latin (Western European, Œ Š Ž Ÿ); full punctuation and symbols; class kerning; WOFF2.

## 2.000
- M, A and N traced from the original 曼 → MAN image; stroke rules derived from it (thick bars, thin stems, flat-cut baseline, 撇 and 捺 diagonals, two heights).

## 1.000
- First sketch: capitals, digits, basic punctuation.
