# SPDX-License-Identifier: MIT
"""Shared paths for the research scripts. Override with environment variables."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Noto Sans CJK Bold (any OTC/TTC that contains the SC face at index 2), SIL OFL 1.1.
# Download: https://github.com/notofonts/noto-cjk/releases
NOTO_CJK = os.environ.get("NOTO_CJK", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")
NOTO_INDEX = int(os.environ.get("NOTO_INDEX", "2"))          # 2 = Simplified Chinese in the .ttc
TANGPING_EVEN = os.path.join(ROOT, "fonts", "otf", "Tangping-Even.otf")
