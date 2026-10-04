"""Gera e trata a narracao pt-BR (Kokoro v1.0, voz pm_alex), offline.

Uso:  python scripts/tts.py
Requer: kokoro-onnx, soundfile, scipy, numpy, pyloudnorm e os arquivos do modelo em
~/.cache/hyperframes/tts (baixados pelo CLI do HyperFrames ou manualmente do release
model-files-v1.0 de thewh1teagle/kokoro-onnx).

Cadeia de tratamento: reamostragem 24k->48k, passa-altas 75 Hz, corte de 2 dB em 320 Hz,
presenca +2,5 dB em 3,2 kHz, compressao suave 3:1, sala curta e discreta, normalizacao
para -18 LUFS por clipe. Os arquivos tratados vao para assets/audio/source/ e o
sound_design.py grava as versoes calibradas (mesmo ganho do mix) em assets/audio/.
"""

import json
import os
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(__file__))
import dsp  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "assets", "audio", "source")
MODEL = os.path.expanduser("~/.cache/hyperframes/tts/models/kokoro-v1.0.onnx")
VOICES = os.path.expanduser("~/.cache/hyperframes/tts/voices/voices-v1.0.bin")

TAKES = [
    ("vo-s1", "Quando a dívida cresce mais rápido que a sua capacidade de pagamento, "
              "o problema deixa de ser apenas o valor da parcela.", 1.10),
    ("vo-s2", "É preciso entender o que está fazendo essa dívida crescer.", 1.08),
    ("vo-s3", "Crédito rural exige análise.", 0.95),
]


def treat(x, sr):
    x = dsp.resample(x, sr, dsp.SR)
    x = dsp.filt(x, "highpass", 75, q=0.7)
    x = dsp.filt(x, "peak", 320, q=1.0, gain_db=-2.0)
    x = dsp.filt(x, "peak", 3200, q=0.8, gain_db=2.5)
    x = dsp.filt(x, "highshelf", 8500, q=0.7, gain_db=1.5)
    x = dsp.compress(x, thr_db=-24, ratio=3.0, attack=0.004, release=0.09, makeup_db=4)
    ir = dsp.make_ir(decay=0.45, predelay=0.006, seed=21, lp=6500, hp=200)
    y = dsp.reverb(x, ir, wet=0.07)[: len(x)]
    target = -18.0
    for _ in range(3):
        y = y * 10 ** ((target - dsp.lufs(y)) / 20)
        y = dsp.limiter(y, ceiling_db=-6.0, lookahead=0.003, release=0.05)
    return y


def main():
    from kokoro_onnx import Kokoro

    os.makedirs(OUT, exist_ok=True)
    k = Kokoro(MODEL, VOICES)
    report = {}
    for name, text, speed in TAKES:
        a, sr = k.create(text, voice="pm_alex", speed=speed, lang="pt-br")
        y = treat(np.asarray(a, dtype=np.float64), sr)
        path = os.path.join(OUT, f"{name}.wav")
        dsp.write_wav(path, y)
        report[name] = {"text": text, "speed": speed, "duration": round(len(y) / dsp.SR, 3),
                        "lufs": round(dsp.lufs(y), 2), "peak_db": round(dsp.db(y), 2)}
        print(name, report[name])
    with open(os.path.join(OUT, "vo-report.json"), "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
