# Editor de vídeos — contexto do projeto e preferências do cliente

Pipeline de edição automatizada (FFmpeg + Python). Entrada: `python editar.py bruto.mp4 --estilo <estilo> --plataforma reels`.
Documentação: `README.md`, `docs/MODELOS.md` (catálogo de estilos), `docs/ETAPA1_briefing.md`, `docs/RESULTADOS.md`. Configuração: `config/default.yaml`,
presets em `config/estilos/`, planos por vídeo em `config/planos/`.

## Fluxo de trabalho com o cliente

- Vídeos brutos chegam na pasta do Google Drive "Edição de vídeo - Claude/Vídeos não editados"
  (pasta pai: https://drive.google.com/drive/folders/1IqX-X-ubjMnxhYctEF2tCocOgdyurgsv). Baixar com
  `.venv/bin/gdown --folder <link>` para `entrada/`. **Entrega: o cliente quer o vídeo na pasta
  "Vídeos editados"** (id `1Ye5BDFvAa2lNBIqbCj6BBe5AmyKi1JxP`), não no chat. O conector Google Drive
  (`create_file`) só aceita conteúdo base64 dentro da chamada — inviável para vídeo; até haver outra
  via, entregar por link (Artifact) ou chat (SendUserFile ≤ 30 MB) e avisar o cliente.
- Vídeos de iPhone vêm em HDR (HLG/Dolby Vision) 4K60: o pipeline já converte para SDR e 1440p30.
- Sempre entregar **duas versões**: com trilha e sem trilha (para áudio em alta no Instagram).
- Conferir frames (contact sheet) do render antes de entregar. Não rodar `--preview` separado (dobra o tempo):
  a revisão é feita pelo **estúdio** (abaixo). A versão sem trilha sai no mesmo render (`geral.versao_sem_trilha`).

## Edição em conjunto (pedido do cliente: ver e editar junto, como no Remotion Studio)

- Com Node/Remotion, a edição vira um projeto Remotion (`editor/projeto.py` → `remotion/public/projetos/<slug>/`,
  composição `Edicao` em `remotion/src/Edicao.tsx`): base (cortes/zoom/cor/áudio, FFmpeg) + camadas React
  (legendas, cards, contadores, B-roll, fotos). O render final sai do Remotion (`render-edicao.mjs`) = WYSIWYG.
- Na nuvem: publicar o **estúdio** (`editor.pagina.estudio(projeto.json, pasta, titulo, sub)` → Artifact com
  `capabilities: {db: {}}` + mídia 720p em `files`). O cliente edita texto/tempo/ocultar na timeline e salva no
  doc `edicao/atual`; ler com ArtifactData (`get edicao/atual`), salvar em JSON e rodar
  `python -m editor.projeto aplicar <projeto.json> <alteracoes.json>` e
  `python -m editor.projeto renderizar <projeto.json> <saida_com_trilha.mp4> --audio-sem-trilha work/<job>/audio_master_sem_trilha.wav`
  (só re-renderiza camadas, ~3 min). O campo `pedido` traz pedidos livres (trocar foto/B-roll).
  Estúdio do vídeo 2 (Santa Cruz): https://claude.ai/artifact/WscyQZuN2PqWBJztGS4y7p
- No Mac do cliente (Claude Code local): `cd remotion && npm i && npx remotion studio` abre o Studio de verdade
  em localhost:3000 com cada vídeo como composição `Edicao-<nome>`.

## Preferências aprovadas (estilo `viral_reels` = v2 aprovada do vídeo 1)

- Legendas: **sem cores** (nada de verde/amarelo/vermelho). Dinâmicas só com variação de fonte,
  peso, tamanho e itálico, em branco, logo abaixo do rosto (`dinamico_branco`).
- **Fontes fixas em TODOS os vídeos e modelos:** legenda comum **Rubik Bold**; quando a fonte troca para
  destacar (palavra-chave, peso maior, itálico, cards, títulos) **Black Jack** (manuscrita, bem diferente da
  Rubik). Config: `legendas.fonte_base` / `fonte_destaque` (+ `fonte_destaque_reserva: Noto Serif`, usada só se
  o arquivo faltar). Black Jack (Typadelic): uso livre em projetos, **redistribuição proibida** → o arquivo
  fica só local em `assets/fonts/` (gitignored); fontsquirrel.com bloqueado na rede → pedir o .otf/.ttf ao cliente.
- Edição dinâmica: troca de plano a cada ≤ 2,6 s, B-roll/fotos/cards nos momentos-chave, fotos das
  pessoas/marcas citadas (ex.: Zuckerberg, Steve Jobs) — só fontes com licença (Openverse/Wikimedia,
  Mixkit). Não usar fotos do Google (direitos autorais).
- SFX: o nível da v2 foi aprovado. **Vetado para sempre:** o "plin"/brilho (Magic sparkle whoosh,
  `sfx.proibidos`). Cliente não gostou de cenas genéricas sem relação (pizza, carteira).
- Trilhas: Mixkit (royalty-free); músicas em alta são adicionadas pelo cliente no app.
- Glossário do ASR por vídeo em `transcricao.correcoes` (ex.: Zuckenberg → Zuckerberg).
- **Pausas e erros de gravação têm que sair**: pausas ≥ 0,22 s cortadas (`silencio`), recomeços/gaguejadas/
  muletas/frase abandonada cortados por `editor/erros.py` (revisão em `revisao/erros_gravacao.yaml`).

## Habilidades extras

- **Vídeo em motion (HyperFrames, HTML+GSAP → MP4)** no estilo do exemplo do cliente
  (`referencias/motion_exemplo.mp4`: fundo branco com brilho lilás/rosa embaixo, texto cinético com desfoque,
  ícones flutuando, palavra soletrada, colagem em anel, celular, logo, abas de capítulo). Roteiro YAML →
  `python -m editor.motion_hf config/motion/<x>.yaml output/x.mp4 [--horizontal] [--rapido]` (modelo em
  `hyperframes/modelos/motion_padrao.html`, demo `config/motion/demo_editor.yaml`). Na edição: item do plano
  `{contem: "...", tipo: motion, roteiro: config/motion/x.yaml}`. Skills oficiais do HyperFrames em
  `.claude/skills/hyperframes*` (restaurar: `npx skills experimental_install`). **Nunca usar CSS `filter: blur`
  grande** (fundo) no HyperFrames: render por software fica 4–5x mais lento (usar radial-gradient).

- **Ângulos de câmera por IA** (Seedance 2.0 via MCP Higgsfield): ver `.claude/skills/angulos-ia/SKILL.md`
  e `editor/angulos.py`. Requer créditos Higgsfield e rede liberada para `upload.higgsfield.ai`.

- **Remotion — ligado em TODOS os modelos** (`remotion:` no default.yaml; tema por preset): cards,
  contador, callout e gancho renderizados por `editor/remotion_fx.py` → `remotion/render-lote.mjs`
  (composição `Elemento`, ProRes 4444 com alfa) e sobrepostos pelo FFmpeg. Sem Node → ASS.
- Remotion (vídeo com React, `remotion/`, instalado com `npx create-video@latest --yes --blank remotion`):
  motion graphics e animações em código. Render: `cd remotion && npx remotion render src/index.ts <Composição> out/x.mp4`
  (o `remotion.config.ts` já aponta para o Chromium headless do ambiente). Licença: grátis para até 3 pessoas.

## Velocidade

- Cor/grão/vinheta aplicados nos segmentos quando o final sai do Remotion (base = montado + áudio, sem
  recodificar); segmentos iguais são reaproveitados entre renders; Mac decodifica HEVC por hardware (VideoToolbox).
- Mezanino HDR→SDR em cache compartilhado (`work/_fontes/`, superfast CRF 12, GOP 15); análise em cache;
  segmentos veryfast CRF 12 e reaproveitados se nada mudou; final preset fast. Vídeo 2 (51 s, 4K60 HDR):
  ~37 min → ~17 min na 1ª vez; ajustes de camadas ~3 min. Num Mac (Apple Silicon) é bem mais rápido.

## Ambiente

- `./setup.sh` reinstala tudo; o modelo de transcrição (Parakeet) baixa do GitHub; HuggingFace é bloqueado.
- Domínios liberados no ambiente: Drive, Mixkit, Openverse/Wikimedia/Flickr (+ Pexels, sem chave disponível).
