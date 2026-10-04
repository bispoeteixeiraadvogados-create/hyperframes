"""Design de som e trilha sintetizados (deterministico), sincronizados a scripts/timeline.json.

Gera assets/audio/music.wav (trilha eletronica cinematografica) e assets/audio/sfx.wav (whooshes,
clicks, PUMs, ticks, riser, alerta, congelamento, sting), um mix de conferencia
(assets/audio/mix-preview.wav, nao usado na composicao). Os stems sao calibrados para que a soma
feita pelo mixer do HyperFrames (data-volume = 1) fique perto de -14 LUFS com pico < -1 dBFS.

Uso:  python scripts/sound_design.py
"""

import json
import os
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(__file__))
import dsp  # noqa: E402
from dsp import SR  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
AUD = os.path.join(HERE, "..", "assets", "audio")
TL = json.load(open(os.path.join(HERE, "timeline.json")))
DUR = TL["duration"]
N = int(round(DUR * SR))

BEATS = [b["t"] for b in TL["beats"]]
WALL0, WALL1 = TL["wall"]
FREEZE0, FREEZE1 = TL["freeze"]
BURST0, BURST1 = TL["burst"]
RESOLVE = TL["resolveStart"]
STING = TL["sting"]


def new():
    return np.zeros((N, 2))


def norm(x, peak=1.0):
    return x * (peak / (np.max(np.abs(x)) + 1e-12))


def hz(note):
    names = {"C": -9, "C#": -8, "Db": -8, "D": -7, "D#": -6, "Eb": -6, "E": -5, "F": -4, "F#": -3,
             "Gb": -3, "G": -2, "G#": -1, "Ab": -1, "A": 0, "A#": 1, "Bb": 1, "B": 2}
    name, octave = note[:-1], int(note[-1])
    return 440.0 * 2 ** ((names[name] + (octave - 4) * 12) / 12)


# =============================================================== elementos de efeito
def whoosh(dur, seed, f0=300.0, f1=3000.0, q=0.9, peak_at=0.6, pan0=-0.5, pan1=0.5,
           color="pink", attack_pow=2.0, release_pow=1.5, start_level=0.0):
    n = int(dur * SR)
    x = dsp.noise(dur, seed, color=color)
    tt = np.linspace(0, 1, n)
    fc = f0 * (f1 / f0) ** tt
    y = dsp.sweep_filter(x, "bandpass", fc, q=q)
    body = dsp.sweep_filter(x, "lowpass", fc * 0.55, q=0.7) * 0.45
    y = y + body
    rise = start_level + (1 - start_level) * (tt / peak_at) ** attack_pow
    fall = ((1 - tt) / (1 - peak_at)) ** release_pow
    e = np.where(tt < peak_at, rise, fall)
    y = y * e
    st = dsp.pan(norm(y), np.linspace(pan0, pan1, n))
    return st


def impact(seed, strength=1.0, sub_f0=110.0, sub_f1=42.0, sub_tau=0.32, tail=0.9, bright=0.35):
    dur = 0.3 + sub_tau * 5 + tail
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = sub_f1 + (sub_f0 - sub_f1) * np.exp(-t / 0.055)
    sub = np.sin(dsp.phase_from_freq(f)) * np.exp(-t / sub_tau)
    fk = 52 + 150 * np.exp(-t / 0.022)
    kick = np.sin(dsp.phase_from_freq(fk)) * np.exp(-t / 0.085)
    tr = dsp.filt(dsp.noise(dur, seed) * np.exp(-t / 0.0035), "highpass", 1800)
    mid = dsp.filt(dsp.noise(dur, seed + 1), "lowpass", 520) * np.exp(-t / 0.055)
    y = 1.0 * sub + 0.75 * kick + bright * tr + 0.55 * mid
    y = dsp.soft_clip(y * (1.2 + 0.6 * strength), 1.6)
    st = dsp.stereo(y)
    ir = dsp.make_ir(decay=max(0.4, tail * 2.2), predelay=0.012, seed=seed + 3, lp=1100, hp=35)
    wet = dsp.reverb(y, ir, wet=0.42, dry=0.0)[:n]
    return norm(st + wet * 0.8 * strength)


def click(seed, f=2600.0, tau=0.012):
    dur = 0.09
    n = int(dur * SR)
    t = np.arange(n) / SR
    imp = dsp.filt(dsp.noise(dur, seed) * np.exp(-t / 0.0012), "highpass", 2200)
    ping = np.sin(2 * np.pi * f * t) * np.exp(-t / tau) * 0.55
    ping2 = np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t / (tau * 0.45)) * 0.22
    body = np.sin(2 * np.pi * 180 * t) * np.exp(-t / 0.01) * 0.35
    y = imp * 0.9 + ping + ping2 + body
    return norm(dsp.stereo(y))


def tick(seed, f=2000.0, dur=0.035, pan=0.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    imp = dsp.filt(dsp.noise(dur, seed) * np.exp(-t / 0.0008), "bandpass", f * 1.6, q=1.2)
    tone = np.sin(2 * np.pi * f * t) * np.exp(-t / 0.006)
    return dsp.pan(norm(imp * 0.7 + tone * 0.6), pan)


def tick_train(buf, t0, t1, p0, p1, seed, f0=1600.0, f1=3200.0, level=0.3, jitter_pan=0.35):
    r = dsp.rng(seed)
    t = t0
    k = 0
    while t < t1:
        frac = (t - t0) / max(t1 - t0, 1e-6)
        f = f0 * (f1 / f0) ** frac
        g = level * (0.75 + 0.25 * r.random())
        dsp.place(buf, tick(seed * 100 + k, f=f, pan=r.uniform(-jitter_pan, jitter_pan)), t, gain=g)
        t += p0 + (p1 - p0) * frac
        k += 1


def riser(dur, seed, f_start=220.0, f_end=2400.0, shepard=0.3, curve=2.2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    tt = t / dur
    x = dsp.noise(dur, seed, color="pink")
    fc = f_start * (f_end / f_start) ** (tt ** 1.4)
    nz = dsp.sweep_filter(x, "bandpass", fc, q=1.4)
    sh = np.zeros(n)
    for k in range(6):
        pos = k + tt * 1.0
        f = 55.0 * 2 ** pos
        w = np.exp(-0.5 * ((pos - 3.0) / 1.15) ** 2)
        sh += np.sin(dsp.phase_from_freq(f) + k) * w
    y = norm(nz) * 0.75 + norm(sh) * shepard
    y = y * tt ** curve
    st = dsp.pan(y, 0.3 * np.sin(2 * np.pi * 0.7 * t))
    return norm(st)


def alert(seed, dur=0.44, f=233.08, pulses=2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    per = dur / pulses
    fdip = f * (1 - 0.06 * ((t % per) / per))
    saw = (dsp.saw_blep(fdip) + 0.8 * dsp.saw_blep(fdip * 1.006) + 0.35 * dsp.saw_blep(fdip * 2.0))
    y = dsp.filt(saw, "lowpass", 1500, q=2.2)
    ph = (t % per) / per
    gate = np.clip(np.minimum(ph / 0.04, (0.7 - ph) / 0.06), 0, 1)
    y = dsp.soft_clip(y * gate * np.exp(-t / 0.9) * 1.6, 2.2)
    ir = dsp.make_ir(decay=0.7, seed=seed, lp=4000, hp=150)
    return norm(dsp.reverb(y, ir, wet=0.25)[: n + int(0.5 * SR)])


def crack(seed):
    dur = 0.7
    n = int(dur * SR)
    t = np.arange(n) / SR
    nz = dsp.filt(dsp.noise(dur, seed), "highpass", 2400) * np.exp(-t / 0.012)
    modes = [(1730, 0.09), (2890, 0.07), (4310, 0.05), (6120, 0.04), (7930, 0.03), (3370, 0.06)]
    m = sum(np.sin(2 * np.pi * f * t + i) * np.exp(-t / tau) for i, (f, tau) in enumerate(modes))
    debris = np.zeros(n)
    r = dsp.rng(seed + 1)
    for _ in range(14):
        k = int(r.uniform(0.02, 0.32) * SR)
        L = int(0.006 * SR)
        if k + L < n:
            debris[k:k + L] += r.standard_normal(L) * np.exp(-np.arange(L) / (0.0015 * SR)) * r.uniform(0.2, 0.6)
    debris = dsp.filt(debris, "highpass", 3000)
    y = nz * 0.9 + norm(m) * 0.35 + debris * 0.5
    ir = dsp.make_ir(decay=0.9, seed=seed + 2, lp=9000, hp=500)
    return norm(dsp.reverb(y, ir, wet=0.3)[:n])


def paper_swish(dur, seed):
    n = int(dur * SR)
    t = np.arange(n) / SR
    tt = t / dur
    x = dsp.noise(dur, seed)
    y = dsp.sweep_filter(x, "bandpass", 1200 + 3800 * np.sin(np.pi * tt), q=0.8)
    flutter = 0.6 + 0.4 * np.sign(np.sin(2 * np.pi * (28 + 10 * tt) * t))
    flutter = dsp.filt(flutter, "lowpass", 300)
    e = np.sin(np.pi * tt) ** 1.5
    return dsp.pan(norm(y * flutter * e), np.linspace(0.7, -0.6, n))


def reverse_whoosh(dur, seed):
    w = whoosh(dur * 0.6, seed, f0=500, f1=4500, q=0.8, peak_at=0.25, pan0=0.0, pan1=0.0)
    ir = dsp.make_ir(decay=dur * 0.9, seed=seed + 5, lp=8000, hp=300)
    tail = dsp.reverb(w, ir, wet=0.9)
    rev = tail[::-1]
    n = int(dur * SR)
    rev = rev[-n:] if len(rev) >= n else np.vstack([np.zeros((n - len(rev), 2)), rev])
    e = np.linspace(0, 1, n) ** 1.8
    return norm(rev * e[:, None])


def tock(seed, f=820.0):
    dur = 0.25
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = (np.sin(2 * np.pi * f * t) * np.exp(-t / 0.035) + 0.5 * np.sin(2 * np.pi * f * 2.02 * t) * np.exp(-t / 0.02)
         + 0.4 * dsp.filt(dsp.noise(dur, seed) * np.exp(-t / 0.002), "bandpass", 3000, q=0.8))
    y = dsp.filt(y, "lowpass", 3500)
    ir = dsp.make_ir(decay=0.8, seed=seed, lp=5000, hp=200)
    return norm(dsp.reverb(y, ir, wet=0.35)[:n])


def shimmer(dur, seed):
    n = int(dur * SR)
    t = np.arange(n) / SR
    tt = t / dur
    x = dsp.noise(dur, seed)
    y = dsp.sweep_filter(x, "bandpass", 4000 + 5000 * tt, q=2.5)
    bells = sum(np.sin(2 * np.pi * f * t) * np.exp(-t / 0.5) for f in (2093.0, 2637.0, 3136.0))
    e = np.sin(np.pi * tt) ** 2
    return dsp.pan(norm(y * e) * 0.6 + norm(bells * e) * 0.4, np.linspace(-0.4, 0.4, n))


def deep_resolve(seed):
    dur = 2.4
    n = int(dur * SR)
    t = np.arange(n) / SR
    sub = np.sin(2 * np.pi * 55 * t) * np.exp(-t / 0.9)
    k = np.sin(dsp.phase_from_freq(50 + 70 * np.exp(-t / 0.03))) * np.exp(-t / 0.12)
    air = dsp.filt(dsp.noise(dur, seed), "highpass", 5500) * np.exp(-t / 0.6) * 0.12
    y = sub + 0.6 * k
    ir = dsp.make_ir(decay=2.6, seed=seed + 1, lp=2500, hp=40)
    st = dsp.reverb(y, ir, wet=0.35)[:n] + dsp.stereo(air)
    return norm(st)


# =============================================================== trilha
def intensity(t):
    pts = [(0.0, 0.0), (0.56, 0.12), (1.68, 0.28), (2.69, 0.42), (3.43, 0.56), (4.41, 0.76),
           (WALL0, 0.86), (FREEZE0, 1.0)]
    ts, vs = zip(*pts)
    return float(np.interp(t, ts, vs))


def note_times():
    bounds = BEATS + [WALL0, FREEZE0]

    def period(t):
        if t < BEATS[-1]:
            return 0.27 - (t - BEATS[0]) / (BEATS[-1] - BEATS[0]) * 0.03
        if t < WALL0:
            return 0.205 - (t - BEATS[-1]) / (WALL0 - BEATS[-1]) * 0.045
        u = (t - WALL0) / (FREEZE0 - WALL0)
        return 0.15 - (u ** 1.25) * 0.088

    out = []
    for a, b in zip(bounds[:-1], bounds[1:]):
        if b - a > 1.4:
            t = a
            while t < b - 0.03:
                out.append(t)
                t += period(t)
        else:
            p = period((a + b) / 2)
            k = max(1, round((b - a) / p))
            p = (b - a) / k
            out += [a + i * p for i in range(k)]
    return out


def pluck(freq, dur, cut_peak, cut_base, seed, level=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = np.full(n, freq)
    y = dsp.saw_blep(f) + 0.7 * dsp.saw_blep(f * 1.004, phase0=0.3) + 0.5 * np.sin(dsp.phase_from_freq(f * 0.5))
    fc = cut_base + (cut_peak - cut_base) * np.exp(-t / 0.07)
    y = dsp.sweep_filter(y, "lowpass", fc, q=1.1, block=32)
    a = np.minimum(1, t / 0.003)
    e = a * np.exp(-t / max(0.05, dur * 0.42))
    e[-int(0.004 * SR):] *= np.linspace(1, 0, int(0.004 * SR))
    return y * e * level


def pad_voice(freqs, t0, t1, cutoff_fn, level_fn, seed, detune=0.006):
    n0, n1 = int(t0 * SR), int(t1 * SR)
    n = n1 - n0
    t = np.arange(n) / SR + t0
    L = np.zeros(n)
    R = np.zeros(n)
    for i, f0 in enumerate(freqs):
        for j, d in enumerate((-detune, 0.0, detune)):
            f = np.full(n, f0 * (1 + d))
            v = dsp.saw_blep(f, phase0=(i * 0.37 + j * 0.21) % 1)
            p = (j - 1) * 0.6
            L += v * np.cos((p + 1) * np.pi / 4)
            R += v * np.sin((p + 1) * np.pi / 4)
    fc = np.array([cutoff_fn(x) for x in t[::64]])
    fc = np.repeat(fc, 64)[:n]
    L = dsp.sweep_filter(L, "lowpass", fc, q=0.8)
    R = dsp.sweep_filter(R, "lowpass", fc, q=0.8)
    lv = np.array([level_fn(x) for x in t[::64]])
    lv = np.repeat(lv, 64)[:n]
    out = np.zeros((N, 2))
    out[n0:n1, 0] = L * lv
    out[n0:n1, 1] = R * lv
    return out


def fm_bell(freq, dur, seed, ratio=3.5, index=2.2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    idx = index * np.exp(-t / 0.35)
    y = np.sin(2 * np.pi * freq * t + idx * np.sin(2 * np.pi * freq * ratio * t))
    y += 0.25 * np.sin(2 * np.pi * freq * 2.0 * t) * np.exp(-t / 0.4)
    e = np.minimum(1, t / 0.004) * np.exp(-t / 1.1)
    return y * e


def build_music():
    m = new()
    pattern_a = ["D2", "D2", "D3", "D2", "D2", "F2", "D3", "D2"]
    pattern_b = ["D2", "D3", "D2", "Eb3", "D2", "D3", "D2", "F3"]
    pattern_c = ["D2", "D3", "D2", "D3", "Eb2", "D3", "F2", "D3"]
    times = note_times()
    for k, t in enumerate(times):
        I = intensity(t)
        pat = pattern_a if t < BEATS[-1] else pattern_b if t < WALL0 else pattern_c
        f = hz(pat[k % 8])
        nxt = times[k + 1] if k + 1 < len(times) else FREEZE0
        dur = min(0.32, max(0.06, (nxt - t) * 1.6))
        if t + dur > FREEZE0:
            dur = FREEZE0 - t
        if dur <= 0.01:
            continue
        x = pluck(f, dur, cut_peak=420 + 3600 * I, cut_base=160 + 500 * I, seed=k, level=0.25 + 0.75 * I)
        dsp.place(m, dsp.pan(x, 0.12 * (1 if k % 2 else -1)), t, gain=0.55)
        if t >= BEATS[-1]:
            # percussao: tom grave nos tempos pares, chimbal em todos
            if k % 2 == 0 or t > WALL0 + 2.0:
                n = int(0.22 * SR)
                tt = np.arange(n) / SR
                tom = np.sin(dsp.phase_from_freq(58 + 55 * np.exp(-tt / 0.03))) * np.exp(-tt / 0.11)
                tom += 0.4 * dsp.filt(dsp.noise(0.22, 900 + k) * np.exp(-tt / 0.02), "lowpass", 900)
                dsp.place(m, dsp.stereo(tom), t, gain=0.32 * (0.5 + 0.5 * I))
            n = int(0.05 * SR)
            tt = np.arange(n) / SR
            hat = dsp.filt(dsp.noise(0.05, 500 + k) * np.exp(-tt / 0.012), "highpass", 7000)
            dsp.place(m, dsp.pan(hat, 0.45 * (1 if k % 2 else -1)), t, gain=0.12 * I)

    # pad de tensao (Dm aberto), abre o filtro com a intensidade e corta seco no congelamento
    m += pad_voice([hz("D2"), hz("A2"), hz("D3"), hz("F3")], 0.0, FREEZE0,
                   cutoff_fn=lambda t: 260 + 1700 * intensity(t),
                   level_fn=lambda t: min(1, t / 0.35) * (0.05 + 0.10 * intensity(t)), seed=1)
    # cluster dissonante na pressao e na parede
    m += pad_voice([hz("Eb3"), hz("A3")], BEATS[-1], FREEZE0,
                   cutoff_fn=lambda t: 500 + 1500 * intensity(t),
                   level_fn=lambda t: min(1, (t - BEATS[-1]) / 0.5) * 0.045, seed=2, detune=0.009)
    # riser shepard da parede
    r = riser(FREEZE0 - (WALL0 + 0.3), 77, f_start=300, f_end=5200, shepard=0.45, curve=1.8)
    dsp.place(m, r, WALL0 + 0.3, gain=0.34)

    # corte seco no congelamento (rampa de 3 ms para nao estalar)
    i0 = int(FREEZE0 * SR)
    ramp = int(0.003 * SR)
    m[i0:i0 + ramp] *= np.linspace(1, 0, ramp)[:, None]
    m[i0 + ramp:int(RESOLVE * SR)] = 0.0

    # mensagem: pad escuro e calmo sob a frase 3
    m += pad_voice([hz("D2"), hz("A2"), hz("F3")], RESOLVE, STING + 0.3,
                   cutoff_fn=lambda t: 520,
                   level_fn=lambda t: min(1, (t - RESOLVE) / 0.45) * min(1, (STING + 0.3 - t) / 0.3) * 0.07,
                   seed=3)
    # sting de marca: Fmaj9 quente, sino FM arpejado, sub
    sting = new()
    sting += pad_voice([hz("F2"), hz("C3"), hz("A3"), hz("E4"), hz("G4")], STING, DUR,
                       cutoff_fn=lambda t: 900 + 700 * np.exp(-(t - STING) / 0.8),
                       level_fn=lambda t: min(1, (t - STING) / 0.07) * np.exp(-(t - STING) / 2.4) * 0.11,
                       seed=4)
    for i, nm in enumerate(["F4", "A4", "C5", "E5", "G5"]):
        b = fm_bell(hz(nm), 2.2, seed=40 + i)
        dsp.place(sting, dsp.pan(b, -0.5 + 0.25 * i), STING + i * 0.075, gain=0.16)
    n = int(2.4 * SR)
    tt = np.arange(n) / SR
    sub = np.sin(2 * np.pi * hz("F1") * tt) * np.minimum(1, tt / 0.05) * np.exp(-tt / 1.2)
    dsp.place(sting, dsp.stereo(sub), STING, gain=0.5)
    ir = dsp.make_ir(decay=2.8, seed=55, lp=7000, hp=90)
    wet = dsp.reverb(sting, ir, wet=0.4)[:N]
    m += wet
    # pequena reverb de sala no resto da trilha
    ir2 = dsp.make_ir(decay=1.1, seed=56, lp=6000, hp=150)
    pre = m.copy()
    pre[int(STING * SR):] = 0
    m = m + (dsp.reverb(pre, ir2, wet=0.18, dry=0.0)[:N])
    m[i0 + ramp:int(RESOLVE * SR)] = 0.0
    # final: fade nos ultimos 0,45 s
    f0 = int((DUR - 0.45) * SR)
    m[f0:] *= np.linspace(1, 0, N - f0)[:, None] ** 1.5
    return m


# =============================================================== efeitos
def build_sfx():
    s = new()
    # abertura: rush ja em movimento + snap de foco
    dsp.place(s, whoosh(0.56, 101, f0=220, f1=2600, q=0.7, peak_at=0.5, pan0=-0.7, pan1=0.6,
                        start_level=0.55, attack_pow=1.0, release_pow=3.0), 0.0, gain=0.85)
    rumble = dsp.filt(dsp.noise(0.7, 102, color="brown"), "lowpass", 140)
    rumble *= np.concatenate([np.full(int(0.45 * SR), 1.0), np.linspace(1, 0, int(0.7 * SR) - int(0.45 * SR))])
    dsp.place(s, dsp.stereo(norm(rumble)), 0.0, gain=0.5)
    n = int(0.05 * SR)
    tt = np.arange(n) / SR
    zip_ = np.sin(dsp.phase_from_freq(2200 * (2.6 ** (tt / 0.05)))) * np.sin(np.pi * tt / 0.05)
    dsp.place(s, dsp.stereo(zip_), 0.47, gain=0.12)

    # R$ 10.000: click seco
    dsp.place(s, click(201, f=2500), BEATS[0], gain=0.55)
    # "cresce": tick do indicador
    dsp.place(s, tick(202, f=2400), TL["cresce"], gain=0.3)

    lead = TL["rollLead"]
    strengths = {"pum1": 0.55, "pum2": 0.72, "pum3": 0.88, "pum4": 1.0}
    for i, b in enumerate(TL["beats"][1:], start=1):
        t = b["t"]
        kind = b["kind"]
        st = strengths[kind]
        # contador rolando antes do golpe
        r0 = t - (0.11 if kind == "pum4" else lead)
        tick_train(s, r0, t - 0.012, 0.03, 0.018, seed=300 + i, f0=1500 + 300 * i, f1=3300 + 300 * i,
                   level=0.17 + 0.05 * i)
        # PUM
        imp = impact(400 + i, strength=st, sub_f0=100 + 12 * i, sub_f1=46 - 2 * i,
                     sub_tau=0.24 + 0.08 * i, tail=0.5 + 0.25 * i, bright=0.3 + 0.08 * i)
        dsp.place(s, imp, t - 0.004, gain=0.42 + 0.30 * st)
        # whoosh de reacao da camera
        dsp.place(s, whoosh(0.34 + 0.06 * i, 500 + i, f0=1800, f1=300, q=0.8, peak_at=0.12,
                            pan0=0.3 * (-1) ** i, pan1=-0.3 * (-1) ** i), t + 0.01, gain=0.13 + 0.04 * i)
        if kind in ("pum2", "pum3"):
            dsp.place(s, click(600 + i, f=3100), t, gain=0.18)
        if kind == "pum2":
            n = int(0.09 * SR)
            tt = np.arange(n) / SR
            flash = dsp.filt(dsp.noise(0.09, 610) * np.exp(-tt / 0.025), "highpass", 4500)
            dsp.place(s, dsp.stereo(norm(flash)), t, gain=0.16)
        if kind == "pum3":
            dsp.place(s, crack(620), t + 0.005, gain=0.2)
            r = riser(TL["commaPause"][0] - t, 621, f_start=300, f_end=1800, shepard=0.35, curve=2.4)
            dsp.place(s, r, t + 0.02, gain=0.09)
        if kind == "pum4":
            # inspiracao reversa no respiro da virgula
            dsp.place(s, reverse_whoosh(0.16, 630), t - 0.16, gain=0.28)
            dsp.place(s, whoosh(0.32, 631, f0=3200, f1=250, q=0.6, peak_at=0.08, pan0=-0.6, pan1=0.6),
                      t + 0.005, gain=0.36)
            dsp.place(s, alert(632, dur=0.44, f=233.08), t + 0.05, gain=0.17)

    # pressao: ticks de rotulos, baques vermelhos, documento e contador acelerando
    for k, lt in enumerate(TL["labels"]):
        dsp.place(s, tick(700 + k, f=4200 + 160 * k, pan=0.4 * (-1) ** k), lt, gain=0.13)
        if k % 2 == 0:
            dsp.place(s, impact(720 + k, strength=0.35, sub_f0=90, sub_f1=45, sub_tau=0.16, tail=0.3,
                                bright=0.1), lt, gain=0.24)
    d0, d1 = TL["docFly"]
    dsp.place(s, paper_swish(d1 - d0, 740), d0, gain=0.12)
    tick_train(s, BEATS[-1] + 0.35, WALL0, 0.11, 0.06, seed=750, f0=4200, f1=5600, level=0.06)

    # mergulho atraves do numero e chegada da parede
    f0_, f1_ = TL["flyThrough"]
    dsp.place(s, whoosh(f1_ - f0_ + 0.15, 800, f0=300, f1=5000, q=0.7, peak_at=0.55, pan0=0, pan1=0,
                        attack_pow=1.6), f0_, gain=0.40)
    dsp.place(s, impact(801, strength=0.7, sub_f0=95, sub_f1=40, sub_tau=0.3, tail=0.8), WALL0, gain=0.55)

    # parede: contador zumbindo, golpes de texto, voos de numeros, alerta critico
    tick_train(s, WALL0 + 0.1, FREEZE0 - 0.005, 0.055, 0.016, seed=810, f0=4400, f1=6800, level=0.06)
    for k, lt in enumerate(TL["s2Lines"]):
        last = k == len(TL["s2Lines"]) - 1
        dsp.place(s, impact(820 + k, strength=0.5 + (0.35 if last else 0.05 * k), sub_f0=105, sub_f1=44,
                            sub_tau=0.2, tail=0.4, bright=0.25), lt - 0.004, gain=0.36 + (0.12 if last else 0.0))
        dsp.place(s, click(830 + k, f=5200), lt, gain=0.07)
    r = dsp.rng(840)
    t = WALL0 + 0.2
    k = 0
    while t < FREEZE0 - 0.25:
        dsp.place(s, whoosh(0.22, 850 + k, f0=900, f1=4200, q=1.0, peak_at=0.7,
                            pan0=r.uniform(-0.8, 0.8), pan1=r.uniform(-0.8, 0.8)), t, gain=0.05)
        t += r.uniform(0.26, 0.42) * (1.0 - 0.45 * (t - WALL0) / (FREEZE0 - WALL0))
        k += 1

    # CONGELAMENTO: corte seco, so um grave muito baixo
    i0 = int(FREEZE0 * SR)
    ramp = int(0.003 * SR)
    s[i0:i0 + ramp] *= np.linspace(1, 0, ramp)[:, None]
    s[i0 + ramp:] = 0.0
    n = int((BURST1 - FREEZE0) * SR)
    tt = np.arange(n) / SR
    drone = (np.sin(2 * np.pi * 38 * tt) + 0.35 * np.sin(2 * np.pi * 57.2 * tt))
    drone *= np.minimum(1, tt / 0.02) * np.minimum(1, (tt[-1] - tt) / 0.05 + 0.0001)
    dsp.place(s, dsp.stereo(drone), FREEZE0, gain=0.06)

    # estouro da parede e impacto limpo da mensagem
    dsp.place(s, reverse_whoosh(BURST1 - BURST0 + 0.04, 900), BURST0 - 0.02, gain=0.34)
    dsp.place(s, deep_resolve(901), RESOLVE, gain=0.40)
    for k, wt in enumerate(TL["s3Words"]):
        dsp.place(s, tock(910 + k, f=760 + 60 * k), wt, gain=0.07)
    dsp.place(s, shimmer(0.45, 920), TL["s3Words"][-1] + 0.1, gain=0.10)
    for k, key in enumerate(("cta1", "cta2")):
        dsp.place(s, tock(930 + k, f=1040 + 120 * k), TL["brand"][key], gain=0.045)
    return s


# =============================================================== mix e calibracao
def vo_track():
    v = new()
    for clip in TL["vo"]:
        x, sr = sf.read(os.path.join(AUD, "source", clip["file"]), dtype="float64")
        assert sr == SR
        dsp.place(v, x, clip["start"])
    return v


def band_split(x, lo=900.0, hi=4200.0):
    from scipy.signal import butter, sosfiltfilt
    sl = butter(4, lo, "lowpass", fs=SR, output="sos")
    sh = butter(4, hi, "highpass", fs=SR, output="sos")
    low = sosfiltfilt(sl, x, axis=0)
    high = sosfiltfilt(sh, x, axis=0)
    mid = x - low - high
    return low, mid, high


def vo_activity(v):
    e = dsp.rms_env(v, SR, 0.03)
    act = (e > 10 ** (-42 / 20)).astype(float)
    # ataque 40 ms, release 260 ms
    a_c = np.exp(-1 / (0.04 * SR))
    r_c = np.exp(-1 / (0.26 * SR))
    out = np.empty_like(act)
    prev = 0.0
    for i, x in enumerate(act):
        c = a_c if x > prev else r_c
        prev = c * prev + (1 - c) * x
        out[i] = prev
    return out


def carve(x, act, broad_db, mid_db):
    low, mid, high = band_split(x)
    g_b = 10 ** (broad_db * act / 20)
    g_m = 10 ** (mid_db * act / 20)
    return (low + mid * g_m[:, None] + high) * g_b[:, None]


def main():
    music = build_music()
    sfx = build_sfx()
    vo = vo_track()
    act = vo_activity(vo)
    music = carve(music, act, broad_db=-4.5, mid_db=-7.0)
    sfx = carve(sfx, act, broad_db=-2.0, mid_db=-9.0)

    # balanco relativo: trilha ~ -9 LU abaixo da voz nos trechos falados
    def seg_lufs(x, t0, t1):
        return dsp.lufs(x[int(t0 * SR):int(t1 * SR)])

    vo_l = seg_lufs(vo, 0.3, 6.9)
    mu_l = seg_lufs(music, 0.3, 6.9)
    music *= 10 ** (((vo_l - 10.5) - mu_l) / 20)
    music = dsp.limiter(music, ceiling_db=-4.0)
    sfx = dsp.limiter(sfx, ceiling_db=-3.0)

    # calibracao: ganho comum para -14 LUFS + limitador de barramento assado nos stems
    g_total = 1.0
    bus = np.ones(N)
    for _ in range(4):
        mix = vo + music + sfx
        g = 10 ** ((-14.0 - dsp.lufs(mix)) / 20)
        vo, music, sfx = vo * g, music * g, sfx * g
        g_total *= g
        mix = vo + music + sfx
        gr = dsp.limiter_gain(mix, ceiling_db=-1.2)
        vo, music, sfx = vo * gr[:, None], music * gr[:, None], sfx * gr[:, None]
        bus *= gr
    mix = vo + music + sfx
    g = g_total

    # a voz e reescrita com o mesmo ganho g para manter a soma calibrada
    for clip in TL["vo"]:
        x, _ = sf.read(os.path.join(AUD, "source", clip["file"]), dtype="float64")
        i0 = int(round(clip["start"] * SR))
        seg = bus[i0:i0 + len(x)]
        seg = np.concatenate([seg, np.ones(len(x) - len(seg))]) if len(seg) < len(x) else seg
        dsp.write_wav(os.path.join(AUD, clip["file"]), x * g * seg[:, None])
    dsp.write_wav(os.path.join(AUD, "music.wav"), music)
    dsp.write_wav(os.path.join(AUD, "sfx.wav"), sfx)
    dsp.write_wav(os.path.join(AUD, "mix-preview.wav"), mix)
    rep = {
        "mix_lufs": round(dsp.lufs(mix), 2),
        "mix_peak_db": round(dsp.db(mix), 2),
        "vo_gain_db": round(20 * np.log10(g), 2),
        "bus_max_reduction_db": round(float(20 * np.log10(np.min(bus))), 2),
        "speech_vs_music_lu": round(seg_lufs(vo, 0.3, 6.9) - seg_lufs(music, 0.3, 6.9), 2),
        "music_peak_db": round(dsp.db(music), 2),
        "sfx_peak_db": round(dsp.db(sfx), 2),
        "freeze_rms_db": round(20 * np.log10(np.sqrt(np.mean(mix[int(FREEZE0 * SR) + 200:int(FREEZE1 * SR)] ** 2)) + 1e-12), 1),
    }
    print(json.dumps(rep, indent=2))
    with open(os.path.join(AUD, "mix-report.json"), "w") as f:
        json.dump(rep, f, indent=2)


if __name__ == "__main__":
    main()
