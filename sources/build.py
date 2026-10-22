#!/usr/bin/env python3
# Tangping (躺平体) font build script
# Copyright 2026 The Tangping Project Authors
# SPDX-License-Identifier: MIT  (the fonts this script produces are licensed under the SIL OFL 1.1)
"""Builds Tangping-Regular.otf and Tangping-Even.otf from code.

Latin letters drawn as bold Hei hanzi lying on their side (曼 turned a quarter-turn and cut reads MAN).
Rules, measured from the original 曼 → MAN image (1px ≈ 4.5 units):
  * stems (Hei horizontals turned upright) = 100 units, bars (Hei verticals turned flat) = 135
  * every stem is cut flat at the baseline
  * exposed long edges of bars are slightly concave and flare at the corners
  * strokes falling to the right are 撇: tapering, flat-cut
  * strokes rising to the right are 捺: sweeping past the top, angled tip
  * condensed: two-stem letters are 340 wide with a 140 counter
  * two heights: tall 689 and short 527; lowercase is the short form of every letter
      Regular: the capitals M N V W X Y Z sit short too, as in the original MAN
      Even:    every capital is tall

Usage:  python3 sources/build.py            # writes fonts/otf and fonts/webfonts
"""
import pathops
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString

VERSION = "3.200"
COPYRIGHT = "Copyright 2026 The Tangping Project Authors (https://github.com/reny1cao/tangping)"
DESIGNER = "Rocco × Claude"
PROJECT_URL = "https://github.com/reny1cao/tangping"

S, B, C = 100, 135, 140        # stem, bar, counter
TALL, LOW = 689, 527
SB = 43
W2 = 2 * S + C                 # 340
LOWCAPS = set("MNVWXYZ")       # capitals that sit low in Regular
DESC = -200


def bi(h):
    """inner (cross) bar thickness: thinner than the outer bars, as in the reference A (~110),
    so letters with stacked bars (B E S 8 3) stay even in colour"""
    return 112 if h >= 600 else 108


# ================================================================ primitives
class Shape:
    def __init__(self):
        self.contours = []
        self.cuts = []          # contours subtracted after the union (chamfers, notches)

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
        t = other.transformed(1, 1, dx, dy)
        self.contours += t.contours
        self.cuts += t.cuts
        return self


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


def hook(sh, x1, h, t=B):
    """钩: the bar's right end turns down into a short tapered hook, angled cut"""
    return sh.poly((x1 - 64, h - t + 1), (x1, h - t + 1), (x1 - 3, h - t - 42), (x1 - 74, h - t - 88))


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


def chamfer(sh, x, y, sx, sy, c_out=130, c_in=58, ts=S, tb=B):
    """cut a 45° chamfer into an outer corner at (x, y); sx/sy = +1 for a right/top corner.
    The inner corner gets a matching fill so the diagonal keeps the stroke weight."""
    e = 30                                   # reach past the corner so bar-end flares are cut too
    sh.cut((x - sx * c_out, y), (x - sx * c_out, y + sy * e), (x + sx * e, y + sy * e),
           (x + sx * e, y - sy * c_out), (x, y - sy * c_out))
    xi, yi = x - sx * ts, y - sy * tb
    sh.poly((xi + sx, yi + sy), (xi - sx * c_in, yi + sy), (xi + sx, yi - sy * c_in))
    return sh


def over(h):
    """how far 捺 tips rise above the stems"""
    return 175 if h < 600 else 140


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
def _B(h):
    s = Shape(); t = bi(h)
    mid = round((h - 2 * B - t) * 0.53) + B
    stem(s, 0, 0, h)
    tbar(s, 0, 310, h)
    stem(s, 210, mid, h - B + 1)
    xbar(s, 0, W2, mid, t)
    stem(s, 240, 0, mid + 1)
    bbar(s, 0, W2)
    return s


@letter("C", 340)
def _C(h):            # 冂 lying down: the hook survives at the top right
    s = Shape()
    stem(s, 0, 0, h)
    tbar(s, 0, 340, h, fr=False); bbar(s, 0, 330)
    hook(s, 340, h)
    return s


@letter("D", W2)
def _D(h):
    s = box(Shape(), 0, 0, W2, h)          # 巳 lying down, with its right corners cut (unlike O)
    chamfer(s, W2, h, 1, 1, 175, 103)
    chamfer(s, W2, 0, 1, -1, 175, 103)
    return s


@letter("E", 340)
def _E(h):            # 山 lying down: middle arm longest, top arm shortest
    s = Shape(); t = bi(h)
    stem(s, 0, 0, h)
    tbar(s, 0, 262, h); bbar(s, 0, 292)
    xbar(s, 0, 340, round((h - t) / 2), t)
    return s


@letter("F", 320)
def _F(h):            # 岂: middle arm longer than the top
    s = Shape(); t = bi(h)
    stem(s, 0, 0, h)
    tbar(s, 0, 262, h)
    xbar(s, 0, 320, round(h * 0.36), t)
    return s


@letter("G", W2)
def _G(h):
    s = Shape(); t = bi(h)
    stem(s, 0, 0, h)
    tbar(s, 0, W2, h); bbar(s, 0, W2)
    top = round(h * 0.48) + (0 if h > 600 else 20)
    stem(s, 240, 0, top)
    xbar(s, 165, W2, top - t, t)
    return s


@letter("H", W2)
def _H(h):            # 工 lying down: the left stem (工's short top bar) stops early
    s = Shape(); t = bi(h)
    stem(s, 0, 0, h - 42); stem(s, 240, 0, h)
    xbar(s, 0, W2, round((h - t) / 2), t)
    return s


@letter("I", 300)
def _I(h):            # 工
    s = Shape()
    tbar(s, 0, 300, h); bbar(s, 0, 300)
    stem(s, 100, 0, h)
    return s


@letter("J", W2)
def _J(h):
    s = Shape()
    stem(s, 240, 0, h)
    bbar(s, 0, W2)
    stem(s, 0, 0, round(h * 0.38))
    return s


@letter("K", 470)
def _K(h):            # 大 lying down
    s = Shape()
    stem(s, 0, 0, h)
    sweep(s, 70, round(h * 0.40), round(h * 0.58), 300, 418)
    tip = h + (round(h * 0.1) if h > 600 else over(h) - 60)
    na(s, 70, round(h * 0.42), 335, tip, wb=128, wt=122, tipdrop=56)
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


def n_shape(sh, h, with_stem=True):
    """N traced from the reference (stem 518). Tip overshoot shrinks on tall forms."""
    k = h / 518
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
    return box(Shape(), 0, 0, W2, h)


@letter("P", W2)
def _P(h):
    s = Shape(); t = bi(h)
    mid = round(h * 0.34)
    stem(s, 0, 0, h)
    tbar(s, 0, W2, h)
    stem(s, 240, mid, h - B + 1)
    xbar(s, 0, W2, mid, t)
    return s


@letter("Q", 360)
def _Q(h):
    s = box(Shape(), 0, 0, W2, h)
    pie(s, 135, 250, 290, -160, wt=118, wb=110)
    return s


@letter("R", 380)
def _R(h):            # 召's 刀 lying down: hooked top, curved 撇 leg
    s = Shape()
    stem(s, 0, 0, h)
    tbar(s, 0, 330, h, fr=False)
    hook(s, 330, h)
    stem(s, 236, round(h * 0.55), h - B + 1, w=94)
    sweep(s, 60, round(h * 0.40), round(h * 0.58), 262, 380)
    return s


@letter("S", W2)
def _S(h):
    s = Shape(); t = bi(h)
    mid = round((h - t) / 2)
    tbar(s, 0, W2, h)
    stem(s, 0, mid, h - B + 1)
    xbar(s, 0, W2, mid, t)
    stem(s, 240, B - 1, mid + 1)
    bbar(s, 0, W2)
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
    bbar(s, 0, W2)
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


@letter("X", 520)
def _X(h):
    s = Shape()
    pie(s, 0, h, 300, 0, wt=112, wb=104, slant=40)
    na(s, 0, 0, 380, h + over(h), wb=112, wt=116, tipdrop=52)
    return s


@letter("Y", 500)
def _Y(h):
    s = Shape()
    jy = round(h * 0.48)
    pie(s, 0, h, 150, jy - 10, wt=128, wb=120, slant=45)
    na(s, 150, jy - 40, 365, h + over(h), wb=125, wt=122, tipdrop=55)
    stem(s, 160, 0, jy + 20, w=110)
    return s


@letter("Z", 420)
def _Z(h):
    s = Shape()
    tbar(s, 0, 420, h); bbar(s, 0, 420)
    s.poly((0, B - 1), (128, B - 1), (420, h - B + 1), (292, h - B + 1))
    return s


# ================================================================ digits
D_ = {}


def digit(name, ch, width):
    def deco(fn):
        D_[name] = (ch, width, fn)
        return fn
    return deco


@digit("zero", "0", W2)
def _0(h):            # dotted zero: a 点 in the counter, so 0 never reads as O
    s = box(Shape(), 0, 0, W2, h)
    rect(s, 124, round(h / 2) - 62, 216, round(h / 2) + 62)
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
    tbar(s, 0, W2, h)
    stem(s, 240, mid, h - B + 1)
    xbar(s, 0, W2, mid, t)
    stem(s, 0, B - 1, mid + 1)
    bbar(s, 0, W2)
    return s


@digit("three", "3", W2)
def _3(h):            # 山 lying down
    s = Shape()
    tbar(s, 0, W2, h); bbar(s, 0, W2)
    xbar(s, 70, W2, round((h - bi(h)) / 2), bi(h))
    stem(s, 240, 0, h)
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
    chamfer(s, W2, mid + t, 1, 1, 150, 92, tb=t)  # a rounded bowl, unlike the square S
    chamfer(s, W2, 0, 1, -1, 160, 88)
    return s


@digit("six", "6", W2)
def _6(h):
    s = Shape()
    t = bi(h)
    mid = round((h - t) * 0.48)
    stem(s, 0, 0, h)
    tbar(s, 0, 250, h, fr=False)                    # open top right: not 8, not S
    xbar(s, 0, W2, mid, t)
    stem(s, 240, B - 1, mid + 1)
    bbar(s, 0, W2)
    return s


@digit("seven", "7", W2)
def _7(h):
    s = Shape()
    tbar(s, 0, W2, h)
    s.poly((95, 0), (210, 0), (W2, h - B + 1), (215, h - B + 1))
    return s


@digit("eight", "8", W2)
def _8(h):
    s = Shape(); t = bi(h)                         # narrower top bowl: not B, not 0
    mid = round((h - t) * 0.5)
    stem(s, 0, 0, mid + t); stem(s, 240, 0, mid + t)
    bbar(s, 0, W2)
    xbar(s, 0, W2, mid, t)
    stem(s, 45, mid, h); stem(s, 195, mid, h)
    tbar(s, 45, 295, h)
    return s


@digit("nine", "9", W2)
def _9(h):
    s = Shape()
    t = bi(h)
    mid = round((h - t) * 0.52)
    tbar(s, 0, W2, h)
    stem(s, 0, mid, h - B + 1)
    xbar(s, 0, W2, mid, t)
    stem(s, 240, 0, h)
    bbar(s, 90, W2, fl=False)                       # open bottom left: 6 turned round
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
    tbar(pts, 0, 320, T)
    stem(pts, 220, 330, T - B + 1)
    xbar(pts, 110, 320, 330)
    stem(pts, 110, 200, 331)
    sq(pts, 101, 0)
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
def _pl():           # bracket with the corners stepped in, like D
    s = Shape(); stem(s, 0, -20, T - 10)
    tbar(s, 70, 230, T + 60, fl=False); bbar(s, 70, 230, y=-90, fl=False)
    return s


@sym("parenright", ")", 230)
def _pr():
    s = Shape(); stem(s, 130, -20, T - 10)
    tbar(s, 0, 160, T + 60, fr=False); bbar(s, 0, 160, y=-90, fr=False)
    return s


@sym("braceleft", "{", 270)
def _bcl():
    s = Shape(); stem(s, 60, -90, T + 60)
    tbar(s, 60, 270, T + 60); bbar(s, 60, 270, y=-90)
    xbar(s, 0, 160, 230, 120)
    return s


@sym("braceright", "}", 270)
def _bcr():
    s = Shape(); stem(s, 110, -90, T + 60)
    tbar(s, 0, 210, T + 60); bbar(s, 0, 210, y=-90)
    xbar(s, 110, 270, 230, 120)
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
    tbar(s, 0, 620, T)
    bar(s, 0, 520, -90, -90 + B, bot=True, fr=False)
    stem(s, 190, 130, 470)
    xbar(s, 190, 620, 130)
    xbar(s, 190, 520, 470 - B)
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
    s = _S(T)
    return stem(s, 120, -90, T + 90)


@sym("cent", "¢", 330)
def _cent():
    s = Shape(); h = LOW
    stem(s, 0, 0, h); tbar(s, 0, 340, h, fr=False); bbar(s, 0, 330)
    hook(s, 340, h)
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
    tbar(s, 80, 420, T); bbar(s, 80, 420)
    xbar(s, 0, 330, 380, 90); xbar(s, 0, 330, 220, 90)
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
    tbar(s, 0, W2, T + 40)
    stem(s, 0, 300, T - 90)
    box(s, 0, 160, W2, 520, tb=100, top=False, bot=False)
    stem(s, 240, 30, 260)
    bbar(s, 0, W2, y=-110)
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
    stem(s, 210, 200, 480, w=90)
    xbar(s, 210, 470, 200, 90); xbar(s, 210, 470, 390, 90)
    return s


@sym("registered", "®", 680)
def _reg():
    s = box(Shape(), 0, -10, 680, T + 10)
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


def acc_ogonek(s, x, y=0):
    stem(s, x - 45, -170, 10, w=90)
    return rect(s, x - 45, -235, x + 125, -145)


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
SIDE_CARON = set("Ľľ")
MARK_X = -(SB + 170)                # combining marks sit over the preceding letter by default

# ================================================================ glyph records
LOWER_DRAW_H = 573                  # lowercase is drawn at this height, then scaled (0.9, 0.92)
LSX, LSY = 0.9, 0.92


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


def letter_record(ch, h, lower):
    """drawing + anchors for one letter form. lower=True gives the narrower, lighter lowercase."""
    w, fn = L_[ch.upper()]
    key = ch.upper()
    if lower:
        shape = fn(LOWER_DRAW_H).transformed(LSX, LSY)
        w, h, sx = w * LSX, LOW, LSX
    else:
        shape, sx = fn(h), 1.0
    cx = TOP_X.get(key, L_[key][0] / 2) * sx
    anchors = {"top": (cx, h + 60), "bottom": (BOTTOM_X.get(key, L_[key][0] / 2) * sx, 0),
               "ogonek": (OGONEK_X.get(key, L_[key][0] - 55) * sx, 0)}
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
    elif mark == "caronside":
        stem_right = (100 if ch_base.isupper() else 100 * LSX) + 25
        acc_caron_side(s, stem_right, h)
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
        if chr(cp) in SIDE_CARON: mark = "caronside"
        out.append((chr(cp), base, mark))
    return out


import unicodedata


def collect(style):
    even = style == "Even"
    G = []
    cap_h = lambda c: TALL if (even or c not in LOWCAPS) else LOW
    base = {}

    # --- base letters: capitals, lowercase (narrower and lighter), ss01 alternates
    for C in L_:
        shape, w, h, an = letter_record(C, cap_h(C), False)
        base[C] = (shape, w, h, an)
        G.append(Glyph(C, C, shape, "letter", w, h, kern_key=C, anchors=an))
        c = C.lower()
        shape, w, h, an = letter_record(c, LOW, True)
        if c in "ij":                       # 点 on i and j; dotless forms for marks above
            stem_c = (150 if c == "i" else 290) * LSX
            dotless = Shape().add(shape)
            shape = Shape().add(shape); sq(shape, stem_c - 54, LOW + 60, 108)
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
        G.append(Glyph(name, ch, with_mark(shape, mark, an, h, b), "letter", w, h,
                       space_key=b, kern_key=b + "_m", anchors=an))
        if not lower and b in LOWCAPS:
            shape, w, h, an = base[b + ".ss01"]
            G.append(Glyph(name + ".ss01", "", with_mark(shape, mark, an, h, b), "letter", w, h,
                           space_key=b, kern_key=b + "_alt_m", anchors=an))

    # --- letters that are not base + mark
    def lc(fn):                                   # draw at the lowercase height, then scale
        return fn(LOWER_DRAW_H).transformed(LSX, LSY)

    def special(name, uni, draw, w):
        for lower in (False, True):
            sh = draw(LOWER_DRAW_H).transformed(LSX, LSY) if lower else draw(TALL)
            ch = uni[1] if lower else uni[0]
            G.append(Glyph(glyph_name(ch), ch, sh, "letter", w * (LSX if lower else 1), LOW if lower else TALL))

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

    def oslash(h):
        s = _O(h); s.poly((-40, -50), (60, -50), (380, h + 50), (280, h + 50)); return s

    def eth(h):
        s = Shape().add(_D(h), dx=80); xbar(s, 0, 240, round((h - 100) / 2), 100); return s

    def thorn(h):
        s = Shape(); t = bi(h); stem(s, 0, 0, h)
        lo, hi = round(h * 0.16), round(h * 0.7)
        xbar(s, 0, W2, lo, t); xbar(s, 0, W2, hi - t, t); stem(s, 240, lo, hi)
        return s

    def lslash(h):
        s = _L(h); s.poly((-50, h * .28), (190, h * .48), (190, h * .48 + 95), (-50, h * .28 + 95)); return s

    def hbar(h):
        s = _H(h); xbar(s, -45, W2 + 45, round(h * .70), 92); return s

    def tbar_(h):
        s = _T(h); xbar(s, 115, 365, round(h * .42), 92); return s

    special("AE", "Ææ", ae, 600); special("OE", "Œœ", oe, 600); special("Oslash", "Øø", oslash, W2)
    special("Eth", "Ðð", eth, W2 + 80); special("Thorn", "Þþ", thorn, W2)
    special("Dcroat", "Đđ", eth, W2 + 80); special("Lslash", "Łł", lslash, 320)
    special("Hbar", "Ħħ", hbar, W2); special("Tbar", "Ŧŧ", tbar_, 480)
    s = lc(_B); stem(s, 0, DESC, 1, w=90)                       # ß: a small B with a descender
    G.append(Glyph("germandbls", "ß", s, "letter", W2 * LSX, LOW))
    s = _B(TALL); chamfer(s, 310, TALL, 1, 1, 175, 103)       # ẞ: B with a cut corner
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


def resolve(shape, dx=0):
    b = pathops.OpBuilder(fix_winding=True, keep_starting_points=False)
    for c in shape.contours:
        b.add(to_path(c, dx), pathops.PathOp.UNION)
    path = b.resolve()
    if shape.cuts:
        cb = pathops.OpBuilder(fix_winding=True, keep_starting_points=False)
        for c in shape.cuts:
            cb.add(to_path(c, dx), pathops.PathOp.UNION)
        path = pathops.op(path, cb.resolve(), pathops.PathOp.DIFFERENCE)
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
                      "StdHW": B, "StdVW": S, "StemSnapH": [108, 112, B], "StemSnapV": [90, S]})
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
