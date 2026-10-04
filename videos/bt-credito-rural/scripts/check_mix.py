"""Mede a relacao voz/fundo na faixa de inteligibilidade (1 a 4 kHz) em janelas de 100 ms."""
import json, os, sys
import numpy as np, soundfile as sf
from scipy.signal import butter, sosfiltfilt
HERE = os.path.dirname(os.path.abspath(__file__))
AUD = os.path.join(HERE, "..", "assets", "audio")
TL = json.load(open(os.path.join(HERE, "timeline.json")))
SR = 48000
N = int(TL["duration"] * SR)
def load(name):
    x, sr = sf.read(os.path.join(AUD, name)); return x.mean(1)
vo = np.zeros(N)
for c in TL["vo"]:
    x = load(c["file"]); i = int(c["start"] * SR); vo[i:i + len(x)] += x[: N - i]
bg = load("music.wav")[:N] + load("sfx.wav")[:N]
sos = butter(4, [1000, 4000], "bandpass", fs=SR, output="sos")
vb, bb = sosfiltfilt(sos, vo), sosfiltfilt(sos, bg)
h = int(0.1 * SR)
rows = []
for i in range(0, N - h, h):
    v = np.sqrt(np.mean(vb[i:i + h] ** 2)); b = np.sqrt(np.mean(bb[i:i + h] ** 2))
    if 20 * np.log10(v + 1e-12) > -45:
        rows.append((i / SR, 20 * np.log10(v / (b + 1e-12))))
snr = np.array([r[1] for r in rows])
print("speech windows:", len(rows), " median SNR %.1f dB  p10 %.1f dB  min %.1f dB" % (np.median(snr), np.percentile(snr, 10), snr.min()))
worst = sorted(rows, key=lambda r: r[1])[:12]
print("worst windows:", [(round(t, 2), round(s, 1)) for t, s in worst])
