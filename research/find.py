# Tangping research tools - Copyright 2026 The Tangping Project Authors
# SPDX-License-Identifier: MIT
"""For every GB2312 hanzi: turn a quarter-turn (both ways), take a component band,
slice across the bottom (up to about half), and score the piece against each letter."""
import os
from paths import NOTO_CJK, NOTO_INDEX, TANGPING_EVEN
import numpy as np, pickle, os, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from multiprocessing import Pool

CJK = NOTO_CJK
TEMPLATE = TANGPING_EVEN
EM = 120
CAN = 160
N = 24
TARGETS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
TOP_CUTS = [0, .25, .4, .5]
BOT_CUTS = [0, .15, .25, .35, .45, .55]


def chars():
    out = []
    for hi in range(0xB0, 0xF8):
        for lo in range(0xA1, 0xFF):
            try:
                out.append(bytes([hi, lo]).decode("gb2312"))
            except Exception:
                pass
    return out


def prep(a):
    ys, xs = np.nonzero(a)
    if len(xs) < 30:
        return None
    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = a.shape
    im = Image.fromarray((a * 255).astype(np.uint8)).resize((N, N), Image.BILINEAR)
    im = im.filter(ImageFilter.GaussianBlur(0.9))
    v = np.asarray(im, np.float32).ravel()
    v = v - v.mean()
    n = np.linalg.norm(v)
    if n == 0:
        return None
    return v / n, w / h, h / EM, w / EM


def templates():
    f = ImageFont.truetype(TEMPLATE, EM)
    T = []
    for ch in TARGETS:
        im = Image.new("L", (CAN * 2, CAN * 2), 0)
        ImageDraw.Draw(im).text((20, 20), ch, font=f, fill=255)
        T.append(prep(np.asarray(im) > 127))
    return T


TPL = None


def init():
    global TPL, FONT
    TPL = templates()
    FONT = ImageFont.truetype(CJK, EM, index=NOTO_INDEX)


def bands(r):
    """column ranges of components, split at blank columns (like 日 | 罒 | 又 in 曼)"""
    H, W = r.shape
    col = r.sum(0)
    cuts = [0]
    x = 0
    while x < W:
        if col[x] == 0:
            s = x
            while x < W and col[x] == 0:
                x += 1
            cuts.append((s + x) // 2)
        x += 1
    cuts.append(W)
    cuts = sorted(set(cuts))
    out = []
    for i in range(len(cuts)):
        for j in range(i + 1, len(cuts)):
            out.append((cuts[i], cuts[j]))
    return out[:15]


def work(ch):
    im = Image.new("L", (CAN, CAN), 0)
    ImageDraw.Draw(im).text((20, 0), ch, font=FONT, fill=255)
    a = np.asarray(im) > 127
    best = {}
    tv = np.stack([t[0] for t in TPL])
    tasp = np.array([t[1] for t in TPL])
    for k in (1, 3):                       # 1 = counter-clockwise (as in 曼), 3 = clockwise
        r = np.rot90(a, k)
        ys, xs = np.nonzero(r)
        if len(xs) == 0:
            continue
        r = r[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        H, W = r.shape
        for (x0, x1) in bands(r):
            for tc in TOP_CUTS:
                for bc in BOT_CUTS:
                    if tc + bc > 0.65:
                        continue
                    y0, y1 = int(H * tc), int(H * (1 - bc))
                    sub = r[y0:y1, x0:x1]
                    p = prep(sub)
                    if p is None:
                        continue
                    v, asp, hem, wem = p
                    if not (0.38 <= hem <= 0.95 and wem >= 0.18):
                        continue
                    s = tv @ v - 0.6 * np.abs(np.log(asp / tasp))
                    s += 0.02 * (k == 1) + 0.015 * (bc > 0)    # prefer the reference's own move
                    for i, sc in enumerate(s):
                        if i not in best or sc > best[i][0]:
                            best[i] = (float(sc), k, x0 / W, x1 / W, tc, bc, hem)
    return ch, best


if __name__ == "__main__":
    C = chars()
    print(len(C), "characters")
    with Pool(initializer=init) as pool:
        res = pool.map(work, C, chunksize=30)
    out = {L: [] for L in TARGETS}
    for ch, best in res:
        for i, b in best.items():
            out[TARGETS[i]].append((b[0], ch) + b[1:])
    for L in TARGETS:
        out[L].sort(reverse=True)
        out[L] = out[L][:40]
        print(L, " ".join(f"{x[1]}{'↺' if x[2]==1 else '↻'}{x[0]:.2f}" for x in out[L][:10]))
    pickle.dump(out, open("found.pkl", "wb"))
