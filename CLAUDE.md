# Editor de vídeos — contexto do projeto e preferências do cliente

Pipeline de edição automatizada (FFmpeg + Python). Entrada: `python editar.py bruto.mp4 --estilo <estilo> --plataforma reels`.
Documentação: `README.md`, `docs/ETAPA1_briefing.md`, `docs/RESULTADOS.md`. Configuração: `config/default.yaml`,
presets em `config/estilos/`, planos por vídeo em `config/planos/`.

## Fluxo de trabalho com o cliente

- Vídeos brutos chegam na pasta do Google Drive "Edição de vídeo - Claude/Vídeos não editados"
  (pasta pai: https://drive.google.com/drive/folders/1IqX-X-ubjMnxhYctEF2tCocOgdyurgsv). Baixar com
  `.venv/bin/gdown --folder <link>` para `entrada/`. Upload de volta ao Drive não é possível daqui:
  entregar pelo chat (SendUserFile, limite 30 MB → cópia 2-pass ~2,95 Mbps) e avisar.
- Vídeos de iPhone vêm em HDR (HLG/Dolby Vision) 4K60: o pipeline já converte para SDR e 1440p30.
- Sempre entregar **duas versões**: com trilha e sem trilha (para áudio em alta no Instagram).
- Fazer preview, conferir frames (contact sheet) antes do render final.

## Preferências aprovadas (estilo `viral_reels` = v2 aprovada do vídeo 1)

- Legendas: **sem cores** (nada de verde/amarelo/vermelho). Dinâmicas só com variação de fonte,
  peso, tamanho e itálico, em branco, logo abaixo do rosto (`dinamico_branco`).
- Edição dinâmica: troca de plano a cada ≤ 2,6 s, B-roll/fotos/cards nos momentos-chave, fotos das
  pessoas/marcas citadas (ex.: Zuckerberg, Steve Jobs) — só fontes com licença (Openverse/Wikimedia,
  Mixkit). Não usar fotos do Google (direitos autorais).
- SFX: o nível da v2 foi aprovado. **Vetado para sempre:** o "plin"/brilho (Magic sparkle whoosh,
  `sfx.proibidos`). Cliente não gostou de cenas genéricas sem relação (pizza, carteira).
- Trilhas: Mixkit (royalty-free); músicas em alta são adicionadas pelo cliente no app.
- Glossário do ASR por vídeo em `transcricao.correcoes` (ex.: Zuckenberg → Zuckerberg).

## Habilidades extras

- **Ângulos de câmera por IA** (Seedance 2.0 via MCP Higgsfield): ver `.claude/skills/angulos-ia/SKILL.md`
  e `editor/angulos.py`. Requer créditos Higgsfield e rede liberada para `upload.higgsfield.ai`.

## Ambiente

- `./setup.sh` reinstala tudo; o modelo de transcrição (Parakeet) baixa do GitHub; HuggingFace é bloqueado.
- Domínios liberados no ambiente: Drive, Mixkit, Openverse/Wikimedia/Flickr (+ Pexels, sem chave disponível).
