"""Rascunho de EDL do video-use: remove silêncios, repetições e hesitações.

Combina duas fontes, porque nenhuma basta sozinha:
  * a transcrição por palavra (Scribe ou faster-whisper) diz O QUE foi dito
    e onde cada palavra fica, o que permite detectar recomeços e repetições;
  * o envelope de energia do áudio diz ONDE há silêncio de fato. O Whisper
    costuma esticar a última palavra de uma frase sobre o silêncio seguinte,
    então só a transcrição deixaria pausas longas no corte.

A saída é um rascunho: <edit>/edl.json no formato do helpers/render.py do
video-use e <edit>/cut_report.md com cada trecho removido e o motivo. O
editor (Claude) revisa o relatório contra takes_packed.md e ajusta o EDL
antes de renderizar. Nenhum corte cai dentro de uma palavra (Hard Rule 6) e
todo corte recebe margem (Hard Rule 7).

Uso:
    python auto_cut.py <video> [<video> ...] --edit-dir DIR
        [--min-silence 0.35] [--pad-pre 0.06] [--pad-post 0.10]
        [--sentence-pad 0.18] [--no-repetitions] [--no-fillers]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

SR = 16000
HOP = 0.01  # resolução do envelope (s)
FILLERS = {"hum", "hmm", "hm", "hã", "ahn", "ah", "eh", "uh", "uhm", "um", "éé", "ééé", "ããã", "mmm"}
SENTENCE_END = re.compile(r"[.!?…]$")


# ---------------------------------------------------------------- áudio ----


def load_envelope(video: Path) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video), "-map", "0:a:0", "-ac", "1",
         "-ar", str(SR), "-f", "s16le", "-"],
        check=True, capture_output=True,
    ).stdout
    pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    hop = int(SR * HOP)
    n = len(pcm) // hop
    frames = pcm[: n * hop].reshape(n, hop)
    rms = np.sqrt((frames ** 2).mean(axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    # suaviza 50ms para não picotar consoantes
    k = 5
    return np.convolve(db, np.ones(k) / k, mode="same")


def speech_intervals(db: np.ndarray, min_silence: float, threshold_db: float | None) -> tuple[list[tuple[float, float]], float]:
    """Intervalos com fala. Limiar adaptativo: piso de ruído + 30% da faixa dinâmica."""
    if threshold_db is None:
        floor = float(np.percentile(db, 10))
        loud = float(np.percentile(db, 95))
        threshold_db = max(floor + 0.30 * (loud - floor), -55.0)
    voiced = db > threshold_db
    intervals: list[tuple[float, float]] = []
    start = None
    for i, v in enumerate(voiced):
        if v and start is None:
            start = i
        elif not v and start is not None:
            intervals.append((start * HOP, i * HOP))
            start = None
    if start is not None:
        intervals.append((start * HOP, len(voiced) * HOP))
    # funde pausas curtas (< min_silence): são respiração dentro da frase
    merged: list[tuple[float, float]] = []
    for s, e in intervals:
        if merged and s - merged[-1][1] < min_silence:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    # descarta estalos isolados (< 60ms)
    return [(s, e) for s, e in merged if e - s >= 0.06], threshold_db


# ------------------------------------------------------------ palavras ----


@dataclass
class Word:
    idx: int
    text: str
    start: float
    end: float
    norm: str
    removed_by: str | None = None
    extra: dict = field(default_factory=dict)


def normalize(t: str) -> str:
    t = unicodedata.normalize("NFKC", t).lower()
    return re.sub(r"[^\w%]+", "", t)


def load_words(transcript: Path) -> list[Word]:
    data = json.loads(transcript.read_text())
    words = data["words"] if isinstance(data, dict) else data
    out: list[Word] = []
    for w in words:
        if isinstance(data, dict) and w.get("type", "word") != "word":
            continue
        text = (w.get("text") or "").strip()
        if not text or w.get("start") is None:
            continue
        out.append(Word(len(out), text, float(w["start"]), float(w.get("end", w["start"])), normalize(text)))
    return out


def snap_to_speech(words: list[Word], speech: list[tuple[float, float]]) -> None:
    """Recorta cada palavra ao intervalo de fala com que mais se sobrepõe."""
    for w in words:
        best, best_ov = None, 0.0
        for s, e in speech:
            if e < w.start - 0.5:
                continue
            if s > w.end + 0.5:
                break
            ov = min(e, w.end) - max(s, w.start)
            if ov > best_ov:
                best, best_ov = (s, e), ov
        if best is None:
            w.extra["no_energy"] = True
            continue
        w.start = max(w.start, best[0])
        w.end = min(w.end, best[1])
        if w.end <= w.start:
            w.end = w.start + 0.05


def mark_fillers(words: list[Word]) -> None:
    for w in words:
        # Só formas inequívocas: "é", "a", "o", "e" são palavras em português e
        # ficam. Vogal alongada ("ééé", "aaah") e "hum"/"hmm" saem.
        if w.norm in FILLERS or re.fullmatch(r"h?u+m+|h?m{2,}|([aeiouáéíóúâêôãõ])\1{2,}h*", w.norm or "x"):
            w.removed_by = "hesitação"


def mark_repetitions(words: list[Word], window: int = 14, max_span_s: float = 10.0) -> None:
    """Recomeços: um trecho dito, abandonado e dito de novo. Mantém a ÚLTIMA tentativa.

    Para cada posição i procura j > i (até `window` palavras à frente) onde a
    sequência a partir de j repete a sequência a partir de i por k palavras.
    Aceita se k >= 3 cobrindo ao menos 60% do trecho abandonado, ou k >= 2 com
    o trecho abandonado curto (<= 3 palavras), ou k == 1 com a mesma palavra
    repetida imediatamente (gagueira).
    """
    alive = [w for w in words if w.removed_by is None]
    toks = [w.norm for w in alive]
    n = len(toks)
    i = 0
    while i < n:
        hit = None
        for j in range(i + 1, min(n, i + 1 + window)):
            k = 0
            while j + k < n and i + k < j and toks[i + k] == toks[j + k] and toks[i + k]:
                k += 1
            span = j - i
            # A repetição tem de cobrir a maior parte do trecho abandonado. Sem
            # isso, enumerações paralelas ("o primeiro motivo é a X ... o segundo
            # motivo é a Y") seriam tomadas por recomeço e cortadas.
            ok = (k >= 3 and k >= 0.6 * span) or (k >= 2 and span <= 3) \
                or (k == 1 and span == 1 and len(toks[i]) > 1)
            if ok and alive[j].start - alive[i].start <= max_span_s:
                hit = j
                break
        if hit is not None:
            label = " ".join(w.text for w in alive[i:hit])
            for w in alive[i:hit]:
                w.removed_by = "repetição"
                w.extra["repeat_of"] = label
            i = hit
        else:
            i += 1


# ----------------------------------------------------------------- EDL ----


def build_ranges(words: list[Word], speech: list[tuple[float, float]], args, duration: float) -> list[dict]:
    kept = [w for w in words if w.removed_by is None]
    if not kept:
        return []

    def silent_between(a: float, b: float) -> bool:
        """Há silêncio >= min_silence entre a e b (pelo envelope)?"""
        if b - a < args.min_silence:
            return False
        gaps = []
        cursor = a
        for s, e in speech:
            if e <= a or s >= b:
                continue
            gaps.append(max(0.0, min(s, b) - cursor))
            cursor = max(cursor, e)
        gaps.append(max(0.0, b - cursor))
        return max(gaps) >= args.min_silence

    groups: list[list[Word]] = [[kept[0]]]
    for prev, cur in zip(kept, kept[1:]):
        removed_between = cur.idx != prev.idx + 1
        if removed_between or silent_between(prev.end, cur.start):
            groups.append([cur])
        else:
            groups[-1].append(cur)

    ranges = []
    for g in groups:
        first, last = g[0], g[-1]
        post = args.sentence_pad if SENTENCE_END.search(last.text) else args.pad_post
        ranges.append({"start": max(0.0, first.start - args.pad_pre),
                       "end": min(duration, last.end + post),
                       "quote": " ".join(w.text for w in g)})
    # não deixa margens sobreporem: divide o vão ao meio
    for a, b in zip(ranges, ranges[1:]):
        if a["end"] > b["start"]:
            mid = (a["end"] + b["start"]) / 2
            a["end"], b["start"] = mid, mid
    # junta trechos contíguos (corte de 0s não serve para nada)
    merged = [ranges[0]]
    for r in ranges[1:]:
        if r["start"] - merged[-1]["end"] < 0.02:
            merged[-1]["end"] = r["end"]
            merged[-1]["quote"] += " " + r["quote"]
        else:
            merged.append(r)
    return [r for r in merged if r["end"] - r["start"] >= 0.12]


def probe_duration(video: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(video)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def fmt(t: float) -> str:
    return f"{int(t // 60):02d}:{t % 60:05.2f}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("videos", type=Path, nargs="+")
    ap.add_argument("--edit-dir", type=Path, required=True)
    ap.add_argument("--min-silence", type=float, default=0.35,
                    help="pausas a partir deste tamanho são cortadas (s)")
    ap.add_argument("--threshold-db", type=float, default=None,
                    help="limiar de silêncio em dBFS (padrão: adaptativo)")
    ap.add_argument("--pad-pre", type=float, default=0.06)
    ap.add_argument("--pad-post", type=float, default=0.10)
    ap.add_argument("--sentence-pad", type=float, default=0.18,
                    help="margem após fim de frase, para o corte respirar")
    ap.add_argument("--no-repetitions", action="store_true")
    ap.add_argument("--no-fillers", action="store_true")
    ap.add_argument("--grade", default="none")
    args = ap.parse_args()

    edit_dir = args.edit_dir.resolve()
    edl = {"version": 1, "sources": {}, "ranges": [], "grade": args.grade, "overlays": []}
    report = ["# Relatório de cortes (rascunho automático)", "",
              "Revise antes de renderizar. Cada item removido traz o motivo.", ""]
    total_in = total_out = 0.0

    for video in args.videos:
        video = video.resolve()
        stem = video.stem
        tpath = edit_dir / "transcripts" / f"{stem}.json"
        if not tpath.exists():
            sys.exit(f"transcrição ausente: {tpath} (rode transcribe primeiro)")
        duration = probe_duration(video)
        db = load_envelope(video)
        speech, thr = speech_intervals(db, args.min_silence, args.threshold_db)
        words = load_words(tpath)
        snap_to_speech(words, speech)
        if not args.no_fillers:
            mark_fillers(words)
        if not args.no_repetitions:
            mark_repetitions(words)
        ranges = build_ranges(words, speech, args, duration)

        edl["sources"][stem] = str(video)
        kept_s = sum(r["end"] - r["start"] for r in ranges)
        total_in += duration
        total_out += kept_s
        for r in ranges:
            edl["ranges"].append({"source": stem, "start": round(r["start"], 3),
                                  "end": round(r["end"], 3), "quote": r["quote"],
                                  "reason": "auto: fala mantida"})

        report += [f"## {stem}", "",
                   f"- duração original: {duration:.2f}s, mantido: {kept_s:.2f}s "
                   f"({100 * (1 - kept_s / duration):.0f}% removido)",
                   f"- limiar de silêncio: {thr:.1f} dBFS, pausa mínima cortada: {args.min_silence}s",
                   f"- trechos mantidos: {len(ranges)}", ""]
        removed = [w for w in words if w.removed_by]
        if removed:
            report += ["### Palavras removidas", "", "| tempo | motivo | texto |", "|---|---|---|"]
            run: list[Word] = []
            for w in removed + [None]:  # type: ignore[list-item]
                if w is not None and run and w.idx == run[-1].idx + 1 and w.removed_by == run[-1].removed_by:
                    run.append(w)
                    continue
                if run:
                    report.append(f"| {fmt(run[0].start)} | {run[0].removed_by} | "
                                  f"{' '.join(x.text for x in run)} |")
                run = [w] if w is not None else []
            report.append("")
        gaps = []
        for a, b in zip(ranges, ranges[1:]):
            if b["start"] - a["end"] >= args.min_silence:
                gaps.append((a["end"], b["start"]))
        if gaps:
            report += ["### Silêncios cortados", "",
                       ", ".join(f"{fmt(s)} a {fmt(e)} ({e - s:.1f}s)" for s, e in gaps), ""]

    edl["total_duration_s"] = round(total_out, 3)
    edit_dir.mkdir(parents=True, exist_ok=True)
    (edit_dir / "edl.json").write_text(json.dumps(edl, indent=2, ensure_ascii=False))
    (edit_dir / "cut_report.md").write_text("\n".join(report), encoding="utf-8")
    print(f"edl: {edit_dir / 'edl.json'}  ({len(edl['ranges'])} trechos)")
    print(f"duração: {total_in:.1f}s → {total_out:.1f}s")
    print(f"relatório: {edit_dir / 'cut_report.md'}")


if __name__ == "__main__":
    main()
