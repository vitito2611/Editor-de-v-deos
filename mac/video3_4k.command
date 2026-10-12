#!/bin/bash
# Vídeo 3 (IA e emprego) em 4K → Mesa > Vídeos editados. Rodar no Terminal do Mac:
#   bash ~/Editor-de-v-deos/mac/video3_4k.command
set -e
cd "$(dirname "$0")/.."
git pull --ff-only || true
(cd hyperframes && npm i --silent)
mkdir -p entrada
BRUTO=$(ls entrada/video3.* 2>/dev/null | head -1)
if [ -z "$BRUTO" ]; then
  echo "Baixando o vídeo bruto (1007 (3).mov, 144 MB) — só desta vez…"
  BRUTO=entrada/video3.mov
  .venv/bin/gdown 1Nydgkh8jqgGKyO3mvFZK_4-hl8Fi2NN6 -O "$BRUTO"
fi
.venv/bin/python editar.py "$BRUTO" --estilo referencia1 --plataforma reels_4k \
  --config config/planos/video3_ia_emprego.yaml --pasta "IA e emprego"
open ~/Desktop/"Vídeos editados"
