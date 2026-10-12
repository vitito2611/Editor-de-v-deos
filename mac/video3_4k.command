#!/bin/bash
# Vídeo 3 (IA e emprego) em 4K → Google Drive > Edição de vídeo - Claude > Vídeos editados. Rodar no Terminal do Mac:
#   bash ~/Editor-de-v-deos/mac/video3_4k.command
set -e
cd "$(dirname "$0")/.."
git pull --ff-only || true
(cd hyperframes && npm i --silent)
mkdir -p entrada
# o 4K precisa de ~12 GB livres durante o render (intermediários + quadros do Remotion)
rm -rf work/video3_*_reels_4k work/_fontes/*.tmp.mp4 2>/dev/null || true   # restos de uma tentativa que falhou
LIVRE=$(df -g . | awk 'NR==2{print $4}')
if [ "${LIVRE:-0}" -lt 12 ]; then
  echo ""
  echo "⚠️  Só ${LIVRE} GB livres no Mac — o vídeo em 4K precisa de uns 12 GB durante o render."
  echo "   Libere espaço (esvazie a Lixeira, apague vídeos/apps que não usa em  → Ajustes → Geral → Armazenamento)"
  echo "   e rode o comando de novo."
  exit 1
fi
BRUTO=$(ls entrada/video3.* 2>/dev/null | head -1)
if [ -z "$BRUTO" ]; then
  echo "Baixando o vídeo bruto (1007 (3).mov, 144 MB) — só desta vez…"
  BRUTO=entrada/video3.mov
  .venv/bin/gdown 1Nydgkh8jqgGKyO3mvFZK_4-hl8Fi2NN6 -O "$BRUTO"
fi
.venv/bin/python editar.py "$BRUTO" --estilo referencia1 --plataforma reels_4k \
  --config config/planos/video3_ia_emprego.yaml --pasta "IA e emprego"
rm -rf work/video3_*_reels_4k work/_fontes   # libera o espaço usado no render (o vídeo pronto já está na pasta)
echo "☁  Subindo para o Google Drive (pasta Edição de vídeo - Claude > Vídeos editados)."
