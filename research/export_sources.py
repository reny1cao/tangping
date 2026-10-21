# Tangping research tools - Copyright 2026 The Tangping Project Authors
# SPDX-License-Identifier: MIT
"""Export the source map: for each letter in picks.json, the real Hei outline turned a
quarter-turn and cut, as SVG path data, plus a similarity score against the Tangping letter.

Writes docs/data/sources.json (used by docs/index.html).
"""
import json, os
import pathops
from fontTools.ttLib import TTCollection
from fontTools.pens.svgPathPen import SVGPathPen
from paths import NOTO_CJK, NOTO_INDEX, ROOT
from verify import piece, letter_arr, sim, f as noto_bitmap_font, EM

HERE = os.path.dirname(os.path.abspath(__file__))
picks = json.load(open(os.path.join(HERE, "picks.json")))

font = TTCollection(NOTO_CJK).fonts[NOTO_INDEX]
glyphs = font.getGlyphSet()
cmap = font.getBestCmap()


class TurnPen:
    """Draws a glyph turned a quarter-turn: k=1 counter-clockwise (as 曼 → MAN), k=3 clockwise."""
    def __init__(self, k):
        self.path = pathops.Path(); self.pen = self.path.getPen(); self.k = k
    def T(self, pt):
        x, y = pt
        return (-y, x) if self.k == 1 else (y, -x)
    def moveTo(self, pt): self.pen.moveTo(self.T(pt))
    def lineTo(self, pt): self.pen.lineTo(self.T(pt))
    def curveTo(self, *pts): self.pen.curveTo(*[self.T(q) for q in pts])
    def qCurveTo(self, *pts): self.pen.qCurveTo(*[self.T(q) for q in pts])
    def closePath(self): self.pen.closePath()
    def endPath(self): self.pen.endPath()


def svg_d(path, x0, y1):
    pen = SVGPathPen(None)

    class Flip:
        def f(self, pt): return (round(pt[0] - x0, 1), round(y1 - pt[1], 1))
        def moveTo(self, pt): pen.moveTo(self.f(pt))
        def lineTo(self, pt): pen.lineTo(self.f(pt))
        def curveTo(self, *pts): pen.curveTo(*[self.f(q) for q in pts])
        def qCurveTo(self, *pts): pen.qCurveTo(*[self.f(q) for q in pts])
        def closePath(self): pen.closePath()
        def endPath(self): pen.endPath()
    path.draw(Flip())
    return pen.getCommands()


def main():
    out = []
    for L, (ch, k, fx0, fx1, tc, bc) in picks.items():
        tp = TurnPen(k)
        glyphs[cmap[ord(ch)]].draw(tp)
        full = pathops.simplify(tp.path)
        X0, Y0, X1, Y1 = full.bounds
        W, H = X1 - X0, Y1 - Y0
        cx0, cx1 = X0 + fx0 * W, X0 + fx1 * W
        cy1, cy0 = Y1 - tc * H, Y0 + bc * H
        rect = pathops.Path(); rp = rect.getPen()
        rp.moveTo((cx0, cy0)); rp.lineTo((cx1, cy0)); rp.lineTo((cx1, cy1)); rp.lineTo((cx0, cy1)); rp.closePath()
        kept = pathops.op(full, rect, pathops.PathOp.INTERSECTION)
        score = sim(piece(ch, k, fx0, fx1, tc, bc, em=EM, font=noto_bitmap_font), letter_arr(L))
        cuts = []
        if bc: cuts.append(["h", round(Y1 - cy0, 1)])
        if tc: cuts.append(["h", round(Y1 - cy1, 1)])
        if fx0 > 0: cuts.append(["v", round(cx0 - X0, 1)])
        if fx1 < 1: cuts.append(["v", round(cx1 - X0, 1)])
        out.append(dict(L=L, ch=ch, turn="ccw" if k == 1 else "cw", cut=round(bc * 100), top=round(tc * 100),
                        band=fx0 > 0 or fx1 < 1, w=round(W), h=round(H),
                        full=svg_d(full, X0, Y1), piece=svg_d(kept, X0, Y1), cuts=cuts, score=round(score, 2)))
        print(f"{L} ← {ch}  {score:.2f}")
    dest = os.path.join(ROOT, "docs", "data", "sources.json")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    json.dump(out, open(dest, "w"), ensure_ascii=False)
    print("wrote", dest)


if __name__ == "__main__":
    main()
