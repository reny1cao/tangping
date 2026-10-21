# Tangping research tools - Copyright 2026 The Tangping Project Authors
# SPDX-License-Identifier: MIT
"""Finer pass for hard letters: any straight cut on each side (0–50%), both quarter turns."""
import os
from paths import NOTO_CJK, NOTO_INDEX, TANGPING_EVEN
import numpy as np, pickle
from multiprocessing import Pool
from PIL import Image, ImageDraw, ImageFont
import find
from find import prep, chars, EM, CAN

import os
HARD = os.environ.get("HARD", "BDGPQRSVY")
FR = [0, .125, .25, .375, .5]


def init():
    global TPL, FONT, IDX
    find.init()
    TPL = find.TPL
    FONT = find.FONT
    IDX = [find.TARGETS.index(L) for L in HARD]


def work(ch):
    im = Image.new("L", (CAN, CAN), 0)
    ImageDraw.Draw(im).text((20, 0), ch, font=FONT, fill=255)
    a = np.asarray(im) > 127
    tv = np.stack([TPL[i][0] for i in IDX]); tasp = np.array([TPL[i][1] for i in IDX])
    best = {}
    for k in (1, 3):
        r = np.rot90(a, k)
        ys, xs = np.nonzero(r)
        if len(xs) == 0: continue
        r = r[ys.min():ys.max()+1, xs.min():xs.max()+1]
        H, W = r.shape
        for l in FR:
            for rr in FR:
                if l + rr > .6: continue
                for t in FR:
                    for b in FR:
                        if t + b > .6: continue
                        sub = r[int(H*t):int(H*(1-b)), int(W*l):int(W*(1-rr))]
                        p = prep(sub)
                        if p is None: continue
                        v, asp, hem, wem = p
                        if not (0.38 <= hem <= 0.95 and wem >= 0.18): continue
                        s = tv @ v - 0.6 * np.abs(np.log(asp / tasp))
                        for i, sc in enumerate(s):
                            if i not in best or sc > best[i][0]:
                                best[i] = (float(sc), k, l, 1 - rr, t, b, hem)
    return ch, best


if __name__ == "__main__":
    C = chars()
    with Pool(initializer=init) as pool:
        res = pool.map(work, C, chunksize=30)
    out = {L: [] for L in HARD}
    for ch, best in res:
        for i, b in best.items():
            out[HARD[i]].append((b[0], ch) + b[1:])
    for L in HARD:
        out[L].sort(reverse=True); out[L] = out[L][:40]
        print(L, " ".join(f"{x[1]}{'L' if x[2]==1 else 'R'}{x[0]:.2f}" for x in out[L][:12]))
    pickle.dump(out, open(os.environ.get("OUT", "found2.pkl"), "wb"))
