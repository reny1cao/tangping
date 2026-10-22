#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Builds docs/index.html (type tester + source map) with the web fonts embedded,
so the page works as a single file and on GitHub Pages."""
import base64, json, os
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
web = os.path.join(ROOT, "fonts", "webfonts")
tpl = open(os.path.join(ROOT, "scripts", "specimen_template.html"), encoding="utf-8").read()
cmap = TTFont(os.path.join(ROOT, "fonts", "otf", "Tangping-Regular.otf")).getBestCmap()
import unicodedata
chars = "".join(chr(c) for c in sorted(cmap) if c not in (0x20, 0xA0) and not unicodedata.category(chr(c)).startswith("M"))
sources = json.load(open(os.path.join(ROOT, "docs", "data", "sources.json"), encoding="utf-8"))
b64 = lambda name: base64.b64encode(open(os.path.join(web, name), "rb").read()).decode()

body = (tpl.replace("__REG__", b64("Tangping-Regular.woff2"))
           .replace("__EVEN__", b64("Tangping-Even.woff2"))
           .replace("__CHARS__", json.dumps(chars, ensure_ascii=False))
           .replace("__SOURCES__", json.dumps(sources, ensure_ascii=False)))
html = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
        'body{margin:0}[hidden]{display:none!important}img{max-width:100%}</style>\n</head>\n<body>\n'
        + body + '\n</body>\n</html>\n')
dest = os.path.join(ROOT, "docs", "index.html")
open(dest, "w", encoding="utf-8").write(html)
print("wrote", dest, len(html), "bytes")
