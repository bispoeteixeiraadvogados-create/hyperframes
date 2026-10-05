"""Transcrição local (sem ElevenLabs) com saída no formato Scribe do video-use.

Usa faster-whisper com timestamps por palavra e grava
<edit_dir>/transcripts/<stem>.json com o mesmo shape que o
helpers/transcribe.py do video-use produz (lista `words` com entradas
`word` e `spacing`), para que pack_transcripts.py, render.py e
auto_cut.py funcionem sem alteração.

É o fallback quando não há ELEVENLABS_API_KEY. O Scribe continua sendo
superior para preservar hesitações ("é...", "hum"); o prompt inicial abaixo
apenas reduz a normalização do Whisper, não a elimina.

Uso:
    python transcribe_local.py <video> [--edit-dir DIR] [--model medium] [--language pt]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

FILLER_PROMPT = "Hum, é... então, tipo, né, ah, eh, hã. Bom, é, ahn, assim, sabe."


def extract_audio(video: Path, dest: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video), "-map", "0:a:0", "-vn", "-ac", "1",
         "-ar", "16000", "-c:a", "pcm_s16le", str(dest)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def to_scribe(segments, language: str) -> dict:
    words: list[dict] = []
    full_text: list[str] = []
    prev_end: float | None = None
    for seg in segments:
        for w in seg.words or []:
            text = w.word.strip()
            if not text:
                continue
            start, end = round(float(w.start), 3), round(float(w.end), 3)
            if prev_end is not None and start > prev_end:
                words.append({"text": " ", "start": prev_end, "end": start,
                              "type": "spacing", "speaker_id": "speaker_0"})
            words.append({"text": text, "start": start, "end": end, "type": "word",
                          "speaker_id": "speaker_0",
                          "logprob": round(float(getattr(w, "probability", 1.0)), 4)})
            full_text.append(text)
            prev_end = end
    return {
        "language_code": language,
        "language_probability": 1.0,
        "text": " ".join(full_text),
        "words": words,
        "transcriber": "faster-whisper (local fallback)",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("video", type=Path)
    ap.add_argument("--edit-dir", type=Path, default=None)
    ap.add_argument("--model", default="medium",
                    help="tiny, base, small, medium, large-v3 (padrão: medium)")
    ap.add_argument("--language", default="pt")
    ap.add_argument("--force", action="store_true", help="ignora o cache")
    args = ap.parse_args()

    video = args.video.resolve()
    if not video.exists():
        sys.exit(f"vídeo não encontrado: {video}")
    edit_dir = (args.edit_dir or video.parent / "edit").resolve()
    out = edit_dir / "transcripts" / f"{video.stem}.json"
    if out.exists() and not args.force:
        print(f"cached: {out.name}")
        return
    out.parent.mkdir(parents=True, exist_ok=True)

    from faster_whisper import WhisperModel

    t0 = time.time()
    model = WhisperModel(args.model, device="cpu", compute_type="int8")
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "a.wav"
        extract_audio(video, wav)
        segments, _info = model.transcribe(
            str(wav), language=args.language, word_timestamps=True,
            initial_prompt=FILLER_PROMPT, condition_on_previous_text=False,
            vad_filter=False, beam_size=5,
        )
        payload = to_scribe(list(segments), args.language)

    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    n = sum(1 for w in payload["words"] if w["type"] == "word")
    print(f"saved: {out} ({n} palavras, {time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
