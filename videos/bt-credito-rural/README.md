# Bispo & Teixeira: Crédito Rural (Reels / Stories 9:16)

Motion graphic de ~15,5 s, 1080x1920, 30 fps, construído em HyperFrames (HTML + GSAP, render
determinístico). Tema: crédito rural, escalada da dívida e perda de controle financeiro.

## Estrutura

| Caminho                                               | O que é                                                                  |
| ----------------------------------------------------- | ------------------------------------------------------------------------ |
| `index.html`                                          | Raiz: duas cenas (sub-composições) e cinco faixas de áudio               |
| `compositions/debt-world.html`                        | Cena 1 (0 a 11,2 s): rush, escalada, pressão, parede, congelamento       |
| `compositions/resolve.html`                           | Cena 2 (11,2 a 15,5 s): "Crédito rural exige análise." e tela de marca   |
| `assets/js/bt-field.js`                               | Lavoura em canvas (função pura do tempo), usada pelas duas cenas         |
| `assets/audio/*.wav`                                  | Narração (3 clipes), trilha e efeitos calibrados (gerados pelos scripts) |
| `assets/audio/source/`                                | Narração tratada (gerada por `tts.py`, entrada do `sound_design.py`)     |
| `assets/brand/bt-logo-white.png`                      | Logo oficial enviado pelo cliente, sem alterações                        |
| `assets/fonts/`                                       | Bodoni Moda, Montserrat e Inter (woff2 local, sem rede no render)        |
| `scripts/`                                            | Geração reprodutível de narração, trilha, efeitos e texturas             |
| `BRIEF.md`, `DESIGN.md`, `SCRIPT.md`, `STORYBOARD.md` | Briefing, regras de marca, narração e batidas                            |

## Renderizar

```bash
npx hyperframes check                                   # gate: lint + runtime + layout + contraste
npx hyperframes render --quality delivery --output renders/BT_Credito_Rural_Reels.mp4
```

## Áudio (reprodutível)

Requer Python 3 com `numpy scipy soundfile pyloudnorm kokoro-onnx` e o modelo Kokoro v1.0 em
`~/.cache/hyperframes/tts` (`npx hyperframes doctor` indica como instalar).

```bash
python scripts/tts.py            # narração pt-BR (Kokoro pm_alex) -> assets/audio/source/
python scripts/sound_design.py   # trilha + efeitos sincronizados, mix calibrado em -14 LUFS
python scripts/check_mix.py      # relação voz/fundo na faixa de inteligibilidade (1 a 4 kHz)
python scripts/textures.py       # grão de filme e curvas de nível
```

O mixer do HyperFrames soma as faixas sem limitador, por isso `sound_design.py` aplica a mesma
curva de ganho de barramento a voz, trilha e efeitos: a soma fica em -14 LUFS com pico < -1 dBFS.
Os `.wav` de áudio não são versionados: o repositório rejeita binários acima de 500 KB fora do
Git LFS. Gere-os com `python scripts/tts.py && python scripts/sound_design.py` antes de renderizar
(a síntese é determinística). Use stems WAV: em teste, stems AAC levaram o render 0.8.124 a aplicar
uma correção de true peak de -5,6 dB no mix inteiro, embora a soma dos mesmos stems no FFmpeg
ficasse em -1,0 dBTP.

## Trocar a narração por locução humana (recomendado antes de veicular)

1. Grave as três frases de `SCRIPT.md` separadamente (WAV 48 kHz).
2. Rode `python scripts/tts.py` uma vez (cria `assets/audio/source/`) e substitua
   `assets/audio/source/vo-s1.wav`, `vo-s2.wav`, `vo-s3.wav` pela gravação (perto de -18 LUFS).
3. Se as durações mudarem, ajuste os tempos em `scripts/timeline.json`, nas constantes `T` de
   `compositions/debt-world.html` e `compositions/resolve.html`, e os `data-start`/`data-duration`
   dos clipes de voz em `index.html`. A narração define o relógio do filme.
4. Rode `python scripts/sound_design.py` para recalibrar o mix e `npx hyperframes check`.
