#!/usr/bin/env python3
# Tangping motion piece — original music, synthesized from scratch
# Copyright 2026 The Tangping Project Authors
# SPDX-License-Identifier: MIT (code). The rendered music is CC BY 4.0, like the video.
"""Background music for the Tangping motion piece.

96 BPM lo-fi in D minor pentatonic (D F G A C, the 羽 mode): guzheng-style plucks over an FM
electric piano, a pad, sub bass and soft swung drums. Sound effects are placed on the video's own
event times (turn, cut, drop, each letter, each keystroke), so picture and sound stay locked.
Nothing is sampled: every sound is generated here.

    from bgm import render
    render(events, duration, "out.wav")
"""
import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 48000
BPM = 96
BEAT = 60 / BPM          # 0.625 s
BAR = 4 * BEAT           # 2.5 s
S16 = BEAT / 4
rng = np.random.default_rng(20261021)

# ---------------------------------------------------------------- pitch
_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def hz(name):
    i, acc = 1, 0
    while name[i] in "#b":
        acc += 1 if name[i] == "#" else -1
        i += 1
    midi = 12 * (int(name[i:]) + 1) + _PC[name[0]] + acc
    return 440.0 * 2 ** ((midi - 69) / 12)


# D minor pentatonic across the guzheng's range
PENTA = ["A3", "C4", "D4", "F4", "G4", "A4", "C5", "D5", "F5", "G5", "A5", "C6", "D6"]

CHORDS = {   # rootless voicings for keys/pad, plus a bass root
    "Dm9":    (["F3", "A3", "C4", "E4"], "D2"),
    "Bbmaj9": (["D4", "F4", "A4", "C5"], "Bb1"),
    "Gm9":    (["Bb3", "D4", "F4", "A4"], "G1"),
    "Am7":    (["A3", "C4", "E4", "G4"], "A1"),
    "A7sus":  (["D4", "E4", "G4", "A4"], "A1"),
}


# ---------------------------------------------------------------- dsp helpers
def tax(dur):
    return np.arange(max(1, int(dur * SR))) / SR


def _sos(kind, f):
    return signal.butter(2, f, btype=kind, fs=SR, output="sos")


def lowpass(x, f): return signal.sosfilt(_sos("lowpass", f), x, axis=-1)
def highpass(x, f): return signal.sosfilt(_sos("highpass", f), x, axis=-1)
def bandpass(x, lo, hi): return signal.sosfilt(_sos("bandpass", [lo, hi]), x, axis=-1)


def edges(x, a=0.002, r=0.01):
    na, nr = int(a * SR), int(r * SR)
    if na: x[:na] *= np.linspace(0, 1, na)
    if nr: x[-nr:] *= np.linspace(1, 0, nr)
    return x


def norm(x):
    return x / (np.max(np.abs(x)) + 1e-12)


def noise_sweep(dur, f0, f1, width_oct=0.7):
    """white noise through a band that glides from f0 to f1 (log), via STFT masking"""
    n = int(dur * SR)
    f, tt, Z = signal.stft(rng.standard_normal(n + 4096), fs=SR, nperseg=1024, noverlap=768)
    fc = f0 * (f1 / f0) ** np.clip(tt / dur, 0, 1)
    lf = np.log2(np.maximum(f, 1.0))[:, None]
    mask = np.exp(-0.5 * ((lf - np.log2(fc)[None, :]) / (width_oct / 2)) ** 2)
    _, y = signal.istft(Z * mask, fs=SR, nperseg=1024, noverlap=768)
    return norm(y[:n])


# ---------------------------------------------------------------- instruments
_PEAK1 = signal.iirpeak(280, 3.5, fs=SR)
_PEAK2 = signal.iirpeak(1150, 5, fs=SR)


def guzheng(note, dur=2.8, slide=0.0, bright=1.0, vib=True):
    """plucked silk-steel string: additive partials with inharmonicity, 按滑 slide into pitch,
    揉弦 vibrato after the attack, pick noise and a small wooden body"""
    f = hz(note)
    t = tax(dur)
    glide = 2 ** (slide * np.exp(-t / 0.075) / 12)
    depth = 0.0038 * np.clip((t - 0.32) / 0.45, 0, 1) if vib else 0.0
    inst = f * glide * (1 + depth * np.sin(2 * np.pi * 5.4 * t))
    phase = 2 * np.pi * np.cumsum(inst) / SR
    x = np.zeros_like(t)
    p = 0.13 if bright > 0.2 else 0.5
    for k in range(1, 18):
        ratio = k * np.sqrt(1 + 0.00009 * k * k)
        if f * ratio > 15000:
            break
        a = abs(np.sin(np.pi * k * p)) / k ** (1.35 - 0.3 * bright)
        if bright <= 0.2 and k > 1:
            a *= 0.08                                    # 泛音: almost a pure fundamental
        tau = 2.3 / (1 + 0.5 * (k - 1) ** 1.2) * (220 / max(f, 110)) ** 0.3
        x += a * np.exp(-t / tau) * np.sin(phase * ratio + rng.uniform(0, 6.283))
    nn = int(0.02 * SR)
    pick = bandpass(rng.standard_normal(nn), 1800, 7000) * np.exp(-np.arange(nn) / (0.0035 * SR))
    x[:nn] += 0.18 * bright * pick / (np.max(np.abs(pick)) + 1e-9) * np.max(np.abs(x[:nn]) + 1e-9)
    x = x + 0.3 * signal.lfilter(*_PEAK1, x) + 0.18 * signal.lfilter(*_PEAK2, x)
    return edges(norm(x), 0.0012, 0.06)


def epiano(note, dur, vel=0.8):
    """two-operator FM electric piano with a short tine"""
    f = hz(note)
    t = tax(dur + 0.5)
    index = (0.9 + 2.2 * vel) * np.exp(-t / 0.22) + 0.22
    x = np.sin(2 * np.pi * f * t + index * np.sin(2 * np.pi * f * t))
    x += 0.22 * vel * np.sin(2 * np.pi * f * 14.0 * t) * np.exp(-t / 0.028)
    env = np.exp(-t / (1.9 * (262 / f) ** 0.35)) * np.clip(1 - (t - dur) / 0.4, 0, 1)
    return edges(x * env * vel, 0.003, 0.01)


def pad(notes, dur, attack=0.9, release=1.2):
    t = tax(dur + release)
    x = np.zeros_like(t)
    for nm in notes:
        f = hz(nm)
        for det in (-0.0065, 0.0, 0.007):
            ph = rng.uniform(0, 6.283)
            for k in range(1, 9):
                if f * k > 7000:
                    break
                x += np.sin(2 * np.pi * f * (1 + det) * k * t + ph * k) / k
    env = np.minimum(1, t / attack) * np.clip(1 - (t - dur) / release, 0, 1)
    return norm(lowpass(x * env, 1300))


def bass(note, dur):
    f = hz(note)
    t = tax(dur + 0.06)
    x = np.sin(2 * np.pi * f * t) + 0.38 * np.sin(4 * np.pi * f * t) + 0.12 * np.sin(6 * np.pi * f * t)
    env = np.minimum(1, t / 0.006) * np.exp(-t / 1.4) * np.clip(1 - (t - dur) / 0.06, 0, 1)
    return np.tanh(1.7 * x * env) / np.tanh(1.7)


def kick():
    t = tax(0.55)
    f = 46 + 125 * np.exp(-t / 0.028)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.24)
    x += 0.25 * highpass(rng.standard_normal(len(t)), 2500) * np.exp(-t / 0.0014)
    return edges(np.tanh(2.0 * x), 0.0004, 0.03)


def snare():
    t = tax(0.4)
    nz = bandpass(rng.standard_normal(len(t)), 1100, 7500) * np.exp(-t / 0.1)
    tone = np.sin(2 * np.pi * 188 * t) * np.exp(-t / 0.045) + 0.45 * np.sin(2 * np.pi * 332 * t) * np.exp(-t / 0.03)
    return edges(np.tanh(1.4 * (0.9 * norm(nz) + 0.6 * tone)), 0.0004, 0.03)


def hat(open_=False):
    t = tax(0.4 if open_ else 0.07)
    x = highpass(rng.standard_normal(len(t)), 7500) * np.exp(-t / (0.11 if open_ else 0.016))
    return edges(norm(x), 0.0003, 0.01)


def tick():
    t = tax(0.03)
    x = norm(bandpass(rng.standard_normal(len(t)), 2200, 6500)) * np.exp(-t / 0.0028)
    x += 0.35 * np.sin(2 * np.pi * rng.uniform(2200, 2900) * t) * np.exp(-t / 0.006)
    return edges(x, 0.0003, 0.004)


def riser(dur):
    t = tax(dur)
    x = noise_sweep(dur, 260, 7000, 0.85) * (t / dur) ** 2.2
    tone = np.sin(2 * np.pi * np.cumsum(110 * 4 ** (t / dur)) / SR) * (t / dur) ** 2 * 0.22
    return x + tone


def slice_sfx():
    dur = 0.6
    t = tax(dur)
    x = noise_sweep(dur, 3200, 15000, 0.5) * np.minimum(1, t / 0.003) * np.exp(-t / 0.055)
    for f, d, a in ((2230, 0.55, 0.22), (3480, 0.4, 0.16), (5310, 0.28, 0.12), (7790, 0.16, 0.08)):
        x += a * np.sin(2 * np.pi * f * t) * np.exp(-t / d) * np.minimum(1, t / 0.002)
    return x


def whoosh_down(dur):
    t = tax(dur)
    return noise_sweep(dur, 2600, 220, 0.9) * np.sin(np.pi * t / dur) ** 2


def impact(strength=1.0):
    t = tax(1.8)
    f = 36 + 34 * np.exp(-t / 0.18)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.55)
    thump = norm(lowpass(rng.standard_normal(len(t)), 170)) * np.exp(-t / 0.06)
    return edges(np.tanh(1.8 * strength * (sub + 0.55 * thump)) / np.tanh(1.8), 0.0005, 0.05)


def crash():
    t = tax(2.6)
    x = norm(highpass(rng.standard_normal(len(t)), 4000)) * np.exp(-t / 0.7)
    return edges(lowpass(x, 11000), 0.0005, 0.05)


def vinyl(dur):
    n = int(dur * SR)
    hiss = highpass(rng.standard_normal(n), 3000) * 0.012
    pops = np.zeros(n)
    idx = rng.integers(0, n, int(dur * 9))
    pops[idx] = rng.uniform(0.05, 0.35, len(idx)) * rng.choice([-1, 1], len(idx))
    pops = bandpass(pops, 900, 9000)
    return hiss + pops


def reverb_ir(dur=2.6, tau_lo=0.42, tau_hi=0.15, predelay=0.016):
    t = tax(dur)
    ir = []
    for _ in range(2):
        nz = rng.standard_normal(len(t))
        x = lowpass(nz, 2600) * np.exp(-t / tau_lo) + 0.6 * highpass(nz, 2600) * np.exp(-t / tau_hi)
        x[: int(predelay * SR)] = 0
        ir.append(x)
    ir = np.array(ir)
    return ir / np.sqrt(np.sum(ir ** 2) / 2)


# ---------------------------------------------------------------- mixer
class Mix:
    BUSES = ("pluck", "keys", "pad", "bass", "drums", "sfx", "air")

    def __init__(self, dur):
        self.dur = dur
        self.n = int((dur + 4.0) * SR)
        self.bus = {b: np.zeros((2, self.n)) for b in self.BUSES}
        self.send = np.zeros((2, self.n))

    def add(self, bus, x, t, gain=1.0, pan=0.0, send=0.0):
        i = int(round(t * SR))
        if i < 0:
            x, i = x[-i:], 0
        x = x[: self.n - i]
        if len(x) == 0:
            return
        pan = np.clip(pan, -1, 1)
        l = np.cos((pan + 1) * np.pi / 4) * gain * 1.4142
        r = np.sin((pan + 1) * np.pi / 4) * gain * 1.4142
        if np.ndim(pan):
            l, r = l[: len(x)], r[: len(x)]
        self.bus[bus][0, i:i + len(x)] += x * l
        self.bus[bus][1, i:i + len(x)] += x * r
        if send:
            self.send[0, i:i + len(x)] += x * l * send
            self.send[1, i:i + len(x)] += x * r * send


def duck(n, times, depth=0.45, release=0.15):
    g = np.ones(n)
    for tk in times:
        i0 = int(tk * SR)
        i1 = min(n, i0 + int(release * 7 * SR))
        if i0 >= n:
            continue
        tt = np.arange(i1 - i0) / SR
        g[i0:i1] = np.minimum(g[i0:i1], 1 - depth * np.clip(tt / 0.004, 0, 1) * np.exp(-tt / release))
    return g


# ---------------------------------------------------------------- composition
def compose(ev):
    """ev: event times from the video timeline (see make_video.py: audio_events)"""
    dur = ev["duration"]
    m = Mix(dur)
    bars = int(round(dur / BAR))
    prog = ["Dm9", "Bbmaj9", "Gm9", "Am7", "Dm9", "Bbmaj9", "Gm9", "Am7", "Bbmaj9", "Dm9", "Dm9"][:bars]
    groove = range(2, 9)                  # bars with drums: the drop (5.0 s) to the end card (22.5 s)
    kicks = []

    # pad: whole piece, a breath before the drop, swelling chord at the end
    for b, ch in enumerate(prog):
        notes, _ = CHORDS[ch]
        t0 = b * BAR
        if b == 1:
            m.add("pad", pad(notes, BAR * 0.72, attack=0.5, release=0.35), t0, 0.9, 0, 0.35)
        elif b >= 9:
            if b == 9:
                m.add("pad", pad(notes + ["D3", "A4"], BAR * 1.6, attack=0.25, release=1.6), t0, 1.0, 0, 0.45)
        else:
            m.add("pad", pad(notes, BAR, attack=1.1 if b == 0 else 0.6), t0, 0.75 if b in groove else 1.35, 0, 0.35)

    # electric piano: from the drop onward, chord on 1, re-hit on the "and" of 2
    for b in range(2, 9):
        notes, _ = CHORDS[prog[b]]
        if b == 8:     # last groove bar: Bbmaj9 then A7sus for the pull back to D
            for half, ch in ((0, "Bbmaj9"), (2, "A7sus")):
                for j, nm in enumerate(CHORDS[ch][0]):
                    m.add("keys", epiano(nm, BEAT * 2, 0.75), b * BAR + half * BEAT + j * 0.012, 1.0, -0.25 + 0.17 * j, 0.22)
            continue
        for j, nm in enumerate(notes):
            m.add("keys", epiano(nm, BEAT * 1.6, 0.8), b * BAR + j * 0.012, 1.0, -0.25 + 0.17 * j, 0.22)
            m.add("keys", epiano(nm, BEAT * 1.2, 0.5), b * BAR + 1.5 * BEAT + j * 0.01, 0.8, -0.25 + 0.17 * j, 0.22)
    for j, nm in enumerate(CHORDS["Dm9"][0] + ["D4"]):
        m.add("keys", epiano(nm, BAR * 1.5, 0.9), ev["end"] + j * 0.018, 1.0, -0.3 + 0.15 * j, 0.3)

    # bass + drums
    pattern_k = [0, 7, 10]
    for b in groove:
        t0 = b * BAR
        root = CHORDS[prog[b]][1] if b != 8 else "Bb1"
        fifth = {"D2": "A2", "Bb1": "F2", "G1": "D2", "A1": "E2"}[root]
        for st, nm, d in ((0, root, 5), (7, root, 2), (10, fifth, 3), (14, root, 2)):
            if b == 8 and st >= 8:
                nm = {0: "A1", 7: "A1", 10: "E2", 14: "A1"}[st]
            m.add("bass", bass(nm, d * S16), t0 + st * S16, 1.0)
        for st in range(16):
            sw = 0.022 if st % 2 else 0.0
            t = t0 + st * S16 + sw
            if st in pattern_k:
                m.add("drums", kick(), t, 0.8); kicks.append(t)
            if st in (4, 12):
                m.add("drums", snare(), t, 0.55, 0.05, 0.12)
            if b == 8 and st in (13, 14, 15):
                m.add("drums", snare(), t, 0.22 + 0.1 * (st - 13), 0.05, 0.12)
            if st == 15 and b in (3, 5):
                m.add("drums", snare(), t, 0.16, 0.05, 0.1)
            v = (1.0, 0.35, 0.65, 0.4)[st % 4] * (0.75 if b in (4, 5) else 1.0)
            if st == 14 and b % 2 == 1:
                m.add("drums", hat(True), t, 0.12, 0.25, 0.05)
            else:
                m.add("drums", hat(), t, 0.16 * v, 0.25, 0.03)
    m.add("bass", bass("D2", BAR * 1.4), ev["end"], 0.9)

    # ---- guzheng: intro motif, flourishes, letter run, answers, ending
    def gz(t, note, vel, pan=0.0, slide=0.0, dur=2.8, bright=1.0, send=0.36):
        m.add("pluck", guzheng(note, dur, slide, bright), t, vel, pan, send)

    gz(BEAT * 1.0, "A4", 0.7, -0.2)
    gz(BEAT * 1.5, "C5", 0.62, -0.1)
    gz(BEAT * 2.0, "D5", 0.95, 0.0, slide=-2)         # 按滑 up from C
    gz(BEAT * 3.5, "F5", 0.6, 0.15)
    gz(ev["turn"][0], "A5", 0.75, 0.1, slide=-2)
    # title: quick run into A5
    for i, nm in enumerate(["D5", "F5", "G5"]):
        gz(ev["title"] - 0.12 + i * 0.04, nm, 0.45, -0.2 + 0.1 * i)
    gz(ev["title"], "A5", 0.85, 0.1, dur=3.2)
    gz(ev["title"] + 2.5 * BEAT, "G5", 0.42, 0.2)
    gz(ev["title"] + 3.0 * BEAT, "A5", 0.45, 0.1)
    gz(ev["title"] + 3.5 * BEAT, "C6", 0.5, 0.0, slide=-2)

    # one pluck per letter as it appears, panned to its column: up through row 1, down through row 2
    down = ["D6", "C6", "A5", "C6", "A5", "G5", "F5", "G5", "F5", "D5", "C5", "D5", "A4"]
    for (t_app, t_cut, pan, i) in ev["letters"]:
        note = PENTA[i] if i < 13 else down[i - 13]
        accent = 0.78 if (i % 13) % 4 == 0 else 0.55
        gz(t_app, note, accent, pan * 0.75, dur=2.2, send=0.3)
        m.add("sfx", tick(), t_cut, 0.11, pan * 0.75, 0.05)

    b6 = ev["alphabet_hold"]
    for beat, nm, v, sl in ((0, "D6", 0.7, -2), (1.5, "C6", 0.5, 0), (2.0, "A5", 0.55, 0), (2.5, "G5", 0.5, 0), (3.0, "A5", 0.62, -2)):
        gz(b6 + beat * BEAT, nm, v, 0.1, slide=sl)
    b8 = ev["answer"]
    for beat, nm, v, sl in ((0, "F5", 0.4, 0), (0.5, "G5", 0.38, 0), (1.0, "A5", 0.48, 0), (2.0, "G5", 0.4, 0), (2.5, "D5", 0.42, 0), (3.0, "E5", 0.5, -2)):
        gz(b8 + beat * BEAT, nm, v, -0.15, slide=sl)

    # 刮奏 glissando into the end card, then a final 泛音 harmonic as 躺 lies down
    gl = ["D4", "F4", "G4", "A4", "C5", "D5", "F5", "G5", "A5", "C6", "D6"]
    for i, nm in enumerate(gl):
        gz(ev["end"] - (len(gl) - 1 - i) * 0.032, nm, 0.32 + 0.05 * i, -0.6 + 0.12 * i, dur=3.0, send=0.45)
    m.add("pluck", guzheng("D6", 3.0, 0.0, 0.0, vib=False), ev["lie_down"], 0.55, 0.0, 0.6)

    # ---- effects on the picture
    t0, t1 = ev["turn"][0], ev["slice"]
    m.add("sfx", riser(t1 - t0), t0, 0.32, np.linspace(-0.2, 0.2, int((t1 - t0) * SR)), 0.3)
    s = slice_sfx()
    m.add("sfx", s, ev["slice"], 0.5, np.linspace(-0.7, 0.7, len(s)), 0.35)
    f0, f1 = ev["fall"]
    m.add("sfx", whoosh_down(f1 - f0), f0, 0.22, 0.0, 0.3)
    m.add("sfx", impact(1.0), ev["drop"], 0.8, 0.0, 0.25); kicks.append(ev["drop"])
    m.add("drums", crash(), ev["drop"], 0.12, 0.3, 0.2)
    m.add("sfx", riser(0.5) * 0.5, ev["parade_out"] - 0.5 + 0.0, 0.18, 0.0, 0.2)
    m.add("sfx", riser(0.625), ev["end"] - 0.625, 0.2, 0.0, 0.25)
    m.add("sfx", impact(0.7), ev["end"], 0.5, 0.0, 0.3); kicks.append(ev["end"])
    m.add("drums", kick(), ev["end"], 0.9)
    m.add("drums", crash(), ev["end"], 0.16, -0.25, 0.3)
    for t, pan in ev["typing"]:
        m.add("sfx", tick(), t + rng.uniform(-0.004, 0.004), rng.uniform(0.18, 0.28), pan, 0.04)
    m.add("air", vinyl(dur + 3), 0.0, 1.0)

    # ---- mix down
    n = m.n
    g = duck(n, kicks)
    m.bus["keys"][:] = lowpass(m.bus["keys"], 5200) * g
    m.bus["pad"] *= duck(n, kicks, 0.35)
    m.bus["bass"] = lowpass(m.bus["bass"], 900) * duck(n, kicks, 0.55, 0.12)
    m.bus["drums"] = np.tanh(1.2 * lowpass(m.bus["drums"], 11500)) / 1.2
    levels = {"pluck": 0.52, "keys": 0.27, "pad": 0.12, "bass": 0.23, "drums": 0.46, "sfx": 0.55, "air": 0.25}
    dry = sum(m.bus[k] * v for k, v in levels.items())
    ir = reverb_ir()
    wet = np.array([signal.fftconvolve(m.send.mean(0), ir[c])[:n] for c in range(2)])
    mix = dry + 0.32 * wet
    return master(mix[:, : int(dur * SR)], dur)


def master(x, dur):
    x = highpass(x, 30)
    a = np.exp(-1 / (0.04 * SR))
    env = np.sqrt(signal.lfilter([1 - a], [1, -a], 0.5 * (x[0] ** 2 + x[1] ** 2)) + 1e-12)
    x = x / (np.percentile(env, 99.5) + 1e-9) * 0.35       # pre-gain so the compressor sees a known level
    env = env / (np.percentile(env, 99.5) + 1e-9) * 0.35
    thr, ratio = 0.18, 2.2
    gain = np.minimum(1.0, (env / thr) ** (1 / ratio - 1))
    b = np.exp(-1 / (0.08 * SR))
    gain = signal.lfilter([1 - b], [1, -b], gain)
    x = x * gain
    t = np.arange(x.shape[1]) / SR
    x *= np.clip(t / 0.25, 0, 1) * np.clip((dur - t) / 0.8, 0, 1)
    x = np.tanh(x / 0.9) * 0.9
    return x / (np.max(np.abs(x)) + 1e-9) * 0.89


def render(ev, path):
    x = compose(ev)
    wavfile.write(path, SR, x.T.astype(np.float32))
    return x
