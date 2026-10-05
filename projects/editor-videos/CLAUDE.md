# Editor de vídeos: video-use + Hyperframes

Projeto do usuário: ele envia um vídeo (normalmente fala para a câmera, em português) e
recebe de volta o vídeo **sem silêncios e sem repetições** (etapa 1, video-use) e com
**animações e visualizações ligadas ao que é dito** (etapa 2, Hyperframes).

Responda sempre em português. Siga também as preferências do usuário (sem travessão
longo, tom crítico, dizer "você deve verificar isto" quando houver incerteza).

## Início de toda sessão (o container é efêmero)

```bash
bash projects/editor-videos/scripts/setup.sh
```

Instala o video-use em `~/video-use` (commit fixado), as dependências Python e confere
ffmpeg, Node 22+ e `hyperframes@0.8.134`. Leia `~/video-use/SKILL.md` (regras do
video-use) e `skills/talking-head-recut/SKILL.md` deste repositório (etapa 2).

## Como o vídeo chega

O vídeo **nunca** vai para o git. Pasta de trabalho: `~/videos/<nome>/`.

- Link público do Google Drive: `gdown --fuzzy "<link>" -O ~/videos/<nome>/bruto.mp4`
- Link do Dropbox: troque `dl=0` por `dl=1` e use `curl -L -o ...`
- Arquivo anexado ao chat, se o cliente permitir: copie para a pasta de trabalho.
- Não use o conector do Google Drive para vídeo: ele devolve base64 pelo contexto.

## Etapa 1: video-use (cortes)

```bash
S=projects/editor-videos/scripts
$S/pipeline.sh analisar ~/videos/<nome>/bruto.mp4    # transcrição + takes_packed.md + edl.json rascunho
```

1. Leia `edit/takes_packed.md` e `edit/cut_report.md`. O `auto_cut.py` remove pausas
   a partir de 0.35s (envelope de energia, não só a transcrição) e recomeços e
   repetições (mantém a última tentativa). Ele **erra**: revise cada remoção.
   Enumerações e repetições retóricas intencionais devem ficar. Corrija `edl.json` à
   mão quando precisar (cortes sempre em fronteira de palavra, margem 30 a 200ms).
2. Em caso de dúvida num corte, `python ~/video-use/helpers/timeline_view.py <video> <ini> <fim>`.
3. `$S/pipeline.sh cortar ~/videos/<nome>/edit` renderiza `edit/cut.mp4` (fades de 30ms,
   loudnorm -14 LUFS) e prepara `edit/hyperframes/` com o transcript já na linha do
   tempo do corte (não transcreva de novo).
4. Confira duração com `ffprobe` e assista aos pontos de corte (frames ±1s) antes de seguir.

Transcrição: Scribe (ElevenLabs) se houver `ELEVENLABS_API_KEY`; senão faster-whisper
local (`WHISPER_MODEL=medium` por padrão). O Whisper normaliza hesitações ("é...",
"hum"), então elas podem passar; o Scribe as preserva. Avise o usuário quando usar o
fallback. Ajustes: `AUTO_CUT_ARGS="--min-silence 0.5"` para um ritmo mais solto.

## Etapa 2: Hyperframes (animações)

Siga `skills/talking-head-recut/SKILL.md` a partir do passo 5 (corrigir transcript), com
`edit/hyperframes/` como diretório de trabalho. `modelos/exemplo-overlay.html` é uma
composição testada (lower-third, contador, lista que cresce com a fala) para servir de
ponto de partida, não de estilo obrigatório.

- Animações nascem do conteúdo: números viram contadores, listas viram listas que
  crescem palavra a palavra, conceitos viram títulos, comparações viram painéis.
- A animação aterrissa na palavra-chave: comece `duração_da_revelação` antes do timestamp.
- Identidade visual: use `identidade.md` se existir; senão proponha paleta e fonte e
  peça confirmação antes do primeiro render (depois registre em `identidade.md`).
- Antes de renderizar, apresente o storyboard (lista de cards com tempo e conteúdo) e
  espere o OK, salvo se o usuário disser para seguir direto.
- `$S/pipeline.sh animar ~/videos/<nome>/edit` roda lint + render → `edit/final.mp4`.
  0 erros de lint é obrigatório. Render leva ~3x a duração do vídeo neste container.
- Verifique frames do resultado (`ffmpeg -ss T -frames:v 1`) e o áudio
  (`ebur128`) antes de entregar. Você não ouve o vídeo: informe os números.

## Entrega

`edit/final.mp4` via SendUserFile. Se passar do limite do envio, avise e proponha
compressão (`-crf 26`) ou outro canal. Registre a sessão em `edit/project.md`
(formato do video-use).
