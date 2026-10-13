# Editor de vídeos — contexto do projeto e preferências do cliente

Pipeline de edição automatizada (FFmpeg + Python). Entrada: `python editar.py bruto.mp4 --estilo <estilo> --plataforma reels`.
Documentação: `README.md`, `docs/MODELOS.md` (catálogo de estilos), `docs/ETAPA1_briefing.md`, `docs/RESULTADOS.md`. Configuração: `config/default.yaml`,
presets em `config/estilos/`, planos por vídeo em `config/planos/`.

## Fluxo de trabalho com o cliente

- Vídeos brutos chegam na pasta do Google Drive "Edição de vídeo - Claude/Vídeos não editados"
  (pasta pai: https://drive.google.com/drive/folders/1IqX-X-ubjMnxhYctEF2tCocOgdyurgsv). Baixar com
  `.venv/bin/gdown --folder <link>` para `entrada/`. **Entrega: pasta "Vídeos editados" do Drive**
  (id `1Ye5BDFvAa2lNBIqbCj6BBe5AmyKi1JxP`), feita pelo Mac (ver abaixo). Da nuvem não dá: o conector só aceita
  base64 na chamada → entregar por link (Artifact) ou chat (SendUserFile ≤ 30 MB) e lembrar que o 4K sai no Mac.
- Vídeos de iPhone vêm em HDR (HLG/Dolby Vision) 4K60: o pipeline já converte para SDR e 1440p30.
- **Entrega = 4K no Google Drive** (o cliente testou a pasta do Finder e voltou ao Drive: ocupava espaço no
  MacBook). No Mac, `editar.py` usa `--plataforma reels_4k` por padrão e copia com/sem trilha para a pasta do
  Drive para Desktop "Edição de vídeo - Claude/Vídeos editados" (`editor/entrega.py`; sem Drive → Mesa; `EDITOR_PASTA`
  força outro caminho; `--pasta "Nome"` dá o nome). Um comando por vídeo: `mac/video3_4k.command` (baixa o bruto,
  confere ~12 GB livres, renderiza, apaga os temporários). Intermediários do 4K em CRF 17 (`crf_intermedio`).
  Ao terminar, responder SÓ o nome da pasta e dos arquivos. Na nuvem o 4K funciona mas não sobe.
- **Edição aprovada congelada** (`congelado:` no plano → `config/planos/<video>_congelado.json` com palavras + trechos
  mantidos): o render em outra máquina/resolução NÃO retranscreve (o Mac transcreveu diferente e mudou legendas/cortes).
- Última entrega do vídeo 3 (v5, motion "Repetição" novo = cena premium `repeticao`): pelo chat, 1080x1920 2-pass
  ~28 MB cada (pedido do cliente: "mandar na conversa com o máximo de qualidade").
- Sempre entregar **duas versões**: com trilha e sem trilha (para áudio em alta no Instagram).
- Conferir frames (contact sheet) do render antes de entregar. Não rodar `--preview` separado (dobra o tempo):
  a revisão é feita pelo **estúdio** (abaixo). A versão sem trilha sai no mesmo render (`geral.versao_sem_trilha`).

## Edição em conjunto — estúdio completo (pedido do cliente: editar junto, em tempo real, sem precisar digitar)

- Toda edição vira um projeto Remotion (`editor/projeto.py` → `remotion/public/projetos/<slug>/`, composição `Edicao`
  em `remotion/src/Edicao.tsx` + núcleo `remotion/src/ajustes.ts`). A base do FFmpeg sai SEM o look de cor e SEM áudio
  (`remotion.cor_ao_vivo: true`): o look (mesma conta do LUT — conferido: diferença média 0,4/255), grão e vinheta
  são aplicados ao vivo por filtro SVG; voz, trilha e cada SFX são faixas separadas (`work/<job>/faixas/`).
  O render final sai do Remotion (mudo) + mixagem/master em Python com os mesmos volumes = WYSIWYG.
- **Estúdio** (sempre publicar um por vídeo): `editor.pagina.estudio(projeto.json, pasta, titulo, sub, cfg)` →
  Artifact com `capabilities: {db: {}, comments: {}}` + mídia leve em `files`. O cliente mexe em TUDO sozinho:
  Cor (look, intensidade, exposição, contraste, saturação, temperatura, tint, pretos, vinheta, grão), Legendas
  (tamanho, altura, contorno, sombra, animação, caixa alta; cada legenda: texto, palavra de destaque, tempo, esconder),
  Áudio (voz/trilha/efeitos, liga/desliga e volume de cada SFX), Camadas (arrastar/redimensionar na linha do tempo,
  esconder, novos títulos/ganchos), Cortes (I/O). Salva sozinho no doc `edicao/atual` e sincroniza entre aparelhos.
- Player do estúdio: cada SFX tem `durationInFrames` (antes ficavam montados até o fim → >5 tags de áudio e o
  player PARAVA aos 14 s) e `numberOfSharedAudioTags={12}`; teste de reprodução com puppeteer em
  `scratchpad/tocar*.cjs` (mídia VP9 porque o Chromium de teste não toca H.264).
- Botão **"Renderizar vídeo final"** = `comments.sendToClaude` → chega aqui como comentário. Fluxo: ler
  `edicao/atual` (ArtifactData get), salvar JSON, `python -m editor.projeto aplicar <projeto.json> <alt.json>` e
  `python -m editor.projeto renderizar <projeto.json> output/<nome>_com_trilha.mp4` (gera com e sem trilha).
  Escrever o andamento em `edicao/status` ({estado: renderizando|pronto|erro, mensagem}) — aparece no estúdio.
  O campo `pedido` traz pedidos livres (trocar motion, música, foto). Depois de renderizar, salvar os ajustes em
  `config/planos/<video>_estudio.json` e apontar `estudio.alteracoes` no plano do vídeo (commit + push): assim o
  render em 4K no Mac (`--pasta`) sai idêntico ao aprovado no estúdio.
- Estúdios: vídeo 2 (Santa Cruz) https://claude.ai/artifact/WscyQZuN2PqWBJztGS4y7p (formato antigo) ·
  vídeo 3 (IA e emprego, estúdio completo v3) https://claude.ai/artifact/WAvvGHiag1c68Zp9zKyFy1
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
- SFX: o nível da v2 foi aprovado; impacto do smash cut −4 dB (`sfx.ajuste_categoria_db`, cliente achou alto). **Vetado para sempre:** o "plin"/brilho (Magic sparkle whoosh,
  `sfx.proibidos`). Cliente não gostou de cenas genéricas sem relação (pizza, carteira).
- Trilhas: Mixkit (royalty-free); músicas em alta são adicionadas pelo cliente no app.
- Glossário do ASR por vídeo em `transcricao.correcoes` (ex.: Zuckenberg → Zuckerberg).
- Cor: cliente prefere **azul cinematográfico** (`cor.look: azul_cinema`) ao tom quente; empresa dele: **Zeal**.
- **O que a Zeal É (usar em TODO motion/texto/card que fale dela):** assistente de IA por voz que é o **copiloto de
  vendas do dentista** — a partir do **áudio da consulta**, ajuda a **fechar mais tratamentos**: perfil comportamental do
  paciente, quais objeções ele teve e **como contorná-las (dica em tempo real)**, nível de rapport do dentista, resumo
  da conversa, observações e **briefing pós-consulta**. **NUNCA** mostrar/dizer: diagnóstico, plano de tratamento,
  como fazer implante/procedimento, agendamento/recepção/atendimento de ligações. Exemplo aprovado de tela:
  paciente "Achei caro…" → Zeal "Objeção: preço. Mostre o parcelamento." + cartão "Briefing da consulta"
  (Perfil · Objeção · Rapport).
- **Pausas e erros de gravação têm que sair**: pausas ≥ 0,22 s cortadas (`silencio`), recomeços/gaguejadas/
  muletas/frase abandonada cortados por `editor/erros.py` (revisão em `revisao/erros_gravacao.yaml`).

## Habilidades extras

- **Receita de edição aprovada: `docs/MODELO_EDICAO.md`** (vídeo 3 = padrão: cortes, legendas/ênfases, SFX, cor, entrega).
  Ler antes de editar qualquer vídeo novo; o que muda por vídeo é só o plano (motions, headline, glossário).
- **Motion padrão a partir do vídeo 4 = modelo "campo"** (pedido: "nível profissional", referência
  `referencias/motion3/ref.mp4` — "ONE SECOND", field guide): preto com estrelas, HUD (cantos, rótulos JetBrains Mono,
  timecode, barra de progresso), NÚMERO GIGANTE contando com zero-fantasma, script (Black Jack; reserva Noto Serif
  itálico), objetos 3D de PONTOS com luz e halo. `hyperframes/modelos/campo.html` + cenas em
  `hyperframes/modelos/cenas_campo/*.js` (`headline`, `contador` com objeto `galaxia|grade|anel`, `tres`, `mar`),
  montador `editor/motion_campo.py`, `modelo: campo` no roteiro. Cada cena: HUD e 3D são função pura do tempo.
- **Headline de abertura** (pedido do vídeo 4): cena `headline` + `formato: janela` (orador numa janela embaixo, sem
  borda; cantos do HUD em volta; a janela abre para tela cheia no fim). Ótimo para gravações em selfie (rosto ocupa
  a zona segura inteira).

- **Motion nível cinema = modelo "cinema3d"** (pedido do cliente no vídeo 3 v4: "nível cinema", MENOS TEXTO nos
  motions — no máximo 1–3 palavras —, mais animação, "formatos bons"). HyperFrames + Three.js local
  (`hyperframes/modelos/cinema3d.html` + cenas em `hyperframes/modelos/cenas3d/*.js`, montador
  `editor/motion_cinema3d.py`): luz de recorte, reflexos de ambiente, névoa, bokeh, partículas, câmera sempre em
  movimento, grão e vinheta. Cenas: `vidros` (cartões que se desintegram), `esteira` (documentos idênticos engolidos
  pelo vórtice da IA), `relogio` (24 h → 1 h), `orbe` (IA como orbe de plasma), `celular3d` (celular 3D com tela viva
  e cartão saltando). Uma cena por motion; `modelo: cinema3d` no roteiro.
- **Formatos com a filmagem** (Remotion, `remotion/src/Formatos.tsx`): `formato: janela` (o cliente numa janela/
  círculo animado por `janela.quadros` sobre o motion — usado no "somar" e no "assistente"), `tipo: efeito` com
  `efeito: multiplica` (grade de clones ×N) ou `efeito: monitor` (o cliente dentro de um editor de vídeo). Usam a base
  no mesmo instante da fala (sincronizado, editável no estúdio).
- **Zona segura do Reels SEMPRE**: 420 px em cima e embaixo (de 1920) e a coluna de botões à direita (~220 px, da
  altura ~1100 para baixo) — `legendas.zona_segura` (Python/ASS) e `caixaSegura` em `remotion/src/ajustes.ts`
  (legendas encolhem/sobem; motions e formatos posicionados dentro). O estúdio mostra as zonas ("Zonas do Reels").
- **Motion "premium"** (`hyperframes/modelos/motion_premium.html` + `editor/motion_premium.py`).
  Feedback do cliente: os motions anteriores estavam "de amador"; referência de MOVIMENTO = `referencias/motion2/ref.mp4`
  (Awake Investors: linha de luz que revela o texto, máscaras, celular 3D com interface real, gráfico que se desenha,
  caminho de etapas, botão com cursor, transições iris/listras/chicote/esfera). Identidade da **Zeal** (logo do GitHub
  app-zeal): roxo #5D2E8C, ciano #24D0DC, branco, fundo quase preto. Cenas: `linha, texto, logo, celular, grafico,
  passos, cta, numero, cards, ciclo, comparacao, soma, timeline`. Showreel: `config/motion/zeal_showreel.yaml`.
  Inserção na edição começa já em movimento (`pre_roll` 0,3 s, sem quadro vazio). Modelos antigos: `modelo: cinema`
  (escuro azul) e `modelo: claro`. Paletas rosa/lilás claro e motions só com letras foram reprovados.
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
