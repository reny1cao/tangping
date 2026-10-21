# Tangping research tools - Copyright 2026 The Tangping Project Authors
# SPDX-License-Identifier: MIT
"""Process strips: 字 → turned → band + cut → piece, next to the Tangping letter, with a similarity score."""
import os
from paths import NOTO_CJK, NOTO_INDEX, TANGPING_EVEN
import json, sys, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from sheet import piece

CJK = NOTO_CJK
EM = 150
f = ImageFont.truetype(CJK, EM, index=NOTO_INDEX)
lab = ImageFont.truetype(CJK, 24, index=NOTO_INDEX)
small = ImageFont.truetype(CJK, 18, index=NOTO_INDEX)
TP = ImageFont.truetype(TANGPING_EVEN, 150)
INK, GRID, CUT, BG = (17, 21, 19), (185, 216, 194), (214, 72, 48), (246, 248, 245)


def turned(ch, k):
    im = Image.new("L", (int(EM * 1.35), int(EM * 1.35)), 0)
    ImageDraw.Draw(im).text((EM // 6, 0), ch, font=f, fill=255)
    r = np.rot90(np.asarray(im) > 127, k)
    ys, xs = np.nonzero(r)
    return r[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def to_rgb(a, ink=INK, bg=BG):
    out = np.zeros(a.shape + (3,), np.uint8); out[:] = bg; out[a] = ink
    return Image.fromarray(out)


def sim(a, b, n=32):
    def prep(x):
        ys, xs = np.nonzero(x); x = x[ys.min():ys.max()+1, xs.min():xs.max()+1]
        im = Image.fromarray((x * 255).astype(np.uint8)).resize((n, n), Image.BILINEAR).filter(ImageFilter.GaussianBlur(1))
        v = np.asarray(im, np.float32).ravel(); v -= v.mean(); return v / np.linalg.norm(v)
    return float(prep(a) @ prep(b))


def letter_arr(L):
    im = Image.new("L", (300, 300), 0)
    ImageDraw.Draw(im).text((20, 20), L, font=TP, fill=255)
    a = np.asarray(im) > 127
    ys, xs = np.nonzero(a)
    return a[ys.min():ys.max()+1, xs.min():xs.max()+1]


def strip(L, ch, k, fx0, fx1, tc, bc):
    up = np.asarray(Image.new("L", (1, 1)))
    im = Image.new("L", (int(EM * 1.35), int(EM * 1.35)), 0)
    ImageDraw.Draw(im).text((EM // 6, 0), ch, font=f, fill=255)
    a = np.asarray(im) > 127; ys, xs = np.nonzero(a); a = a[ys.min():ys.max()+1, xs.min():xs.max()+1]
    r = turned(ch, k)
    H, W = r.shape
    p = piece(ch, k, fx0, fx1, tc, bc, em=EM, font=f)
    la = letter_arr(L[0])
    s = sim(p, la)
    pad, cell = 18, 190
    img = Image.new("RGB", (cell * 5 + 40, cell + 70), BG)
    d = ImageDraw.Draw(img)
    def put(arr_img, i):
        x = 10 + i * cell + (cell - arr_img.width) // 2
        y = 10 + (cell - arr_img.height)
        img.paste(arr_img, (x, y)); return x, y
    put(to_rgb(a), 0)
    # turned, with kept region and cut line
    rim = to_rgb(r, ink=(170, 180, 174))
    keep = np.zeros_like(r); y0, y1 = int(H * tc), int(H * (1 - bc)); x0, x1 = int(fx0 * W), int(fx1 * W)
    keep[y0:y1, x0:x1] = r[y0:y1, x0:x1]
    arr = np.asarray(rim).copy(); arr[keep] = INK; rim = Image.fromarray(arr)
    x, y = put(rim, 1)
    dd = ImageDraw.Draw(img)
    dd.line((x - 6, y + y1, x + W + 6, y + y1), fill=CUT, width=3)
    if tc: dd.line((x - 6, y + y0, x + W + 6, y + y0), fill=CUT, width=3)
    if fx0 > 0: dd.line((x + x0, y - 4, x + x0, y + H + 4), fill=CUT, width=2)
    if fx1 < 1: dd.line((x + x1, y - 4, x + x1, y + H + 4), fill=CUT, width=2)
    put(to_rgb(p), 2)
    d.text((10 + 3 * cell + cell // 2 - 10, cell // 2 - 10), "≈", font=lab, fill=INK)
    put(to_rgb(la), 4)
    turn = "↺ 90°" if k == 1 else "↻ 90°"
    cutdesc = f"cut {int(bc*100)}%" + (f" + top {int(tc*100)}%" if tc else "")
    d.text((14, cell + 22), f"{L}  ←  {ch}   {turn}   {cutdesc}", font=lab, fill=INK)
    d.text((cell * 5 - 150, cell + 26), f"match {s:.2f}", font=small, fill=(29, 115, 70) if s > .8 else (150, 110, 40))
    return img, s


if __name__ == "__main__":
    picks = json.load(open(sys.argv[1]))
    rows = []
    for L, spec in picks.items():
        img, s = strip(L, *spec)
        rows.append((L, img, s))
        print(L, spec[0], f"{s:.3f}")
    W = rows[0][1].width
    cols = 2
    Hh = rows[0][1].height
    sheet = Image.new("RGB", (W * cols, Hh * ((len(rows) + cols - 1) // cols)), BG)
    for i, (L, img, s) in enumerate(rows):
        sheet.paste(img, ((i % cols) * W, (i // cols) * Hh))
    sheet.save(sys.argv[2])
