"""Pequena biblioteca de DSP (numpy/scipy) usada pela narracao e pelo design de som.

Tudo e deterministico: ruidos usam geradores com semente fixa.
"""

import numpy as np
from scipy.signal import fftconvolve, lfilter, resample_poly

SR = 48000


def rng(seed):
    return np.random.default_rng(seed)


# ---------------------------------------------------------------- filtros RBJ
def biquad(kind, f0, sr=SR, q=0.707, gain_db=0.0):
    f0 = float(np.clip(f0, 10.0, sr * 0.49))
    a_lin = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * f0 / sr
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw / (2 * q)
    if kind == "lowpass":
        b = [(1 - cw) / 2, 1 - cw, (1 - cw) / 2]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "highpass":
        b = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "bandpass":
        b = [alpha, 0, -alpha]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "peak":
        b = [1 + alpha * a_lin, -2 * cw, 1 - alpha * a_lin]
        a = [1 + alpha / a_lin, -2 * cw, 1 - alpha / a_lin]
    elif kind == "lowshelf":
        sq = 2 * np.sqrt(a_lin) * alpha
        b = [a_lin * ((a_lin + 1) - (a_lin - 1) * cw + sq), 2 * a_lin * ((a_lin - 1) - (a_lin + 1) * cw),
             a_lin * ((a_lin + 1) - (a_lin - 1) * cw - sq)]
        a = [(a_lin + 1) + (a_lin - 1) * cw + sq, -2 * ((a_lin - 1) + (a_lin + 1) * cw),
             (a_lin + 1) + (a_lin - 1) * cw - sq]
    elif kind == "highshelf":
        sq = 2 * np.sqrt(a_lin) * alpha
        b = [a_lin * ((a_lin + 1) + (a_lin - 1) * cw + sq), -2 * a_lin * ((a_lin - 1) + (a_lin + 1) * cw),
             a_lin * ((a_lin + 1) + (a_lin - 1) * cw - sq)]
        a = [(a_lin + 1) - (a_lin - 1) * cw + sq, 2 * ((a_lin - 1) - (a_lin + 1) * cw),
             (a_lin + 1) - (a_lin - 1) * cw - sq]
    else:
        raise ValueError(kind)
    b = np.array(b) / a[0]
    a = np.array(a) / a[0]
    return b, a


def filt(x, kind, f0, sr=SR, q=0.707, gain_db=0.0):
    b, a = biquad(kind, f0, sr, q, gain_db)
    return lfilter(b, a, x, axis=0)


def sweep_filter(x, kind, f_curve, q=0.9, sr=SR, block=64):
    """Filtro variante no tempo: f_curve tem o mesmo comprimento de x (mono)."""
    y = np.zeros_like(x)
    zi = np.zeros(2)
    for i in range(0, len(x), block):
        f0 = float(np.mean(f_curve[i:i + block]))
        b, a = biquad(kind, f0, sr, q)
        seg, zi = lfilter(b, a, x[i:i + block], zi=zi)
        y[i:i + block] = seg
    return y


# ---------------------------------------------------------------- sinais
def t_axis(dur, sr=SR):
    return np.arange(int(round(dur * sr))) / sr


def noise(dur, seed, sr=SR, color="white"):
    n = int(dur * sr)
    w = rng(seed).standard_normal(n)
    if color == "pink":
        # filtro de Paul Kellet (aprox. 1/f)
        b = [0.049922035, -0.095993537, 0.050612699, -0.004408786]
        a = [1, -2.494956002, 2.017265875, -0.522189400]
        w = lfilter(b, a, w)
        w /= np.max(np.abs(w)) + 1e-9
    elif color == "brown":
        w = np.cumsum(w)
        w = filt(w, "highpass", 20, sr)
        w /= np.max(np.abs(w)) + 1e-9
    return w


def phase_from_freq(freq, sr=SR):
    return 2 * np.pi * np.cumsum(freq) / sr


def saw_blep(freq, sr=SR, phase0=0.0):
    """Dente de serra limitado em banda (PolyBLEP) com frequencia variavel."""
    dt = np.asarray(freq, dtype=float) / sr
    ph = (phase0 + np.cumsum(dt)) % 1.0
    y = 2 * ph - 1
    # correcao polyBLEP perto das descontinuidades
    m1 = ph < dt
    tt = ph[m1] / dt[m1]
    y[m1] -= tt + tt - tt * tt - 1
    m2 = ph > 1 - dt
    tt = (ph[m2] - 1) / dt[m2]
    y[m2] -= tt * tt + tt + tt + 1
    return y


def env_points(points, n, sr=SR, curve="lin"):
    """points: lista (t, valor). Interpola em n amostras."""
    ts = np.array([p[0] for p in points]) * sr
    vs = np.array([p[1] for p in points], dtype=float)
    idx = np.arange(n)
    if curve == "exp":
        vs = np.log(np.maximum(vs, 1e-6))
        return np.exp(np.interp(idx, ts, vs))
    return np.interp(idx, ts, vs)


def adsr(n, a, d, s, r, sr=SR, hold=None):
    """Envelope ADSR simples em amostras; hold = duracao do sustain (s)."""
    A, D, R = int(a * sr), int(d * sr), int(r * sr)
    H = n - A - D - R if hold is None else int(hold * sr)
    H = max(H, 0)
    e = np.concatenate([
        np.linspace(0, 1, max(A, 1), endpoint=False),
        np.linspace(1, s, max(D, 1), endpoint=False),
        np.full(H, s),
        np.linspace(s, 0, max(R, 1)),
    ])
    if len(e) < n:
        e = np.concatenate([e, np.zeros(n - len(e))])
    return e[:n]


def exp_decay(n, tau, sr=SR):
    return np.exp(-np.arange(n) / (tau * sr))


# ---------------------------------------------------------------- espaco
def make_ir(decay=1.6, predelay=0.012, sr=SR, seed=7, lp=7000.0, hp=120.0, early=True):
    n = int((decay * 1.2 + predelay) * sr)
    out = np.zeros((n, 2))
    pd = int(predelay * sr)
    for ch in range(2):
        w = rng(seed + ch).standard_normal(n - pd)
        tail = w * np.exp(-np.arange(n - pd) / (decay / 6.9 * sr))
        tail = filt(tail, "lowpass", lp, sr)
        tail = filt(tail, "highpass", hp, sr)
        out[pd:, ch] = tail
        if early:
            r = rng(seed + 10 + ch)
            for _ in range(10):
                k = pd + int(r.uniform(0.002, 0.07) * sr)
                if k < n:
                    out[k, ch] += r.uniform(0.25, 0.6) * (1 if r.random() > 0.5 else -1)
    out /= np.sqrt(np.sum(out ** 2) / 2) + 1e-9
    return out


def reverb(x, ir, wet=0.25, dry=1.0):
    """x mono ou estereo; ir estereo."""
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    y = np.zeros((len(x) + len(ir) - 1, 2))
    for ch in range(2):
        y[:, ch] = fftconvolve(x[:, ch], ir[:, ch])
    y[: len(x)] *= wet
    y[len(x):] *= wet
    y[: len(x)] += dry * x
    return y


def pan(mono, pos=0.0):
    """pos -1 (esquerda) .. +1 (direita), lei de potencia constante. pos pode ser vetor."""
    pos = np.clip(np.asarray(pos, dtype=float), -1, 1)
    ang = (pos + 1) * np.pi / 4
    return np.stack([mono * np.cos(ang), mono * np.sin(ang)], axis=1)


def stereo(x):
    return x if x.ndim == 2 else np.stack([x, x], axis=1)


# ---------------------------------------------------------------- dinamica
def rms_env(x, sr, win):
    mono = x if x.ndim == 1 else x.mean(axis=1)
    k = max(int(win * sr), 1)
    return np.sqrt(np.convolve(mono ** 2, np.ones(k) / k, "same") + 1e-12)


def compress(x, sr=SR, thr_db=-20.0, ratio=3.0, attack=0.005, release=0.08, makeup_db=0.0, knee_db=6.0):
    mono = x if x.ndim == 1 else np.max(np.abs(x), axis=1)
    lvl = 20 * np.log10(np.abs(mono) + 1e-9)
    # curva estatica com joelho suave
    over = lvl - thr_db
    gr = np.where(
        over <= -knee_db / 2, 0.0,
        np.where(over >= knee_db / 2, over * (1 - 1 / ratio),
                 (1 - 1 / ratio) * (over + knee_db / 2) ** 2 / (2 * knee_db)),
    )
    # suavizacao ataque/release em dominio dB
    a_c = np.exp(-1 / (attack * sr))
    r_c = np.exp(-1 / (release * sr))
    g = np.zeros_like(gr)
    prev = 0.0
    for i, v in enumerate(gr):
        c = a_c if v > prev else r_c
        prev = c * prev + (1 - c) * v
        g[i] = prev
    gain = 10 ** ((-g + makeup_db) / 20)
    return x * (gain if x.ndim == 1 else gain[:, None])


def limiter(x, sr=SR, ceiling_db=-1.0, lookahead=0.004, release=0.06):
    ceil = 10 ** (ceiling_db / 20)
    peak = np.max(np.abs(stereo(x)), axis=1)
    la = int(lookahead * sr)
    # pico futuro dentro da janela de lookahead
    from scipy.ndimage import maximum_filter1d
    fut = maximum_filter1d(peak, size=2 * la + 1, origin=0)
    need = np.minimum(1.0, ceil / (fut + 1e-12))
    r_c = np.exp(-1 / (release * sr))
    g = np.empty_like(need)
    prev = 1.0
    for i, v in enumerate(need):
        prev = v if v < prev else r_c * prev + (1 - r_c) * v
        g[i] = prev
    return stereo(x) * g[:, None]


def limiter_gain(x, sr=SR, ceiling_db=-1.0, lookahead=0.005, release=0.08):
    """Curva de ganho de um limitador com lookahead calculada sobre x (soma de stems).

    Aplicar a mesma curva a cada stem equivale a limitar a soma linear deles.
    """
    from scipy.ndimage import maximum_filter1d, uniform_filter1d
    ceil = 10 ** (ceiling_db / 20)
    peak = np.max(np.abs(stereo(x)), axis=1)
    la = int(lookahead * sr)
    fut = maximum_filter1d(peak, size=2 * la + 1)
    need = np.minimum(1.0, ceil / (fut + 1e-12))
    r_c = np.exp(-1 / (release * sr))
    g = np.empty_like(need)
    prev = 1.0
    for i, v in enumerate(need):
        prev = v if v < prev else r_c * prev + (1 - r_c) * v
        g[i] = prev
    # suaviza o ataque sem perder o teto (minimo apos media curta)
    g = np.minimum(g, uniform_filter1d(g, size=max(3, la)))
    return g


def soft_clip(x, drive=1.0):
    return np.tanh(x * drive) / np.tanh(drive)


def lufs(x, sr=SR):
    import pyloudnorm as pyln
    return pyln.Meter(sr).integrated_loudness(stereo(x))


def db(x):
    return 20 * np.log10(np.max(np.abs(x)) + 1e-12)


def write_wav(path, x, sr=SR):
    import soundfile as sf
    sf.write(path, stereo(x).astype(np.float32), sr, subtype="PCM_24")


def place(buf, clip, t, sr=SR, gain=1.0):
    """Mixa clip (estereo) em buf a partir do tempo t (s)."""
    clip = stereo(clip) * gain
    i = int(round(t * sr))
    if i < 0:
        clip = clip[-i:]
        i = 0
    j = min(len(buf), i + len(clip))
    if j > i:
        buf[i:j] += clip[: j - i]
    return buf


def resample(x, sr_from, sr_to):
    from math import gcd
    g = gcd(sr_from, sr_to)
    return resample_poly(x, sr_to // g, sr_from // g, axis=0)
