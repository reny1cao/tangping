#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Renders the Tangping motion piece (1920×1080, 30 fps, H.264 + AAC) from real outlines:
Noto Sans CJK Bold for the hanzi, the Tangping fonts for the letters, and original music from
scripts/bgm.py. Picture and music share one timeline on a 96 BPM grid (a bar is 2.5 s).

    python3 scripts/make_video.py [out.mp4]
    python3 scripts/make_video.py --still 5.2 14.8     # PNG stills for checking

Needs pycairo, uharfbuzz, fonttools, numpy, scipy, ffmpeg and Noto Sans CJK (see research/paths.py).
"""
import json, math, os, subprocess, sys
import cairo
import uharfbuzz as hb
from fontTools.ttLib import TTFont, TTCollection
from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "research"))
from paths import NOTO_CJK, NOTO_INDEX  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "scripts"))
import bgm  # noqa: E402

W, H, FPS = 1920, 1080, 30
BEAT, BAR, S16 = bgm.BEAT, bgm.BAR, bgm.S16
S32 = S16 / 2


def bar(n, beat=0.0):
    return n * BAR + beat * BEAT


DUR = bar(11)                                   # 27.5 s
TL = dict(
    cell=(0.0, 0.9), han_in=(0.3, 1.1),
    turn=(bar(1), bar(1, 2)),                   # 曼 lies down over two beats
    cutline=(bar(1, 2), bar(1, 3)),
    slice=bar(1, 3),                            # the blade: beat 4 of bar 2
    fall=(bar(1, 3.5), bar(2, 0.7)),            # the cut-off part falls through the downbeat
    drop=bar(2),                                # beat drops: 5.0 s
    morph=(bar(2, 0.25), bar(2, 1.5)),
    glide=(bar(2, 2), bar(2, 3.4)),
    title=bar(3),                               # TANGPING lands on bar 4
    intro_out=(bar(3, 3.2), bar(4)),
    parade=(bar(4), bar(5)),                    # row starts: one letter per 16th
    parade_out=(bar(6, 3.2), bar(7)),
    type_out=(bar(8, 3.4), bar(9)),
    end=bar(9),                                 # end card on the downbeat: 22.5 s
    lie_down=bar(10),                           # 躺 lies down: 25.0 s
)
# letter animation, relative to its appearance (cut lands exactly 4 sixteenths later)
L_APPEAR, L_TURN, L_CUT, L_MORPH = (0, 0.2), (0.2, 0.6), (4 * S16, 4 * S16 + 0.18), (0.9, 1.25)
TYPE_LINES = [   # (label, style, text, baseline, px, colour, start)
    ("REGULAR", "REG", "LIE FLAT. STAND TALL.", 420, 150, "INK", bar(7, 0.25)),
    ("EVEN", "EVEN", "TURN · CUT · READ", 730, 150, "INK", bar(7, 3)),
    (None, "EVEN", "ÉCRIT · KÖRT · 2026", 900, 90, "MUTED", bar(8, 0)),
]
OUT = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else \
    os.path.join(ROOT, "docs", "media", "tangping-motion.mp4")


def hexrgb(h):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


PAPER, INK, GRID, GRID2, CUT, GREEN, MUTED = map(hexrgb, ("f6f8f5", "111513", "b9d8c2", "5c9f73", "c4513a", "1d7346", "5b6a61"))


# ------------------------------------------------------------------ easing
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def seg(t, t0, t1): return clamp((t - t0) / (t1 - t0)) if t1 > t0 else float(t >= t1)
def ease(x): return x * x * (3 - 2 * x)
def ease_io(x): return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2
def ease_out(x): return 1 - (1 - x) ** 3
def lerp(a, b, x): return a + (b - a) * x


# ------------------------------------------------------------------ fonts
class CairoPen(BasePen):
    def __init__(self, gs, ctx): super().__init__(gs); self.ctx = ctx
    def _moveTo(self, p): self.ctx.move_to(*p)
    def _lineTo(self, p): self.ctx.line_to(*p)
    def _curveToOne(self, a, b, c): self.ctx.curve_to(*a, *b, *c)
    def _closePath(self): self.ctx.close_path()


class Face:
    def __init__(self, path, index=None):
        if index is None:
            self.tt = TTFont(path); data = open(path, "rb").read(); self.hbf = hb.Font(hb.Face(hb.Blob(data)))
        else:
            self.tt = TTCollection(path).fonts[index]; self.hbf = None
        self.gs = self.tt.getGlyphSet(); self.cmap = self.tt.getBestCmap()
        self.order = self.tt.getGlyphOrder()

    def gname(self, ch): return self.cmap[ord(ch)]

    def bounds(self, name):
        bp = BoundsPen(self.gs); self.gs[name].draw(bp); return bp.bounds

    def draw(self, ctx, name):
        self.gs[name].draw(CairoPen(self.gs, ctx))

    def shape(self, text):
        buf = hb.Buffer(); buf.add_str(text); buf.guess_segment_properties()
        hb.shape(self.hbf, buf, {"kern": True})
        x, out = 0, []
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            out.append((self.order[info.codepoint], x + pos.x_offset)); x += pos.x_advance
        return out, x


REG = Face(os.path.join(ROOT, "fonts", "otf", "Tangping-Regular.otf"))
EVEN = Face(os.path.join(ROOT, "fonts", "otf", "Tangping-Even.otf"))
NOTO = Face(NOTO_CJK, NOTO_INDEX)
PICKS = json.load(open(os.path.join(ROOT, "research", "picks.json"), encoding="utf-8"))


# ------------------------------------------------------------------ drawing helpers
def fill(ctx, rgb, a=1.0): ctx.set_source_rgba(*rgb, a); ctx.fill()


def text_run(ctx, face, text, x, baseline, px, rgb=INK, a=1.0, reveal=None):
    """Tangping text with kerning. reveal: fraction of characters shown (typing effect)."""
    glyphs, adv = face.shape(text)
    s = px / 1000
    n = len(glyphs)
    for i, (g, gx) in enumerate(glyphs):
        k = 1.0 if reveal is None else clamp(reveal * n - i)
        if k <= 0: continue
        ctx.save(); ctx.translate(x + gx * s, baseline + (1 - ease_out(k)) * 18); ctx.scale(s, -s)
        face.draw(ctx, g); ctx.restore(); fill(ctx, rgb, a * ease(k))
    return adv * s


def label(ctx, text, x, y, size=22, rgb=MUTED, a=1.0, family="DejaVu Sans Mono", weight=cairo.FONT_WEIGHT_NORMAL, anchor="left"):
    ctx.select_font_face(family, cairo.FONT_SLANT_NORMAL, weight); ctx.set_font_size(size)
    w = ctx.text_extents(text).x_advance
    ctx.move_to(x - (w if anchor == "right" else w / 2 if anchor == "center" else 0), y)
    ctx.set_source_rgba(*rgb, a); ctx.show_text(text)


def tianzi(ctx, cx, cy, size, a=1.0, draw=1.0):
    """田字格 practice cell; draw animates the lines in"""
    h = size / 2
    ctx.set_line_width(2); ctx.set_source_rgba(*GRID2, a)
    k = ease_out(draw)
    ctx.move_to(cx - h, cy - h); ctx.line_to(cx - h + 2 * h * k, cy - h)
    ctx.move_to(cx + h, cy - h); ctx.line_to(cx + h, cy - h + 2 * h * k)
    ctx.move_to(cx + h, cy + h); ctx.line_to(cx + h - 2 * h * k, cy + h)
    ctx.move_to(cx - h, cy + h); ctx.line_to(cx - h, cy + h - 2 * h * k)
    ctx.stroke()
    ctx.set_line_width(1.2); ctx.set_source_rgba(*GRID, a); ctx.set_dash([10, 8])
    ctx.move_to(cx - h, cy); ctx.line_to(cx - h + 2 * h * k, cy)
    ctx.move_to(cx, cy - h); ctx.line_to(cx, cy - h + 2 * h * k)
    ctx.stroke(); ctx.set_dash([])


class Turned:
    """A hanzi that turns a quarter-turn about its centre and is then cut, as in research/picks.json."""
    def __init__(self, ch, k=1, fx0=0, fx1=1, tc=0, bc=0):
        self.name = NOTO.gname(ch)
        x0, y0, x1, y1 = NOTO.bounds(self.name)
        self.c = ((x0 + x1) / 2, (y0 + y1) / 2); self.w, self.h = x1 - x0, y1 - y0
        self.dir = 1 if k == 1 else -1
        # kept rectangle in the turned, centred frame (font units, y up)
        Wt, Ht = self.h, self.w      # turned bbox: width = upright height
        self.keep = (-Wt / 2 + fx0 * Wt, -Ht / 2 + bc * Ht, -Wt / 2 + fx1 * Wt, Ht / 2 - tc * Ht)
        self.tb = (-Wt / 2, -Ht / 2, Wt / 2, Ht / 2)

    def _path(self, ctx, X, Y, s, ang):
        ctx.save(); ctx.translate(X, Y); ctx.scale(s, -s); ctx.rotate(ang)
        ctx.translate(-self.c[0], -self.c[1]); NOTO.draw(ctx, self.name); ctx.restore()

    def draw(self, ctx, X, Y, s, turn, cut=0.0, drop=0.0, rgb=INK, a=1.0, ghost=0.35):
        """turn 0..1 quarter-turn; cut 0..1 shows the cut (kept part ink, rest fades); drop pushes the rest away"""
        ang = self.dir * math.pi / 2 * ease_io(turn)
        if cut <= 0:
            self._path(ctx, X, Y, s, ang); fill(ctx, rgb, a); return
        kx0, ky0, kx1, ky1 = self.keep
        # discarded part: fades to the grid colour and drops
        ctx.save(); ctx.translate(X, Y); ctx.scale(s, -s)
        ctx.rectangle(-1e4, -1e4, 2e4, 2e4); ctx.rectangle(kx0, ky0, kx1 - kx0, ky1 - ky0)
        ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD); ctx.clip(); ctx.restore()
        dy = drop * 140
        self._path(ctx, X, Y + dy, s, ang)
        ctx.set_fill_rule(cairo.FILL_RULE_WINDING)
        mix = tuple(lerp(rgb[i], GRID[i], ease(cut)) for i in range(3))
        fill(ctx, mix, a * (1 - drop))
        ctx.reset_clip()
        # kept part
        ctx.save(); ctx.translate(X, Y); ctx.scale(s, -s)
        ctx.rectangle(kx0, ky0, kx1 - kx0, ky1 - ky0); ctx.restore(); ctx.clip()
        self._path(ctx, X, Y, s, ang); fill(ctx, rgb, a); ctx.reset_clip()

    def cutlines(self, ctx, X, Y, s, k, a=1.0):
        """animated red dashed cut lines along the kept rectangle's inner edges"""
        kx0, ky0, kx1, ky1 = self.keep; tx0, ty0, tx1, ty1 = self.tb
        ctx.set_source_rgba(*CUT, a); ctx.set_line_width(3); ctx.set_dash([16, 10])
        P = lambda x, y: (X + x * s, Y - y * s)
        pad = 40 / s
        if ky0 > ty0 + 1:
            a0, a1 = P(tx0 - pad, ky0), P(tx1 + pad, ky0)
            ctx.move_to(*a0); ctx.line_to(lerp(a0[0], a1[0], k), a0[1])
        if ky1 < ty1 - 1:
            a0, a1 = P(tx0 - pad, ky1), P(tx1 + pad, ky1)
            ctx.move_to(*a0); ctx.line_to(lerp(a0[0], a1[0], k), a0[1])
        if kx0 > tx0 + 1:
            a0, a1 = P(kx0, ty1 + pad), P(kx0, ty0 - pad)
            ctx.move_to(*a0); ctx.line_to(a0[0], lerp(a0[1], a1[1], k))
        if kx1 < tx1 - 1:
            a0, a1 = P(kx1, ty1 + pad), P(kx1, ty0 - pad)
            ctx.move_to(*a0); ctx.line_to(a0[0], lerp(a0[1], a1[1], k))
        ctx.stroke(); ctx.set_dash([])

    def kept_screen_box(self, X, Y, s):
        kx0, ky0, kx1, ky1 = self.keep
        return X + kx0 * s, Y - ky1 * s, X + kx1 * s, Y - ky0 * s


# ------------------------------------------------------------------ scenes
MAN = Turned("曼", 1, 0, 1, 0, 0.44)
MAN_S = 0.62                     # px per font unit for the big 曼
MAN_X, MAN_Y = W / 2, H / 2 + 10


def scene_intro(ctx, t):
    """bar 1–4: 曼 stands, lies down, is cut, reads mAn; then the title"""
    steps = [(0.4, TL["turn"][0], "曼  màn", "stand"), (TL["turn"][0], TL["cutline"][0], "躺平", "lie down"),
             (TL["cutline"][0], TL["drop"], "切", "cut"), (TL["drop"], 6.6, "读", "read")]
    a_scene = 1 - ease(seg(t, *TL["intro_out"]))
    for t0, t1, zh, en in steps:
        a = ease(seg(t, t0, t0 + .25)) * (1 - ease(seg(t, t1 - .2, t1))) * a_scene
        if a > 0:
            label(ctx, zh, 120, H - 120, 40, INK, a, "Noto Sans CJK SC", cairo.FONT_WEIGHT_BOLD)
            label(ctx, en.upper(), 120, H - 78, 20, MUTED, a)

    a_cr = ease(seg(t, 0.6, 1.2)) * a_scene
    label(ctx, "IDEA: 曼 → MAN, BY サイバー環状線 @CyberKanjousen", W - 120, 92, 22, MUTED, a_cr,
          "Noto Sans CJK SC", anchor="right")
    tianzi(ctx, MAN_X, MAN_Y, 700, a=1 - ease(seg(t, TL["turn"][0] - 0.3, TL["turn"][0] + 0.4)), draw=seg(t, *TL["cell"]))
    turn = seg(t, *TL["turn"])
    cut = seg(t, TL["slice"], TL["slice"] + 0.3)
    drop = ease_out(seg(t, *TL["fall"]))
    morph = ease(seg(t, *TL["morph"]))
    a_in = ease(seg(t, *TL["han_in"]))
    if morph < 1:
        MAN.draw(ctx, MAN_X, MAN_Y, MAN_S, turn, cut=cut, drop=drop, a=a_in * (1 - morph))
        if t >= TL["cutline"][0]:
            MAN.cutlines(ctx, MAN_X, MAN_Y, MAN_S, ease_out(seg(t, *TL["cutline"])),
                         a=1 - ease(seg(t, TL["drop"], TL["drop"] + 0.4)))
    if morph > 0:
        x0, y0, x1, y1 = MAN.kept_screen_box(MAN_X, MAN_Y, MAN_S)
        glyphs, adv = EVEN.shape("mAn")
        px = (x1 - x0) / (adv / 1000) * 0.98
        g = ease_io(seg(t, *TL["glide"]))
        bx = lerp(x0, 150, g); by = lerp(y1, 420, g); pxx = lerp(px, 230, g)
        text_run(ctx, EVEN, "mAn", bx, by, pxx, INK, morph * a_scene)
        a = ease(seg(t, TL["title"] - 0.45, TL["title"])) * a_scene
        if a > 0:
            text_run(ctx, EVEN, "TANGPING", 150, 740, 250, INK, a)
            label(ctx, "躺平体", 1770, 400, 96, INK, a, "Noto Sans CJK SC", cairo.FONT_WEIGHT_BOLD, anchor="right")
            label(ctx, "LATIN LETTERS DRAWN AS HEI HANZI LYING ON THEIR SIDE", 154, 830, 24, GREEN, a)


COLS, CW, ROW_H = 13, 129, 360
LEFT = (W - COLS * CW) / 2


def letter_slot(i):
    """screen centre and appearance time of letter i (row 1 on bar 5, row 2 on bar 6)"""
    col, row = i % COLS, i // COLS
    return LEFT + col * CW + CW / 2, 330 + row * ROW_H, TL["parade"][row] + col * S16


def scene_parade(ctx, t):
    """bars 5–7: every letter from its source character, one per 16th"""
    a_scene = ease(seg(t, TL["parade"][0] - 0.3, TL["parade"][0])) * (1 - ease(seg(t, *TL["parade_out"])))
    if a_scene <= 0: return
    label(ctx, "EVERY LETTER IS A REAL CHARACTER, TURNED AND CUT", 120, 120, 24, GREEN, a_scene)
    for i, L in enumerate(PICKS):
        ch = PICKS[L][0]
        cx, cy, ta = letter_slot(i)
        tau = t - ta
        if tau <= 0: continue
        appear = ease(seg(tau, *L_APPEAR))
        turn = seg(tau, *L_TURN)
        cut = seg(tau, *L_CUT)
        morph = ease(seg(tau, *L_MORPH))
        if morph < 1:
            PARADE[L].draw(ctx, cx, cy, 0.105, turn, cut=cut, drop=0, a=appear * (1 - morph) * a_scene)
        if morph > 0:
            name = EVEN.gname(L)
            bx0, by0, bx1, by1 = EVEN.bounds(name)
            sc = 120 / 1000
            ctx.save(); ctx.translate(cx - (bx0 + bx1) / 2 * sc, cy + 60); ctx.scale(sc, -sc)
            EVEN.draw(ctx, name); ctx.restore(); fill(ctx, INK, morph * a_scene)
        a = appear * a_scene
        label(ctx, ch, cx - 22, cy + 120, 24, MUTED, a, "Noto Sans CJK SC")
        label(ctx, "→", cx + 2, cy + 118, 20, GRID2, a)
        label(ctx, L, cx + 26, cy + 118, 22, INK, a * max(morph, .35), "DejaVu Sans Mono", cairo.FONT_WEIGHT_BOLD)


def type_spans(line):
    """(start, end) of the typing reveal for a TYPE_LINES entry: one character per 32nd note"""
    text, start = line[2], line[6]
    return start, start + len(text) * S32


def scene_type(ctx, t):
    """bars 8–9: sample lines type on, one character per 32nd"""
    a_scene = ease(seg(t, TL["parade_out"][1], TL["parade_out"][1] + 0.3)) * (1 - ease(seg(t, *TL["type_out"])))
    if a_scene <= 0: return
    for line in TYPE_LINES:
        lab, style, text, base, px, colour, start = line
        a0, a1 = type_spans(line)
        if lab:
            label(ctx, lab, 150, base - px - 20, 20, GREEN, a_scene * ease(seg(t, a0 - 0.3, a0)))
        face = REG if style == "REG" else EVEN
        text_run(ctx, face, text, 150, base, px, INK if colour == "INK" else MUTED, a_scene, reveal=seg(t, a0, a1))


TANG = None


def scene_end(ctx, t):
    """bars 10–11: end card on the downbeat; at 25 s 躺 itself lies down"""
    t0 = TL["end"]
    a = ease(seg(t, t0, t0 + .5)) * (1 - ease(seg(t, DUR - .7, DUR)))
    if a <= 0: return
    tianzi(ctx, 330, 470, 300, a=a, draw=seg(t, t0, t0 + .7))
    TANG.draw(ctx, 330, 470, 0.25, ease_io(seg(t, TL["lie_down"], TL["lie_down"] + 0.6)), a=a)
    text_run(ctx, EVEN, "Tangping", 600, 560, 230, INK, a)
    label(ctx, "FREE & OPEN SOURCE  ·  SIL OPEN FONT LICENSE 1.1", 606, 660, 26, GREEN, a)
    label(ctx, "REGULAR & EVEN  ·  205 GLYPHS  ·  OTF + WOFF2", 606, 706, 22, MUTED, a)
    a2 = a * ease(seg(t, t0 + 0.6, t0 + 1.2))
    label(ctx, "IDEA: サイバー環状線  @CyberKanjousen", 606, 760, 24, INK, a2, "Noto Sans CJK SC", cairo.FONT_WEIGHT_BOLD)
    label(ctx, "MUSIC: ORIGINAL, SYNTHESIZED IN CODE  ·  github.com/reny1cao/tangping", 606, 800, 18, MUTED, a2)


PARADE = {L: Turned(*PICKS[L]) for L in PICKS}
TANG = Turned("躺", 1)


def frame(t):
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
    ctx = cairo.Context(surf)
    ctx.set_source_rgb(*PAPER); ctx.paint()
    if t < TL["intro_out"][1]: scene_intro(ctx, t)
    scene_parade(ctx, t)
    scene_type(ctx, t)
    scene_end(ctx, t)
    return surf


def audio_events():
    """every sound cue, taken from the same timeline the picture uses"""
    letters = []
    for i in range(len(PICKS)):
        cx, cy, ta = letter_slot(i)
        letters.append((ta, ta + L_CUT[0], (cx - W / 2) / (W / 2), i))
    typing = []
    for line in TYPE_LINES:
        lab, style, text, base, px, colour, start = line
        face = REG if style == "REG" else EVEN
        glyphs, _ = face.shape(text)
        for i, (ch, (g, gx)) in enumerate(zip(text, glyphs)):
            if ch.strip() and ch != "·":
                x = 150 + gx * px / 1000
                typing.append((start + i * S32, 0.6 * (x - W / 2) / (W / 2)))
    return dict(duration=DUR, turn=TL["turn"], slice=TL["slice"], fall=TL["fall"], drop=TL["drop"],
                title=TL["title"], letters=letters, alphabet_hold=bar(6), answer=bar(8),
                parade_out=TL["parade_out"][1], typing=typing, end=TL["end"], lie_down=TL["lie_down"])


def loudnorm(src, dst):
    """two-pass EBU R128 normalisation to -16 LUFS, true peak -1.5 dBTP, encoded as AAC"""
    target = "I=-16:TP=-1.5:LRA=11"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", src, "-af", f"loudnorm={target}:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True)
    js = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
    flt = (f"loudnorm={target}:measured_I={js['input_i']}:measured_TP={js['input_tp']}:"
           f"measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:"
           f"offset={js['target_offset']}:linear=true")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-af", flt, "-ar", "48000",
                    "-c:a", "aac", "-b:a", "192k", dst], check=True)


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".parts"
    os.makedirs(tmp, exist_ok=True)
    wav, m4a, silent = (os.path.join(tmp, n) for n in ("music.wav", "music.m4a", "video.mp4"))
    bgm.render(audio_events(), wav)
    loudnorm(wav, m4a)
    n = int(round(DUR * FPS))
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow",
                           "-crf", "18", "-pix_fmt", "yuv420p", silent], stdin=subprocess.PIPE)
    for i in range(n):
        ff.stdin.write(bytes(frame(i / FPS).get_data()))
    ff.stdin.close(); ff.wait()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", m4a, "-map", "0:v", "-map", "1:a",
                    "-c", "copy", "-shortest", "-movflags", "+faststart", OUT], check=True)
    music = os.path.join(os.path.dirname(OUT), "tangping-theme.m4a")
    os.replace(m4a, music)
    for f in (wav, silent):
        os.remove(f)
    os.rmdir(tmp)
    print("wrote", OUT, "and", music)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--still":
        for ts in sys.argv[2:]:
            frame(float(ts)).write_to_png(f"still_{ts}.png")
    elif len(sys.argv) > 1 and sys.argv[1] == "--audio":
        bgm.render(audio_events(), "music.wav"); print("wrote music.wav")
    else:
        main()
