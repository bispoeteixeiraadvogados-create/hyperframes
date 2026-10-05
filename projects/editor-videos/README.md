# Editor de vídeos (video-use + Hyperframes)

Fluxo em duas etapas para vídeos de fala:

1. **video-use** ([browser-use/video-use](https://github.com/browser-use/video-use)):
   transcreve com tempo por palavra, remove silêncios, hesitações e repetições, e
   renderiza o corte com fades de 30ms e loudness normalizado.
2. **Hyperframes** (este repositório, fluxo `talking-head-recut`): sobre o vídeo cortado,
   adiciona títulos, contadores, listas e painéis sincronizados com a fala.

```
bruto.mp4 → transcrição → auto_cut (rascunho) → revisão → cut.mp4
          → transcript remapeado → composição HTML/GSAP → final.mp4
```

## Scripts

| Script                           | Função                                                                         |
| -------------------------------- | ------------------------------------------------------------------------------ |
| `scripts/setup.sh`               | instala video-use (commit fixado), dependências e confere o Hyperframes        |
| `scripts/pipeline.sh`            | `analisar`, `cortar`, `animar`                                                 |
| `scripts/transcribe_local.py`    | transcrição local (faster-whisper) no formato Scribe, sem chave de API         |
| `scripts/auto_cut.py`            | rascunho do EDL: silêncio pelo envelope de áudio + repetições pela transcrição |
| `scripts/remap_transcript.py`    | leva o transcript para a linha do tempo do vídeo cortado                       |
| `scripts/prepare_hyperframes.sh` | monta `edit/hyperframes/` (fontes, GSAP, vídeo com GOP denso)                  |
| `modelos/exemplo-overlay.html`   | composição de exemplo testada                                                  |

## Limitações conhecidas

- Sem chave da ElevenLabs a transcrição é local (Whisper), que tende a apagar
  hesitações como "é..." e "hum". Silêncios e repetições continuam sendo detectados.
- A detecção de repetição é heurística. O relatório `cut_report.md` lista cada remoção
  para revisão; enumerações paralelas são preservadas por regra, mas casos ambíguos
  exigem decisão editorial.
- Vídeos não são versionados. Envie por link público (Drive/Dropbox).
