# ETAPA 1 — Análise dos vídeos de referência e briefing técnico

Método: `ffprobe` (metadados), `ffmpeg select=scene` (detecção de cortes, limiar 0.3 e 0.08),
`ebur128` (loudness), `silencedetect` (-35 dB / 0.3 s), `signalstats` (luma/saturação no
miolo do quadro) e contact sheets de 1 frame a cada 2 s inspecionados visualmente.

## 1. Dados técnicos medidos

| Ref | Formato | FPS | Duração | Cortes (≥0.08) | Cortes/min | Loudness | LRA | Silêncios >0.3 s |
|-----|---------|-----|---------|----------------|-----------|----------|-----|------------------|
| ref1 | 1276×720 (16:9) | 30 | 50 s | 19 | ~23 | -14.1 LUFS | 4.0 | 0 |
| ref2 | 720×1280 com 16:9 letterbox | 23.976 | 38 s | 8 + jump cuts | ~13+ | -14.4 LUFS | 3.1 | 0 |
| ref3 | 720×1280 com 16:9 letterbox | 30 | 50 s | 9 + jump cuts | ~11+ | -14.7 LUFS | 4.0 | 0 |
| ref4 | 720×1280 (hook 9:16 → 16:9 letterbox) | 23.976 | 70 s | 54 | ~46 | -14.3 LUFS | 5.1 | 1 |
| ref5 | 1276×718 (16:9) | 30 | 91 s | 50 | ~33 | -14.1 LUFS | 12.8 | 1 |

Conclusões objetivas:
- **Todos masterizados em ≈ -14 LUFS** (padrão de redes) → confirma o alvo do módulo de áudio.
- **Zero silêncios** abaixo de -35 dB: há sempre trilha/ambiente por baixo e as pausas da fala
  foram cortadas. O detector de silêncio deve trabalhar **na faixa de voz isolada**, não no mix.
- LRA baixo (3–5 LU) nos talking-heads = voz bem comprimida. ref5 (LRA 12.8) é estilo
  "brand film" com trilha dinâmica e crescendos.
- Jump cuts no mesmo enquadramento são sutis (não aparecem no limiar 0.3), mas existem: ref2/ref3
  alternam entre plano aberto e plano fechado (punch-in) do mesmo take.

## 2. Análise por vídeo

### ref1 — Talking-head + B-roll emocional (16:9, look quente)
- **Corte**: rápido; alterna entrevista (2 pessoas à mesa), close do orador, e B-roll variado
  (celular selfie, escritório, câmera lenta, close de óculos, cenas externas). Smash cuts para
  B-roll no meio de frases; L-cuts (voz continua sobre o B-roll).
- **Legendas**: sans-serif geométrica (estilo Inter/SF Pro), branca, **sem fundo**, sombra leve.
  Padrão: pequena, centralizada na altura do peito. **Variações de impacto**: frases
  grandes no centro com tamanhos mistos e linhas sobrepostas ("A criação é a / **coisa mais** /
  importante que"), palavra isolada gigante ("E…", "pra você."), repetição espalhada pela tela
  ("muita muita muita").
- **Motion graphics**: título de conceito em fonte manuscrita verde-limão ("PRONOIA") acima
  da legenda de definição — estilo "dicionário".
- **Cor**: quente/âmbar, contraste médio, pretos levemente levantados (Yavg 93, Ylow 42).
- **Áudio**: trilha emocional por baixo; final com riso/ambiência.

### ref2 — Entrevista com inserts de filme (9:16 com quadro 16:9)
- **Formato**: vídeo 16:9 centralizado num canvas 9:16 preto (letterbox). Às vezes o quadro
  encolhe e ganha **cantos arredondados** (inserts de filme — cena de *Whiplash*).
- **Corte**: alterna plano médio/fechado do mesmo take (jump cut com punch-in), smash cut para
  cena de filme para ilustrar a ideia ("energia", "sem se esforçar de verdade!").
- **Legendas**: posicionadas no **espaço negativo ao lado do orador** (à direita), não embaixo.
  Tipografia em camadas: palavra/linha menor regular + **palavra-chave bold maior** + linha em
  *itálico* ("Dos 20 aos / **40 anos**", "que elas / ***nunca plantaram***", "*tem tempo*, **energia**").
  1–3 palavras por bloco, palavra a palavra.
- **Cor**: frio/teal com highlights preservados; pretos profundos (Ylow 16).

### ref3 — Talking-head em carro (9:16 com quadro 16:9)
- Mesmo editor/estilo do ref2: letterbox, legendas laterais em espaço negativo,
  palavra-chave em **bold maior** ("**simples.**", "**pessoas**", "**gênio.**", "**execução,**")
  e **palavra futura em cinza** (efeito karaoke inverso: "de formar / executores" com
  "executores" esmaecido até ser dita).
- Posição da legenda varia: topo-direita, centro-direita, embaixo-centro (sobre o peito).
- Corte: jump cuts no mesmo plano, sem transições; ritmo constante.
- Cor: neutra-fria, contraste alto, saturação baixa (Sat 7.8).

### ref4 — Mini-documentário cinematográfico (hook 9:16 → corpo 16:9)
- **Hook** (0–4 s): plano vertical selfie/celular com texto de gancho centralizado bold
  ("Dirigi 642 km pra transformar a história desse artista do sertão em cinema"). Depois
  **smash cut** para o filme em 16:9 letterbox.
- **Corte**: muitos planos (54 cortes), B-roll de paisagem, natureza (gavião), detalhe de mãos e
  artesanato; sequência rápida no final cortada no ritmo da música (**beat cut**: cortes
  espaçados ~0.58 s entre 58–65 s = ~103 BPM).
- **Legendas**: estilo "cinema" — pequenas, embaixo, branca com fundo cinza semi-transparente,
  com ♪ quando é canto. Créditos em lower-third pequenos nos cantos ("ALBERES JUNIOR",
  "ZÉ BEZERRA").
- **Efeitos visuais**: overlay de **película 8 mm/Super 8** (borda de filme com perfuração),
  grão. **Cor**: tons terrosos, céu azul-teal, look de cinema (teal & orange suave).

### ref5 — Brand film escuro (16:9)
- **Corte**: B-roll macro (olho, mãos, óculos, post-its), transição **flash branco / textura de
  tinta** (frame branco com manchas), cortes rápidos em sequência no ritmo da trilha.
- **Legendas**: **monoespaçada pequena** (estilo terminal/máquina de escrever), minúscula,
  frases **divididas em esquerda e direita** do quadro; palavra-chave em **verde** ou **vermelho**.
- **Cor**: low-key, pretos esmagados, highlights quentes laranja vs sombras teal, halation/glow
  nos brilhos, saturação mais alta nas cores pontuais (Sat 13.3).
- **Áudio**: trilha cinematográfica dinâmica (LRA 12.8), voz em off.

## 3. Briefing técnico — o que replicar

### 3.1 Estilos ("presets de estilo" no YAML)
| Preset | Base | Elementos-chave |
|--------|------|-----------------|
| `referencia1` | ref1 | legenda pequena central + frases de impacto grandes multi-tamanho, título manuscrito colorido, look quente |
| `referencia2` | ref2+ref3 | canvas 9:16 com quadro 16:9, legendas laterais em espaço negativo, mix regular/**bold**/*itálico*, palavra futura em cinza, look frio |
| `documentario` | ref4 | hook vertical com texto, letterbox, legenda cinema com fundo, lower-thirds de crédito, grão + borda de película, beat cuts no clímax |
| `brand_dark` | ref5 | legenda monoespaçada dividida esq/dir com keyword colorida, flash branco, low-key teal&orange + glow |
| `viral_reels` | genérico | legendas word-by-word com highlight, pop/slide, zoom em jump cuts, SFX |

### 3.2 Características transversais (valem para todos)
1. Silêncios removidos de forma agressiva na voz; trilha contínua por baixo (nunca silêncio digital).
2. Loudness final -14 LUFS, voz comprimida (LRA 3–5 LU).
3. Legendas 1–4 palavras, sincronizadas por palavra, **ênfase tipográfica por peso/tamanho**
   (mais do que por cor) — cor só em ref1 (título) e ref5 (keyword).
4. Legendas **evitam o rosto**: posição escolhida no espaço negativo do quadro.
5. Grade de cor consistente por vídeo, contraste cinematográfico, saturação contida.
6. Inserts/B-roll em L-cut (voz continua sobre a imagem).

## 4. Funcionalidades × ferramentas

| Funcionalidade | Ferramenta escolhida | Observação |
|----------------|---------------------|------------|
| Decodificar/encodar, filtros, overlay, LUT | **FFmpeg** (lut3d, eq, curves, colorbalance, overlay, zoompan, ass) | engine principal |
| Montagem programática / timeline | **Python + FFmpeg filtergraph** (MoviePy como apoio) | MoviePy é lento para 1080p; FFmpeg faz o render final |
| Análise de frames, rosto, histograma | **OpenCV** (+ **MediaPipe** face detection) | posição do orador p/ legenda e match cut |
| Detecção de silêncio / energia / RMS | **librosa**, **numpy**, **pydub** | |
| Beats / BPM | **librosa.beat** | Beat Cut |
| Transcrição palavra a palavra | **faster-whisper** (+ openai-whisper como fallback) | PT-BR, `word_timestamps=True` |
| Legendas animadas | **ASS/SSA (libass via FFmpeg)** gerado em Python (`pysubs2`) | suporta karaoke `\k`, `\t` (pop/scale), `\move` (slide), fade, cores por palavra |
| Títulos/elementos gráficos | **Pillow + NumPy** → PNG/sequência com alpha | fontes manuscritas e monoespaçadas (Google Fonts, OFL) |
| NLP de palavras-chave / tom | **spaCy `pt_core_news_sm`** + regras | substantivos, verbos, números, conectivos dramáticos |
| Correção de cor primária | **OpenCV/NumPy** (análise) + FFmpeg `eq/colorbalance/curves` | gray-world WB, normalização entre clipes |
| Gradação / LUT | **colour-science** para gerar `.cube` + FFmpeg `lut3d` | 5 LUTs geradas para os presets |
| Redução de ruído | **noisereduce** (+ FFmpeg `afftdn`) | |
| EQ, de-esser, compressão, hum | FFmpeg `highpass`, `equalizer`, `deesser`, `acompressor`, `bandreject` | ou **pedalboard** (Spotify, GPL-3) |
| Loudness -14 LUFS | FFmpeg `loudnorm` (2 passes) + **pyloudnorm** p/ verificação | |
| Ducking | FFmpeg `sidechaincompress` ou envelope calculado em numpy | |
| SFX | banco local categorizado (gerado/CC0) + **Freesound API** opcional | |
| Trilha | banco local royalty-free + Freesound API opcional | |
| Config | **PyYAML** | tudo parametrizado |
| CLI | **argparse/typer** + **rich** para logs | `python editar.py input.mp4 --estilo referencia2 --plataforma reels` |

## 5. Avisos honestos de viabilidade

1. **B-roll e inserts de filme** (ref1, ref2, ref4, ref5) são decisões criativas com material
   externo. O pipeline **não consegue inventar B-roll**. Alternativa: pasta `broll/` com clipes
   etiquetados por palavra-chave; o pipeline sugere/insere quando a transcrição casar
   (L-cut automático). Sem B-roll, aplica-se punch-in/zoom para variar o plano.
2. **Remotion** tem licença própria (paga para empresas acima de 3 pessoas) e **Manim** exige
   Cairo/LaTeX e é voltado a animação matemática. Para o estilo destas referências
   (tipografia cinética), **ASS + Pillow** entrega o mesmo resultado com menos dependências.
   Manim fica opcional.
3. **Suno** não tem API oficial pública; os pesos do **MusicGen** são CC-BY-NC (uso
   **não comercial**). Recomendação: banco local royalty-free (ex.: Pixabay Music,
   YouTube Audio Library, Free Music Archive CC0/CC-BY) + Freesound API (requer chave gratuita).
   No ambiente de teste vou gerar trilhas/SFX sintéticos para validar o pipeline.
4. **Match cut** automático só funciona quando há material com composição parecida; será
   detectado por histograma + posição do rosto e **ignorado quando não houver**, como pedido.
5. **"Continuidade visual" do orador** (gesto/expressão durante o silêncio) é aproximada por
   fluxo óptico/diferença de frames no OpenCV — é heurística, por isso o modo de revisão
   manual existe.
6. **Smash cut / clímax / punch line** por NLP simples é heurístico (marcadores lexicais,
   números, pontuação, pico de energia). Um LLM opcional pode refinar, mas não será obrigatório.
7. As referências chegaram já comprimidas (Instagram, ~0.5–0.8 Mbps, 720p). O teste da
   Etapa 12 vai usá-las como entrada, mas a qualidade final é limitada pela fonte.
