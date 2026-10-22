# Tangping research tools - Copyright 2026 The Tangping Project Authors
# SPDX-License-Identifier: MIT
"""Contact sheets for fixed.py: the best real pieces per letter, drawn at true relative size."""
import os, pickle, sys
import numpy as np
import cairo
from PIL import Image, ImageDraw, ImageFont
import fixed
from realpiece import piece, draw_cairo
from paths import NOTO_CJK, NOTO_INDEX

PXS = 0.13
CW, CH = 112, 132


def frac(ch, k, x0, x1):
    f = ImageFont.truetype(NOTO_CJK, fixed.EMPX, index=NOTO_INDEX)
    im = Image.new("L", (fixed.EMPX * 2, fixed.EMPX * 2), 0)
    ImageDraw.Draw(im).text((fixed.EMPX // 4, fixed.EMPX // 4), ch, font=f, fill=255)
    r = fixed.crop(np.rot90(np.asarray(im) > 127, k))
    return x0 / r.shape[1], x1 / r.shape[1]


def sheet(found, labels, out, K=14):
    W = 70 + CW * K
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, W, CH * len(labels))
    c = cairo.Context(surf); c.set_source_rgb(1, 1, 1); c.paint()
    c.select_font_face("Noto Sans CJK SC");
    picks = {}
    for row, lab in enumerate(labels):
        y = row * CH
        c.set_source_rgb(0, 0, 0); c.set_font_size(40); c.move_to(14, y + 70); c.show_text(lab)
        seen, i = set(), 0
        for (sc, ch, k, x0, x1, hpx, h, w) in found[lab]:
            if ch in seen: continue
            seen.add(ch)
            fx0, fx1 = frac(ch, k, x0, x1)
            try:
                p = piece(ch, k, fx0, fx1, hpx / fixed.PX)
            except Exception:
                continue
            picks.setdefault(lab, []).append((ch, k, fx0, fx1, hpx / fixed.PX))
            x = 70 + i * CW
            c.save(); c.translate(x + 8, y + 108); c.scale(PXS, -PXS)
            c.set_source_rgb(0.92, 0.92, 0.92)
            c.rectangle(0, 0, 340, 689); c.fill()        # 340 × 689 reference box
            c.set_source_rgb(0, 0, 0); draw_cairo(c, p); c.fill(); c.restore()
            c.set_source_rgb(0.3, 0.3, 0.3); c.set_font_size(13); c.move_to(x + 8, y + 126)
            c.show_text(f"{i} {ch}{'↺' if k == 1 else '↻'} {sc:.2f}")
            i += 1
            if i >= K: break
    surf.write_to_png(out)
    return picks


if __name__ == "__main__":
    d = pickle.load(open(sys.argv[1], "rb"))
    labels = sys.argv[2].split(",")
    picks = sheet(d["found"], labels, sys.argv[3])
    pickle.dump(picks, open(sys.argv[3] + ".pkl", "wb"))
