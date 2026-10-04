# Bispo & Teixeira: design spec do motion "Crédito Rural"

Fonte da verdade: Design System Bispo & Teixeira enviado pelo cliente (guia visual resumido para
criação com IA) e o perfil do Instagram @bispoeteixeiraadvogados. Este arquivo transcreve as
regras da marca e registra as extensões específicas desta peça.

## DNA da marca

Clean + Human + Editorial. Minimalista, contemporâneo e confiável. Visual premium, sóbrio e
acolhedor. Leitura clara no celular. Elegância sem rigidez excessiva.
Tom: humano, confiável, elegante, técnico, próximo, moderno.

## Paleta da marca (tokens)

| Token           | Hex       | Uso                                                                 |
| --------------- | --------- | ------------------------------------------------------------------- |
| `--bt-midnight` | `#081A35` | fundo profundo, bordas, vinheta                                     |
| `--bt-navy`     | `#0B1F4B` | base da identidade, fundo da tela de marca                          |
| `--bt-sand`     | `#F4EDE2` | papel, documentos, superfícies claras                               |
| `--bt-white`    | `#FAF8F4` | tipografia principal (warm white, nunca #FFF puro)                  |
| `--bt-gold`     | `#D4A77C` | acento em detalhes (filetes, ponto final, rótulos). Nunca dominante |

## Extensões desta peça

| Token           | Hex       | Papel                                                   |
| --------------- | --------- | ------------------------------------------------------- |
| `--rural-olive` | `#3E4B2C` | oliva escuro: folhas, silhuetas, camada rural profunda  |
| `--rural-crop`  | `#2F5A3E` | verde lavoura: fileiras próximas                        |
| `--rural-sage`  | `#8FA876` | verde natural suave: brilho de borda, curvas de nível   |
| `--alert-red`   | `#E5333F` | vermelho funcional de alerta (só na pressão financeira) |
| `--alert-deep`  | `#7A0E18` | vinheta vermelha profunda                               |

Progressão: navy + verde + branco (abertura) → + dourado (escalada) → navy + vermelho + branco
(explosão) → navy + oliva + warm white + dourado discreto (marca).

## Contexto rural: bananal (v2)

Bananicultura irrigada (região de Jaíba). Bananeira real, nunca folhagem tropical genérica: pseudocaule
verde-marrom com manchas escuras e bainhas secas, folhas de 1,5 a 2,2 m com nervura central clara e
rasgos de vento, folhas velhas amarelando e secas penduradas, cachos verdes. Crepúsculo navy com
contraluz dourado discreto, névoa que se dissolve no fundo navy da composição. O bananal é camada de
contexto: os números continuam protagonistas.

## Tipografia

- Títulos e números heróis: **Bodoni Moda** (Bodoni do Google Fonts, variável wght 400 a 900,
  opsz 6 a 96), algarismos tabulares (`tnum`) no contador. O guia da marca indica
  "Bodoni / Cormorant Garamond".
- Subtítulos, fragmentos cinéticos e legendas em caixa alta: **Montserrat** SemiBold/Bold.
- Microdados financeiros: **Inter** com `tnum` (texto corrido "Montserrat / Inter Regular").
- Todas as fontes embutidas localmente em `assets/fonts/` (woff2, subset latin), sem rede no render.

## Regras de estilo (do guia)

- Fundos escuros, cartões claros e contraste elegante. Composição com respiro.
- Ícones lineares e formas discretas. Textura sutil, nunca pesada.
- Hierarquia vertical clara. Título forte + apoio objetivo + CTA discreto.
- Evitar: 3D com brilhos chamativos, dourado dominante, visual artificial ou genérico, poluição
  visual, cara de panfleto, excesso de texto sem hierarquia.

## Logo

Usar somente `assets/brand/bt-logo-white.png` (versão oficial branca, fundo transparente), sem
redesenho, recoloração ou distorção. Aplicação sobre navy.

## Zonas seguras (9:16, 1080x1920)

Conteúdo-chave dentro do title-safe (x 108 a 972, y 192 a 1728). Para Reels, CTA e logo ficam
acima de y 1500 para não colidir com a legenda e os botões da interface.
