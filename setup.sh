#!/usr/bin/env bash
# Instalação do pipeline (macOS e Linux).
#   ./setup.sh            instala tudo
# Requisitos de sistema: Python 3.10+, FFmpeg com libass e libx264.
set -euo pipefail
cd "$(dirname "$0")"

echo "==> Verificando FFmpeg"
if ! command -v ffmpeg >/dev/null; then
  if [[ "$OSTYPE" == darwin* ]]; then brew install ffmpeg
  elif command -v apt-get >/dev/null; then sudo apt-get update && sudo apt-get install -y ffmpeg
  else echo "Instale o FFmpeg manualmente"; exit 1; fi
fi
ffmpeg -hide_banner -filters | grep -q " ass " || { echo "FFmpeg sem libass (legendas)."; exit 1; }

echo "==> Ambiente Python (.venv)"
PY=${PYTHON:-python3}
$PY -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -m spacy download pt_core_news_sm -q || echo "aviso: modelo spaCy PT não baixado (heurísticas serão usadas)"

echo "==> Modelos"
mkdir -p models
if [ ! -f models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8/tokens.txt ]; then
  curl -L -o models/p.tar.bz2 https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2
  tar xjf models/p.tar.bz2 -C models && rm models/p.tar.bz2
fi
[ -f models/face_detection_yunet_2023mar.onnx ] || curl -L -o models/face_detection_yunet_2023mar.onnx \
  https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx

echo "==> Banco local de SFX e trilhas (sintetizado)"
[ -f assets/music/library.yaml ] || .venv/bin/python -m editor.assets_gen

echo "==> Verificação"
.venv/bin/python -m editor.doctor
