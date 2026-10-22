#!/usr/bin/env python3
# Tangping (躺平体) font build script
# Copyright 2026 The Tangping Project Authors
# SPDX-License-Identifier: MIT  (the fonts this script produces are licensed under the SIL OFL 1.1)
"""Builds Tangping-Regular.otf and Tangping-Even.otf from code.

Latin letters drawn as bold Hei hanzi lying on their side (曼 turned a quarter-turn and cut reads MAN).
Rules, measured from the original 曼 → MAN image (1px ≈ 4.5 units):
  * stems (Hei horizontals turned upright) = 100 units, bars (Hei verticals turned flat) = 135;
    inner bars are lighter (~112), as the reference A's crossbar is
  * every stem is cut flat at the baseline
  * exposed long edges of bars are slightly concave and flare at the corners
  * strokes falling to the right are 撇: tapering, flat-cut
  * strokes rising to the right are 捺: sweeping past the top, angled tip
  * where a Latin letter is round, its corner bends like a Hei turn (横折弯, 竖弯 as in 九 己 乚);
    where it is square, the corner stays square (O is 口)
  * condensed: two-stem letters are 340 wide with a 140 counter
  * two heights: tall 689 and short 527
      capitals stand tall; Regular sets M N V W X Y Z short, as in the original MAN
      lowercase stands on the short height, with ascenders to 689 and descenders to -190

Usage:  python3 sources/build.py            # writes fonts/otf and fonts/webfonts
"""
import pathops
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString

VERSION = "4.000"
COPYRIGHT = "Copyright 2026 The Tangping Project Authors (https://github.com/reny1cao/tangping)"
DESIGNER = "Rocco × Claude"
PROJECT_URL = "https://github.com/reny1cao/tangping"

S, B, C = 100, 135, 140        # stem, bar, counter
TALL, LOW = 689, 527
SB = 43
W2 = 2 * S + C                 # 340
LOWCAPS = set("MNVWXYZ")       # capitals that sit low in Regular
DESC = -190
RO, RI = 130, 40               # Hei turn radii (outer, counter)


def bi(h):
    """inner (cross) bar thickness: thinner than the outer bars, as in the reference A (~110),
    so letters with stacked bars (B E S 8 3) stay even in colour"""
    return 112 if h >= 600 else 108


# ================================================================ primitives
class Shape:
    def __init__(self):
        self.contours = []
        self.cuts = []          # contours subtracted after the union (Hei turns)

    def cut(self, *pts):
        self.cuts.append([("M", pts[0])] + [("L", p) for p in pts[1:]])
        return self

    def transformed(self, sx=1.0, sy=1.0, dx=0.0, dy=0.0):
        out = Shape()
        f = lambda p: (p[0] * sx + dx, p[1] * sy + dy)
        out.contours = [[(op[0],) + tuple(f(p) for p in op[1:]) for op in c] for c in self.contours]
        out.cuts = [[(op[0],) + tuple(f(p) for p in op[1:]) for op in c] for c in self.cuts]
        return out

    def poly(self, *pts):
        self.contours.append([("M", pts[0])] + [("L", p) for p in pts[1:]])
        return self

    def raw(self, ops):
        self.contours.append(ops)
        return self

    def add(self, other, dx=0, dy=0):
        """add another shape; its cuts (turns, notches) are applied to it first, so they never
        bite into what it is added to"""
        if other.cuts:
            other = other.baked()
        t = other.transformed(1, 1, dx, dy)
        self.contours += t.contours
        return self

    def baked(self):
        """the resolved outline (union minus cuts) as plain contours"""
        out = Shape()
        for segs in _contours(resolve(self)):
            if not segs:
                continue
            ops = [("M", segs[0][1][0])]
            for kind, P in segs:
                ops.append(("L", P[1]) if kind == "L" else ("C", P[1], P[2], P[3]))
            out.contours.append(ops)
        return out


def to_path(contour, dx=0):
    p = pathops.Path()
    pen = p.getPen()
    for op in contour:
        pts = [(q[0] + dx, q[1]) for q in op[1:]]
        if op[0] == "M":
            pen.moveTo(pts[0])
        elif op[0] == "L":
            pen.lineTo(pts[0])
        elif op[0] == "C":
            pen.curveTo(*pts)
    pen.closePath()
    return p


def rect(sh, x0, y0, x1, y1):
    return sh.poly((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def stem(sh, x, y0, y1, w=S):
    return rect(sh, x, y0, x + w, y1)


def bar(sh, x0, x1, y0, y1, top=False, bot=False, fl=True, fr=True):
    """Bar = rotated Hei vertical. Exposed long edge is concave, corners flare."""
    L = x1 - x0
    sag = 0.022 * L
    f, k = 6, 28
    ops = []
    if bot:
        xl, xr = x0 - (f if fl else 0), x1 + (f if fr else 0)
        ops += [("M", (x0, y0 + k)),
                ("C", (x0, y0 + 11), (xl + f * .4, y0 + 2), (xl, y0)),
                ("C", (x0 + L * .3, y0 + sag * 1.33), (x1 - L * .3, y0 + sag * 1.33), (xr, y0)),
                ("C", (xr - f * .4, y0 + 2), (x1, y0 + 11), (x1, y0 + k))]
    else:
        ops += [("M", (x0, y0)), ("L", (x1, y0))]
    if top:
        xl, xr = x0 - (f if fl else 0), x1 + (f if fr else 0)
        ops += [("L", (x1, y1 - k)),
                ("C", (x1, y1 - 11), (xr - f * .4, y1 - 2), (xr, y1)),
                ("C", (x1 - L * .3, y1 - sag * 1.33), (x0 + L * .3, y1 - sag * 1.33), (xl, y1)),
                ("C", (xl + f * .4, y1 - 2), (x0, y1 - 11), (x0, y1 - k))]
    else:
        ops += [("L", (x1, y1)), ("L", (x0, y1))]
    return sh.raw(ops)


def tbar(sh, x0, x1, h, t=B, **kw):
    return bar(sh, x0, x1, h - t, h, top=True, **kw)


def bbar(sh, x0, x1, y=0, t=B, **kw):
    return bar(sh, x0, x1, y, y + t, bot=True, **kw)


def xbar(sh, x0, x1, y0, t=B):
    return rect(sh, x0, y0, x1, y0 + t)


def pie(sh, xt, yt, xb, yb, wt=132, wb=116, slant=0):
    """撇 rotated: runs down-right, tapers, flat-cut bottom."""
    return sh.poly((xb, yb), (xb + wb, yb), (xt + wt, yt), (xt, yt - slant))


def na(sh, xb, yb, xt, yt, wb=118, wt=126, tipdrop=59, bend=0.35):
    """捺 rotated: sweeps up-right to a tip, angled cut."""
    dx, dy = xt - xb, yt - yb
    l1 = (xb + dx * (0.55 + bend * .3), yb + dy * 0.45)
    l2 = (xt - dx * 0.02, yt - dy * 0.35)
    r_top = (xt + wt, yt - tipdrop)
    r1 = (xt + wt - dx * 0.05, yt - tipdrop - dy * 0.35)
    r2 = (xb + wb + dx * (0.45 + bend * .3), yb + dy * 0.35)
    return sh.raw([("M", (xb, yb)), ("C", l1, l2, (xt, yt)), ("L", r_top),
                   ("C", r1, r2, (xb + wb, yb))])


def sweep(sh, x0, y0, y1, xb0, xb1):
    """curved 撇 leg: leaves the stem between y0..y1 and lands flat on the baseline at xb0..xb1"""
    return sh.raw([("M", (x0, y1)),
                   ("C", (x0 + (xb1 - x0) * 0.55, y1 - 10), (xb1 - 10, y1 * 0.5), (xb1, 0)),
                   ("L", (xb0, 0)),
                   ("C", (xb0 - 6, y0 * 0.45), (x0 + (xb0 - x0) * 0.45, y0 - 4), (x0, y0))])


def sq(sh, x, y, w=118):
    return rect(sh, x, y, x + w, y + w)


def box(sh, x0, y0, x1, y1, ts=S, tb=B, top=True, bot=True):
    stem(sh, x0, y0, y1, ts); stem(sh, x1 - ts, y0, y1, ts)
    if top: bar(sh, x0, x1, y1 - tb, y1, top=True)
    else: xbar(sh, x0, x1, y1 - tb, tb)
    if bot: bar(sh, x0, x1, y0, y0 + tb, bot=True)
    else: xbar(sh, x0, x1, y0, tb)
    return sh


def over(h):
    """how far 捺 tips rise above the stems"""
    return 175 if h < 600 else 140



def bend(sh, x, y, sx, sy, ro=None, ri=None, ts=S, tb=B, k=0.58):
    """Hei turn (横折弯 / 竖弯): round the outer corner at (x, y), and the counter corner inside it.
    sx/sy = +1 for a right/top corner, -1 for a left/bottom corner."""
    ro = RO if ro is None else ro
    ri = RI if ri is None else ri
    if ro <= 0:
        return sh
    M = lambda u, v: (x + sx * u, y + sy * v)
    e, q = 40, 1 - k
    sh.cuts.append([("M", M(-ro, 0)), ("L", M(-ro, e)), ("L", M(e, e)), ("L", M(e, -ro)), ("L", M(0, -ro)),
                    ("C", M(0, -ro * q), M(-ro * q, 0), M(-ro, 0))])
    if ri:
        cx, cy = -ts, -tb
        sh.raw([("M", M(cx, cy)), ("L", M(cx, cy - ri)),
                ("C", M(cx, cy - ri * q), M(cx - ri * q, cy), M(cx - ri, cy))])
    return sh


def pie_c(sh, xt, yt, xb, yb, wt=124, wb=108, bow=0.06):
    """撇 turned: falls to the right, tapers, flat cut at both ends; the edges bow slightly"""
    dx, dy = xb - xt, yb - yt
    nx, ny = -dy, dx                      # normal (pointing up-right for a down-right stroke)
    L = (dx * dx + dy * dy) ** 0.5
    bx, by = nx / L * bow * L, ny / L * bow * L
    a, b = (xt, yt), (xb, yb)
    c, d = (xb + wb, yb), (xt + wt, yt)
    return sh.raw([("M", a),
                   ("C", (a[0] + dx / 3 + bx, a[1] + dy / 3 + by), (a[0] + 2 * dx / 3 + bx, a[1] + 2 * dy / 3 + by), b),
                   ("L", c),
                   ("C", (c[0] - dx / 3 + bx * 0.6, c[1] - dy / 3 + by * 0.6),
                         (c[0] - 2 * dx / 3 + bx * 0.6, c[1] - 2 * dy / 3 + by * 0.6), d)])


# ================================================================ letters
# each fn(h) -> Shape ; widths are drawing widths (side bearings added at build)
L_ = {}


def letter(ch, width):
    def deco(fn):
        L_[ch] = (width, fn)
        return fn
    return deco


@letter("A", W2)
def _A(h):
    s = Shape()
    tbar(s, 0, W2, h)
    stem(s, 0, 0, h - B + 1); stem(s, 240, 0, h - B + 1)
    xbar(s, 0, W2, 122, B if h >= 600 else bi(h))   # full bar weight, as measured in the reference
    return s


@letter("B", W2)
def _B(h):            # 日 lying down; the bowls turn on the right
    s = Shape(); t = bi(h)
    mid = round((h - 2 * B - t) * 0.54) + B
    stem(s, 0, 0, h); stem(s, 240, 0, h)
    tbar(s, 0, W2, h, fr=False); bbar(s, 0, W2, fr=False)
    xbar(s, 0, W2, mid, t)
    bend(s, W2, h, 1, 1); bend(s, W2, 0, 1, -1)
    return s


@letter("C", 330)
def _C(h):
    s = Shape()
    stem(s, 0, 0, h)
    tbar(s, 0, 330, h, fl=False); bbar(s, 0, 320, fl=False)
    bend(s, 0, h, -1, 1); bend(s, 0, 0, -1, -1)
    return s


@letter("D", W2)
def _D(h):            # 刀's turn: the right side bends
    s = box(Shape(), 0, 0, W2, h)
    r = min(RO * 1.75, h * 0.33)
    bend(s, W2, h, 1, 1, r, RI * 2); bend(s, W2, 0, 1, -1, r, RI * 2)
    return s


@letter("E", 330)
def _E(h):            # 山 lying down
    s = Shape(); t = bi(h)
    stem(s, 0, 0, h)
    tbar(s, 0, 310, h); bbar(s, 0, 330)
    xbar(s, 0, 290, round((h - t) / 2), t)
    return s


@letter("F", 310)
def _F(h):            # 岂
    s = Shape(); t = bi(h)
    stem(s, 0, 0, h)
    tbar(s, 0, 310, h)
    xbar(s, 0, 290, round(h * 0.40), t)
    return s


@letter("G", W2)
def _G(h):
    s = Shape(); t = bi(h)
    stem(s, 0, 0, h)
    tbar(s, 0, W2, h, fl=False); bbar(s, 0, W2, fl=False)
    top = round(h * 0.47)
    stem(s, 240, 0, top)
    xbar(s, 160, W2, top - t, t)
    bend(s, 0, h, -1, 1); bend(s, 0, 0, -1, -1); bend(s, W2, 0, 1, -1)
    return s


@letter("H", W2)
def _H(h):            # 工 lying down
    s = Shape(); t = bi(h)
    stem(s, 0, 0, h); stem(s, 240, 0, h)
    xbar(s, 0, W2, round((h - t) / 2), t)
    return s


@letter("I", 300)
def _I(h):            # 工
    s = Shape()
    tbar(s, 0, 300, h); bbar(s, 0, 300)
    stem(s, 100, 0, h)
    return s


@letter("J", W2)
def _J(h):            # 亅
    s = Shape()
    stem(s, 240, 0, h)
    bbar(s, 0, W2, fr=False)
    stem(s, 0, 0, round(h * 0.36))
    bend(s, W2, 0, 1, -1); bend(s, 0, 0, -1, -1)
    return s


@letter("K", 450)
def _K(h):            # 大 lying down
    s = Shape()
    stem(s, 0, 0, h)
    sweep(s, 70, round(h * 0.40), round(h * 0.58), 290, 405)
    tip = h + (round(h * 0.1) if h > 600 else over(h) - 60)
    na(s, 70, round(h * 0.42), 320, tip, wb=124, wt=118, tipdrop=56)
    return s


@letter("L", 320)
def _L(h):
    s = Shape()
    stem(s, 0, 0, h)
    bbar(s, 0, 320)
    return s


@letter("M", 486)
def _M(h):            # measured
    s = Shape()
    tbar(s, 0, 486, h)
    for x in (0, 193, 386):
        stem(s, x, 0, h - B + 1)
    return s


def n_shape(sh, h, with_stem=True, ko=None):
    """N traced from the reference (stem 518). Tip overshoot shrinks on tall forms."""
    k = h / 518
    if ko is None:
        ko = 1.0 if k <= 1.02 else 0.62

    def Y(y):
        return y * k if y <= 518 else 518 * k + (y - 518) * ko

    ops = []
    if with_stem:
        ops += [("M", (0, 0)), ("L", (104, 0)), ("L", (104, Y(281))), ("L", (261, 0))]
    else:
        ops += [("M", (261, 0))]
    ops += [("L", (378, 0)),
            ("C", (430, Y(165)), (515, Y(420)), (536, Y(706))),
            ("L", (410, Y(765))),
            ("C", (400, Y(560)), (365, Y(340)), (315, Y(153))),
            ("L", (306, Y(162)))]
    if with_stem:
        ops += [("C", (250, Y(266)), (160, Y(400)), (113, Y(459))),
                ("L", (68, Y(518))), ("L", (0, Y(437)))]
    else:
        ops += [("C", (250, Y(266)), (165, Y(410)), (112, Y(518))),
                ("L", (0, Y(468)))]
    return sh.raw(ops)


@letter("N", 536)
def _N(h):
    return n_shape(Shape(), h)


@letter("O", W2)
def _O(h):
    return box(Shape(), 0, 0, W2, h)          # 口: the one round letter that stays square


@letter("P", W2)
def _P(h):
    s = Shape(); t = bi(h)
    mid = round(h * 0.34)
    stem(s, 0, 0, h)
    tbar(s, 0, W2, h, fr=False)
    stem(s, 240, mid, h - B + 1)
    xbar(s, 0, W2, mid, t)
    bend(s, W2, h, 1, 1); bend(s, W2, mid, 1, -1, ri=RI, tb=t)
    return s


@letter("Q", 360)
def _Q(h):
    s = _O(h)
    s.poly((240, 120), (345, 120), (425, -125), (320, -125))      # a 撇 foot kicks out below the corner
    return s


@letter("R", 390)
def _R(h):
    s = Shape(); t = bi(h)
    mid = round(h * 0.40)
    stem(s, 0, 0, h)
    tbar(s, 0, W2, h, fr=False)
    stem(s, 240, mid, h - B + 1)
    xbar(s, 0, W2 - 60, mid, t)
    bend(s, W2, h, 1, 1); bend(s, W2, mid + 2, 1, -1, ri=0)
    sweep(s, 100, mid - 2, mid + t, 270, 390)
    return s


@letter("S", W2)
def _S(h):
    s = Shape(); t = bi(h)
    mid = round((h - t) / 2)
    tbar(s, 0, W2, h, fl=False)
    stem(s, 0, mid, h - B + 1)
    xbar(s, 0, W2, mid, t)
    stem(s, 240, B - 1, mid + 1)
    bbar(s, 0, W2, fr=False)
    bend(s, 0, h, -1, 1); bend(s, 0, mid, -1, -1, tb=t)
    bend(s, W2, mid + t, 1, 1, tb=t); bend(s, W2, 0, 1, -1)
    return s


@letter("T", 480)
def _T(h):            # 十 with its top half cut: wide bar
    s = Shape()
    tbar(s, 0, 480, h)
    stem(s, 190, 0, h - B + 1)
    return s


@letter("U", W2)
def _U(h):
    s = Shape()
    stem(s, 0, 0, h); stem(s, 240, 0, h)
    bbar(s, 0, W2, fl=False, fr=False)
    bend(s, 0, 0, -1, -1); bend(s, W2, 0, 1, -1)
    return s


@letter("V", 536)
def _V(h):
    return n_shape(Shape(), h, with_stem=False)


@letter("W", 486)
def _W(h):            # 山
    s = Shape()
    bbar(s, 0, 486)
    for x in (0, 193, 386):
        stem(s, x, B - 1, h)
    return s


@letter("X", 500)
def _X(h):            # 乂: a 撇 falling right, crossed by a 捺 rising past the top
    s = Shape()
    pie_c(s, 0, h, 290, 0, wt=120, wb=104, bow=0.05)
    na(s, 10, 0, 360, h + over(h), wb=112, wt=116, tipdrop=52)
    return s


@letter("Y", 480)
def _Y(h):
    s = Shape()
    jy = round(h * 0.46)
    pie_c(s, 0, h, 150, jy - 6, wt=122, wb=112, bow=0.05)
    na(s, 140, jy - 40, 350, h + over(h), wb=122, wt=118, tipdrop=55)
    stem(s, 150, 0, jy + 20, w=108)
    return s


@letter("Z", 420)
def _Z(h):
    s = Shape()
    tbar(s, 0, 420, h); bbar(s, 0, 420)
    pie_c(s, 292, h - B + 1, 0, B - 1, wt=128, wb=128, bow=-0.03)
    return s


# ================================================================ lowercase (x-height 527, ascenders 689, descenders -190)
XH, ASC, DSC = LOW, TALL, DESC
LB, LI = 124, 104                     # lowercase outer and inner bars
LC_ = {}


def lower(ch, width, top_x=None, asc=False):
    def deco(fn):
        LC_[ch] = (width, fn, top_x, asc)
        return fn
    return deco


@lower("a", 320)
def _la():
    s = Shape()
    tbar(s, 0, 320, XH, t=LB, fr=False)
    stem(s, 220, 0, XH - LB + 1)
    xbar(s, 0, 320, 205, LI)
    stem(s, 0, 0, 205 + LI)
    bbar(s, 0, 320, t=LB, fr=False)
    bend(s, 320, XH, 1, 1, tb=LB)
    return s


@lower("b", 320, asc=True)
def _lb():
    s = Shape()
    stem(s, 0, 0, ASC)
    bar(s, 0, 320, XH - LB, XH, top=True, fl=False, fr=False)
    stem(s, 220, LB - 1, XH - LB + 1)
    bbar(s, 0, 320, t=LB, fr=False)
    bend(s, 320, XH, 1, 1, tb=LB); bend(s, 320, 0, 1, -1, tb=LB)
    return s


@lower("c", 300)
def _lc():
    s = Shape()
    stem(s, 0, 0, XH)
    tbar(s, 0, 300, XH, t=LB, fl=False); bbar(s, 0, 290, t=LB, fl=False)
    bend(s, 0, XH, -1, 1, tb=LB); bend(s, 0, 0, -1, -1, tb=LB)
    return s


@lower("d", 320, top_x=270, asc=True)
def _ld():
    s = Shape()
    stem(s, 220, 0, ASC)
    bar(s, 0, 320, XH - LB, XH, top=True, fl=False, fr=False)
    stem(s, 0, LB - 1, XH - LB + 1)
    bbar(s, 0, 320, t=LB, fl=False)
    bend(s, 0, XH, -1, 1, tb=LB); bend(s, 0, 0, -1, -1, tb=LB)
    return s


@lower("e", 320)
def _le(left_round=True):
    s = Shape()
    stem(s, 0, 0, XH)
    tbar(s, 0, 320, XH, t=LB, fl=False, fr=False)
    stem(s, 220, 225, XH - LB + 1)
    xbar(s, 0, 320, 225, LI)
    bbar(s, 0, 300, t=LB, fl=False)
    bend(s, 320, XH, 1, 1, tb=LB)
    if left_round:
        bend(s, 0, XH, -1, 1, tb=LB); bend(s, 0, 0, -1, -1, tb=LB)
    return s


@lower("f", 270, top_x=110, asc=True)
def _lf():
    s = Shape()
    stem(s, 60, 0, ASC)
    tbar(s, 60, 270, ASC, t=LB, fl=False)
    xbar(s, 0, 250, XH - LI, LI)
    bend(s, 60, ASC, -1, 1, tb=LB)
    return s


@lower("g", 320)
def _lg():
    s = Shape()
    tbar(s, 0, 320, XH, t=LB, fl=False)
    stem(s, 0, 0, XH - LB + 1)
    stem(s, 220, DSC + LB - 1, XH)
    xbar(s, 0, 320, 0, LI)
    bbar(s, 0, 320, DSC, t=LB, fr=False)
    bend(s, 0, XH, -1, 1, tb=LB); bend(s, 0, 0, -1, -1, tb=LI); bend(s, 320, DSC, 1, -1, tb=LB)
    return s


@lower("h", 320, top_x=50, asc=True)
def _lh():
    s = Shape()
    stem(s, 0, 0, ASC)
    bar(s, 0, 320, XH - LB, XH, top=True, fl=False)
    stem(s, 220, 0, XH - LB + 1)
    return s


@lower("i", 100)
def _li():
    s = Shape()
    stem(s, 0, 0, XH)
    return s


@lower("j", 230)
def _lj():
    s = Shape()
    stem(s, 130, DSC + LB - 1, XH)
    bbar(s, 0, 230, DSC, t=LB, fr=False)
    bend(s, 230, DSC, 1, -1, tb=LB)
    return s


@lower("k", 420, top_x=50, asc=True)
def _lk():
    s = Shape()
    stem(s, 0, 0, ASC)
    sweep(s, 70, round(XH * 0.36), round(XH * 0.56), 280, 395)
    na(s, 70, round(XH * 0.40), 300, XH + 70, wb=118, wt=112, tipdrop=52)
    return s


@lower("l", 100, asc=True)
def _ll():
    return stem(Shape(), 0, 0, ASC)


@lower("m", 470)
def _lm():
    s = Shape()
    tbar(s, 0, 470, XH, t=LB)
    for x in (0, 185, 370):
        stem(s, x, 0, XH - LB + 1)
    return s


@lower("n", 320)
def _ln():
    s = Shape()
    tbar(s, 0, 320, XH, t=LB)
    stem(s, 0, 0, XH - LB + 1); stem(s, 220, 0, XH - LB + 1)
    return s


@lower("o", 320)
def _lo():
    return box(Shape(), 0, 0, 320, XH, tb=LB)


@lower("p", 320)
def _lp():
    s = Shape()
    stem(s, 0, DSC, XH)
    bar(s, 0, 320, XH - LB, XH, top=True, fr=False)
    stem(s, 220, 0, XH)
    xbar(s, 0, 320, 0, LB)
    bend(s, 320, XH, 1, 1, tb=LB); bend(s, 320, 0, 1, -1, tb=LB)
    return s


@lower("q", 320, top_x=160)
def _lq():
    s = Shape()
    stem(s, 220, DSC, XH)
    bar(s, 0, 320, XH - LB, XH, top=True, fl=False)
    stem(s, 0, 0, XH)
    xbar(s, 0, 320, 0, LB)
    bend(s, 0, XH, -1, 1, tb=LB); bend(s, 0, 0, -1, -1, tb=LB)
    return s


@lower("r", 250)
def _lr():
    s = Shape()
    stem(s, 0, 0, XH)
    tbar(s, 0, 250, XH, t=LB)
    return s


@lower("s", 320)
def _ls():
    s = Shape()
    mid = round((XH - LI) / 2)
    tbar(s, 0, 320, XH, t=LB, fl=False)
    stem(s, 0, mid, XH - LB + 1)
    xbar(s, 0, 320, mid, LI)
    stem(s, 220, LB - 1, mid + 1)
    bbar(s, 0, 320, t=LB, fr=False)
    bend(s, 0, XH, -1, 1, tb=LB); bend(s, 0, mid, -1, -1, tb=LI)
    bend(s, 320, mid + LI, 1, 1, tb=LI); bend(s, 320, 0, 1, -1, tb=LB)
    return s


@lower("t", 270, top_x=110)
def _lt():
    s = Shape()
    stem(s, 60, LB - 1, 640)
    xbar(s, 0, 270, XH - LI, LI)
    bbar(s, 60, 270, t=LB, fl=False)
    bend(s, 60, 0, -1, -1, tb=LB)
    return s


@lower("u", 320)
def _lu():
    s = Shape()
    stem(s, 0, 0, XH); stem(s, 220, 0, XH)
    bbar(s, 0, 320, t=LB, fl=False, fr=False)
    bend(s, 0, 0, -1, -1, tb=LB); bend(s, 320, 0, 1, -1, tb=LB)
    return s


@lower("v", 440, top_x=330)
def _lv():            # the 捺 tip barely clears the x-height, so v never reads as a capital
    return n_shape(Shape(), XH, with_stem=False, ko=0.16).transformed(0.82, 1.0)


@lower("w", 470)
def _lw():
    s = Shape()
    bbar(s, 0, 470, t=LB)
    for x in (0, 185, 370):
        stem(s, x, LB - 1, XH)
    return s


@lower("x", 470)
def _lx():
    s = Shape()
    pie_c(s, 0, XH, 270, 0, wt=116, wb=100, bow=0.05)
    na(s, 10, 0, 330, XH + 100, wb=108, wt=112, tipdrop=50)
    return s


@lower("y", 320)
def _ly():
    s = Shape()
    stem(s, 0, 0, XH)
    stem(s, 220, DSC + LB - 1, XH)
    xbar(s, 0, 320, 0, LI)
    bbar(s, 0, 320, DSC, t=LB, fr=False)
    bend(s, 0, 0, -1, -1, tb=LI); bend(s, 320, DSC, 1, -1, tb=LB)
    return s


@lower("z", 380)
def _lz():
    s = Shape()
    tbar(s, 0, 380, XH, t=LB); bbar(s, 0, 380, t=LB)
    pie_c(s, 262, XH - LB + 1, 0, LB - 1, wt=118, wb=118, bow=-0.03)
    return s


# ================================================================ digits
D_ = {}


def digit(name, ch, width):
    def deco(fn):
        D_[name] = (ch, width, fn)
        return fn
    return deco


@digit("zero", "0", 300)
def _0(h):            # narrower than O, and every corner turns
    s = box(Shape(), 0, 0, 300, h)
    for x, y, sx, sy in ((0, 0, -1, -1), (300, 0, 1, -1), (0, h, -1, 1), (300, h, 1, 1)):
        bend(s, x, y, sx, sy, RO * 1.1, RI * 1.2)
    return s


@digit("one", "1", 300)
def _1(h):            # the flag is a 撇, so 1 never reads as I
    s = Shape()
    stem(s, 100, 0, h)
    s.poly((100, h), (200, h), (96, h - 200), (-4, h - 200))
    bbar(s, 0, 300)
    return s


@digit("two", "2", W2)
def _2(h):
    s = Shape(); t = bi(h)
    mid = round((h - t) / 2)
    tbar(s, 0, W2, h, fr=False)
    stem(s, 240, mid, h - B + 1)
    xbar(s, 0, W2, mid, t)
    stem(s, 0, B - 1, mid + 1)
    bbar(s, 0, W2)
    bend(s, W2, h, 1, 1); bend(s, W2, mid, 1, -1, tb=t); bend(s, 0, mid + t, -1, 1, tb=t)
    return s


@digit("three", "3", W2)
def _3(h):            # 山 lying down
    s = Shape()
    tbar(s, 0, W2, h, fr=False); bbar(s, 0, W2, fr=False)
    xbar(s, 70, W2, round((h - bi(h)) / 2), bi(h))
    stem(s, 240, 0, h)
    bend(s, W2, h, 1, 1); bend(s, W2, 0, 1, -1)
    return s


@digit("four", "4", W2)
def _4(h):            # 上 lying down
    s = Shape()
    y = round(h * 0.30)
    stem(s, 0, y, h)
    xbar(s, 0, W2, y)
    stem(s, 220, 0, h)
    return s


@digit("five", "5", W2)
def _5(h):
    s = Shape()
    t = bi(h)
    mid = round((h - t) * 0.56)
    tbar(s, 0, W2, h)
    stem(s, 0, mid, h - B + 1)
    xbar(s, 0, W2, mid, t)
    stem(s, 240, B - 1, mid + 1)
    bbar(s, 0, W2, fr=False)
    bend(s, W2, mid + t, 1, 1, RO * 1.2, RI * 1.3, tb=t); bend(s, W2, 0, 1, -1, RO * 1.2, RI * 1.3)
    return s


@digit("six", "6", W2)
def _6(h):
    s = Shape()
    t = bi(h)
    mid = round((h - t) * 0.48)
    stem(s, 0, 0, h)
    tbar(s, 0, 290, h, fl=False)
    xbar(s, 0, W2, mid, t)
    stem(s, 240, B - 1, mid + 1)
    bbar(s, 0, W2, fl=False, fr=False)
    bend(s, 0, h, -1, 1); bend(s, 0, 0, -1, -1); bend(s, W2, 0, 1, -1); bend(s, W2, mid + t, 1, 1, tb=t)
    return s


@digit("seven", "7", W2)
def _7(h):
    s = Shape()
    tbar(s, 0, W2, h)
    pie_c(s, 220, h - B + 1, 70, 0, wt=120, wb=112, bow=-0.04)
    return s


@digit("eight", "8", W2)
def _8(h):
    s = Shape(); t = bi(h)                         # narrower top bowl: not B, not 0
    mid = round((h - t) * 0.5)
    stem(s, 0, 0, mid + t); stem(s, 240, 0, mid + t)
    bbar(s, 0, W2, fl=False, fr=False)
    xbar(s, 0, W2, mid, t)
    stem(s, 30, mid, h); stem(s, 210, mid, h)
    tbar(s, 30, 310, h, fl=False, fr=False)
    bend(s, 0, 0, -1, -1); bend(s, W2, 0, 1, -1); bend(s, 30, h, -1, 1); bend(s, 310, h, 1, 1)
    return s


@digit("nine", "9", W2)
def _9(h):
    s = Shape()
    t = bi(h)
    mid = round((h - t) * 0.52)
    tbar(s, 0, W2, h, fl=False, fr=False)
    stem(s, 0, mid, h - B + 1)
    xbar(s, 0, W2, mid, t)
    stem(s, 240, 0, h)
    bbar(s, 50, W2, fr=False)
    bend(s, 0, h, -1, 1); bend(s, W2, h, 1, 1); bend(s, 0, mid, -1, -1, tb=t); bend(s, W2, 0, 1, -1)
    return s



# ================================================================ punctuation & symbols
T = TALL
P_ = {}   # name -> (unicode char, width, fn)


def sym(name, ch, width):
    def deco(fn):
        P_[name] = (ch, width, fn)
        return fn
    return deco


def comma_shape(x=0, y=0):
    s = sq(Shape(), x, y)
    pie(s, x, y + 60, x + 30, y - 130, wt=118, wb=60)
    return s


@sym("period", ".", 118)
def _period(): return sq(Shape(), 0, 0)


@sym("comma", ",", 118)
def _comma(): return comma_shape()


@sym("colon", ":", 118)
def _colon(): return sq(sq(Shape(), 0, 0), 0, 330)


@sym("semicolon", ";", 118)
def _semicolon(): return sq(comma_shape(), 0, 330)


@sym("ellipsis", "…", 118 * 3 + 120)
def _ell():
    s = Shape()
    for i in range(3):
        sq(s, i * 178, 0)
    return s


@sym("hyphen", "-", 260)
def _hyphen(): return rect(Shape(), 0, 250, 260, 250 + B)


@sym("endash", "–", 420)
def _endash(): return rect(Shape(), 0, 250, 420, 250 + B)


@sym("emdash", "—", 820)
def _emdash(): return rect(Shape(), 0, 250, 820, 250 + B)


@sym("exclam", "!", 118)
def _exclam():
    s = Shape(); rect(s, 9, 200, 109, T)
    return sq(s, 0, 0)


@sym("exclamdown", "¡", 118)
def _exclamdown():
    s = Shape(); rect(s, 9, -170, 109, 330)
    return sq(s, 0, 412)


def question(s, dy=0, flip=False):
    pts = Shape()
    tbar(pts, 0, 320, T, fr=False)
    stem(pts, 220, 330, T - B + 1)
    xbar(pts, 110, 320, 330, 112)
    stem(pts, 110, 200, 331)
    sq(pts, 101, 0)
    bend(pts, 320, T, 1, 1); bend(pts, 320, 330, 1, -1, tb=112)
    if flip:   # rotate 180° about (160, T/2) and drop below
        for c in pts.contours:
            nc = []
            for op in c:
                nc.append((op[0],) + tuple((320 - p[0], T - p[1] + dy) for p in op[1:]))
            s.contours.append(nc)
        return s
    return s.add(pts, 0, dy)


@sym("question", "?", 320)
def _question(): return question(Shape())


@sym("questiondown", "¿", 320)
def _questiondown(): return question(Shape(), dy=-180, flip=True)


@sym("quotesingle", "'", 100)
def _qs(): return stem(Shape(), 0, T - 230, T)


@sym("quotedbl", '"', 270)
def _qd():
    s = stem(Shape(), 0, T - 230, T)
    return stem(s, 170, T - 230, T)


def tick(s, x, y, up=False):
    """a comma-like quote mark; up=True gives the opening form"""
    if up:
        sq(s, x, y + 120)
        s.poly((x + 88, y + 180), (x + 118, y + 180), (x + 60, y), (x, y))
    else:
        sq(s, x, y)
        pie(s, x, y + 60, x + 30, y - 120, wt=118, wb=60)
    return s


@sym("quoteleft", "‘", 118)
def _ql(): return tick(Shape(), 0, T - 250, up=True)


@sym("quoteright", "’", 118)
def _qr(): return tick(Shape(), 0, T - 118)


@sym("quotesinglbase", "‚", 118)
def _qsb(): return tick(Shape(), 0, 0)


@sym("quotedblleft", "“", 290)
def _qdl(): return tick(tick(Shape(), 0, T - 250, up=True), 172, T - 250, up=True)


@sym("quotedblright", "”", 290)
def _qdr(): return tick(tick(Shape(), 0, T - 118), 172, T - 118)


@sym("quotedblbase", "„", 290)
def _qdb(): return tick(tick(Shape(), 0, 0), 172, 0)


def chevron(s, x, y, w=200, h=300, t=150, left=True):
    """angle quote built from a 撇 and a 捺-ish bar meeting at a point"""
    if left:
        s.poly((x + w, y + h), (x + w - t, y + h), (x, y + h / 2 + 45), (x, y + h / 2 - 45),
               (x + w - t, y), (x + w, y), (x + t * 0.9, y + h / 2))
    else:
        s.poly((x, y + h), (x + t, y + h), (x + w, y + h / 2 + 45), (x + w, y + h / 2 - 45),
               (x + t, y), (x, y), (x + w - t * 0.9, y + h / 2))
    return s


@sym("guilsinglleft", "‹", 200)
def _gsl(): return chevron(Shape(), 0, 160, left=True)


@sym("guilsinglright", "›", 200)
def _gsr(): return chevron(Shape(), 0, 160, left=False)


@sym("guillemotleft", "«", 360)
def _gl(): return chevron(chevron(Shape(), 0, 160), 160, 160)


@sym("guillemotright", "»", 360)
def _gr(): return chevron(chevron(Shape(), 0, 160, left=False), 160, 160, left=False)


@sym("slash", "/", 380)
def _slash(): return Shape().poly((0, -60), (118, -60), (380, T + 40), (262, T + 40))


@sym("backslash", "\\", 380)
def _bslash(): return Shape().poly((262, -60), (380, -60), (118, T + 40), (0, T + 40))


@sym("bar", "|", 100)
def _bar(): return stem(Shape(), 0, -150, T + 80)


@sym("brokenbar", "¦", 100)
def _bbar():
    s = stem(Shape(), 0, -150, 210)
    return stem(s, 0, 330, T + 80)


@sym("bracketleft", "[", 240)
def _bkl():
    s = Shape(); stem(s, 0, -90, T + 60)
    tbar(s, 0, 240, T + 60); bbar(s, 0, 240, y=-90)
    return s


@sym("bracketright", "]", 240)
def _bkr():
    s = Shape(); stem(s, 140, -90, T + 60)
    tbar(s, 0, 240, T + 60); bbar(s, 0, 240, y=-90)
    return s


@sym("parenleft", "(", 230)
def _pl():           # a bracket whose corners turn, like D
    s = Shape(); stem(s, 0, -90, T + 60)
    tbar(s, 0, 230, T + 60, t=118, fl=False); bbar(s, 0, 230, y=-90, t=118, fl=False)
    bend(s, 0, T + 60, -1, 1, 150, 45, tb=118); bend(s, 0, -90, -1, -1, 150, 45, tb=118)
    return s


@sym("parenright", ")", 230)
def _pr():
    s = Shape(); stem(s, 130, -90, T + 60)
    tbar(s, 0, 230, T + 60, t=118, fr=False); bbar(s, 0, 230, y=-90, t=118, fr=False)
    bend(s, 230, T + 60, 1, 1, 150, 45, tb=118); bend(s, 230, -90, 1, -1, 150, 45, tb=118)
    return s


@sym("braceleft", "{", 270)
def _bcl():
    s = Shape(); stem(s, 60, -90, T + 60)
    tbar(s, 60, 270, T + 60, t=118, fl=False); bbar(s, 60, 270, y=-90, t=118, fl=False)
    xbar(s, 0, 160, 230, 120)
    bend(s, 60, T + 60, -1, 1, 130, 40, tb=118); bend(s, 60, -90, -1, -1, 130, 40, tb=118)
    return s


@sym("braceright", "}", 270)
def _bcr():
    s = Shape(); stem(s, 110, -90, T + 60)
    tbar(s, 0, 210, T + 60, t=118, fr=False); bbar(s, 0, 210, y=-90, t=118, fr=False)
    xbar(s, 110, 270, 230, 120)
    bend(s, 210, T + 60, 1, 1, 130, 40, tb=118); bend(s, 210, -90, 1, -1, 130, 40, tb=118)
    return s


@sym("uni300C", "「", 300)
def _cbl():           # 「
    s = Shape(); stem(s, 0, -60, T + 60)
    tbar(s, 0, 300, T + 60, fl=True)
    return s


@sym("uni300D", "」", 300)
def _cbr():           # 」
    s = Shape(); stem(s, 200, -60, T + 60)
    bbar(s, 0, 300, y=-60)
    return s


@sym("less", "<", 400)
def _less(): return chevron(Shape(), 0, 110, w=400, h=420, t=200)


@sym("greater", ">", 400)
def _greater(): return chevron(Shape(), 0, 110, w=400, h=420, t=200, left=False)


@sym("plus", "+", 400)
def _plus():
    s = Shape(); xbar(s, 0, 400, 230)
    return stem(s, 150, 100, 495)


@sym("minus", "−", 400)
def _minus(): return xbar(Shape(), 0, 400, 230)


@sym("plusminus", "±", 400)
def _pm():
    s = Shape(); xbar(s, 0, 400, 330)
    stem(s, 150, 200, 595)
    return xbar(s, 0, 400, 0)


@sym("multiply", "×", 400)
def _mul():
    s = Shape()
    s.poly((0, 120), (125, 120), (400, 480), (275, 480))
    s.poly((275, 120), (400, 120), (125, 480), (0, 480))
    return s


@sym("divide", "÷", 400)
def _div():
    s = Shape(); xbar(s, 0, 400, 230)
    sq(s, 141, 420); return sq(s, 141, 46)


@sym("equal", "=", 400)
def _equal():
    s = Shape(); xbar(s, 0, 400, 140)
    return xbar(s, 0, 400, 345)


@sym("underscore", "_", 400)
def _us(): return rect(Shape(), 0, -200, 400, -200 + B)


@sym("asciicircum", "^", 360)
def _circ():
    return Shape().poly((0, 380), (110, 380), (180, 560), (250, 380), (360, 380),
                        (235, T), (125, T))


@sym("asciitilde", "~", 400)
def _tilde():
    s = Shape()
    rect(s, 0, 260, 110, 400); rect(s, 0, 300, 220, 400)
    rect(s, 180, 210, 400, 310); rect(s, 290, 210, 400, 350)
    return s


@sym("grave", "`", 200)
def _grv(): return Shape().poly((0, T), (110, T), (200, T - 170), (100, T - 170))


@sym("asterisk", "*", 340)
def _ast():
    s = Shape(); cx, cy = 170, 520
    stem(s, cx - 50, cy - 170, cy + 170)
    for sg in (1, -1):
        s.poly((0, cy - 95 * sg - 52), (340, cy + 95 * sg - 52),
               (340, cy + 95 * sg + 52), (0, cy - 95 * sg + 52))
    return s


@sym("numbersign", "#", 520)
def _hash():
    s = Shape(); stem(s, 120, 0, T); stem(s, 300, 0, T)
    xbar(s, 0, 520, 150); return xbar(s, 0, 520, 400)


@sym("at", "@", 620)
def _at():
    s = Shape()
    stem(s, 0, -90, T); stem(s, 520, 130, T)
    tbar(s, 0, 620, T, fl=False, fr=False)
    bar(s, 0, 540, -90, -90 + B, bot=True, fl=False, fr=False)
    stem(s, 190, 130, 470)
    xbar(s, 190, 620, 130)
    xbar(s, 190, 520, 470 - B)
    bend(s, 0, T, -1, 1); bend(s, 620, T, 1, 1); bend(s, 0, -90, -1, -1)
    bend(s, 190, 470, -1, 1, 90, 0); bend(s, 190, 130, -1, -1, 90, 0)
    return s


@sym("ampersand", "&", 560)
def _amp():           # "Et": an E with a t-stem through its arm
    s = Shape()
    stem(s, 0, 0, T)
    tbar(s, 0, 270, T)
    bbar(s, 0, 300, fr=False)
    xbar(s, 0, 560, 300)
    stem(s, 330, 0, 560)
    xbar(s, 330, 470, 0, 110)
    return s


@sym("dollar", "$", W2)
def _dollar():
    s = Shape().add(_S(T))
    return stem(s, 120, -90, T + 90)


@sym("cent", "¢", 330)
def _cent():
    s = Shape(); h = LOW
    s.add(_lc())
    return stem(s, 140, -90, h + 90)


@sym("sterling", "£", 380)
def _pound():
    s = Shape()
    stem(s, 60, 0, T)
    tbar(s, 60, 360, T)
    xbar(s, 0, 300, 250)
    bbar(s, 0, 380)
    return s


@sym("yen", "¥", 500)
def _yen():
    s = _Y(T)
    xbar(s, 60, 440, 160, 90); xbar(s, 60, 440, 300, 90)
    return s


@sym("Euro", "€", 420)
def _euro():
    s = Shape()
    stem(s, 80, 0, T)
    tbar(s, 80, 420, T, fl=False); bbar(s, 80, 420, fl=False)
    bend(s, 80, T, -1, 1); bend(s, 80, 0, -1, -1)
    xbar(s, 0, 330, 390, 90); xbar(s, 0, 330, 210, 90)
    return s


@sym("percent", "%", 560)
def _pct():
    s = Shape()
    for x0, y0 in ((0, 400), (320, 0)):
        stem(s, x0, y0, y0 + 289, w=88); stem(s, x0 + 152, y0, y0 + 289, w=88)
        rect(s, x0, y0, x0 + 240, y0 + 92); rect(s, x0, y0 + 197, x0 + 240, y0 + 289)
    s.poly((60, 0), (170, 0), (500, T), (390, T))
    return s


@sym("section", "§", W2)
def _sect():
    s = Shape()
    tbar(s, 0, W2, T + 40, fl=False)
    stem(s, 0, 300, T - 90)
    box(s, 0, 160, W2, 520, tb=100, top=False, bot=False)
    stem(s, 240, 20, 260)
    bbar(s, 0, W2, y=-110, fr=False)
    bend(s, 0, T + 40, -1, 1); bend(s, W2, -110, 1, -1)
    bend(s, W2, 520, 1, 1, 110, 30, tb=100); bend(s, 0, 160, -1, -1, 110, 30, tb=100)
    return s


@sym("paragraph", "¶", 420)
def _para():
    s = Shape()
    tbar(s, 0, 420, T)
    stem(s, 200, -110, T); stem(s, 320, -110, T)
    rect(s, 0, 320, 200, T)
    return s


@sym("periodcentered", "·", 118)
def _mdot(): return sq(Shape(), 0, 260)


@sym("bullet", "•", 220)
def _bullet(): return sq(Shape(), 0, 220, 220)


@sym("degree", "°", 240)
def _deg():
    s = Shape(); stem(s, 0, 430, T, w=90); stem(s, 150, 430, T, w=90)
    rect(s, 0, T - 90, 240, T); rect(s, 0, 430, 240, 520)
    return s


@sym("copyright", "©", 680)
def _copy():
    s = box(Shape(), 0, -10, 680, T + 10)
    for x, y, sx, sy in ((0, -10, -1, -1), (680, -10, 1, -1), (0, T + 10, -1, 1), (680, T + 10, 1, 1)):
        bend(s, x, y, sx, sy)
    stem(s, 210, 200, 480, w=90)
    xbar(s, 210, 470, 200, 90); xbar(s, 210, 470, 390, 90)
    return s


@sym("registered", "®", 680)
def _reg():
    s = box(Shape(), 0, -10, 680, T + 10)
    for x, y, sx, sy in ((0, -10, -1, -1), (680, -10, 1, -1), (0, T + 10, -1, 1), (680, T + 10, 1, 1)):
        bend(s, x, y, sx, sy)
    stem(s, 210, 200, 490, w=90)
    xbar(s, 210, 470, 400, 90); xbar(s, 210, 470, 290, 80)
    stem(s, 380, 290, 490, w=90)
    s.poly((300, 290), (390, 290), (470, 200), (380, 200))
    return s


@sym("trademark", "™", 640)
def _tm():
    s = Shape()
    xbar(s, 0, 240, T - 100, 100); stem(s, 75, 380, T, w=90)
    xbar(s, 290, 650, T - 100, 100)
    for x in (290, 425, 560):
        stem(s, x, 380, T, w=90)
    return s


@sym("logicalnot", "¬", 400)
def _not():
    s = Shape(); xbar(s, 0, 400, 300)
    return stem(s, 300, 150, 300)


@sym("arrowleft", "←", 700)
def _arl():
    s = Shape(); xbar(s, 60, 700, 240)
    return chevron(s, 0, 60, w=260, h=500, t=135)


@sym("arrowright", "→", 700)
def _arr():
    s = Shape(); xbar(s, 0, 640, 240)
    return chevron(s, 440, 60, w=260, h=500, t=135, left=False)


@sym("arrowup", "↑", 500)
def _aru():
    s = Shape(); stem(s, 200, 0, T - 40)
    s.poly((0, 470), (125, 470), (250, 610), (375, 470), (500, 470), (250, T + 40))
    return s


@sym("arrowdown", "↓", 500)
def _ard():
    s = Shape(); stem(s, 200, 40, T)
    s.poly((0, 220), (125, 220), (250, 80), (375, 220), (500, 220), (250, -40))
    return s


# ================================================================ accents
# Top marks are drawn with their bottom edge on y, centred on cx. Bottom marks hang below y = 0.
def acc_acute(s, cx, y):
    return s.poly((cx - 75, y), (cx + 30, y), (cx + 105, y + 160), (cx - 5, y + 175))


def acc_grave(s, cx, y):
    return s.poly((cx + 75, y), (cx - 30, y), (cx - 105, y + 160), (cx + 5, y + 175))


def acc_circ(s, cx, y):
    return s.poly((cx - 175, y), (cx - 65, y), (cx, y + 70), (cx + 65, y), (cx + 175, y),
                  (cx + 50, y + 165), (cx - 50, y + 165))


def acc_caron(s, cx, y):
    return s.poly((cx - 175, y + 165), (cx - 65, y + 165), (cx, y + 95), (cx + 65, y + 165),
                  (cx + 175, y + 165), (cx + 50, y), (cx - 50, y))


def acc_dier(s, cx, y):
    sq(s, cx - 148, y, 112); return sq(s, cx + 36, y, 112)


def acc_ring(s, cx, y):
    stem(s, cx - 110, y, y + 200, w=88); stem(s, cx + 22, y, y + 200, w=88)
    rect(s, cx - 110, y, cx + 110, y + 84); rect(s, cx - 110, y + 116, cx + 110, y + 200)
    return s


def acc_tilde(s, cx, y):
    rect(s, cx - 180, y + 30, cx - 90, y + 150); rect(s, cx - 180, y + 60, cx + 10, y + 150)
    rect(s, cx - 10, y, cx + 180, y + 90); rect(s, cx + 90, y, cx + 180, y + 120)
    return s


def acc_macron(s, cx, y):
    return rect(s, cx - 140, y + 20, cx + 140, y + 112)


def acc_breve(s, cx, y):
    stem(s, cx - 140, y, y + 160, w=90); stem(s, cx + 50, y, y + 160, w=90)
    return rect(s, cx - 140, y, cx + 140, y + 90)


def acc_dot(s, cx, y):
    return sq(s, cx - 59, y)


def acc_hung(s, cx, y):
    for c in (cx - 72, cx + 72):
        s.poly((c - 58, y), (c + 30, y), (c + 92, y + 160), (c + 4, y + 175))
    return s


def acc_cedilla(s, cx, y=0):
    stem(s, cx - 40, -80, 10, w=90)
    return rect(s, cx - 150, -200, cx + 50, -110)


def acc_comma(s, cx, y=0):          # comma below: a short 撇
    return s.poly((cx - 15, -75), (cx + 85, -75), (cx + 15, -250), (cx - 85, -250))


def acc_ogonek(s, x, y=0):          # a small 乚: drops, then turns right
    stem(s, x - 45, -150, 10, w=90)
    rect(s, x - 45, -225, x + 115, -140)
    return bend(s, x - 45, -225, -1, -1, 80, 0)


def acc_caron_side(s, x, ytop):     # Ľ ľ: the caron becomes a 撇 beside the stem
    return s.poly((x + 10, ytop), (x + 110, ytop), (x + 55, ytop - 190), (x - 45, ytop - 190))


TOP_MARKS = {"grave": acc_grave, "acute": acc_acute, "circumflex": acc_circ, "tilde": acc_tilde,
             "macron": acc_macron, "breve": acc_breve, "dotaccent": acc_dot, "dieresis": acc_dier,
             "ring": acc_ring, "hungarumlaut": acc_hung, "caron": acc_caron}
BOTTOM_MARKS = {"commaaccent": acc_comma, "cedilla": acc_cedilla}
COMBINING = {0x300: "grave", 0x301: "acute", 0x302: "circumflex", 0x303: "tilde", 0x304: "macron",
             0x306: "breve", 0x307: "dotaccent", 0x308: "dieresis", 0x30A: "ring", 0x30B: "hungarumlaut",
             0x30C: "caron", 0x326: "commaaccent", 0x327: "cedilla", 0x328: "ogonek"}
SPACING_MARKS = {0xA8: "dieresis", 0xAF: "macron", 0xB4: "acute", 0xB8: "cedilla", 0x2C6: "circumflex",
                 0x2C7: "caron", 0x2D8: "breve", 0x2D9: "dotaccent", 0x2DA: "ring", 0x2DB: "ogonek",
                 0x2DC: "tilde", 0x2DD: "hungarumlaut"}
GAP = {"ring": 30}                  # distance between the letter and a top mark (default 60)
TOP_X = {"N": 160, "Y": 175, "W": 243, "K": 150, "L": 70, "R": 165}    # off-centre top anchors
BOTTOM_X = {"N": 185, "K": 165}
OGONEK_X = {"A": 290, "E": 240, "I": 220, "U": 290}
COMMA_BELOW = set("ĢģĶķĻļŅņŖŗ")     # Latvian: comma below, though Unicode decomposes to cedilla
SIDE_CARON = {"Ľ": (125, TALL), "ľ": (125, TALL), "ď": (345, TALL), "ť": (185, 640)}
SIDE_CARON_CH = set(SIDE_CARON)
MARK_X = -(SB + 170)                # combining marks sit over the preceding letter by default

# ================================================================ glyph records
class Glyph:
    def __init__(self, name, unis, shape, kind, w=0, h=TALL, space_key=None, kern_key=None, anchors=None):
        self.name, self.unis, self.shape, self.kind = name, list(unis), shape, kind
        self.w, self.h = w, h
        self.space_key = space_key or name     # glyphs sharing a key share spacing (accents don't move letters)
        self.kern_key = kern_key or name       # kerning class
        self.anchors = anchors or {}


from fontTools.agl import UV2AGL


def glyph_name(ch):
    if ch.isascii() and ch.isalpha():
        return ch
    return UV2AGL.get(ord(ch), "uni%04X" % ord(ch))


OGONEK_XL = {"a": 265, "e": 250, "i": 50, "u": 265}
DOT_X = {"i": 50, "j": 180}


def letter_record(ch, h, lower):
    """drawing + anchors for one letter form: a capital at height h, or a lowercase letter"""
    if lower:
        w, fn, top_x, asc = LC_[ch]
        shape = fn()
        cx = w / 2 if top_x is None else top_x
        anchors = {"top": (cx, (ASC if asc else XH) + 60), "bottom": (w / 2, 0),
                   "ogonek": (OGONEK_XL.get(ch, w - 55), 0)}
        return shape, w, LOW, anchors
    w, fn = L_[ch]
    shape = fn(h)
    anchors = {"top": (TOP_X.get(ch, w / 2), h + 60), "bottom": (BOTTOM_X.get(ch, w / 2), 0),
               "ogonek": (OGONEK_X.get(ch, w - 55), 0)}
    return shape, w, h, anchors


def with_mark(shape, mark, anchors, h, ch_base):
    s = Shape().add(shape)
    if mark in TOP_MARKS:
        x, y = anchors["top"]
        TOP_MARKS[mark](s, x, y - 60 + GAP.get(mark, 60))
    elif mark in BOTTOM_MARKS:
        BOTTOM_MARKS[mark](s, anchors["bottom"][0])
    elif mark == "ogonek":
        acc_ogonek(s, anchors["ogonek"][0])
    elif mark == "commaabove":
        x, y = anchors["top"]
        s.poly((x - 85, y), (x + 15, y), (x + 85, y + 175), (x - 15, y + 175))
    elif mark == "caronside":
        x, ytop = SIDE_CARON[ch_base]
        acc_caron_side(s, x, ytop)
    return s


def decompositions():
    """precomposed Latin letters we can build: Latin-1, Latin Extended-A, Ș Ț, Ẁ–ẅ, Ỳ ỳ"""
    cps = list(range(0xC0, 0x180)) + list(range(0x218, 0x21C)) + list(range(0x1E80, 0x1E86)) + [0x1EF2, 0x1EF3]
    out = []
    for cp in cps:
        d = unicodedata.decomposition(chr(cp)).split()
        if len(d) != 2 or d[0].startswith("<"):
            continue
        base, mk = chr(int(d[0], 16)), int(d[1], 16)
        if base.upper() not in L_ or mk not in COMBINING:
            continue
        mark = COMBINING[mk]
        if chr(cp) in COMMA_BELOW: mark = "commaaccent"
        if chr(cp) == "ģ": mark = "commaabove"         # Latvian ģ: the comma turns and sits on top
        if chr(cp) in SIDE_CARON_CH: mark = "caronside"
        out.append((chr(cp), base, mark))
    return out


import unicodedata


def collect(style):
    even = style == "Even"
    G = []
    cap_h = lambda c: TALL if (even or c not in LOWCAPS) else LOW
    base = {}

    # --- base letters: capitals, lowercase, ss01 alternates
    for C in L_:
        shape, w, h, an = letter_record(C, cap_h(C), False)
        base[C] = (shape, w, h, an)
        G.append(Glyph(C, C, shape, "letter", w, h, kern_key=C, anchors=an))
        c = C.lower()
        shape, w, h, an = letter_record(c, LOW, True)
        if c in "ij":                       # 点 on i and j; dotless forms for marks above
            dotless = Shape().add(shape)
            shape = Shape().add(shape); rect(shape, DOT_X[c] - 52, XH + 78, DOT_X[c] + 52, XH + 174)
            dname = "dotlessi" if c == "i" else glyph_name("ȷ")
            base[dname] = (dotless, w, h, an)
            G.append(Glyph(dname, "ı" if c == "i" else "ȷ", dotless, "letter", w, h, space_key=c, kern_key=c, anchors=an))
        base[c] = (shape, w, h, an)
        G.append(Glyph(c, c, shape, "letter", w, h, kern_key=c, anchors=an))
    alt_h = LOW if even else TALL
    for C in sorted(LOWCAPS):
        shape, w, h, an = letter_record(C, alt_h, False)
        base[C + ".ss01"] = (shape, w, h, an)
        G.append(Glyph(C + ".ss01", "", shape, "letter", w, h, space_key=C, kern_key=C + "_alt", anchors=an))

    # --- precomposed letters
    for ch, b, mark in decompositions():
        name = glyph_name(ch)
        lower = b.islower()
        bkey = b
        if lower and b in "ij" and mark in TOP_MARKS:
            bkey = "dotlessi" if b == "i" else glyph_name("ȷ")
        shape, w, h, an = base[bkey]
        G.append(Glyph(name, ch, with_mark(shape, mark, an, h, ch), "letter", w, h,
                       space_key=b, kern_key=b + "_m", anchors=an))
        if not lower and b in LOWCAPS:
            shape, w, h, an = base[b + ".ss01"]
            G.append(Glyph(name + ".ss01", "", with_mark(shape, mark, an, h, ch), "letter", w, h,
                           space_key=b, kern_key=b + "_alt_m", anchors=an))

    # --- letters that are not base + mark
    def special(ch, sh, w, space_key=None):
        G.append(Glyph(glyph_name(ch), ch, sh, "letter", w, LOW if ch.islower() else TALL, space_key=space_key))

    def ae(h):
        s = Shape(); t = bi(h)
        tbar(s, 0, 522, h); stem(s, 0, 0, h - B + 1); stem(s, 240, 0, h)
        xbar(s, 0, 340, 122, t); xbar(s, 340, 600, round((h - t) / 2), t)
        bbar(s, 240, 552, fl=False)
        return s

    def oe(h):
        s = Shape(); t = bi(h)
        tbar(s, 0, 522, h); bbar(s, 0, 552); stem(s, 0, 0, h); stem(s, 240, 0, h)
        xbar(s, 340, 600, round((h - t) / 2), t)
        return s

    def slash_through(s, w, top, bottom=-50):
        return s.poly((-40, bottom), (60, bottom), (w + 40, top), (w - 60, top))

    special("Æ", ae(TALL), 600)
    special("æ", Shape().add(_la()).add(_le(False), dx=220), 540)
    special("Œ", oe(TALL), 600)
    special("œ", Shape().add(_lo()).add(_le(False), dx=220), 540)
    special("Ø", slash_through(_O(TALL), W2, TALL + 50), W2, space_key="O")
    special("ø", slash_through(_lo(), 320, XH + 50), 320, space_key="o")
    eth = Shape().add(_D(TALL), dx=80); xbar(eth, 0, 240, round((TALL - 100) / 2), 100)
    special("Ð", eth, W2 + 80); special("Đ", Shape().add(eth), W2 + 80)
    d_bar = Shape().add(_ld()); xbar(d_bar, 130, 400, 575, 90)
    special("đ", d_bar, 400)
    eth_l = Shape().add(_ld()); xbar(eth_l, 110, 380, 575, 90)
    special("ð", eth_l, 380)
    thorn = Shape(); t = bi(TALL); stem(thorn, 0, 0, TALL)
    lo, hi = round(TALL * 0.16), round(TALL * 0.7)
    xbar(thorn, 0, W2, lo, t); xbar(thorn, 0, W2, hi - t, t); stem(thorn, 240, lo, hi)
    special("Þ", thorn, W2)
    th = Shape(); stem(th, 0, DSC, ASC); xbar(th, 0, 320, XH - LB, LB); stem(th, 220, 0, XH); xbar(th, 0, 320, 0, LB)
    bend(th, 320, XH, 1, 1, tb=LB); bend(th, 320, 0, 1, -1, tb=LB)
    special("þ", th, 320)
    lsl = _L(TALL); lsl.poly((-50, TALL * .28), (190, TALL * .48), (190, TALL * .48 + 95), (-50, TALL * .28 + 95))
    special("Ł", lsl, 320, space_key="L")
    lsl = _ll(); lsl.poly((-80, 250), (180, 400), (180, 490), (-80, 340))
    special("ł", lsl, 100)
    hb = _H(TALL); xbar(hb, -45, W2 + 45, round(TALL * .70), 92)
    special("Ħ", hb, W2, space_key="H")
    hb = _lh(); xbar(hb, -50, 200, 575, 90)
    special("ħ", hb, 320)
    tb_ = _T(TALL); xbar(tb_, 115, 365, round(TALL * .42), 92)
    special("Ŧ", tb_, 480, space_key="T")
    tb_ = _lt(); xbar(tb_, 0, 270, 250, 90)
    special("ŧ", tb_, 270, space_key="t")
    s = Shape(); mid = 300                                        # ß: a narrow upper turn over an open lower one
    stem(s, 0, 0, ASC); tbar(s, 0, 290, ASC, t=LB, fl=False, fr=False); stem(s, 190, mid + LI - 1, ASC - LB + 1)
    xbar(s, 0, 320, mid, LI); stem(s, 220, LB - 1, mid + 1); bbar(s, 150, 320, t=LB, fr=False)
    bend(s, 0, ASC, -1, 1, tb=LB); bend(s, 290, ASC, 1, 1, tb=LB); bend(s, 320, mid + LI, 1, 1, tb=LI); bend(s, 320, 0, 1, -1, tb=LB)
    G.append(Glyph("germandbls", "ß", s, "letter", 320, LOW))
    s = Shape(); t = bi(TALL); mid = 300                          # ẞ: the same turns, capital size
    stem(s, 0, 0, TALL); tbar(s, 0, 310, TALL, fr=False); stem(s, 210, mid + t - 1, TALL - B + 1)
    xbar(s, 0, W2, mid, t); stem(s, 240, B - 1, mid + 1); bbar(s, 160, W2, fr=False)
    bend(s, 310, TALL, 1, 1); bend(s, W2, mid + t, 1, 1, tb=t); bend(s, W2, 0, 1, -1)
    G.append(Glyph(glyph_name("ẞ"), "ẞ", s, "letter", W2, TALL))
    for ch, fn in (("ª", _A), ("º", _O)):                       # ordinals: raised small letter, underlined
        s = fn(TALL).transformed(0.48, 0.48, 0, 340); xbar(s, 0, W2 * 0.48, 250, 60)
        G.append(Glyph(glyph_name(ch), ch, s, "symbol", W2 * 0.48))

    # --- figures (tabular), punctuation and symbols
    for name, (ch, w, fn) in D_.items():
        G.append(Glyph(name, ch, fn(TALL), "digit", w))
    for name, (ch, w, fn) in P_.items():
        G.append(Glyph(name, ch, fn(), "symbol", w))
    for cp, mark in SPACING_MARKS.items():
        s = Shape()
        if mark in TOP_MARKS: TOP_MARKS[mark](s, 0, LOW + 60)
        elif mark == "ogonek": acc_ogonek(s, 0)
        else: BOTTOM_MARKS[mark](s, 0)
        G.append(Glyph(glyph_name(chr(cp)), chr(cp), s, "symbol"))

    # --- combining marks (zero width, positioned by the mark feature)
    for cp, mark in COMBINING.items():
        s = Shape()
        if mark in TOP_MARKS: TOP_MARKS[mark](s, MARK_X, TALL + GAP.get(mark, 60))
        elif mark == "ogonek": acc_ogonek(s, MARK_X)
        else: BOTTOM_MARKS[mark](s, MARK_X)
        pos = "top" if mark in TOP_MARKS else ("ogonek" if mark == "ogonek" else "bottom")
        G.append(Glyph(glyph_name(chr(cp)), chr(cp), s, "mark", anchors={pos: (MARK_X, TALL + 60 if pos == "top" else 0)}))
    return G


# ================================================================ outlines
from fontTools.pens.recordingPen import RecordingPen
from fontTools.misc.bezierTools import splitCubicAtT
import numpy as np


class RoundPen:
    def __init__(self, pen): self.p = pen
    def _r(self, pt): return (round(pt[0]), round(pt[1]))
    def moveTo(self, pt): self.p.moveTo(self._r(pt))
    def lineTo(self, pt): self.p.lineTo(self._r(pt))
    def curveTo(self, *pts): self.p.curveTo(*[self._r(q) for q in pts])
    def qCurveTo(self, *pts): self.p.qCurveTo(*[self._r(q) for q in pts])
    def closePath(self): self.p.closePath()
    def endPath(self): self.p.endPath()


def _union(paths):
    try:
        b = pathops.OpBuilder(fix_winding=True, keep_starting_points=False)
        for q in paths:
            b.add(q, pathops.PathOp.UNION)
        return b.resolve()
    except pathops.PathOpsError:               # coincident edges: merge one contour at a time
        acc = pathops.Path()
        for q in paths:
            acc = pathops.op(acc, pathops.simplify(q, fix_winding=True), pathops.PathOp.UNION,
                             fix_winding=True, keep_starting_points=False)
        return acc


def resolve(shape, dx=0):
    path = _union([to_path(c, dx) for c in shape.contours])
    if shape.cuts:
        path = pathops.op(path, _union([to_path(c, dx) for c in shape.cuts]), pathops.PathOp.DIFFERENCE)
    return path


def _contours(path):
    rp = RecordingPen(); path.draw(rp)
    out, cur, start = [], None, None
    for op, pts in rp.value:
        if op == "moveTo":
            start = cur = pts[0]; out.append([])
        elif op == "lineTo":
            out[-1].append(("L", [cur, pts[0]])); cur = pts[0]
        elif op == "curveTo":
            out[-1].append(("C", [cur, *pts])); cur = pts[-1]
        elif op == "qCurveTo":
            q0, q1, q2 = cur, pts[0], pts[-1]
            out[-1].append(("C", [q0, (q0[0] + 2 / 3 * (q1[0] - q0[0]), q0[1] + 2 / 3 * (q1[1] - q0[1])),
                                   (q2[0] + 2 / 3 * (q1[0] - q2[0]), q2[1] + 2 / 3 * (q1[1] - q2[1])), q2]))
            cur = q2
        elif op in ("closePath", "endPath"):
            if cur != start:
                out[-1].append(("L", [cur, start]))
            cur = start
    return out


def _extrema(P):
    ts = []
    for k in (0, 1):
        p0, p1, p2, p3 = (q[k] for q in P)
        a = -p0 + 3 * p1 - 3 * p2 + p3; b = 2 * (p0 - 2 * p1 + p2); c = p1 - p0
        roots = []
        if abs(a) > 1e-9:
            d = b * b - 4 * a * c
            if d >= 0:
                roots = [(-b + sg * d ** 0.5) / (2 * a) for sg in (1, -1)]
        elif abs(b) > 1e-9:
            roots = [-c / b]
        for t in roots:
            if 0.01 < t < 0.99:
                v = (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t * t * p2 + t ** 3 * p3
                if abs(v - p0) > 0.5 and abs(v - p3) > 0.5:
                    ts.append(t)
    return sorted(set(round(t, 6) for t in ts))


def clean_draw(path, pen):
    """points at extrema, integer coordinates, no zero-length or colinear segments"""
    R = lambda p: (round(p[0]), round(p[1]))
    for segs in _contours(path):
        out = []
        for kind, P in segs:
            pieces = [P]
            if kind == "C":
                ts = _extrema(P)
                if ts:
                    pieces = [list(x) for x in splitCubicAtT(*P, *ts)]
            for Q in pieces:
                Q = [R(q) for q in Q]
                if Q[0] == Q[-1] and (kind == "L" or len(set(Q)) == 1):
                    continue
                out.append(("L" if kind == "L" else "C", Q))
        changed = True
        while changed and len(out) > 2:            # merge colinear lines, cyclically
            changed = False
            for i in range(len(out)):
                a, b = out[i], out[(i + 1) % len(out)]
                if a[0] == b[0] == "L":
                    (x0, y0), (x1, y1) = a[1]; (_, _), (x2, y2) = b[1]
                    if (x1 - x0) * (y2 - y1) - (y1 - y0) * (x2 - x1) == 0 and (x1 - x0) * (x2 - x1) + (y1 - y0) * (y2 - y1) > 0:
                        j = (i + 1) % len(out)
                        out[i] = ("L", [a[1][0], b[1][1]])
                        del out[j]
                        changed = True
                        break
        if len(out) < 2:
            continue
        pen.moveTo(out[0][1][0])
        for kind, Q in out:
            if kind == "L":
                if Q[1] != out[0][1][0] or (kind, Q) != out[-1]:
                    pen.lineTo(Q[1])
            else:
                pen.curveTo(*Q[1:])
        pen.closePath()


# ================================================================ spacing and kerning
YS = np.arange(-262.5, 1000, 5.0)


def _flatten(path, steps=10):
    segs = []
    for c in _contours(path):
        for kind, P in c:
            if kind == "L":
                segs.append((P[0], P[1]))
            else:
                prev = P[0]
                for i in range(1, steps + 1):
                    t = i / steps; m = 1 - t
                    q = tuple(m ** 3 * P[0][k] + 3 * m * m * t * P[1][k] + 3 * m * t * t * P[2][k] + t ** 3 * P[3][k] for k in (0, 1))
                    segs.append((prev, q)); prev = q
    return np.array(segs, float).reshape(-1, 2, 2)


def profile(path):
    """leftmost and rightmost ink x on each row of YS (nan where the row is empty)"""
    S_ = _flatten(path)
    if len(S_) == 0:
        n = np.full(len(YS), np.nan); return n, n.copy()
    x1, y1, x2, y2 = S_[:, 0, 0], S_[:, 0, 1], S_[:, 1, 0], S_[:, 1, 1]
    Y = YS[:, None]
    lo, hi = np.minimum(y1, y2), np.maximum(y1, y2)
    m = (Y >= lo) & (Y < hi)
    t = (Y - y1) / np.where(y2 != y1, y2 - y1, 1)
    X = np.where(m, x1 + t * (x2 - x1), np.nan)
    with np.errstate(all="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return np.nanmin(X, 1), np.nanmax(X, 1)


def side_bearings(path, h, T, k=0.2, D=160, sbmin=8):
    """shape-aware sidebearings: open sides (white reaching deep into the letter) get less space"""
    band = (YS >= 0) & (YS <= h)
    l, r = profile(path)
    lb, rb = l[band], r[band]
    # measure from the main stroke edge, not from the 6-unit flares at bar ends
    x0 = float(np.nanpercentile(lb, 8)); x1 = float(np.nanpercentile(rb, 92))
    dl = np.where(np.isnan(lb), D, np.clip(lb - x0, 0, D))
    dr = np.where(np.isnan(rb), D, np.clip(x1 - rb, 0, D))
    return max(sbmin, T - k * dl.mean()), max(sbmin, T - k * dr.mean()), x0, x1


PUNCT_KERN = ["period", "comma", "colon", "semicolon", "ellipsis", "exclam", "question", "hyphen", "endash",
              "emdash", "quotesingle", "quotedbl", "quoteleft", "quoteright", "quotedblleft", "quotedblright",
              "quotesinglbase", "quotedblbase", "parenleft", "parenright", "bracketleft", "bracketright",
              "guillemotleft", "guillemotright", "guilsinglleft", "guilsinglright", "slash", "ampersand"]


def auto_kerning(glyphs, paths, adv, min_gap=45):
    """class kerning by closest approach: spacing already handles each side's openness, so kerning
    only closes up shapes that interlock (L|T, T|a, T|.) and opens pairs that would touch"""
    by_key = {}
    for g in glyphs:
        if g.kind == "letter" or g.name in PUNCT_KERN:
            by_key.setdefault(g.kern_key, []).append(g)
    prof = {}
    for key, members in by_key.items():
        L = np.full(len(YS), np.nan); Rg = np.full(len(YS), np.nan)
        lo, hi = 1e9, -1e9
        for g in members:
            l, r = profile(paths[g.name])
            with np.errstate(all="ignore"):
                L = np.fmin(L, l); Rg = np.fmin(Rg, adv[g.name] - r)
            if g.kind == "letter":
                lo, hi = min(lo, 0), max(hi, g.h)
            else:
                b = paths[g.name].bounds
                if b: lo, hi = min(lo, b[1]), max(hi, b[3])
        T = 40 if members[0].kind == "letter" and members[0].h <= LOW and key.islower() else 43
        prof[key] = (L, Rg, lo, hi, T)
    pairs = []
    keys = list(prof)
    for a in keys:
        La, Ra, loa, hia, Ta = prof[a]
        for b in keys:
            if a in PUNCT_KERN and b in PUNCT_KERN:
                continue
            Lb, Rb, lob, hib, Tb = prof[b]
            both = ~np.isnan(Ra) & ~np.isnan(Lb)
            if not both.any():
                continue
            raw_min = float(np.min(Ra[both] + Lb[both]))     # closest approach of the two inks
            ref = Ta + Tb                                       # the H|H gap
            slack = raw_min - ref
            if slack > 0.4 * ref:                              # interlocking shapes (LT, Ta, T.): close up
                k = max(-0.6 * slack, -170)
            elif raw_min < min_gap:                            # would touch (accents, tips): open up
                k = min_gap - raw_min
            else:
                k = 0.0
            k = int(round(k / 10.0) * 10)
            if abs(k) >= 20:
                pairs.append((a, b, k))
    return by_key, pairs


# ================================================================ features
def class_name(key):
    return "k_" + "".join(c if c.isalnum() else "_" for c in key) + ("_lc" if key.islower() else "")


def features(glyphs, by_key, pairs, anchors, style):
    names = {g.name for g in glyphs}
    out = ["languagesystem DFLT dflt;", "languagesystem latn dflt;", ""]
    for key, members in by_key.items():
        out.append(f"@{class_name(key)} = [{' '.join(g.name for g in members)}];")
    out.append("lookup kernPairs {\n  lookupflag IgnoreMarks;")
    for a, b, k in pairs:
        out.append(f"  pos @{class_name(a)} @{class_name(b)} {k};")
    out.append("} kernPairs;\nfeature kern { lookup kernPairs; } kern;\n")

    marks = [g for g in glyphs if g.kind == "mark"]
    for pos in ("top", "bottom", "ogonek"):
        ms = [g.name for g in marks if pos in g.anchors]
        if ms:
            x, y = [g for g in marks if pos in g.anchors][0].anchors[pos]
            out.append(f"markClass [{' '.join(ms)}] <anchor {round(x)} {round(y)}> @MC_{pos};")
    out.append("feature mark {\n  lookup markBase {")
    for g in glyphs:
        if g.kind == "letter" and g.name in anchors and anchors[g.name]:
            an = anchors[g.name]
            parts = " ".join(f"<anchor {round(an[p][0])} {round(an[p][1])}> mark @MC_{p}" for p in ("top", "bottom", "ogonek") if p in an)
            out.append(f"    pos base {g.name} {parts};")
    out.append("  } markBase;\n} mark;")
    tops = [g.name for g in marks if "top" in g.anchors]
    out.append(f"feature mkmk {{\n  pos mark [{' '.join(tops)}] <anchor {MARK_X} {TALL + 60 + 230}> mark @MC_top;\n}} mkmk;")
    dj = glyph_name("ȷ")
    out.append(f"@TOPMARKS = [{' '.join(tops)}];\nlookup dotless {{ sub i by dotlessi; sub j by {dj}; }} dotless;\n"
               "feature ccmp { sub [i j]' lookup dotless @TOPMARKS; } ccmp;")
    alts = sorted(n for n in names if n.endswith(".ss01"))
    label = "Short capitals M N V W X Y Z (as in the original MAN)" if style == "Even" else "Tall capitals M N V W X Y Z"
    out.append("feature ss01 {\n  featureNames { name \"" + label + "\"; };")
    for a in alts:
        out.append(f"  sub {a[:-5]} by {a};")
    out.append("} ss01;")
    return "\n".join(out)


# ================================================================ build
def build(style, out):
    glyphs = collect(style)
    paths0 = {g.name: resolve(g.shape) for g in glyphs}

    # spacing: per spacing key (a letter and all its accented forms share one)
    spacing = {}
    for g in glyphs:
        if g.kind != "letter" or g.space_key != g.name or g.name in spacing:
            continue
        T = 40 if g.h <= LOW and g.name.islower() else 43
        lsb, rsb, x0, x1 = side_bearings(paths0[g.name], g.h, T)
        spacing[g.name] = (lsb - x0, round(lsb + (x1 - x0) + rsb))
    dx, adv = {}, {}
    for g in glyphs:
        b = paths0[g.name].bounds
        if g.kind == "letter":
            key = g.space_key if g.space_key in spacing else g.name
            if key not in spacing:
                T = 40 if g.h <= LOW and g.name.islower() else 43
                lsb, rsb, x0, x1 = side_bearings(paths0[g.name], g.h, T)
                spacing[key] = (lsb - x0, round(lsb + (x1 - x0) + rsb))
            dx[g.name], adv[g.name] = spacing[key]
        elif g.kind == "digit":                       # tabular figures, ink centred
            A = W2 + 2 * SB
            dx[g.name] = (A - (b[2] - b[0])) / 2 - b[0]; adv[g.name] = A
        elif g.kind == "mark":
            dx[g.name], adv[g.name] = 0, 0
        else:
            x0 = b[0] if b else 0
            dx[g.name] = SB - min(x0, 0) if g.w else SB - x0
            right = (b[2] if b else 0) + dx[g.name]
            adv[g.name] = round(max((g.w or 0) + 2 * SB, right + SB))
    paths = {g.name: resolve(g.shape, dx[g.name]) for g in glyphs}
    anchors = {g.name: {k: (v[0] + dx[g.name], v[1]) for k, v in g.anchors.items()}
               for g in glyphs if g.kind == "letter"}
    by_key, pairs = auto_kerning(glyphs, paths, adv)

    order = [".notdef", "space"]
    cs, mt, cmap = {}, {}, {0x20: "space", 0xA0: "space"}

    def charstring(path, a):
        pen = T2CharStringPen(a, None)
        if path is not None:
            clean_draw(path, pen)
        return pen.getCharString()

    nd = Shape(); rect(nd, 0, 0, 340, TALL); nd.cut((70, 70), (270, 70), (270, TALL - 70), (70, TALL - 70))
    cs[".notdef"] = charstring(resolve(nd, SB), 340 + 2 * SB); mt[".notdef"] = (340 + 2 * SB, SB)
    cs["space"] = charstring(None, 220); mt["space"] = (220, 0)
    for g in glyphs:
        if g.name in cs:
            raise ValueError(f"duplicate glyph {g.name}")
        p = paths[g.name]
        cs[g.name] = charstring(p, adv[g.name])
        b = p.bounds
        mt[g.name] = (adv[g.name], round(b[0]) if b else 0)
        order.append(g.name)
        for u in g.unis:
            cmap[ord(u)] = g.name

    fb = FontBuilder(1000, isTTF=False)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    ps = f"Tangping-{style}"
    fb.setupCFF(ps, {"FullName": f"Tangping {style}", "FamilyName": "Tangping",
                     "Notice": COPYRIGHT, "Weight": "Regular"}, cs,
                  {   # alignment zones and stems, for hinting: baseline, short height, cap height
                      "BlueValues": [-12, 0, LOW, LOW + 12, TALL, TALL + 12], "OtherBlues": [DESC - 12, DESC],
                      "StdHW": B, "StdVW": S, "StemSnapH": [LI, 112, LB, B], "StemSnapV": [90, S]})
    fb.setupHorizontalMetrics(mt)
    fb.setupHorizontalHeader(ascent=950, descent=-250)
    regular = style == "Regular"
    names = {
        "copyright": COPYRIGHT,
        "familyName": "Tangping" if regular else "Tangping Even",
        "styleName": "Regular",
        "uniqueFontIdentifier": f"{VERSION};NONE;{ps}",
        "fullName": f"Tangping {style}",
        "version": f"Version {VERSION}",
        "psName": ps,
        "manufacturer": "The Tangping Project Authors",
        "designer": DESIGNER,
        "description": ("躺平体 — Latin letters drawn as bold Hei hanzi lying on their side. "
                        "Idea: 曼 split into MAN, by サイバー環状線 (@CyberKanjousen on X)."),
        "licenseDescription": ("This Font Software is licensed under the SIL Open Font License, Version 1.1. "
                               "This license is available with a FAQ at: https://openfontlicense.org"),
        "licenseInfoURL": "https://openfontlicense.org",
    }
    if PROJECT_URL:
        names["vendorURL"] = PROJECT_URL
    if not regular:
        names["typographicFamily"] = "Tangping"
        names["typographicSubfamily"] = "Even"
    fb.setupNameTable(names, mac=False)
    fb.setupOS2(sTypoAscender=950, sTypoDescender=-250, sTypoLineGap=0,
                usWinAscent=1000, usWinDescent=300, sCapHeight=TALL, sxHeight=LOW,
                achVendID="NONE", fsType=0, usWeightClass=400,
                fsSelection=(1 << 6) | (1 << 7), version=4)
    fb.setupPost(underlinePosition=-150, underlineThickness=80)
    fb.font["head"].fontRevision = float(VERSION)
    addOpenTypeFeaturesFromString(fb.font, features(glyphs, by_key, pairs, anchors, style))
    fb.font["OS/2"].recalcUnicodeRanges(fb.font)
    fb.font["OS/2"].recalcCodePageRanges(fb.font)
    fb.save(out)
    return fb.font, len(pairs)


def autohint(path):
    """hint with AFDKO's otfautohint when it is installed (requirements.txt lists it)"""
    import shutil, subprocess
    if not shutil.which("otfautohint"):
        print("  otfautohint not found: fonts left unhinted")
        return False
    subprocess.run(["otfautohint", path], check=True, capture_output=True, text=True)
    return True


if __name__ == "__main__":
    import os
    from fontTools.ttLib import TTFont
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    otf_dir = os.path.join(root, "fonts", "otf"); web_dir = os.path.join(root, "fonts", "webfonts")
    os.makedirs(otf_dir, exist_ok=True); os.makedirs(web_dir, exist_ok=True)
    for style in ("Regular", "Even"):
        otf = os.path.join(otf_dir, f"Tangping-{style}.otf")
        f, npairs = build(style, otf)
        hinted = autohint(otf)
        w = TTFont(otf); w.flavor = "woff2"; w.save(os.path.join(web_dir, f"Tangping-{style}.woff2"))
        print(f"Tangping-{style}: {len(f.getGlyphOrder())} glyphs, {npairs} kerning class pairs"
              + (", hinted" if hinted else ""))
