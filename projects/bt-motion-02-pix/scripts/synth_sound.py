"""Sound design sintetizado para o BT Motion 02 (PIX não autorizado).

Tudo é gerado aqui, de forma determinística (semente fixa): trilha ambiente
discreta, notas de piano suaves, sub graves, clique, confirmação e whoosh da
dissolução. Nenhum sample de terceiros. Saída: WAV estéreo 48 kHz (seco); o
reverb e a normalização de loudness são aplicados depois com ffmpeg.

Uso:
  python3 scripts/synth_sound.py /tmp/dry.wav
  ffmpeg -i /tmp/dry.wav -af "aecho=0.8:0.6:60|130|210:0.22|0.15|0.09,loudnorm=I=-18:TP=-2:LRA=14" \
    -ar 48000 -ac 2 -c:a aac -b:a 160k assets/audio/bt-motion-02-sound.m4a
"""

import math
import random
import struct
import sys
import wave

SR = 48000
DUR = 18.5
N = int(SR * DUR)
TAU = 2 * math.pi
rng = random.Random(4850)

L = [0.0] * N
R = [0.0] * N


def add(i, l, r):
    if 0 <= i < N:
        L[i] += l
        R[i] += r


def smoothstep(a, b, x):
    if x <= a:
        return 0.0
    if x >= b:
        return 1.0
    t = (x - a) / (b - a)
    return t * t * (3 - 2 * t)


# ---------------- Pad ambiente (três harmonias, crossfade) ----------------
SECTIONS = [
    # (início, fim, fade, frequências, ganho)
    (0.0, 8.3, 1.8, [146.83, 174.61, 220.00, 329.63], 0.030),  # Ré menor add9, expectativa
    (8.9, 16.6, 1.2, [116.54, 146.83, 174.61, 220.00], 0.026),  # Si bemol maj7, dúvida
    (16.3, 18.5, 0.8, [87.31, 130.81, 220.00, 392.00], 0.030),  # Fá add9, autoridade serena
]
for start, end, fade, freqs, gain in SECTIONS:
    i0, i1 = int(start * SR), min(N, int(end * SR))
    voices = []
    for k, f in enumerate(freqs):
        for det in (-0.18, 0.18):
            voices.append((f + det, rng.random() * TAU, 0.5 if det < 0 else -0.5, k))
    for i in range(i0, i1):
        t = i / SR
        env = smoothstep(start, start + fade, t) * (1 - smoothstep(end - fade, end, t))
        if env <= 0:
            continue
        trem = 0.85 + 0.15 * math.sin(TAU * 0.11 * t)
        l = r = 0.0
        for f, ph, pan, k in voices:
            s = math.sin(TAU * f * t + ph) + 0.18 * math.sin(TAU * 2 * f * t + ph)
            w = 1.0 / (1 + 0.35 * k)
            l += s * w * (0.5 + 0.25 * pan)
            r += s * w * (0.5 - 0.25 * pan)
        g = gain * env * trem
        L[i] += l * g
        R[i] += r * g


# ---------------- Piano extremamente discreto ----------------
def piano(t0, f, gain, decay=2.2, pan=0.0):
    i0 = int(t0 * SR)
    n = int((decay * 2.5) * SR)
    for j in range(n):
        t = j / SR
        a = min(1.0, t / 0.006) * math.exp(-t / decay) * (1 - smoothstep(decay * 2.0, decay * 2.5, t))
        s = (
            math.sin(TAU * f * t)
            + 0.32 * math.sin(TAU * 2 * f * t) * math.exp(-t / (decay * 0.5))
            + 0.12 * math.sin(TAU * 3.01 * f * t) * math.exp(-t / (decay * 0.3))
        )
        v = s * a * gain
        add(i0 + j, v * (1 - pan) * 0.7, v * (1 + pan) * 0.7)


piano(0.25, 293.66, 0.045, pan=-0.15)  # entrada inicial
piano(1.00, 220.00, 0.050, pan=0.1)  # "Você não autorizou."
piano(9.30, 220.00, 0.045, decay=2.8, pan=-0.1)  # entrada da pergunta
piano(9.52, 329.63, 0.030, decay=2.8, pan=0.15)
piano(12.30, 174.61, 0.038, decay=2.6, pan=0.0)  # mensagem jurídica
piano(16.60, 174.61, 0.045, decay=3.0, pan=-0.1)  # assinatura
piano(16.62, 261.63, 0.032, decay=3.0, pan=0.1)
piano(16.64, 440.00, 0.020, decay=2.6, pan=0.2)


# ---------------- Sub grave ----------------
def sub_hit(t0, gain, f0=52.0, f1=36.0, decay=0.55):
    i0 = int(t0 * SR)
    n = int(decay * 4 * SR)
    ph = 0.0
    for j in range(n):
        t = j / SR
        f = f1 + (f0 - f1) * math.exp(-t / 0.12)
        ph += TAU * f / SR
        a = min(1.0, t / 0.01) * math.exp(-t / decay)
        v = math.sin(ph) * a * gain
        add(i0 + j, v, v)


sub_hit(1.00, 0.22)  # impacto grave discreto na segunda frase
sub_hit(7.92, 0.30, decay=0.7)  # dissolução do dinheiro
sub_hit(16.60, 0.12, decay=0.8)  # assinatura


# ---------------- Clique da confirmação ----------------
def click(t0, gain):
    i0 = int(t0 * SR)
    n = int(0.03 * SR)
    prev = 0.0
    for j in range(n):
        t = j / SR
        x = rng.uniform(-1, 1)
        hp = x - prev  # passa altas simples
        prev = x
        a = math.exp(-t / 0.004)
        tone = math.sin(TAU * 2400 * t) * math.exp(-t / 0.006)
        v = (0.6 * hp + 0.5 * tone) * a * gain
        add(i0 + j, v, v)


click(6.32, 0.16)


# ---------------- PIX enviado: confirmação funcional ----------------
def soft_tone(t0, f, gain, decay=0.35, pan=0.0):
    i0 = int(t0 * SR)
    n = int(decay * 5 * SR)
    for j in range(n):
        t = j / SR
        a = min(1.0, t / 0.01) * math.exp(-t / decay)
        v = (math.sin(TAU * f * t) + 0.2 * math.sin(TAU * 2 * f * t)) * a * gain
        add(i0 + j, v * (1 - pan), v * (1 + pan))


soft_tone(6.68, 880.00, 0.030)
soft_tone(6.80, 1318.51, 0.022, pan=0.1)


# ---------------- Whoosh curto da dissolução (esquerda para direita) ----------------
def whoosh(t0, dur, gain):
    i0 = int(t0 * SR)
    n = int(dur * SR)
    lp1 = lp2 = 0.0
    for j in range(n):
        u = j / n
        x = rng.uniform(-1, 1)
        cutoff = 300 + 5200 * math.sin(math.pi * min(1.0, u * 1.15)) ** 2
        alpha = 1 - math.exp(-TAU * cutoff / SR)
        lp1 += alpha * (x - lp1)
        lp2 += alpha * (lp1 - lp2)
        env = (u / 0.22) ** 2 if u < 0.22 else (1 - (u - 0.22) / 0.78) ** 2.2
        pan = -0.6 + 1.4 * u  # o dinheiro sai para a direita
        v = lp2 * env * gain
        add(i0 + j, v * (1 - pan) * 0.8, v * (1 + pan) * 0.8)


whoosh(7.84, 1.05, 0.55)


# ---------------- Texturas eletrônicas quase imperceptíveis ----------------
prev_l = prev_r = 0.0
for i in range(N):
    t = i / SR
    env = smoothstep(0.0, 1.5, t) * (1 - smoothstep(17.6, 18.5, t)) * (0.6 + 0.4 * smoothstep(7.8, 8.4, t) * (1 - smoothstep(9.0, 11.0, t)))
    xl, xr = rng.uniform(-1, 1), rng.uniform(-1, 1)
    hl, hr = xl - prev_l, xr - prev_r
    prev_l, prev_r = xl, xr
    L[i] += hl * 0.0016 * env
    R[i] += hr * 0.0016 * env


# ---------------- Fade final de 0.4 s e escrita ----------------
peak = 0.0
for i in range(N):
    t = i / SR
    g = 1 - smoothstep(18.1, 18.5, t)
    L[i] *= g
    R[i] *= g
    peak = max(peak, abs(L[i]), abs(R[i]))
scale = 0.89 / peak if peak > 0.89 else 1.0

out = sys.argv[1]
with wave.open(out, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    frames = bytearray()
    for i in range(N):
        frames += struct.pack("<hh", int(L[i] * scale * 32767), int(R[i] * scale * 32767))
    w.writeframes(bytes(frames))
print(f"peak={peak:.3f} scale={scale:.3f} -> {out}")
