# Tangping research tools - Copyright 2026 The Tangping Project Authors
# SPDX-License-Identifier: MIT
"""Evidence image for rhythm.py: each capital's best real piece standing tall and sitting short,
cut exactly as 曼 is cut, at the original scale. Writes docs/images/rhythm.png.

    python3 research/rhythm.py && python3 research/rhythm_sheet.py
"""
import json, os, pickle
import cairo
import pathops
from fontTools.pens.transformPen import TransformPen
from paths import ROOT
from realpiece import turned, gaps, rect, draw_cairo

HERE = os.path.dirname(os.path.abspath(__file__))
found = pickle.load(open(os.environ.get("OUT", os.path.join(HERE, "rhythm.pkl")), "rb"))
result = json.load(open(os.path.join(HERE, "rhythm.json")))
INK, PALE, GREEN, RED, PAPER, MUTED = (.067, .082, .075), (.73, .79, .75), (.11, .45, .27), (.77, .32, .23), (.965, .973, .961), (.36, .42, .38)


def piece(ch, k, cf, fx0, fx1):
    """the component of ch between fx0 and fx1, after one cut across the whole turned character"""
    p, W, H = turned(ch, k)
    cy = -H * (1 - cf)
    kept = pathops.op(p, rect(-10, cy, W + 10, 10), pathops.PathOp.INTERSECTION)
    g = gaps(kept, W, H)
    xa = min(g, key=lambda v: abs(v - fx0 * W)); xb = min(g, key=lambda v: abs(v - fx1 * W))
    q = pathops.op(kept, rect(xa, cy - 5, xb, 10), pathops.PathOp.INTERSECTION)
    out = pathops.Path(); q.draw(TransformPen(out.getPen(), (1, 0, 0, 1, -q.bounds[0], -cy)))
    return out, q.bounds[2] - q.bounds[0]


def best(L, cls):
    for x in found[(0, L, cls)]:
        try:
            p, w = piece(x[1], x[2], x[3], x[4], x[5])
        except Exception:
            continue
        if w < 700:
            return x, p
    return None, None


def main():
    sc, CW, CH = 0.085, 150, 190
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 13 * CW + 40, 2 * CH + 70)
    c = cairo.Context(surf); c.set_source_rgb(*PAPER); c.paint()
    c.select_font_face("Noto Sans CJK SC")
    c.set_source_rgb(*GREEN); c.set_font_size(15); c.move_to(20, 28)
    c.show_text("Each capital's best real piece standing tall (left) and sitting short (right), cut exactly as 曼 is cut, "
                "at the same scale. Short wins only if it wins under every weighting.")
    for i, L in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        v = result["letters"][L]
        short = v["height"] == "short"
        margin = sum(v["short_minus_tall"]) / len(v["short_minus_tall"])
        unclear = not short and any(m > 0 for m in v["short_minus_tall"])
        x0 = 20 + (i % 13) * CW; y0 = 50 + (i // 13) * CH
        for j, cls in enumerate(("tall", "short")):
            x, p = best(L, cls)
            if p is None:
                continue
            c.save(); c.translate(x0 + 4 + j * 70, y0 + 100); c.scale(sc, -sc)
            c.set_source_rgb(*(INK if (cls == "short") == short else PALE)); draw_cairo(c, p); c.fill(); c.restore()
            c.set_source_rgb(*MUTED); c.set_font_size(12); c.move_to(x0 + 4 + j * 70, y0 + 120); c.show_text(x[1])
        c.set_source_rgb(*INK); c.set_font_size(28); c.move_to(x0 + 4, y0 + 156); c.show_text(L)
        c.set_source_rgb(*(RED if short else GREEN)); c.set_font_size(13); c.move_to(x0 + 32, y0 + 150)
        c.show_text("short" if short else ("tall (unclear)" if unclear else "tall"))
        c.set_source_rgb(*MUTED); c.set_font_size(11); c.move_to(x0 + 32, y0 + 166)
        c.show_text(f"short − tall {margin:+.3f}")
    dest = os.path.join(ROOT, "docs", "images", "rhythm.png")
    surf.write_to_png(dest)
    print("wrote", dest)


if __name__ == "__main__":
    main()
