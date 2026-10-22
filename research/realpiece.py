# Tangping research tools - Copyright 2026 The Tangping Project Authors
# SPDX-License-Identifier: MIT
"""Vector pieces of real hanzi: Noto Sans CJK Bold outline → scale S → quarter-turn → component
band → straight cut. Coordinates come out in Tangping units with the cut on the baseline."""
import numpy as np
import pathops
import cairo
from fontTools.ttLib import TTCollection
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.basePen import BasePen
from paths import NOTO_CJK, NOTO_INDEX

S = 1.35
_noto = TTCollection(NOTO_CJK).fonts[NOTO_INDEX]
_gs = _noto.getGlyphSet()
_cm = _noto.getBestCmap()


def turned(ch, k):
    """the glyph scaled by S and turned: k=1 counter-clockwise (as 曼 → MAN), k=3 clockwise"""
    p = pathops.Path()
    m = (0, S, -S, 0, 0, 0) if k == 1 else (0, -S, S, 0, 0, 0)
    _gs[_cm[ord(ch)]].draw(TransformPen(p.getPen(), m))
    p = pathops.simplify(p, fix_winding=True)
    x0, y0, x1, y1 = p.bounds
    q = pathops.Path()
    p.draw(TransformPen(q.getPen(), (1, 0, 0, 1, -x0, -y1)))     # left edge x=0, top edge y=0
    return q, x1 - x0, y1 - y0


def rect(x0, y0, x1, y1):
    r = pathops.Path(); pen = r.getPen()
    pen.moveTo((x0, y0)); pen.lineTo((x1, y0)); pen.lineTo((x1, y1)); pen.lineTo((x0, y1)); pen.closePath()
    return r


def column_ink(path, width, depth, step=2.0):
    """which x positions (step units apart) have ink, from a fine raster"""
    sc = 1 / step
    w = int(width * sc) + 4; h = int(depth * sc) + 4
    surf = cairo.ImageSurface(cairo.FORMAT_A8, w, h)
    c = cairo.Context(surf); c.scale(sc, -sc)
    draw_cairo(c, path); c.fill()
    a = np.ndarray((h, surf.get_stride()), np.uint8, surf.get_data())[:, :w] > 40
    return a.any(0), a


def gaps(path, width, depth):
    """x positions (units) in the middle of blank column runs, plus both edges"""
    ink, _ = column_ink(path, width, depth)
    xs, x, n = [0.0], 0, len(ink)
    while x < n:
        if not ink[x]:
            s = x
            while x < n and not ink[x]: x += 1
            if 0 < s and x < n: xs.append((s + x) / 2 * 2.0)
        x += 1
    xs.append(width)
    return sorted(set(xs))


def piece(ch, k, fx0, fx1, height, snap=True):
    """band [fx0, fx1] (fractions of the turned width), cut `height` units below the band's top"""
    p, W, H = turned(ch, k)
    xa, xb = fx0 * W, fx1 * W
    if snap:
        g = gaps(p, W, H)
        xa = min(g, key=lambda v: abs(v - xa)); xb = min(g, key=lambda v: abs(v - xb))
    band = pathops.op(p, rect(xa, -H - 10, xb, 10), pathops.PathOp.INTERSECTION)
    top = band.bounds[3]
    cut = pathops.op(band, rect(xa - 1, top - height, xb + 1, top + 10), pathops.PathOp.INTERSECTION)
    bx0 = cut.bounds[0]
    out = pathops.Path()
    cut.draw(TransformPen(out.getPen(), (1, 0, 0, 1, -bx0, -(top - height))))
    return out


class _CP(BasePen):
    def __init__(self, c): super().__init__(None); self.c = c
    def _moveTo(self, p): self.c.move_to(*p)
    def _lineTo(self, p): self.c.line_to(*p)
    def _curveToOne(self, a, b, c): self.c.curve_to(*a, *b, *c)
    def _qCurveToOne(self, a, b):
        x0, y0 = self.c.get_current_point()
        self.c.curve_to(x0 + 2 / 3 * (a[0] - x0), y0 + 2 / 3 * (a[1] - y0),
                        b[0] + 2 / 3 * (a[0] - b[0]), b[1] + 2 / 3 * (a[1] - b[1]), *b)
    def _closePath(self): self.c.close_path()


def draw_cairo(ctx, path):
    path.draw(_CP(ctx))
