# Tangping research tools - Copyright 2026 The Tangping Project Authors
# SPDX-License-Identifier: MIT
import os
from paths import NOTO_CJK, NOTO_INDEX, TANGPING_EVEN
import pickle, sys, numpy as np
from PIL import Image, ImageDraw, ImageFont

CJK = NOTO_CJK
EM = 120
CAN = 160
f = ImageFont.truetype(CJK, EM, index=NOTO_INDEX)
lab = ImageFont.truetype(CJK, 20, index=NOTO_INDEX)
big = ImageFont.truetype(TANGPING_EVEN, 90)


def piece(ch, k, fx0, fx1, tc, bc, em=EM, font=None):
    font = font or f
    im = Image.new("L", (int(em * 1.35), int(em * 1.35)), 0)
    ImageDraw.Draw(im).text((em // 6, 0), ch, font=font, fill=255)
    r = np.rot90(np.asarray(im) > 127, k)
    ys, xs = np.nonzero(r)
    r = r[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    H, W = r.shape
    sub = r[int(H * tc):int(H * (1 - bc)), int(fx0 * W):int(fx1 * W)]
    ys, xs = np.nonzero(sub)
    return sub[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


if __name__ == "__main__":
    import os
    found = pickle.load(open(os.environ.get("FOUND", "found.pkl"), "rb"))
    letters = sys.argv[1]
    out = sys.argv[2]
    K = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    cw, ch_ = 140, 175
    img = Image.new("L", (110 + cw * K, ch_ * len(letters)), 255)
    d = ImageDraw.Draw(img)
    for row, L in enumerate(letters):
        y = row * ch_
        d.text((14, y + 30), L, font=big, fill=0)
        for i, (sc, ch, k, fx0, fx1, tc, bc, hem) in enumerate(found[L][:K]):
            p = piece(ch, k, fx0, fx1, tc, bc)
            pim = Image.fromarray(((~p) * 255).astype(np.uint8))
            x = 110 + i * cw
            d.rectangle((x + 4, y + 4, x + cw - 4, y + 132), outline=225)
            img.paste(pim, (x + (cw - pim.width) // 2, y + 128 - pim.height))
            d.text((x + 6, y + 138), f"{i}{ch}{'↺' if k == 1 else '↻'} -{int(bc*100)}%", font=lab, fill=0)
    img.save(out)
