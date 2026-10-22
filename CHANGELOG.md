# Changelog

## 4.100 — 2026-10-22
Fixes from an independent review of 4.000.
- **Counters:** accented letters built on a letter with Hei turns (á é ğ Ď Ř æ œ Ð đ …) had their counters filled in. Fixed, and the build now refuses any accented letter with fewer counters than its base.
- **Sentence case in Regular:** M N V W X Y Z stay short in all-caps (MAN, NASA) but stand tall before lowercase (`calt`), so "Mozart", "Wien" and "Zürich" no longer read as lowercase.
- **Glyphs that read wrong:** opening quotes are now the closing quotes turned 180°; a new & built from a loop, a 撇 and a 捺 (no longer "Et"); ß and ẞ with an open lower turn; § as hook, ring, hook; £ with an f-like turn; ð with a hooked ascender, distinct from đ; Þ with P's bowl; ¿ is ? turned.
- **Accents:** cedilla joined to its stem; side carons on ď ľ Ľ ť clear of the stem, with their own spacing; a larger ring; a wave tilde; Y X V and lowercase v x anchors moved clear of the rising 捺; ASCII grave at the height of the other marks; square i/j dots.
- **Kerning:** closest approach is now measured with 20 units of vertical slack, so a hyphen no longer slides over J's spur or z's foot; braces are kerned like brackets.
- **Shapes:** tighter Hei turns (radius 95, was 130); bar-end flares 3 units, flush with the stems as in the reference; heavier lowercase bars (126) with larger a and e counters; S terminals pulled in (not 5); a smaller waist step on 8; clean joints on K, k, Y and R.

## 4.000 — 2026-10-22
A redesign, because the alphabet did not live up to the original MAN.
- **Hei turns instead of gimmicks.** Where a Latin letter is round, its corners bend the way 九, 己 and 乚 bend in a bold Hei font: B C D G J P R S U, 0 2 3 5 6 8 9, the lowercase bowls, ( ) { } ? @ € § © ®. O stays a square 口. The 45° chamfers (D, 5, ẞ), the dotted zero, the notched H, and the hooks on C and R are gone; D, O and 0, B and 8, and S, 5 and 2 are now told apart by their turns.
- **A real lowercase.** Same stroke weights as the capitals, standing on the short height (527) with ascenders (689) and descenders (−190): squared a e g s y, b d h k l t f with ascenders, g j p q y with descenders, ß as two stacked turns. Previously lowercase was a shrunken, lighter copy of the capitals.
- **Diagonals** in X, Y, Z and 7 are tapering, slightly bowed 撇 strokes; R gets P's bowl and a curved 撇 leg; Q a 撇 foot below the corner.
- **Sources:** E is now the 山 inside 端, K the 不 inside 否, U the 口 inside 烹 (mean match 0.76). New `research/fixed.py` repeats the search at the exact scale of the original cut.
- M, A and N are unchanged: typing **MAN** in Regular still reproduces the original.

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
