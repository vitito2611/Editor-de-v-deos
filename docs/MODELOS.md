# Modelos de edição (`--estilo`) — com as preferências do cliente

Uso: `python editar.py bruto.mp4 --estilo <modelo> --plataforma <reels|tiktok|shorts|youtube|youtube_vertical>`

## Regras que valem para TODOS os modelos
- Legenda **sem cores** (só branco; variação de fonte, peso, tamanho e itálico).
- SFX "plin"/brilho (Magic sparkle whoosh) **vetado para sempre** (`sfx.proibidos`).
- Nada de cenas genéricas sem relação com a fala (ex.: pizza, carteira).
- Fotos de pessoas/marcas citadas só com licença (Openverse/Wikimedia, Mixkit) — nunca Google.
- Trilhas Mixkit royalty-free; música em alta o cliente põe no app.
- Sempre **duas versões**: com trilha e sem trilha. Preview + contact sheet antes do final.
- iPhone HDR 4K60 → SDR 1440p30 automático. Áudio a -14 LUFS.
- Brutos vêm do Drive ("Vídeos não editados"); entrega pelo chat (≤ 30 MB).
- Glossário por vídeo em `transcricao.correcoes` (ex.: Zuckenberg → Zuckerberg).
- **Remotion ligado em todos os modelos** (`remotion.ativo`): cards de frase, contador, título de conceito
  e gancho animados em React, fundo transparente, sempre brancos. Sem Node → mesmos elementos em ASS.
- Extra opcional: ângulos por IA (Seedance/Higgsfield — precisa de créditos e rede).

## 1. `viral_reels` ⭐ (aprovado — v2 do vídeo 1)
Legenda `dinamico_branco` logo abaixo do rosto; troca de plano a cada ≤ 2,6 s (punch-ins
1.0/1.16/1.06/1.26/1.10); B-roll, fotos e cards nos momentos-chave (`dinamismo`); whip pan
(≥ 12 s entre si) + glitch; SFX no nível da v2; pausas de 0,22 s; look `vibrante`;
trilha energética que troca a cada 26–36 s com crossfade.
Remotion: animação `pop` (mola elástica), palavra-chave gigante em CAIXA ALTA.

## 2. `referencia1` — talking-head emocional
Legenda pequena no peito + frases de impacto cinéticas; título de conceito manuscrito
(Permanent Marker, branco); punch-in progressivo; reaction cut; look quente; trilha emocional.
Remotion: animação `suave` (sobe com desfoque), título manuscrito Permanent Marker.

## 3. `referencia2` — 16:9 dentro do 9:16
Letterbox, legendas laterais no espaço negativo misturando regular/bold/itálico (palavra
seguinte em cinza claro); punch-in alternado 1.16; look frio; trilha informativa.
Remotion: animação `deslize` (entra da esquerda).

## 4. `documentario` — mini-doc
Gancho com texto, letterbox, legenda de cinema, grão + vinheta, beat cuts, look terroso,
sem SFX, trilha emocional.
Remotion: animação `suave`, letras espaçadas, sem caixa alta.

## 5. `brand_dark` — brand film escuro
Legenda dinâmica branca em fonte mono (JetBrains Mono) logo abaixo do rosto, flash
branco nas transições, grão + vinheta, low-key teal & orange, trilha sombria.
Remotion: animação `digitacao` (máquina de escrever) em JetBrains Mono.
