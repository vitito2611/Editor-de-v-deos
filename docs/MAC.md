# Rodar o editor no seu Mac (4K direto no Google Drive)

Na nuvem não dá para subir vídeo grande no Drive. No Mac, o editor salva o vídeo pronto na pasta
"Vídeos editados" que o Google Drive para Desktop sincroniza — o upload acontece sozinho.
Bônus: o chip do Mac decodifica o vídeo do iPhone por hardware, então fica bem mais rápido.

## 1. Uma vez só (instalação, ~20 min)

1. **Google Drive para Desktop**: baixe em google.com/drive/download, entre com a sua conta e deixe
   rodando. Confira no Finder que aparece "Google Drive > Meu Drive > Edição de vídeo - Claude > Vídeos editados".
2. **Homebrew** (gerenciador de programas): abra o app Terminal e cole
   `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
3. **Programas**: no Terminal, `brew install ffmpeg python@3.13 node git`
4. **Projeto**: `git clone https://github.com/vitito2611/Editor-de-v-deos.git ~/Editor-de-v-deos`
   e depois `cd ~/Editor-de-v-deos && git checkout claude/automated-video-editing-pipeline-5feprt`
5. **Instalar tudo**: `./setup.sh` (baixa modelos, Remotion, HyperFrames…)
6. **Fonte Black Jack** (destaque): copie o arquivo `BlackJack.otf`/`.ttf` para `assets/fonts/`.
   (A licença não deixa ela ir para o GitHub, por isso é manual.)
7. **Claude Code no Mac**: no app Claude, abra a aba Code e escolha a pasta `~/Editor-de-v-deos`.
   O Claude lê o `CLAUDE.md` e lembra de todas as suas preferências.

### Conferir a instalação

No Terminal: `cd ~/Editor-de-v-deos && git pull && .venv/bin/python -m editor.doctor`
(✔ = ok, ✘ = falta — com a dica → de como resolver).

## 2. Todo vídeo

Peça no chat do Claude Code (no Mac), por exemplo: *"edite o vídeo X do Drive no estilo referencia1 em 4K e
suba no Drive"*. Por baixo ele roda:

```
python editar.py entrada/video.mov --estilo referencia1 --plataforma reels_4k --config config/planos/<plano>.yaml --drive "Nome do vídeo"
```

- `--plataforma reels_4k` → 2160x3840 (4K de verdade, a partir do bruto em resolução cheia).
- `--drive "Nome"` → salva "Nome (com trilha).mp4" e "Nome (sem trilha).mp4" em "Vídeos editados".
- Para ver e editar junto: `cd remotion && npx remotion studio` abre o Remotion Studio no navegador.
