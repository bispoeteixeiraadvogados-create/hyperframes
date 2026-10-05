"""Narração feminina PT-BR local (Kokoro-82M, voz pf_dora, velocidade 1.1).

Modelos (GitHub releases de thewh1teagle/kokoro-onnx, model-files-v1.0):
  kokoro-v1.0.onnx e voices-v1.0.bin. Dependências: pip install kokoro-onnx soundfile.

Uso:
  python3 scripts/tts_kokoro.py <pasta_dos_modelos> <pasta_saida>
Gera l1..l12.wav e as versões aparadas t1..t12.wav (silêncio de borda removido),
que é o que scripts/build_audio.py consome.
"""

import os
import subprocess
import sys

import soundfile as sf
from kokoro_onnx import Kokoro

LINES = [
    "Uma mensagem.",
    "Um número novo.",
    "E um pedido urgente de Pix.",
    "Nessa hora, a pressa costuma esconder o golpe.",
    "Antes de transferir, pare.",
    "Antes do Pix, confirme por outro meio.",
    "Ligue.",
    "Faça uma videochamada.",
    "Confirme com alguém da família.",
    "Recebeu uma mensagem assim?",
    "Antes de fazer o Pix, confirme.",
    "Se precisar de orientação, fale com nossa equipe.",
]

models, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
k = Kokoro(os.path.join(models, "kokoro-v1.0.onnx"), os.path.join(models, "voices-v1.0.bin"))
trim = "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse"
for i, text in enumerate(LINES, 1):
    audio, sr = k.create(text, voice="pf_dora", speed=1.1, lang="pt-br")
    raw = os.path.join(out, f"l{i}.wav")
    sf.write(raw, audio, sr)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-af", trim, os.path.join(out, f"t{i}.wav")], check=True)
    print(i, text)
