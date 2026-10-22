# Tangping research tools - Copyright 2026 The Tangping Project Authors
# SPDX-License-Identifier: MIT
"""Which capitals stand tall and which sit short, decided by real characters.

In the original, 曼 is turned a quarter-turn and cut once, straight across, a little under
half-way. Every part then keeps its natural height: 罒 spans the full width of 曼, so A stands
tall; 日 and the body of 又 are set in, so M and N sit short (N's 捺 still sweeps past the top).

This script repeats exactly that move for every GB2312 character, at the original scale:
turn either way, cut ONCE across the whole character (25-55% removed, as 曼 loses 44%), split
into components at blank columns, and keep each component at its natural height and width.
Every piece is scored against every capital drawn tall (689) and short (527), at true size.
A capital sits short when its best real pieces are short ones, and stays short however the
size of a piece is weighed against its shape (four weightings): a capital with no clear answer
stands tall. The check is 曼 itself: M and N must come out short and A tall.

    python3 research/rhythm.py            # writes rhythm.json (and rhythm.pkl for sheets)
"""
import json, os, pickle, sys
import numpy as np
import cairo
from multiprocessing import Pool
from PIL import Image, ImageDraw, ImageFont
from paths import NOTO_CJK, NOTO_INDEX, ROOT
import fixed
from fixed import PX, EMPX, vec, crop, chars

sys.path.insert(0, os.path.join(ROOT, "sources"))
import build as B                                    # noqa: E402

TALL, LOW = B.TALL, B.LOW
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
CUTS = (0.30, 0.35, 0.40, 0.44, 0.50, 0.55)          # fraction of the turned character cut away
WEIGHTS = ((0.9, 0.7), (0.6, 0.5), (1.2, 0.9), (0.9, 0.3))   # (height, width) size penalties


class _Pen:
    def __init__(self, c): self.c = c
    def moveTo(self, p): self.c.move_to(*p)
    def lineTo(self, p): self.c.line_to(*p)
    def curveTo(self, a, b, d): self.c.curve_to(*a, *b, *d)
    def qCurveTo(self, *pts): self.c.line_to(*pts[-1])
    def closePath(self): self.c.close_path()
    def endPath(self): pass


def letter_bitmap(ch, h):
    """a Tangping capital drawn at height h, rasterised at the search scale"""
    path = B.resolve(B.L_[ch][1](h))
    x0, y0, x1, y1 = path.bounds
    w, hh = int((x1 - x0) * PX) + 4, int((y1 - min(y0, 0)) * PX) + 4
    surf = cairo.ImageSurface(cairo.FORMAT_A8, w, hh)
    c = cairo.Context(surf)
    c.translate(-x0 * PX + 2, y1 * PX + 2); c.scale(PX, -PX)
    path.draw(_Pen(c)); c.fill()
    a = np.ndarray((hh, surf.get_stride()), np.uint8, surf.get_data())[:, :w] > 127
    return crop(a)


def templates():
    T = []                                            # (letter, height class, vec, h_px, w_px)
    for ch in LETTERS:
        for cls, h in (("tall", TALL), ("short", LOW)):
            a = letter_bitmap(ch, h)
            T.append((ch, cls, vec(a), a.shape[0], a.shape[1]))
    return T


TPL = FONT = None


def init():
    global TPL, FONT, TV, TH, TW
    TPL = templates()
    FONT = ImageFont.truetype(NOTO_CJK, EMPX, index=NOTO_INDEX)
    TV = np.stack([t[2] for t in TPL])
    TH = np.array([t[3] for t in TPL], float); TW = np.array([t[4] for t in TPL], float)


def work(ch):
    im = Image.new("L", (EMPX * 2, EMPX * 2), 0)
    ImageDraw.Draw(im).text((EMPX // 4, EMPX // 4), ch, font=FONT, fill=255)
    a = np.asarray(im) > 127
    best = {}
    for k in (1, 3):
        r = crop(np.rot90(a, k))
        if r is None: continue
        Hc = r.shape[0]
        for cf in CUTS:
            cut = int(round(Hc * (1 - cf)))          # one cut across the whole character
            kept = r[:cut]
            for x0, x1 in fixed.bands(kept):
                b = kept[:, x0:x1]
                rows = np.nonzero(b.any(1))[0]
                if len(rows) == 0 or not b[-1].any():  # the piece must stand on the cut
                    continue
                p = crop(b)
                h, w = p.shape
                if h < 380 * PX or w < 140 * PX: continue
                v = vec(p)
                if v is None: continue
                ratio = (cut - rows[0]) / cut          # 1.0 = as tall as the whole kept character
                corr = TV @ v
                for wi, (wh, ww) in enumerate(WEIGHTS):
                    s = corr - wh * np.abs(np.log(h / TH)) - ww * np.abs(np.log(w / TW))
                    for i in np.argsort(-s)[:8]:
                        key = (wi, i)
                        if key not in best or s[i] > best[key][0]:
                            best[key] = (float(s[i]), k, cf, x0 / r.shape[1], x1 / r.shape[1], h / PX, w / PX, float(ratio))
    return ch, best


def main():
    C = chars()
    with Pool(initializer=init) as pool:
        res = pool.map(work, C, chunksize=40)
    init()
    found = {(wi, t[0], t[1]): [] for wi in range(len(WEIGHTS)) for t in TPL}
    for ch, best in res:
        for (wi, i), b in best.items():
            found[(wi, TPL[i][0], TPL[i][1])].append((b[0], ch) + b[1:])
    for key in found:
        found[key].sort(reverse=True)
        found[key] = found[key][:40]
    verdict = {}
    for L in LETTERS:
        margins = []
        for wi in range(len(WEIGHTS)):
            top = {cls: np.mean([x[0] for x in found[(wi, L, cls)][:5]]) for cls in ("tall", "short")}
            margins.append(round(float(top["short"] - top["tall"]), 3))
        height = "short" if all(m > 0 for m in margins) else "tall"
        verdict[L] = dict(height=height, short_minus_tall=margins,
                          best_tall=found[(0, L, "tall")][0][1], best_short=found[(0, L, "short")][0][1])
    assert verdict["M"]["height"] == "short" and verdict["N"]["height"] == "short" and verdict["A"]["height"] == "tall", \
        "the analysis must reproduce 曼 → MAN"
    short = "".join(L for L in LETTERS if verdict[L]["height"] == "short")
    out = os.environ.get("JSON", os.path.join(os.path.dirname(os.path.abspath(__file__)), "rhythm.json"))
    json.dump(dict(short=short, letters=verdict), open(out, "w"), ensure_ascii=False, indent=1)
    pickle.dump(found, open(os.environ.get("OUT", "rhythm.pkl"), "wb"))
    for L in LETTERS:
        v = verdict[L]
        print(f"{L}  {v['height']:5}  short−tall {' '.join(f'{m:+.3f}' for m in v['short_minus_tall'])}"
              f"   tall {v['best_tall']}  short {v['best_short']}")
    print("short capitals:", " ".join(short))


if __name__ == "__main__":
    main()
