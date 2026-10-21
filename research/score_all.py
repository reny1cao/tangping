# Tangping research tools - Copyright 2026 The Tangping Project Authors
# SPDX-License-Identifier: MIT
"""Score every source piece against the current Tangping letter (same metric as the verify strips)."""
import os
from paths import NOTO_CJK, NOTO_INDEX, TANGPING_EVEN
import json, sys, importlib
import verify
from PIL import ImageFont
verify.TP = ImageFont.truetype(sys.argv[1] if len(sys.argv) > 1 else TANGPING_EVEN, 150)
from verify import piece, letter_arr, sim, f, EM
picks = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "picks.json")))
out = {}
for L, (ch, k, fx0, fx1, tc, bc) in picks.items():
    out[L] = round(sim(piece(ch, k, fx0, fx1, tc, bc, em=EM, font=f), letter_arr(L)), 3)
print(json.dumps(out))
