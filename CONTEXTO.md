# CONTEXTO — padrão fixo de TODA edição (pedido do cliente: "sempre faça sem que eu peça")

Este é o fluxo-padrão aprovado. Em todo vídeo novo, executar tudo abaixo **automaticamente**, sem esperar pedido.
Receita de corte/legenda/som: `docs/MODELO_EDICAO.md`. Preferências gerais e a Zeal: `CLAUDE.md`.

## 0. Nome do cliente (regra fixa, nunca esquecer)

- O nome é **Victor Hugo Rodriguez** — "Victor" com **c** e "Rodriguez" com **Z**. Em toda legenda, título, card ou
  motion em que o nome aparecer, escrever exatamente assim. O ASR costuma errar ("Vitor", "Rodrigues"): a correção já
  é automática para todos os vídeos (`transcricao.correcoes` em `config/default.yaml`), mas conferir na revisão.

## 1. Edição (padrão do vídeo 4, aprovado)

- **Corte, legendas, ênfases e SFX** = receita do vídeo 3 (`docs/MODELO_EDICAO.md`): pausas ≥ 0,22 s e erros de gravação
  fora, jump zoom ≤ 2,6 s, legenda branca Rubik Bold no peito com contorno/sombra fortes quando a roupa/fundo for claro,
  ênfases em `cinetico`, SFX no nível aprovado (nunca o "plin").
- **Motions = modelo `produto`** (referência `referencias/motion4/ref.mp4`): fundo claro com grade, rótulo com ponto
  ciano, título cujas palavras escurecem uma a uma, marca-texto ciano (`*várias palavras*`), cards de interface ligados
  por setas com estado ativo que caminha, hub com nós, listas com barras e selo, explosão (anel + raios), barra ciano
  que varre a tela na entrada. Cores da Zeal (ciano #24D0DC, roxo #5D2E8C), fontes do cliente.
  - Ler a transcrição e escolher **um motion por momento-chave** (números, listas, comparações, conclusões), com os
    itens sincronizados palavra a palavra (`t` de cada item = tempo da fala − início do motion).
  - Cenas prontas em `hyperframes/modelos/cenas_produto/`: `headline`, `clinicas` (número + mosaico), `dez`
    (fração em grade), `experiencia` (comparação de cards), `fluxo` (etapas ligadas por setas), `hub` (centro + nós),
    `automacao` (lista que vira "automatizado"), `mar` (frase final + pilares). Criar cenas novas no mesmo idioma
    quando o conteúdo pedir. Conferir cada cena num quadro antes de montar o vídeo.
  - Pouco texto por motion; nada fora da zona segura do Reels (420 px em cima/embaixo, coluna de botões à direita).
  - **Motions CENTRALIZADOS** (pedido do cliente no 1014: "estavam muito para a esquerda, perdendo um pouco quando
    abriam"): rótulo e título com `centro: true`, cards/grades/listas simétricos em torno de x = 540 (largura ≤ 720 abaixo
    de y ≈ 1100 por causa da coluna de botões), e a entrada (`varredura`) só faz fade, sem deslizar o palco de lado.
- **Headline na abertura (sempre)**: cena `headline` com `formato: janela` — título no topo e o orador num cartão
  embaixo que abre para a tela cheia em ~3 s. Exemplo: plano `config/planos/video4_10anos.yaml`.
- Plano por vídeo em `config/planos/<video>.yaml`; conferir contact sheet do render antes de entregar.

## 2. Estúdio de edição em tempo real (sempre publicar)

- Depois do render, publicar o estúdio do vídeo: `editor.pagina.estudio(projeto.json, estudio/<video>, título, sub, cfg)`
  → Artifact com `capabilities: {db: {}, comments: {}}` e os arquivos de `estudio/<video>/`. O vídeo base do estúdio vai
  em 540p (`-crf 27`) para caber em 15 MB por arquivo.
- Gravar no banco do estúdio (`edicao/atual`) os ajustes que já usei no render, para ele abrir igual ao entregue.
- Quando o cliente apertar **"Renderizar vídeo final"** (comentário enviado ao Claude): ler `edicao/atual`, salvar em
  `config/planos/<video>_estudio.json`, `python -m editor.projeto aplicar` + `renderizar`, escrever o andamento em
  `edicao/status`, entregar (item 3), responder e resolver o comentário.

## 3. Entrega pela página (sempre, no lugar do chat)

- `python -m editor.entrega_web entrega/<video>/web "Título do vídeo" output/<nome>_com_trilha.mp4 output/<nome>_sem_trilha.mp4`
  → codifica uma vez (1080x1920, ~6,3 Mbps 2-pass), monta com e sem trilha, divide em partes de 14 MB e gera a página.
- Publicar `entrega/<video>/web/index.html` com `capabilities: {downloads: true}` e `files` = `manifesto.json` +
  `partes/*`, em lotes de até 64 MB por publicação (15 MB por arquivo, 256 MB por versão).
- Entregar o **link** ao cliente (botão "Baixar .mp4" junta as partes e salva um único arquivo; "Assistir aqui").
  Não mandar mais pelo chat comprimido. No Mac continua valendo o 4K na pasta do Drive.

## 4. Velocidade e disco (já embutidos — não desfazer)

- Render final: cor do estúdio aplicada por LUT no FFmpeg (`cor_pronta`), sem o filtro SVG (2× mais rápido).
- `render-edicao.mjs` empacota só o projeto atual e apaga o bundle; mixagens intermediárias são apagadas.
- Antes de renderizar, se o disco estiver acima de ~85%: apagar projetos antigos em `remotion/public/projetos`,
  `hyperframes/projetos/motion_*` antigos, `estudio/` e `entrega/` de vídeos já entregues e `output/` velho.

## Checklist de cada vídeo novo (fazer tudo sem perguntar)

1. Baixar o bruto do Drive, transcrever, montar glossário (`transcricao.correcoes`).
2. Plano: headline + motions `produto` sincronizados + receita do vídeo 3. Testar cada cena.
3. Render → contact sheet → corrigir o que estiver errado.
4. Publicar o estúdio (com os ajustes gravados em `edicao/atual`).
5. Publicar a página de entrega e mandar os dois links (estúdio + entrega).
6. Commit + push de plano, cenas e documentação.
