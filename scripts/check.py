#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Release checks: OTS sanitizer on every font file, Font Bakery universal profile on the OTFs,
and a coverage check that every printable ASCII character is mapped."""
import glob, os, subprocess, sys
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
otfs = sorted(glob.glob(os.path.join(ROOT, "fonts", "otf", "*.otf")))
woffs = sorted(glob.glob(os.path.join(ROOT, "fonts", "webfonts", "*.woff2")))
ok = True
for f in otfs + woffs:
    r = subprocess.run([sys.executable, "-m", "ots", f], capture_output=True, text=True)
    print(("OTS pass  " if r.returncode == 0 else "OTS FAIL  ") + os.path.relpath(f, ROOT))
    ok &= r.returncode == 0
for f in otfs:
    cmap = TTFont(f).getBestCmap()
    missing = [chr(c) for c in range(0x20, 0x7F) if c not in cmap]
    print(f"ASCII coverage {'complete' if not missing else 'missing ' + ''.join(missing)}  {os.path.basename(f)}")
    ok &= not missing
r = subprocess.run(["fontbakery", "check-universal", "-l", "WARN", "--succinct", *otfs], capture_output=True, text=True)
summary = [l for l in r.stdout.splitlines() if "FAIL:" in l]
print("Font Bakery:", summary[-1].strip() if summary else r.stdout[-500:])
ok &= bool(summary) and " FAIL: 0 " in summary[-1] + " "
sys.exit(0 if ok else 1)
