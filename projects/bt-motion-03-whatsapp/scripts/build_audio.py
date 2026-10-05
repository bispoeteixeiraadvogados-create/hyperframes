"""Áudio completo do BT Motion 03 (golpe do WhatsApp): narração, trilha e sound design.

Determinístico (semente fixa). Três fontes:
  1. Narração feminina PT-BR gerada localmente com Kokoro (voz pf_dora), uma fala por arquivo.
  2. Trilha sintetizada aqui, em quatro seções que acompanham a narrativa
     (tensão, corte no freeze, orientação mais segura, resolução de marca).
  3. Efeitos: plim, whoosh de vento, sub graves e ticks sintetizados aqui; pop, click,
     glitch e impacto vêm do pacote de SFX do skill media-use (licença Pixabay, ver CREDITS.md).

Uso:
  python3 scripts/build_audio.py <pasta_com_vozes_t1..t12.wav> /tmp/mix.wav
  ffmpeg -i /tmp/mix.wav -af "loudnorm=I=-14:TP=-1.5:LRA=11" -ar 48000 -ac 2 \
    -c:a aac -b:a 128k assets/audio/bt-motion-03-mix.m4a
"""

import math
import os
import subprocess
import sys

import numpy as np

SR = 48000
DUR = 25.2
N = int(SR * DUR)
TAU = 2 * math.pi
rng = np.random.default_rng(2210)

HERE = os.path.dirname(os.path.abspath(__file__))
SFX = os.path.join(HERE, "..", "..", "..", "skills", "media-use", "audio", "assets", "sfx")

# Falas: (id, início em segundos). Os tempos batem com a timeline do index.html.
VO = [
    (1, 1.20),  # Uma mensagem.
    (2, 2.31),  # Um número novo.
    (3, 3.42),  # E um pedido urgente de Pix.
    (4, 5.42),  # Nessa hora, a pressa costuma esconder o golpe.
    (5, 8.08),  # Antes de transferir, pare.
    (6, 9.95),  # Antes do Pix, confirme por outro meio.
    (7, 12.21),  # Ligue.
    (8, 12.85),  # Faça uma videochamada.
    (9, 14.36),  # Confirme com alguém da família.
    (10, 18.02),  # Recebeu uma mensagem assim?
    (11, 19.87),  # Antes de fazer o Pix, confirme.
    (12, 21.81),  # Se precisar de orientação, fale com nossa equipe.
]
FREEZE = 9.26


def load(path, gain=1.0):
    """Decodifica qualquer áudio para float32 estéreo 48 kHz via ffmpeg."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
        check=True,
        capture_output=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).astype(np.float64) * gain


def place(bus, clip, t0, pan=0.0):
    i0 = int(round(t0 * SR))
    if i0 >= N:
        return
    seg = clip[: N - i0]
    if pan:
        seg = seg * np.array([1 - max(0, pan), 1 + min(0, pan)])
    bus[i0 : i0 + len(seg)] += seg


def t_axis(dur):
    return np.arange(int(dur * SR)) / SR


def stereo(mono, pan=0.0):
    return np.stack([mono * (1 - max(0, pan)), mono * (1 + min(0, pan))], axis=1)


def smooth(a, b, x):
    y = np.clip((x - a) / (b - a), 0, 1)
    return y * y * (3 - 2 * y)


def onepole_lp(x, cutoff):
    """Passa baixas de um polo com cutoff variável (array ou escalar)."""
    cutoff = np.broadcast_to(cutoff, x.shape)
    alpha = 1 - np.exp(-TAU * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += alpha[i] * (x[i] - acc)
        y[i] = acc
    return y


# =============================== TRILHA ===============================
music = np.zeros((N, 2))
t_all = np.arange(N) / SR


def pad(freqs, t0, t1, gain, fade_in, fade_out, cutoff0, cutoff1, detune=0.22):
    i0, i1 = int(t0 * SR), min(N, int(t1 * SR))
    t = t_all[i0:i1]
    env = smooth(t0, t0 + fade_in, t) * (1 - smooth(t1 - fade_out, t1, t))
    sig_l = np.zeros_like(t)
    sig_r = np.zeros_like(t)
    for k, f in enumerate(freqs):
        for d, side in ((-detune, 0), (detune, 1)):
            ph = rng.random() * TAU
            # serra suavizada (poucos harmônicos), mais quente que seno puro
            s = sum(np.sin(TAU * (f + d) * h * t + ph * h) / h for h in range(1, 6))
            w = 1.0 / (1 + 0.3 * k)
            if side == 0:
                sig_l += s * w
            else:
                sig_r += s * w
    cutoff = cutoff0 + (cutoff1 - cutoff0) * smooth(t0, t1, t)
    sig_l = onepole_lp(onepole_lp(sig_l, cutoff), cutoff)
    sig_r = onepole_lp(onepole_lp(sig_r, cutoff), cutoff)
    music[i0:i1, 0] += sig_l * env * gain
    music[i0:i1, 1] += sig_r * env * gain


def pluck(t0, f, gain, decay=0.22, pan=0.0, bright=4):
    t = t_axis(decay * 5)
    a = np.minimum(1, t / 0.004) * np.exp(-t / decay)
    s = sum(np.sin(TAU * f * h * t) * np.exp(-t * h / (decay * 6)) / h for h in range(1, bright + 1))
    place(music, stereo(s * a * gain, pan), t0)


def sub_pulse(t0, f, gain, decay=0.18):
    t = t_axis(decay * 5)
    fr = f * (1 + 0.6 * np.exp(-t / 0.02))
    ph = np.cumsum(TAU * fr / SR)
    a = np.minimum(1, t / 0.003) * np.exp(-t / decay)
    place(music, stereo(np.sin(ph) * a * gain), t0)


def tick(bus, t0, gain, pan=0.0, length=0.03, hp=True):
    t = t_axis(length)
    x = rng.uniform(-1, 1, len(t))
    if hp:
        x = np.diff(x, prepend=0)
    a = np.exp(-t / (length / 5))
    place(bus, stereo(x * a * gain, pan), t0)


# --- Seção 1 (0 a 9.26): tensão moderna e leve, crescendo ---
BPM = 120.0
beat = 60 / BPM
pad([73.42, 87.31, 110.0, 146.83], 0.2, FREEZE, 0.020, 1.2, 0.02, 380, 2400)  # Ré menor
step = beat / 2
k = 0
t = 1.2
while t < FREEZE - 0.01:
    g = 0.30 if k % 2 == 0 else 0.16
    g *= 0.7 + 0.3 * min(1, (t - 1.2) / 6)
    sub_pulse(t, 36.71, g)
    if k % 4 == 2:
        pluck(t, 293.66 if (k // 8) % 2 == 0 else 349.23, 0.035, pan=0.25)
    t += step
    k += 1
t = 4.4
k = 0
while t < FREEZE - 0.01:
    tick(music, t, 0.05 * (0.55 + 0.45 * ((t - 4.4) / 4.9)) * (1.0 if k % 2 == 0 else 0.6), pan=0.3 if k % 2 else -0.3)
    t += beat / 4
    k += 1
# riser tonal da tensão máxima (7.9 a 9.26), corte seco no freeze
tt = t_axis(FREEZE - 7.9)
f = 220 * 2 ** (tt / (FREEZE - 7.9) * 1.0)
rise = np.sin(np.cumsum(TAU * f / SR)) + 0.5 * np.sin(np.cumsum(TAU * 1.5 * f / SR))
rise *= (tt / tt[-1]) ** 2 * 0.05
place(music, stereo(rise), 7.9)
noise = rng.uniform(-1, 1, len(tt))
noise = onepole_lp(noise, 600 + 5000 * (tt / tt[-1]) ** 2) * (tt / tt[-1]) ** 2.5 * 0.12
place(music, stereo(noise), 7.9)
i_fz = int(FREEZE * SR)
music[i_fz : i_fz + int(0.6 * SR)] = 0  # silêncio no freeze

# --- Seção 2 (9.9 a 16.0): pulso se reorganiza, mais seguro ---
pad([58.27, 87.31, 116.54, 174.61, 233.08], 9.85, 16.05, 0.017, 0.7, 0.2, 700, 1500)  # Si bemol add9
t = 9.95
k = 0
arp = [349.23, 466.16, 523.25, 698.46]
while t < 16.0:
    if k % 2 == 0:
        sub_pulse(t, 29.14 if t < 12.2 else 34.65, 0.22)
    pluck(t, arp[k % 4], 0.022, decay=0.18, pan=-0.3 if k % 2 else 0.3, bright=3)
    t += beat / 2
    k += 1

# --- Seção 3 (16.0 a 17.9): o alerta, pulso apertado ---
pad([73.42, 110.0, 146.83, 220.0], 16.0, 17.9, 0.016, 0.1, 0.1, 900, 2200)
t = 16.0
k = 0
while t < 17.84:
    sub_pulse(t, 36.71, 0.24 if k % 2 == 0 else 0.12, decay=0.12)
    tick(music, t, 0.045, pan=0.25 if k % 2 else -0.25)
    t += beat / 4
    k += 1

# --- Seção 4 (17.95 a 25.2): resolução de marca, Fá add9 ---
pad([43.65, 87.31, 130.81, 174.61, 196.0, 261.63], 17.9, 25.2, 0.019, 0.6, 1.2, 600, 1300)
t = 18.0
k = 0
while t < 21.8:
    if k % 4 == 0:
        sub_pulse(t, 43.65, 0.14, decay=0.3)
    t += beat / 2
    k += 1

# =============================== SOUND DESIGN ===============================
fx = np.zeros((N, 2))


def plim(t0, gain):
    """Notificação estilo iPhone: dois toques cristalinos, sem copiar som de terceiros."""
    for dt, f, g in ((0.0, 1318.5, 1.0), (0.085, 1975.5, 0.85)):
        t = t_axis(0.9)
        a = np.minimum(1, t / 0.002) * np.exp(-t / 0.16)
        s = np.sin(TAU * f * t) + 0.25 * np.sin(TAU * 2 * f * t) * np.exp(-t / 0.05) + 0.12 * np.sin(TAU * 2.76 * f * t) * np.exp(-t / 0.04)
        place(fx, stereo(s * a * gain * g, 0.05), t0 + dt)


def wind(t0, dur, gain, pan_from=-0.7, pan_to=0.3, rev=False):
    t = t_axis(dur)
    u = t / dur
    x = rng.uniform(-1, 1, len(t))
    cutoff = 250 + 4200 * np.sin(np.pi * np.minimum(1, u * 1.1)) ** 2
    y = onepole_lp(onepole_lp(x, cutoff), cutoff)
    env = np.where(u < 0.35, (u / 0.35) ** 1.6, (1 - (u - 0.35) / 0.65) ** 2.2)
    if rev:
        y, env = y[::-1], env[::-1]
    pan = pan_from + (pan_to - pan_from) * u
    v = y * env * gain
    place(fx, np.stack([v * (1 - np.maximum(0, pan)), v * (1 + np.minimum(0, pan))], axis=1), t0)


def sub_hit(t0, gain, f0=60.0, f1=34.0, decay=0.5):
    t = t_axis(decay * 4)
    fr = f1 + (f0 - f1) * np.exp(-t / 0.1)
    a = np.minimum(1, t / 0.004) * np.exp(-t / decay)
    place(fx, stereo(np.sin(np.cumsum(TAU * fr / SR)) * a * gain), t0)


def piano(t0, f, gain, decay=2.4, pan=0.0):
    t = t_axis(decay * 2.4)
    a = np.minimum(1, t / 0.005) * np.exp(-t / decay)
    s = np.sin(TAU * f * t) + 0.32 * np.sin(TAU * 2 * f * t) * np.exp(-t / (decay * 0.5)) + 0.12 * np.sin(TAU * 3.01 * f * t) * np.exp(-t / (decay * 0.3))
    place(fx, stereo(s * a * gain, pan), t0)


def sample(name, t0, gain, pan=0.0, start=0.0, length=None, fade=0.03):
    clip = load(os.path.join(SFX, name), gain)
    clip = clip[int(start * SR) :]
    if length:
        clip = clip[: int(length * SR)].copy()
        nf = int(fade * SR)
        clip[-nf:] *= np.linspace(1, 0, nf)[:, None]
    place(fx, clip, t0, pan)


# abertura: vento + whoosh
wind(0.0, 0.62, 0.55)
sample("whoosh-short.mp3", 0.0, 0.35)
# notificação e toque
plim(0.54, 0.12)
sample("click-soft.mp3", 1.0, 0.55)
wind(1.06, 0.34, 0.22, 0.2, -0.2)
# mensagens
for tm in (1.42, 2.3, 3.14, 3.82, 5.5, 6.62, 7.72):
    sample("pop.mp3", tm, 0.32, pan=-0.15)
    tick(fx, tm + 0.01, 0.05, length=0.02)
for t0, t1 in ((1.74, 2.3), (2.6, 3.14), (4.42, 5.5)):
    tt = t0 + 0.05
    while tt < t1 - 0.08:
        tick(fx, tt, 0.018, pan=-0.2, length=0.012)
        tt += 0.09
# glitches leves
sample("glitch-3.mp3", 4.6, 0.32, length=0.42)
sample("glitch-3.mp3", 5.02, 0.22, start=0.6, length=0.14)
sample("glitch-1.mp3", 7.02, 0.2, length=0.22)
sample("glitch-3.mp3", 7.76, 0.2, start=1.0, length=0.12)
sample("glitch-3.mp3", 8.6, 0.16, start=1.4, length=0.08)
sample("glitch-1.mp3", 8.98, 0.16, start=0.1, length=0.16)
# ênfase PIX / AGORA
wind(5.92, 0.3, 0.3, -0.6, -0.1)
wind(6.24, 0.3, 0.3, 0.6, 0.1)
sub_hit(6.0, 0.16, decay=0.3)
sub_hit(6.32, 0.14, decay=0.3)
# freeze: impacto seco
sample("impact-bass-1.mp3", FREEZE, 0.6)
sub_hit(FREEZE, 0.3, decay=0.6)
tick(fx, FREEZE, 0.25, length=0.05, hp=False)
# recuo e tipografia
wind(9.5, 0.5, 0.35, 0.4, -0.4, rev=True)
for tm in (9.98, 10.4, 11.22):
    sample("click-soft.mp3", tm, 0.22)
wind(11.9, 0.32, 0.32, -0.3, 0.3)
sub_hit(12.2, 0.2, decay=0.35)
sample("click.mp3", 12.2, 0.18)
wind(12.76, 0.28, 0.24, 0.3, -0.3)
sample("click-soft.mp3", 12.86, 0.22)
wind(14.26, 0.28, 0.24, -0.3, 0.3)
sample("click-soft.mp3", 14.36, 0.22)
# núcleo do alerta
wind(15.9, 0.42, 0.4, -0.5, 0.5)
for tm in (16.2, 16.72, 16.94, 17.14):
    sample("click-soft.mp3", tm, 0.24)
sample("ping.mp3", 17.46, 0.16)
sub_hit(17.46, 0.3, decay=0.45)
wind(17.7, 0.42, 0.42, 0.0, 0.0)
# fechamento
for tm in (18.08, 18.62):
    sample("click-soft.mp3", tm, 0.16)
wind(19.66, 0.3, 0.22, 0.3, -0.3)
wind(21.55, 0.36, 0.26, -0.3, 0.3)
# sting de marca refinado
sub_hit(21.86, 0.18, f0=50, f1=40, decay=0.9)
piano(21.86, 174.61, 0.05, decay=3.0, pan=-0.1)
piano(21.88, 261.63, 0.04, decay=3.0, pan=0.05)
piano(21.9, 349.23, 0.03, decay=2.8, pan=0.15)
piano(22.3, 523.25, 0.022, decay=2.4, pan=0.2)
sample("sparkle.mp3", 21.9, 0.1)

# =============================== NARRAÇÃO ===============================
voice = np.zeros((N, 2))
vo_dir = sys.argv[1]
for idx, t0 in VO:
    clip = load(os.path.join(vo_dir, f"t{idx}.wav"))
    place(voice, clip, t0)
# leve tratamento: limpeza de graves, presença e compressão suave
vtmp = os.path.join(os.path.dirname(sys.argv[2]) or ".", "_vo_dry.f32")
voice.astype(np.float32).tofile(vtmp)
proc = subprocess.run(
    [
        "ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", vtmp,
        "-af", "highpass=f=90,equalizer=f=3200:t=q:w=1.2:g=2.5,equalizer=f=250:t=q:w=1:g=-2,"
        "acompressor=threshold=-20dB:ratio=3:attack=8:release=120:makeup=2,"
        "aecho=0.9:0.5:38|71:0.08|0.05",
        "-f", "f32le", "-ac", "2", "-ar", str(SR), "-",
    ],
    check=True,
    capture_output=True,
)
os.remove(vtmp)
voice = np.frombuffer(proc.stdout, dtype=np.float32).reshape(-1, 2).astype(np.float64)[:N]
if len(voice) < N:
    voice = np.vstack([voice, np.zeros((N - len(voice), 2))])

# ducking: a trilha abaixa ~8 dB enquanto a voz fala
env = np.abs(voice).max(axis=1)
win = int(0.12 * SR)
env = np.convolve(env, np.ones(win) / win, mode="same")
duck = 1 - 0.62 * np.clip(env / 0.02, 0, 1)
duck = onepole_lp(duck, 6.0)
music *= duck[:, None]

# =============================== MIX ===============================
mix = voice * 1.0 + music * 0.6 + fx * 0.8
fade = 1 - smooth(DUR - 0.35, DUR, t_all)
mix *= fade[:, None]
peak = np.abs(mix).max()
mix *= 0.9 / peak
mix.astype(np.float32).tofile(sys.argv[2] + ".f32")
subprocess.run(
    ["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", sys.argv[2] + ".f32", sys.argv[2]],
    check=True,
)
os.remove(sys.argv[2] + ".f32")
print(f"peak={peak:.3f} -> {sys.argv[2]}")
