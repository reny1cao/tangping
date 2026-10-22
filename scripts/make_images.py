#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Renders the README images in docs/images from the fonts (and, for the process images,
from the motion piece's own frames).   python3 scripts/make_images.py"""
import os, sys
import cairo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_video as mv  # noqa: E402

OUT = os.path.join(mv.ROOT, "docs", "images")


def specimen(path):
    W, H = 1600, 1000
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
    ctx = cairo.Context(surf)
    ctx.set_source_rgb(*mv.PAPER); ctx.paint()
    rows = [   # (label, face, text, px, colour)
        ("TANGPING EVEN", mv.EVEN, "TURN · CUT · READ", 150, mv.INK),
        ("TANGPING REGULAR", mv.REG, "Lie flat, stand tall.", 118, mv.INK),
        ("TYPED MAN IN REGULAR, AS IN THE ORIGINAL IMAGE", mv.REG, "MAN", 150, mv.INK),
        ("ACCENTS AND FIGURES", mv.EVEN, "Łódź · Árvíztűrő · Şişli · 2026", 92, mv.INK),
        ("PANGRAM", mv.EVEN, "The quick brown fox jumps over the lazy dog. SPHINX OF BLACK QUARTZ.", 46, mv.MUTED),
    ]
    y = 70
    for lab, face, text, px, rgb in rows:
        mv.label(ctx, lab, 70, y, 17, mv.GREEN, 1.0, "DejaVu Sans Mono", cairo.FONT_WEIGHT_BOLD)
        y += px * 0.86 + 26
        mv.text_run(ctx, face, text, 70, y, px, rgb)
        y += 62
    surf.write_to_png(path)


def frame(t, path, width=1600):
    """a frame of the motion piece, scaled down for the README"""
    src = mv.frame(t)
    k = width / src.get_width()
    out = cairo.ImageSurface(cairo.FORMAT_RGB24, width, round(src.get_height() * k))
    ctx = cairo.Context(out)
    ctx.scale(k, k); ctx.set_source_surface(src); ctx.get_source().set_filter(cairo.FILTER_BEST); ctx.paint()
    out.write_to_png(path)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    specimen(os.path.join(OUT, "specimen.png"))
    frame(5.1, os.path.join(OUT, "cut-man.png"))
    frame(16.2, os.path.join(OUT, "alphabet.png"))
    print("wrote specimen.png, cut-man.png, alphabet.png")
