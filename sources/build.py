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

VERSION = "3.100"
COPYRIGHT = "Copyright 2026 The Tangping Project Authors"
DESIGNER = "Rocco × Claude"
PROJECT_URL = "https://github.com/reny1cao/tangping"

S, B, C = 100, 135, 140        # stem, bar, counter
TALL, LOW = 689, 527
SB = 43
W2 = 2 * S + C                 # 340
LOWCAPS = set("MNVWXYZ")       # capitals that sit low in Regular
DESC = -200


def bi(h):
    """inner (cross) bar thickness: lighter on short forms so counters stay open"""
    return B if h >= 600 else 108


# ================================================================ primitives
class Shape:
    def __init__(self):
        self.contours = []

    def poly(self, *pts):
        self.contours.append([("M", pts[0])] + [("L", p) for p in pts[1:]])
        return self

    def raw(self, ops):
        self.contours.append(ops)
        return self

    def add(self, other, dx=0, dy=0):
        for c in other.contours:
            nc = []
            for op in c:
                nc.append((op[0],) + tuple((p[0] + dx, p[1] + dy) for p in op[1:]))
            self.contours.append(nc)
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
    xbar(s, 0, W2, 122, bi(h))
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
    s = Shape()
    stem(s, 0, 0, h)
    tbar(s, 0, 262, h, fr=False); bbar(s, 0, 262, fr=False)
    stem(s, 240, 72, h - 72)
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
    pie(s, 150, 230, 255, -95, wt=118, wb=105)
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
    pie(s, 0, h, 300, 0, wt=126, wb=116, slant=45)
    na(s, 0, 0, 380, h + over(h), wb=125, wt=124, tipdrop=56)
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
def _0(h):
    s = box(Shape(), 0, 0, W2, h)
    s.poly((100, B - 1), (172, B - 1), (240, h - B + 1), (168, h - B + 1))
    return s


@digit("one", "1", 300)
def _1(h):
    s = Shape()
    stem(s, 100, 0, h)
    tbar(s, 0, 200, h, fr=False)
    bbar(s, 0, 300)
    return s


@digit("two", "2", W2)
def _2(h):
    s = Shape(); t = B
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
    xbar(s, 70, W2, round((h - B) / 2))
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
    mid = round((h - B) * 0.56)
    tbar(s, 0, W2, h)
    stem(s, 0, mid, h - B + 1)
    xbar(s, 0, 255, mid)
    stem(s, 240, B - 1, mid + 1)
    bbar(s, 0, W2)
    return s


@digit("six", "6", W2)
def _6(h):
    s = Shape()
    mid = round((h - B) * 0.48)
    stem(s, 0, 0, h)
    tbar(s, 0, W2, h)
    xbar(s, 0, W2, mid)
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
    s = box(Shape(), 0, 0, W2, h)
    xbar(s, 0, W2, round((h - B) * 0.53))
    return s


@digit("nine", "9", W2)
def _9(h):
    s = Shape()
    mid = round((h - B) * 0.52)
    tbar(s, 0, W2, h)
    stem(s, 0, mid, h - B + 1)
    xbar(s, 0, W2, mid)
    stem(s, 240, 0, h)
    bbar(s, 0, 260, fr=False)
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


def chevron(s, x, y, w=200, h=300, t=110, left=True):
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
def _less(): return chevron(Shape(), 0, 110, w=400, h=420, t=125)


@sym("greater", ">", 400)
def _greater(): return chevron(Shape(), 0, 110, w=400, h=420, t=125, left=False)


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
    s.poly((0, 120), (85, 120), (400, 480), (315, 480))
    s.poly((315, 120), (400, 120), (85, 480), (0, 480))
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
        s.poly((0, cy - 95 * sg - 45), (340, cy + 95 * sg - 45),
               (340, cy + 95 * sg + 45), (0, cy - 95 * sg + 45))
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
        stem(s, x0, y0, y0 + 289, w=70); stem(s, x0 + 170, y0, y0 + 289, w=70)
        rect(s, x0, y0, x0 + 240, y0 + 90); rect(s, x0, y0 + 199, x0 + 240, y0 + 289)
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
    s = Shape(); stem(s, 0, 450, T, w=80); stem(s, 160, 450, T, w=80)
    rect(s, 0, T - 80, 240, T); rect(s, 0, 450, 240, 530)
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
    xbar(s, 0, 240, T - 100, 100); stem(s, 80, 380, T, w=80)
    xbar(s, 290, 640, T - 100, 100)
    for x in (290, 425, 560):
        stem(s, x, 380, T, w=80)
    return s


@sym("logicalnot", "¬", 400)
def _not():
    s = Shape(); xbar(s, 0, 400, 300)
    return stem(s, 300, 150, 300)


@sym("arrowleft", "←", 700)
def _arl():
    s = Shape(); xbar(s, 60, 700, 240)
    return chevron(s, 0, 60, w=260, h=500, t=125)


@sym("arrowright", "→", 700)
def _arr():
    s = Shape(); xbar(s, 0, 640, 240)
    return chevron(s, 440, 60, w=260, h=500, t=125, left=False)


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
    stem(s, cx - 110, y, y + 190, w=72); stem(s, cx + 38, y, y + 190, w=72)
    rect(s, cx - 110, y, cx + 110, y + 66); rect(s, cx - 110, y + 124, cx + 110, y + 190)
    return s


def acc_tilde(s, cx, y):
    rect(s, cx - 180, y + 30, cx - 70, y + 150); rect(s, cx - 180, y + 70, cx + 10, y + 150)
    rect(s, cx - 10, y, cx + 180, y + 80); rect(s, cx + 70, y, cx + 180, y + 120)
    return s


def acc_cedilla(s, cx, y=0):
    stem(s, cx - 40, -80, 10, w=90)
    return rect(s, cx - 150, -200, cx + 50, -110)


def acc_dot(s, cx, y):
    return sq(s, cx - 59, y)


ACC = {"acute": acc_acute, "grave": acc_grave, "circumflex": acc_circ, "caron": acc_caron,
       "dieresis": acc_dier, "ring": acc_ring, "tilde": acc_tilde, "dotaccent": acc_dot}

# (char, base letter, accent)
ACCENTED = []
for base, marks in {
    "A": "grave acute circumflex tilde dieresis ring", "C": "cedilla",
    "E": "grave acute circumflex dieresis", "I": "grave acute circumflex dieresis",
    "N": "tilde", "O": "grave acute circumflex tilde dieresis",
    "U": "grave acute circumflex dieresis", "Y": "acute dieresis",
    "S": "caron", "Z": "caron",
}.items():
    for m in marks.split():
        ACCENTED.append((base, m))

import unicodedata


def accented_char(base, mark, lower):
    nm = {"grave": "GRAVE", "acute": "ACUTE", "circumflex": "CIRCUMFLEX", "tilde": "TILDE",
          "dieresis": "DIAERESIS", "ring": "RING ABOVE", "cedilla": "CEDILLA", "caron": "CARON"}[mark]
    case = "SMALL" if lower else "CAPITAL"
    try:
        return unicodedata.lookup(f"LATIN {case} LETTER {base} WITH {nm}")
    except KeyError:
        return None


# ================================================================ build
class RoundPen:
    def __init__(self, pen): self.p = pen
    def _r(self, pt): return (round(pt[0]), round(pt[1]))
    def moveTo(self, pt): self.p.moveTo(self._r(pt))
    def lineTo(self, pt): self.p.lineTo(self._r(pt))
    def curveTo(self, *pts): self.p.curveTo(*[self._r(q) for q in pts])
    def qCurveTo(self, *pts): self.p.qCurveTo(*[self._r(q) for q in pts])
    def closePath(self): self.p.closePath()
    def endPath(self): self.p.endPath()


def resolve(shape, dx):
    b = pathops.OpBuilder(fix_winding=True, keep_starting_points=False)
    for c in shape.contours:
        b.add(to_path(c, dx), pathops.PathOp.UNION)
    return b.resolve()


def glyph_name(ch):
    if ch.isascii() and ch.isalpha():
        return ch
    return "uni%04X" % ord(ch)


def collect(style):
    """returns list of (glyphname, unicode or None, width, Shape)"""
    even = style == "Even"
    out = []

    def cap_h(ch):
        return TALL if (even or ch not in LOWCAPS) else LOW

    letters = {}
    for ch, (w, fn) in L_.items():
        hc = cap_h(ch)
        letters[ch] = (w, hc, fn(hc))
        letters[ch.lower()] = (w, LOW, fn(LOW))
    for ch, (w, h, shp) in letters.items():
        out.append((ch, ch, w, shp))
    for name, (ch, w, fn) in D_.items():
        out.append((name, ch, w, fn(TALL)))
    for name, (ch, w, fn) in P_.items():
        out.append((name, ch, w, fn()))

    # accented letters
    for base, mark in ACCENTED:
        for lower in (False, True):
            ch = accented_char(base, mark, lower)
            if not ch:
                continue
            key = base.lower() if lower else base
            w, h, shp = letters[key]
            s = Shape().add(shp)
            cx = w / 2
            if mark == "cedilla":
                acc_cedilla(s, cx)
            else:
                gap = 40 if mark == "ring" else 60
                if base == "N":
                    cx = 160
                if base == "Y":
                    cx = 175
                ACC[mark](s, cx, h + gap)
            out.append((glyph_name(ch), ch, w, s))

    # specials
    def letter_shape(k):
        return letters[k]

    for lower in (False, True):
        hA = LOW if lower else TALL
        t = bi(hA)
        # Æ
        s = Shape()
        tbar(s, 0, 522, hA); stem(s, 0, 0, hA - B + 1); stem(s, 240, 0, hA)
        xbar(s, 0, 340, 122, t); xbar(s, 340, 600, round((hA - t) / 2), t)
        bbar(s, 240, 552, fl=False)
        out.append((glyph_name("æ" if lower else "Æ"), "æ" if lower else "Æ", 600, s))
        # Œ
        s = Shape()
        tbar(s, 0, 522, hA); bbar(s, 0, 552); stem(s, 0, 0, hA); stem(s, 240, 0, hA)
        xbar(s, 340, 600, round((hA - t) / 2), t)
        out.append((glyph_name("œ" if lower else "Œ"), "œ" if lower else "Œ", 600, s))
        # Ø
        w, h, shp = letter_shape("o" if lower else "O")
        s = Shape().add(shp)
        s.poly((-40, -50), (60, -50), (380, h + 50), (280, h + 50))
        out.append((glyph_name("ø" if lower else "Ø"), "ø" if lower else "Ø", W2, s))
        # Ð
        w, h, shp = letter_shape("d" if lower else "D")
        s = Shape().add(shp, dx=80)
        xbar(s, 0, 240, round((h - 100) / 2), 100)
        out.append((glyph_name("ð" if lower else "Ð"), "ð" if lower else "Ð", W2 + 80, s))
        # Þ
        s = Shape()
        stem(s, 0, 0, hA)
        lo, hi = round(hA * 0.16), round(hA * 0.7)
        xbar(s, 0, W2, lo, t); xbar(s, 0, W2, hi - t, t); stem(s, 240, lo, hi)
        out.append((glyph_name("þ" if lower else "Þ"), "þ" if lower else "Þ", W2, s))
    # Ÿ ÿ handled by ACCENTED? (Y dieresis capital is U+0178 "LATIN CAPITAL LETTER Y WITH DIAERESIS")
    # ß: B with the stem dropped below the baseline
    s = _B(LOW); stem(s, 0, DESC, 1)
    out.append(("germandbls", "ß", W2, s))
    # ı dotless i == i
    out.append(("dotlessi", "ı", 300, _I(LOW)))
    return out


def kerning_fea(names):
    have = set(names)
    def cls(chars):
        g = []
        for c in chars:
            n = glyph_name(c) if len(c) == 1 else c
            if n in have:
                g.append(n)
        return "[" + " ".join(g) + "]"
    lowpunct = cls([".", ",", "…", "‚", "„"]).replace("[", "[period comma ellipsis ").replace(
        "uni2026", "").replace("uni201A", "quotesinglbase").replace("uni201E", "quotedblbase")
    lowpunct = "[period comma ellipsis quotesinglbase quotedblbase]"
    quotes = "[quotesingle quotedbl quoteright quotedblright]"
    rules = [
        (cls("TFPtfp"), lowpunct, -90),
        (cls("VYvy"), lowpunct, -70),
        (cls("Ll"), cls("TVYtvy"), -60),
        (cls("Ll"), quotes, -90),
        (cls("Ll"), cls("Oo"), -15),
        # 捺 overshoot: pull the next letter in under the tip
        (cls("NVXKYnvxky"), cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"), -35),
        (cls("Pp"), cls("Aa"), -20),
        (cls("Tt"), cls("Jj"), -30),
        # wide T (十): tuck neighbours under its bar
        (cls("Tt"), cls("ABCDEGHIJKLMNOPQRSUVWXYZabcdeghijklmnopqrsuvwxyz0123456789"), -45),
        (cls("ABCDEFGHIJKLMNOPQRSUVWXYZabcdefghijklmnopqrsuvwxyz0123456789"), cls("Tt"), -45),
        (cls("Tt"), cls("Tt"), -20),
        (cls("Tt"), lowpunct, -60),
        # R and K legs land far right; pull round and straight followers in a little
        (cls("RrKk"), cls("OoCcGgQqEeIiTt"), -15),
    ]
    lines = ["languagesystem DFLT dflt;", "languagesystem latn dflt;", "feature kern {"]
    for a, b, v in rules:
        if v and a != "[]" and b != "[]":
            lines.append(f"  pos {a} {b} {v};")
    lines.append("} kern;")
    return "\n".join(lines)


def build(style, out):
    items = collect(style)
    order = [".notdef", "space"]
    cs, mt, cmap = {}, {}, {0x20: "space", 0xA0: "space"}

    def charstring(path, adv):
        pen = T2CharStringPen(adv, None)
        if path is not None:
            path.draw(RoundPen(pen))
        return pen.getCharString()

    nd = Shape(); rect(nd, 0, 0, 340, TALL)
    hole = Shape(); rect(hole, 70, 70, 270, TALL - 70)
    p = pathops.op(resolve(nd, SB), resolve(hole, SB), pathops.PathOp.DIFFERENCE)
    cs[".notdef"] = charstring(p, 340 + 2 * SB); mt[".notdef"] = (340 + 2 * SB, SB)
    cs["space"] = charstring(None, 220); mt["space"] = (220, 0)

    for name, ch, w, shape in items:
        if name in cs:
            continue
        path = resolve(shape, SB)
        bx = path.bounds
        lsb = round(bx[0]) if bx else 0
        adv = w + 2 * SB
        if bx and bx[2] > w + SB + 5:
            adv = round(bx[2]) + SB
        if bx and bx[0] < 0:     # something pokes out left (e.g. Ø slash): shift it in
            pass
        cs[name] = charstring(path, adv)
        mt[name] = (adv, lsb)
        order.append(name)
        if ch:
            cmap[ord(ch)] = name

    fb = FontBuilder(1000, isTTF=False)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    ps = f"Tangping-{style}"
    fb.setupCFF(ps, {"FullName": f"Tangping {style}", "FamilyName": "Tangping",
                     "Notice": COPYRIGHT, "Weight": "Regular"}, cs, {})
    fb.setupHorizontalMetrics(mt)
    fb.setupHorizontalHeader(ascent=950, descent=-250)
    regular = style == "Regular"
    names = {
        "copyright": COPYRIGHT,
        # legacy family/style: Even is its own family so it installs side by side on Windows
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
                fsSelection=(1 << 6) | (1 << 7),          # REGULAR + USE_TYPO_METRICS
                version=4)
    fb.setupPost(underlinePosition=-150, underlineThickness=80)
    fb.font["head"].fontRevision = float(VERSION)
    fb.font["OS/2"].recalcUnicodeRanges(fb.font)
    fb.font["OS/2"].recalcCodePageRanges(fb.font)
    addOpenTypeFeaturesFromString(fb.font, kerning_fea(order))
    fb.save(out)
    return fb.font


if __name__ == "__main__":
    import os
    from fontTools.ttLib import TTFont
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    otf_dir = os.path.join(root, "fonts", "otf"); web_dir = os.path.join(root, "fonts", "webfonts")
    os.makedirs(otf_dir, exist_ok=True); os.makedirs(web_dir, exist_ok=True)
    for style in ("Regular", "Even"):
        otf = os.path.join(otf_dir, f"Tangping-{style}.otf")
        f = build(style, otf)
        w = TTFont(otf); w.flavor = "woff2"; w.save(os.path.join(web_dir, f"Tangping-{style}.woff2"))
        print(f"Tangping-{style}: {len(f.getGlyphOrder())} glyphs")
