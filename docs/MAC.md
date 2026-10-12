# Rodar o editor no seu Mac (4K direto no Google Drive)

No Mac, o editor salva o vídeo pronto em 4K na pasta "Vídeos editados" do Google Drive para Desktop — o upload
acontece sozinho e, no modo streaming, o vídeo não fica ocupando o disco.
Bônus: o chip do Mac decodifica o vídeo do iPhone por hardware, então fica bem mais rápido.

## 1. Uma vez só (instalação, ~20 min)

1. **Homebrew** (gerenciador de programas): abra o app Terminal e cole
   `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
2. **Programas**: no Terminal, `brew install ffmpeg ffmpeg-full python@3.13 node git`
   (o `ffmpeg-full` traz o libass, que desenha as legendas — o `ffmpeg` comum do Homebrew veio sem)
3. **Projeto**: `git clone https://github.com/vitito2611/Editor-de-v-deos.git ~/Editor-de-v-deos`
   e depois `cd ~/Editor-de-v-deos && git checkout claude/automated-video-editing-pipeline-5feprt`
4. **Instalar tudo**: `PYTHON=python3.13 ./setup.sh` (baixa modelos, Remotion, HyperFrames…)
5. **Fonte Black Jack** (destaque): copie o arquivo `BlackJack.otf`/`.ttf` para `assets/fonts/`.
   (A licença não deixa ela ir para o GitHub, por isso é manual.)
6. **Claude Code no Mac**: no app Claude, abra a aba Code e escolha a pasta `~/Editor-de-v-deos`.
   O Claude lê o `CLAUDE.md` e lembra de todas as suas preferências.

### Conferir a instalação

No Terminal: `cd ~/Editor-de-v-deos && git pull && .venv/bin/python -m editor.doctor`
(✔ = ok, ✘ = falta — com a dica → de como resolver).

## 2. Todo vídeo

Peça no chat do Claude Code (no Mac), por exemplo: *"edite o vídeo X no estilo referencia1"*. Por baixo ele roda:

```
python editar.py entrada/video.mov --estilo referencia1 --config config/planos/<plano>.yaml --pasta "Nome do vídeo"
```

- No Mac o padrão já é 4K (2160x3840, a partir do bruto em resolução cheia).
- `--pasta "Nome"` → salva "Nome (com trilha).mp4" e "Nome (sem trilha).mp4" em Drive > Edição de vídeo - Claude > Vídeos editados.
- Para ver e editar junto: `cd remotion && npx remotion studio` abre o Remotion Studio no navegador.
