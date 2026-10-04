---
workflow: general-video
flow: automation
storyboard: no
message: "Em 25 anos o lucro dos cinco maiores bancos do Brasil saltou de menos de R$ 2 bi para dezenas de bilhões cada, com quedas nas crises e altas nos ciclos de juros."
destination: youtube
aspect: 1920x1080
language: pt-BR
length: 30s
angle: narrative
---

## Intent

Vídeo animado de exatamente 30 segundos, em português do Brasil, sobre a evolução
dos resultados dos cinco maiores bancos do Brasil (por ativos totais) de 2000 até
o ano mais recente com balanço anual fechado (2025). Gráfico de linhas animado
desenhado da esquerda para a direita, Selic anual tracejada no eixo secundário,
selos dos bancos na ponta de cada linha, pilha de moedas de ouro à direita e
balões de eventos marcantes. Fundo azul-marinho, cores das marcas, tipografia limpa.

Pedido original do usuário (resumo fiel): usar apenas dados reais pesquisados;
destacar 2000, 2008, 2015-2016, 2020, 2022 e o ano mais recente; incluir
privatizações e fusões, crises, pandemia, ciclos da Selic, recessões e
crescimento; nota final com as fontes.

## Customizations

- Métrica: lucro líquido (o pedido autoriza o lucro quando "faturamento" não está
  disponível; bancos não divulgam faturamento comparável).
- Selic: meta vigente no fim de cada ano (Copom), linha tracejada que muda de cor
  em alta e em queda e pulsa nos picos e vales.
- Moedas de ouro: soma anual do lucro dos cinco bancos nos anos com dado verificado.
- Narração: textos na tela (TTS local indisponível nesta sessão).

## Notes

- Valores nominais, sem correção pela inflação.
- Caixa e Santander só têm série verificada a partir de 2008.
- Todas as fontes estão em `FONTES.md`; o roteiro cena a cena está em `ROTEIRO.md`.
