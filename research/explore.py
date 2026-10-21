# Tangping research tools - Copyright 2026 The Tangping Project Authors
# SPDX-License-Identifier: MIT
import os
from paths import NOTO_CJK, NOTO_INDEX, TANGPING_EVEN
import sys, numpy as np
from PIL import Image, ImageDraw, ImageFont
from sheet import piece
CJK = NOTO_CJK
lab = ImageFont.truetype(CJK, 18, index=NOTO_INDEX)
CUTS = [(0, 0), (0, .25), (0, .5), (.25, 0), (.5, 0), (.25, .25)]
chars = sys.argv[1]; out = sys.argv[2]
cw, chh = 112, 140
cols = len(CUTS) * 2
img = Image.new("L", (60 + cw * cols, chh * len(chars) + 30), 255)
d = ImageDraw.Draw(img)
for j, (tc, bc) in enumerate(CUTS * 2):
    k = 1 if j < len(CUTS) else 3
    d.text((60 + j * cw + 4, 4), f"{'L' if k==1 else 'R'} t{int(tc*100)} b{int(bc*100)}", font=lab, fill=120)
for i, ch in enumerate(chars):
    y = 30 + i * chh
    d.text((10, y + 40), ch, font=ImageFont.truetype(CJK, 40, index=NOTO_INDEX), fill=0)
    for j, (tc, bc) in enumerate(CUTS * 2):
        k = 1 if j < len(CUTS) else 3
        try:
            p = piece(ch, k, 0, 1, tc, bc, em=100)
        except ValueError:
            continue
        pim = Image.fromarray(((~p) * 255).astype(np.uint8))
        x = 60 + j * cw
        d.rectangle((x + 2, y + 2, x + cw - 2, y + chh - 6), outline=225)
        img.paste(pim, (x + (cw - pim.width) // 2, y + chh - 10 - pim.height))
img.save(out)
