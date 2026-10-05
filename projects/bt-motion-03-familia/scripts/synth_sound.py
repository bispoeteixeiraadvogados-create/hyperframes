"""Sound design sintetizado do BT Motion 03 (Direito de Família).

Determinístico (semente fixa), sem samples de terceiros. Deixa espaço para a
narração (SRT/áudio fornecido depois): música contida, impactos curtos.

Uso:
  python3 scripts/synth_sound.py /tmp/dry.wav
  ffmpeg -y -i /tmp/dry.wav -af "aecho=0.8:0.5:50|110:0.18|0.1,loudnorm=I=-18:TP=-2:LRA=12" \
    -ar 48000 -ac 2 -c:a aac -b:a 192k assets/audio/bt-motion-03-sound.m4a
"""

import sys
import wave

import numpy as np

SR = 48000
DUR = 18.0
N = int(SR * DUR)
rng = np.random.default_rng(3318)
L = np.zeros(N)
R = np.zeros(N)
t_all = np.arange(N) / SR


def place(sig, t, gain=1.0, pan=0.0):
    i = int(t * SR)
    j = min(N, i + len(sig))
    if j <= i:
        return
    s = sig[: j - i] * gain
    L[i:j] += s * np.sqrt(0.5 * (1 - pan))
    R[i:j] += s * np.sqrt(0.5 * (1 + pan))


def env(n, a, d):
    x = np.arange(n) / SR
    e = np.minimum(1, x / max(a, 1e-4)) * np.exp(-np.maximum(0, x - a) / d)
    return e


def lowpass(x, fc):
    a = np.exp(-2 * np.pi * fc / SR)
    y = np.zeros_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def noise(n):
    return rng.standard_normal(n)


def whoosh(dur=0.45, up=True):
    n = int(dur * SR)
    x = noise(n)
    x = x - lowpass(x, 400)
    x = lowpass(x, 5000)
    ph = np.linspace(0, 1, n)
    shape = np.sin(np.pi * ph) ** 2 if up else np.sin(np.pi * ph ** 0.6) ** 2
    return x * shape * 0.5


def impact(f=48, dur=0.7, click=0.4):
    n = int(dur * SR)
    x = np.arange(n) / SR
    sweep = f * (1 + 2.5 * np.exp(-x * 30))
    body = np.sin(2 * np.pi * np.cumsum(sweep) / SR) * np.exp(-x * 5.5)
    c = noise(n) * np.exp(-x * 120) * click
    return body + lowpass(c, 3000)


def click(f=2400, dur=0.05, g=0.3):
    n = int(dur * SR)
    x = np.arange(n) / SR
    return (np.sin(2 * np.pi * f * x) * np.exp(-x * 160) + noise(n) * np.exp(-x * 400) * 0.3) * g


def paper(dur=0.25):
    n = int(dur * SR)
    x = noise(n)
    x = x - lowpass(x, 1500)
    ph = np.linspace(0, 1, n)
    grain = 0.6 + 0.4 * np.abs(np.sin(ph * 60))
    return x * np.sin(np.pi * ph) * grain * 0.25


def kick(dur=0.35):
    n = int(dur * SR)
    x = np.arange(n) / SR
    f = 52 * (1 + 1.8 * np.exp(-x * 40))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 9)


def tone(f, dur, a=0.01, d=0.6, harm=(1, 0.3, 0.1)):
    n = int(dur * SR)
    x = np.arange(n) / SR
    s = sum(h * np.sin(2 * np.pi * f * (k + 1) * x) for k, h in enumerate(harm))
    return s * env(n, a, d)


# ---- music bed: low pad, pulse, then calm resolve ----
def pad(t0, t1, freqs, gain):
    n = int((t1 - t0) * SR)
    x = np.arange(n) / SR
    s = sum(np.sin(2 * np.pi * f * x + k) for k, f in enumerate(freqs)) / len(freqs)
    s *= 1 + 0.25 * np.sin(2 * np.pi * 0.3 * x)
    fade = np.minimum(1, x / 0.4) * np.minimum(1, (x[-1] - x) / 0.25)
    place(s * fade, t0, gain)


pad(0.0, 9.95, [55.0, 82.4, 110.0, 164.8], 0.16)
pad(10.2, 12.05, [49.0, 73.4, 98.0], 0.14)
pad(12.05, 15.0, [65.4, 98.0, 130.8, 196.0], 0.11)
pad(14.9, 18.0, [58.3, 87.3, 116.5, 174.6, 233.1], 0.12)

# pulse accelerating from accumulation into overload
beat = 2.7
step = 0.5
while beat < 9.9:
    place(kick(), beat, 0.55)
    if beat > 5.8:
        place(click(7000, 0.03, 0.12), beat + step / 2, 1.0, 0.3)
    if beat >= 5.8:
        step = 0.4
    if beat >= 9.0:
        step = 0.2
    beat += step
for b in np.arange(12.45, 14.8, 0.6):
    place(kick(0.25), b, 0.25)

# riser into freeze
n = int(1.4 * SR)
r = noise(n)
r = r - lowpass(r, 800)
place(r * np.linspace(0, 1, n) ** 2 * 0.22, 8.55)

# ---- events ----
place(impact(55, 0.6, 0.6), 0.3, 0.75)          # FIM?
place(whoosh(0.5), 0.8, 0.9)                    # split
place(impact(40, 0.8, 0.2), 1.1, 0.4)
place(whoosh(0.3, False), 1.85, 0.7, 0.4)       # TERMINOU swiped
place(paper(0.2), 1.9, 0.8, 0.3)
place(impact(44, 0.9, 0.5), 2.16, 0.95)         # NÃO
place(whoosh(0.35), 2.45, 0.6)
for t, p in [(2.78, -0.4), (3.12, 0), (4.85, 0.4)]:
    place(click(1800, 0.06, 0.4), t, 1.0, p)
place(impact(36, 0.5, 0.1), 3.12, 0.5)          # DÍVIDAS weight
place(paper(0.35), 3.45, 1.0, -0.3)             # PATRIMÔNIO unfold
place(tone(523.3, 1.2, 0.2, 0.7), 3.8, 0.06)    # FILHOS soft
place(tone(659.3, 1.2, 0.25, 0.7), 3.85, 0.04)
place(click(1300, 0.06, 0.4), 4.15, 1.0, 0.4)   # PENSÃO
place(whoosh(0.25), 4.42, 0.7, -0.5)            # FINANCIAMENTO
place(paper(0.2), 4.5, 1.0, -0.5)
place(click(3200, 0.04, 0.3), 5.15, 1.0, 0.4)   # toggle
for i in range(4):
    place(paper(0.12), 5.2 + i * 0.06, 0.9, (-1) ** i * 0.3)
place(click(1500, 0.05, 0.35), 5.52, 1.0)

place(whoosh(0.35), 5.62, 0.8)                  # Q1 push
place(impact(50, 0.4, 0.3), 5.82, 0.5)
place(whoosh(0.22, False), 6.45, 1.0, -0.6)     # whip
place(whoosh(0.22, False), 6.58, 0.9, 0.6)
place(impact(48, 0.35, 0.3), 6.62, 0.45)
place(tone(392.0, 1.0, 0.15, 0.6), 7.42, 0.05)  # FILHOS question, gentle
place(whoosh(0.3), 8.1, 0.6)
place(click(2000, 0.05, 0.35), 8.24, 1.0)       # mask reveal
place(impact(46, 0.4, 0.3), 8.92, 0.5)
for i in range(12):
    place(click(900 + i * 140, 0.04, 0.22), 9.02 + i * 0.055, 1.0, ((i % 3) - 1) * 0.6)
for i in range(3):
    place(whoosh(0.2, False), 9.2 + i * 0.12, 0.5, (-1) ** i * 0.6)

# HARD FREEZE: cut everything 9.95 to 10.2 except a faint air tone
fi, fo = int(9.95 * SR), int(10.2 * SR)
L[fi:fo] *= 0.0
R[fi:fo] *= 0.0
air = noise(fo - fi)
air = lowpass(air, 600) * 0.02
L[fi:fo] += air
R[fi:fo] += air

place(impact(42, 0.9, 0.5), 10.24, 0.8)         # O DIVÓRCIO
place(impact(38, 1.0, 0.6), 10.62, 1.0)         # NÃO TERMINA
place(whoosh(0.3), 10.5, 0.5, -0.4)
place(paper(0.5), 11.3, 0.6)                    # signature stroke
place(whoosh(0.35), 11.85, 0.7)                 # wipe to sand

for i in range(5):                              # magnetic snaps
    place(click(1600 + i * 120, 0.05, 0.4), 12.97 + i * 0.07, 1.0, (i - 2) * 0.3)
for i in range(5):                              # ticks
    place(click(2600, 0.035, 0.28), 13.1 + i * 0.09, 1.0, (i - 2) * 0.3)
place(whoosh(0.35, False), 14.72, 0.7)          # collapse to CTA
place(impact(44, 0.7, 0.2), 14.95, 0.5)

# closing sting: warm chord + soft bell
for f, g in [(233.1, 0.10), (293.7, 0.08), (349.2, 0.07), (466.2, 0.05)]:
    place(tone(f, 1.6, 0.02, 0.9, (1, 0.25, 0.08)), 16.9, g)
place(tone(932.3, 1.4, 0.005, 0.5, (1, 0.5, 0.2)), 16.92, 0.04)
place(impact(50, 0.8, 0.1), 16.9, 0.35)

# master fade-out and soft clip
fade = np.ones(N)
k = int(0.6 * SR)
fade[-k:] = np.linspace(1, 0, k)
L *= fade
R *= fade
peak = max(np.abs(L).max(), np.abs(R).max())
L = np.tanh(L / peak * 1.2) * 0.85
R = np.tanh(R / peak * 1.2) * 0.85

out = sys.argv[1] if len(sys.argv) > 1 else "dry.wav"
data = np.empty(N * 2, dtype=np.int16)
data[0::2] = (L * 32767).astype(np.int16)
data[1::2] = (R * 32767).astype(np.int16)
with wave.open(out, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(data.tobytes())
print("wrote", out)
