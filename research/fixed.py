# Tangping research tools - Copyright 2026 The Tangping Project Authors
# SPDX-License-Identifier: MIT
"""Fixed-scale search: the same move as 曼 → MAN, at the same scale.

Every GB2312 hanzi in Noto Sans CJK Bold is scaled by S (so its strokes come out as heavy as
the original MAN), turned a quarter-turn either way, split into components at blank columns,
and cut straight across at the baseline. Each piece is scored against each letter for shape,
size and stroke weight. Because nothing is rescaled, a winning piece can be used as it is."""
import os, pickle, sys
import numpy as np
from multiprocessing import Pool
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy import ndimage
from paths import NOTO_CJK, NOTO_INDEX, ROOT

S = 1.35                    # Tangping units per Noto unit (曼 cut 44% → A = 689)
PX = 0.08                   # pixels per Tangping unit for the search raster
EMPX = round(1000 * S * PX)
N = 24
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
REG = os.path.join(ROOT, "fonts", "otf", "Tangping-Regular.otf")
EVEN = os.path.join(ROOT, "fonts", "otf", "Tangping-Even.otf")


def chars():
    out = []
    for hi in range(0xB0, 0xF8):
        for lo in range(0xA1, 0xFF):
            try: out.append(bytes([hi, lo]).decode("gb2312"))
            except Exception: pass
    return out


def crop(a):
    ys, xs = np.nonzero(a)
    if len(xs) == 0: return None
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def vec(a):
    im = Image.fromarray((a * 255).astype(np.uint8)).resize((N, N), Image.BILINEAR)
    v = np.asarray(im.filter(ImageFilter.GaussianBlur(0.9)), np.float32).ravel()
    v = v - v.mean(); n = np.linalg.norm(v)
    return v / n if n else None


def weight(a):
    """median stroke thickness in Tangping units"""
    d = ndimage.distance_transform_edt(np.pad(a, 2))
    ridge = (d == ndimage.maximum_filter(d, size=3)) & (d > 1.5)
    return float(np.median(2 * d[ridge]) / PX) if ridge.any() else 0.0


def render(text, path, size, index=0):
    f = ImageFont.truetype(path, size, index=index)
    im = Image.new("L", (size * 3, size * 3), 0)
    ImageDraw.Draw(im).text((size // 2, size // 2), text, font=f, fill=255)
    return np.asarray(im) > 127


def templates():
    T = []      # (label, vec, h_px, w_px, weight)
    size = round(1000 * PX)
    for L in LETTERS:
        for lab, path, ch in ((L, EVEN, L), (L.lower(), REG, L.lower())):
            a = crop(render(ch, path, size))
            T.append((lab, vec(a), a.shape[0], a.shape[1], weight(a)))
    return T


TPL = FONT = None


def init():
    global TPL, FONT, TV, TH, TW
    TPL = templates()
    FONT = ImageFont.truetype(NOTO_CJK, EMPX, index=NOTO_INDEX)
    TV = np.stack([t[1] for t in TPL]); TH = np.array([t[2] for t in TPL], float); TW = np.array([t[3] for t in TPL], float)


def bands(r):
    W = r.shape[1]
    col = r.any(0)
    edges, x = [0], 0
    while x < W:
        if not col[x]:
            s = x
            while x < W and not col[x]: x += 1
            edges.append((s + x) // 2)
        x += 1
    edges.append(W)
    edges = sorted(set(edges))
    return [(edges[i], edges[j]) for i in range(len(edges)) for j in range(i + 1, len(edges))][:21]


def work(ch):
    im = Image.new("L", (EMPX * 2, EMPX * 2), 0)
    ImageDraw.Draw(im).text((EMPX // 4, EMPX // 4), ch, font=FONT, fill=255)
    a = np.asarray(im) > 127
    best = {}
    for k in (1, 3):                                  # 1 = counter-clockwise, as 曼 → MAN
        r = crop(np.rot90(a, k))
        if r is None: continue
        for x0, x1 in bands(r):
            b = r[:, x0:x1]
            rows = np.nonzero(b.any(1))[0]
            if len(rows) == 0: continue
            t, bot = rows[0], rows[-1] + 1
            for hpx in range(int(470 * PX), int(860 * PX) + 1, 2):
                c = t + hpx
                if c > bot: break
                if (bot - c) / (bot - t) > 0.6: continue          # cut at most ~half
                p = b[t:c]
                if not p[-1].any(): continue                        # must stand on the cut
                p = crop(p)
                if p is None or p.shape[1] < 140 * PX: continue
                v = vec(p)
                if v is None: continue
                h, w = p.shape
                s = TV @ v - 0.9 * np.abs(np.log(h / TH)) - 0.7 * np.abs(np.log(w / TW))
                s += 0.02 * (k == 1)
                for i in np.argsort(-s)[:6]:
                    if i not in best or s[i] > best[i][0]:
                        best[i] = (float(s[i]), k, x0, x1, int(c - t), h, w)
    return ch, best


if __name__ == "__main__":
    C = chars()
    if len(sys.argv) > 1: C = C[:int(sys.argv[1])]
    with Pool(initializer=init) as pool:
        res = pool.map(work, C, chunksize=40)
    init()
    out = {t[0]: [] for t in TPL}
    for ch, best in res:
        for i, b in best.items():
            out[TPL[i][0]].append((b[0], ch) + b[1:])
    for lab in out:
        out[lab].sort(reverse=True); out[lab] = out[lab][:80]
        print(lab, " ".join(f"{x[1]}{'↺' if x[2] == 1 else '↻'}{x[0]:.2f}" for x in out[lab][:12]))
    pickle.dump(dict(found=out, tpl=[(t[0], t[2], t[3], t[4]) for t in TPL]),
                open(os.environ.get("OUT", "fixed.pkl"), "wb"))
