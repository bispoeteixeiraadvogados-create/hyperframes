"""Converte a transcrição das fontes para a linha do tempo do vídeo já cortado.

Lê <edit>/edl.json e <edit>/transcripts/*.json (formato Scribe do video-use)
e grava um array plano [{text, start, end}, ...] em tempo de SAÍDA, que é o
transcript.json que o fluxo talking-head-recut do Hyperframes espera. Assim a
segunda etapa não precisa transcrever de novo o vídeo cortado.

    output_time = word.start - range.start + range_offset   (Hard Rule 5)

Uso:
    python remap_transcript.py --edit-dir DIR -o DIR/hyperframes/transcript.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--edit-dir", type=Path, required=True)
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args()

    edit_dir = args.edit_dir.resolve()
    edl = json.loads((edit_dir / "edl.json").read_text())
    cache: dict[str, list[dict]] = {}
    out: list[dict] = []
    offset = 0.0
    for r in edl["ranges"]:
        src = r["source"]
        if src not in cache:
            data = json.loads((edit_dir / "transcripts" / f"{src}.json").read_text())
            cache[src] = [w for w in data.get("words", []) if w.get("type", "word") == "word"]
        start, end = float(r["start"]), float(r["end"])
        for w in cache[src]:
            ws, we = float(w["start"]), float(w.get("end", w["start"]))
            # Sobreposição, não ponto médio: o Whisper estica palavras sobre o
            # silêncio vizinho, e o ponto médio pode cair fora do trecho mantido.
            # O limiar de 0.08s fica acima das margens de corte (pad), então a
            # palavra removida ao lado não entra.
            overlap = min(we, end) - max(ws, start)
            if overlap < min(0.08, 0.5 * max(we - ws, 0.01)):
                continue
            out.append({
                "text": w["text"].strip(),
                "start": round(max(ws, start) - start + offset, 3),
                "end": round(min(we, end) - start + offset, 3),
            })
        offset += end - start

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"{len(out)} palavras → {args.output} (duração de saída {offset:.2f}s)")


if __name__ == "__main__":
    main()
