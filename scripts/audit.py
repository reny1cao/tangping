#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Design audit for Tangping: spacing evenness, kerned collisions, stroke weights, typographic
colour, confusable glyphs, outline extrema, features and metrics.   python3 scripts/audit.py [font.otf]"""
import json, os, sys
import numpy as np
import cairo
import uharfbuzz as hb
from scipy import ndimage
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
from fontTools.pens.recordingPen import RecordingPen

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "fonts", "otf", "Tangping-Even.otf")
S = 0.5                     # px per unit for rasterising (1 px = 2 units)
YMIN, YMAX = -320, 1100

tt = TTFont(FONT)
gs = tt.getGlyphSet()
cmap = tt.getBestCmap()
hmtx = tt["hmtx"].metrics
order = tt.getGlyphOrder()
hbf = hb.Font(hb.Face(hb.Blob(open(FONT, "rb").read())))


class CPen(BasePen):
    def __init__(self, ctx): super().__init__(gs); self.c = ctx
    def _moveTo(self, p): self.c.move_to(*p)
    def _lineTo(self, p): self.c.line_to(*p)
    def _curveToOne(self, a, b, c): self.c.curve_to(*a, *b, *c)
    def _closePath(self): self.c.close_path()


_cache = {}


def raster(name):
    """bitmap of a glyph: rows from YMAX down to YMIN, columns from x=-200 units"""
    if name in _cache: return _cache[name]
    adv = hmtx[name][0]
    w = int((adv + 400) * S) + 2; h = int((YMAX - YMIN) * S)
    surf = cairo.ImageSurface(cairo.FORMAT_A8, w, h)
    ctx = cairo.Context(surf)
    ctx.translate(200 * S, YMAX * S); ctx.scale(S, -S)
    gs[name].draw(CPen(ctx)); ctx.fill()
    a = np.ndarray((h, surf.get_stride()), np.uint8, surf.get_data())[:, :w] > 127
    _cache[name] = a
    return a


def gname(ch): return cmap[ord(ch)]


def row_extents(name):
    """per-row leftmost and rightmost ink x in font units (nan where no ink)"""
    a = raster(name)
    has = a.any(1)
    left = np.where(has, a.argmax(1) / S - 200, np.nan)
    right = np.where(has, (a.shape[1] - 1 - a[:, ::-1].argmax(1)) / S - 200, np.nan)
    return left, right


def y_rows(y0, y1):
    """row indices covering font-unit y range [y0, y1]"""
    r0 = int((YMAX - y1) * S); r1 = int((YMAX - y0) * S)
    return slice(max(r0, 0), r1)


def kern(a, b):
    buf = hb.Buffer(); buf.add_str(a + b); buf.guess_segment_properties()
    hb.shape(hbf, buf, {"kern": True})
    p = buf.glyph_positions
    return p[0].x_advance - hmtx[gname(a)][0]


out = {}

# ---------------------------------------------------------------- spacing evenness (HT-Letterspacer-style area)
def side_area(name, side, y0, y1, depth=160):
    left, right = row_extents(name)
    adv = hmtx[name][0]
    rows = y_rows(y0, y1)
    d = left[rows] if side == "L" else adv - right[rows]
    d = np.where(np.isnan(d), depth, np.minimum(d, depth))
    return float(np.mean(d))


def spacing(letters, control, top):
    ref_l, ref_r = side_area(gname(control), "L", 0, top), side_area(gname(control), "R", 0, top)
    res = []
    for ch in letters:
        n = gname(ch)
        l, r = side_area(n, "L", 0, top), side_area(n, "R", 0, top)
        res.append((ch, round(l / ref_l, 2), round(r / ref_r, 2)))
    return res


caps = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
digits = "0123456789"
out["spacing_caps"] = spacing(caps, "H", 689)
out["spacing_digits"] = spacing(digits, "H", 689)

# ---------------------------------------------------------------- collisions / near-collisions after kerning
pairset = caps + caps.lower() + digits + ".,:;!?'\"-()/&"
ext = {c: row_extents(gname(c)) for c in pairset}
coll = []
for a in pairset:
    la, ra = ext[a]
    adv = hmtx[gname(a)][0]
    for b in pairset:
        lb, rb = ext[b]
        k = kern(a, b)
        gap = (adv + k + lb) - ra
        if np.all(np.isnan(gap)): continue
        g = float(np.nanmin(gap))
        if g < 40:
            coll.append((a + b, round(g), k))
coll.sort(key=lambda x: x[1])
out["tight_pairs"] = coll[:40]
out["tight_pairs_count"] = len(coll)
out["kern_pairs_nonzero"] = sum(1 for a in caps + caps.lower() for b in caps + caps.lower() if kern(a, b) != 0)

# ---------------------------------------------------------------- stroke thickness (distance transform ridges)
def strokes(name):
    a = raster(name)
    if not a.any(): return None
    d = ndimage.distance_transform_edt(a)
    ridge = (d == ndimage.maximum_filter(d, size=5)) & (d > 3)
    w = 2 * d[ridge] / S
    return float(np.percentile(w, 5)), float(np.median(w)), float(np.percentile(w, 95))


weights = {}
for ch in caps + digits + "&@#%$?!*+/()[]{}<>«»©®™°ÅÑÃÖÉ":
    if ord(ch) in cmap:
        weights[ch] = [round(v) for v in strokes(gname(ch))]
out["thin_strokes"] = sorted([(c, w) for c, w in weights.items() if w[0] < 80], key=lambda x: x[1][0])

# ---------------------------------------------------------------- typographic colour
def density(ch, top):
    a = raster(gname(ch))[y_rows(0, top)]
    adv = hmtx[gname(ch)][0]
    return a.sum() / (adv * S * top * S)


dens = {c: round(float(density(c, 689)), 3) for c in caps}
v = np.array(list(dens.values()))
out["color_caps"] = dict(mean=round(float(v.mean()), 3), cv=round(float(v.std() / v.mean()), 3),
                         darkest=sorted(dens.items(), key=lambda x: -x[1])[:5],
                         lightest=sorted(dens.items(), key=lambda x: x[1])[:5])

# ---------------------------------------------------------------- confusable glyphs (IoU after aligning on origin)
def mask(ch):
    a = raster(gname(ch))[y_rows(-150, 900)]
    return a


conf = []
pool = caps + digits
for i, a in enumerate(pool):
    for b in pool[i + 1:]:
        ma, mb = mask(a), mask(b)
        w = max(ma.shape[1], mb.shape[1])
        pa = np.zeros((ma.shape[0], w), bool); pb = np.zeros_like(pa)
        pa[:, :ma.shape[1]] = ma; pb[:, :mb.shape[1]] = mb
        iou = (pa & pb).sum() / max((pa | pb).sum(), 1)
        if iou > 0.6:
            conf.append((a + "/" + b, round(float(iou), 2)))
out["confusable"] = sorted(conf, key=lambda x: -x[1])

# ---------------------------------------------------------------- outline: missing extrema on curves
def missing_extrema(name):
    rp = RecordingPen(); gs[name].draw(rp)
    cur, n = None, 0
    for op, pts in rp.value:
        if op == "moveTo": cur = pts[0]
        elif op == "lineTo": cur = pts[0]
        elif op == "curveTo":
            p0, p1, p2, p3 = cur, *pts
            for k in (0, 1):
                a = -p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]
                b = 2 * (p0[k] - 2 * p1[k] + p2[k])
                c = p1[k] - p0[k]
                roots = []
                if abs(a) > 1e-9:
                    disc = b * b - 4 * a * c
                    if disc >= 0:
                        roots = [(-b + s * disc ** 0.5) / (2 * a) for s in (1, -1)]
                elif abs(b) > 1e-9:
                    roots = [-c / b]
                for t in roots:
                    if 0.02 < t < 0.98:
                        # only count real bumps (>2 units) as missing extrema
                        q = (1 - t) ** 3 * p0[k] + 3 * (1 - t) ** 2 * t * p1[k] + 3 * (1 - t) * t * t * p2[k] + t ** 3 * p3[k]
                        if abs(q - p0[k]) > 2 and abs(q - p3[k]) > 2:
                            n += 1
            cur = pts[-1]
    return n


me = {n: missing_extrema(n) for n in order if n not in (".notdef", "space")}
out["missing_extrema_glyphs"] = sum(1 for v in me.values() if v)
out["missing_extrema_examples"] = [k for k, v in me.items() if v][:12]

# ---------------------------------------------------------------- features, digits, metrics
feats = set()
for tag in ("GSUB", "GPOS"):
    if tag in tt:
        for fr in tt[tag].table.FeatureList.FeatureRecord:
            feats.add(fr.FeatureTag)
out["features"] = sorted(feats)
out["digit_advances"] = {d: hmtx[gname(d)][0] for d in digits}
os2, hhea, head = tt["OS/2"], tt["hhea"], tt["head"]
out["metrics"] = dict(upm=head.unitsPerEm, cap=os2.sCapHeight, x=os2.sxHeight, typoAsc=os2.sTypoAscender,
                      typoDesc=os2.sTypoDescender, lineGap=os2.sTypoLineGap, winAsc=os2.usWinAscent,
                      winDesc=os2.usWinDescent, yMax=head.yMax, yMin=head.yMin)
out["has_combining_marks"] = any(0x300 <= c <= 0x36F for c in cmap)
out["has_GDEF"] = "GDEF" in tt
out["hinted"] = bool(tt["CFF "].cff.topDictIndex[0].Private.rawDict.get("BlueValues"))
out["glyph_count"] = len(order)
print(json.dumps(out, ensure_ascii=False, indent=1))
