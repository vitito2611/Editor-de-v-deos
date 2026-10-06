# Editor de vídeos — pipeline de edição automatizada

Recebe um vídeo bruto (talking-head, entrevista, vlog) e entrega o vídeo editado: cortes de silêncio
com interpretação de contexto, técnicas de corte (J/L/match/smash/jump-zoom/beat/reaction),
legendas dinâmicas animadas, correção de cor com LUT, áudio limpo e masterizado em -14 LUFS,
SFX, trilha com ducking e motion graphics — exportado por plataforma.

```bash
./setup.sh                                                   # instala tudo (macOS / Linux)
python editar.py bruto.mp4 --estilo referencia2 --plataforma reels
```

Briefing com a análise dos vídeos de referência: [`docs/ETAPA1_briefing.md`](docs/ETAPA1_briefing.md) ·
Resultados dos testes: [`docs/RESULTADOS.md`](docs/RESULTADOS.md)

## Uso

```bash
source .venv/bin/activate
python editar.py bruto.mp4 --estilo viral_reels --plataforma tiktok --preview   # preview rápido
python editar.py bruto.mp4 --estilo viral_reels --plataforma tiktok             # versão final
python editar.py bruto.mp4 --modo sugestao        # só lista onde aplicaria cada técnica
python editar.py bruto.mp4 --revisar              # para após o corte de silêncio p/ revisão manual
python editar.py bruto.mp4 --usar-revisao         # aplica os YAML de revisão editados
python editar.py take1.mp4 take2.mp4              # várias tomadas viram um vídeo
python editar.py bruto.mp4 --set cortes.j_cut.ativo=false --set musica.humor=dramatico
python -m editor.doctor                           # confere dependências
```

| Estilo (`--estilo`) | Base | O que faz |
|---|---|---|
| `referencia1` | ref1 | legenda pequena no peito, frases de impacto cinéticas, título manuscrito verde, look quente |
| `referencia2` | ref2+ref3 | quadro 16:9 em tela 9:16, legenda lateral no espaço vazio (regular/**bold**/*itálico*, palavra futura cinza), punch-in alternado, look frio |
| `documentario` | ref4 | gancho em texto, letterbox, legenda de cinema, grão + vinheta, beat cuts, look terroso |
| `brand_dark` | ref5 | legenda monoespaçada dividida esq/dir com palavra-chave colorida, flash branco, low-key teal & orange |
| `viral_reels` | genérico | karaoke word-by-word, rotação de estilo/posição, zoom progressivo, whip/glitch, SFX |

Plataformas (`--plataforma`): `reels` (1080x1920, máx 90 s), `tiktok` (máx 3 min), `shorts` (máx 60 s),
`youtube` (1920x1080), `youtube_vertical`. Todas em H.264 + AAC, -14 LUFS, true peak -1 dBTP.

## Saídas

- `output/<nome>_<estilo>_<plataforma>.mp4` — vídeo final
- `output/..._relatorio.md/.json` — o que cada etapa fez, onde e **por quê** (cada corte e técnica com motivo)
- `output/..._contato.jpg`, `..._histograma.png` (cor antes/depois), `..._silencio.png` (energia + cortes)
- `work/<nome>_<estilo>_<plataforma>/revisao/` — `cortes_silencio.yaml` e `tecnicas.yaml` editáveis
- O vídeo original nunca é alterado: tudo trabalha em `work/.../fonte.*` (cópia)

## Configuração

Tudo em [`config/default.yaml`](config/default.yaml) — nada é hard-coded. Os presets em `config/estilos/`
sobrescrevem só o que declaram; `--config meu.yaml` e `--set chave=valor` sobrescrevem por cima.
Cada técnica de corte tem `ativo`, intervalo mínimo e parâmetros próprios em `cortes:`.

## Arquitetura

| Etapa | Módulo | Implementação |
|---|---|---|
| Análise inicial | `editor/analysis.py` | ffprobe, ebur128, cena (planos), piso de ruído, hum, clipping, remoção de tarjas |
| Transcrição | `editor/transcribe.py` | Parakeet TDT v3 (sherpa-onnx, offline) ou faster-whisper; timestamp por palavra |
| NLP | `editor/nlp.py` | spaCy PT: palavras-chave, impacto por frase, tópicos, tom, gatilhos, nomes, números |
| 3 · Silêncios | `editor/silence.py` | RMS na banda da voz + ASR (híbrido); 4 regras de contexto; revisão YAML; preview |
| 4 · Cortes | `editor/cinematic.py`, `timeline.py` | EDL com áudio/vídeo separados (split edits), decisões com motivo, modo sugestão |
| 5 · Legendas | `editor/subtitles.py` | ASS/libass: 10 estilos, 7 animações, rotação, desvio do rosto, destaque de keywords |
| 6 · Cor | `editor/color.py` | WB gray-world, exposição, níveis, skin tone line, normalização entre planos; LUT 33³ (colour-science) |
| 7 · Áudio | `editor/audio.py` | noisereduce, HPF, hum, declip, de-esser, EQ, compressor, loudnorm 2 passes + limiter |
| 8 · SFX | `editor/sfx.py` | whoosh alinhado ao corte, impactos em keywords/smash, atenção, humor, room tone |
| 9 · Trilha | `editor/music.py` | humor por tom, troca a cada 60–90 s c/ crossfade, beats, ducking, dinâmica, corte no smash |
| 10 · Motion | `editor/motion.py`, `render.py` | lower third, callout, contador, gancho, B-roll, película; zoom/whip/flash/glitch |
| 11 · Orquestração | `editor/pipeline.py`, `editar.py` | CLI, perfis, preview, logs com tempo por etapa, relatório |

Assets: `assets/fonts` (Inter, JetBrains Mono, Permanent Marker, Caveat Brush, Anton — licenças OFL/Apache
incluídas), `assets/music` e `assets/sfx` (gerados por `python -m editor.assets_gen`), `assets/luts`
(geradas a cada execução), `assets/broll` (seus clipes, nomeados pela palavra-chave).

### Banco de trilhas e SFX

O banco incluso é **sintetizado** (livre de direitos, funciona offline) e serve para validar o pipeline.
Para qualidade de produção, coloque faixas royalty-free reais em `assets/music/<humor>/` (humores:
`energetico`, `informativo`, `emocional`, `dramatico`, `sombrio`) e efeitos em `assets/sfx/<categoria>/`
(`transicao`, `impacto`, `atencao`, `humor`, `ambiente`). BPM e beats de faixas reais são detectados com
librosa automaticamente. Pode apagar os sintetizados.

## Limitações conhecidas

- **B-roll e cenas de filme** (muito usados nas referências) não podem ser inventados: o pipeline insere
  clipes de `assets/broll/` quando a palavra-chave aparece na fala; sem eles, varia o plano com zoom.
- **J-cut / L-cut com um único plano** mostrariam a boca fora de sincronia; por padrão só são aplicados
  entre planos diferentes, sobre B-roll ou sem rosto visível (`permitir_mesmo_plano` no YAML). Quando não
  aplicados, ficam registrados no relatório com o motivo.
- **Smash cut, clímax e revelação** vêm de heurísticas de linguagem — use `--modo sugestao` para aprovar.
- **Reframe 16:9 → 9:16** de fonte 720p resulta em upscale grande (perda de nitidez); grave em 4K/1080p
  ou use `layout.modo: letterbox`.
- **Manim / Remotion** não são usados: o motion destas referências é tipografia animada, que o ASS/libass
  faz com menos dependências (Remotion tem licença comercial restrita; Manim exige Cairo/LaTeX).
- **Música por IA** (Suno sem API oficial; MusicGen com licença não comercial) não foi integrada.
- Neste ambiente de desenvolvimento o HuggingFace é bloqueado; por isso a transcrição padrão é o
  Parakeet (baixado do GitHub). Com internet livre, `transcricao.motor: faster_whisper` também funciona.
