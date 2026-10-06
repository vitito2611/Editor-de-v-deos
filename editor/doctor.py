"""Verifica se todas as dependências e modelos estão instalados e funcionais.

Uso: python -m editor.doctor
"""
from __future__ import annotations

import importlib
import shutil
import subprocess

from .utils import ROOT

CHECKS = [
    ("numpy", "núcleo"), ("scipy", "núcleo"), ("yaml", "config YAML"), ("cv2", "visão (OpenCV)"),
    ("PIL", "Pillow"), ("librosa", "beats/BPM"), ("soundfile", "áudio"), ("noisereduce", "redução de ruído"),
    ("pyloudnorm", "loudness"), ("sherpa_onnx", "transcrição Parakeet"), ("faster_whisper", "transcrição Whisper"),
    ("spacy", "NLP"), ("colour", "colour-science (LUTs)"), ("matplotlib", "relatórios"),
    ("pydub", "opcional"), ("moviepy", "opcional"), ("PyOpenColorIO", "opcional (OCIO)"),
]


def main() -> int:
    ok = True
    print("Binários:")
    for b in ("ffmpeg", "ffprobe"):
        found = shutil.which(b) is not None
        ok &= found
        print(f"  {'✔' if found else '✘'} {b}")
    if shutil.which("ffmpeg"):
        flt = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
        for f in ("ass", "lut3d", "loudnorm", "deesser", "xfade", "afftdn", "rgbashift"):
            has = f" {f} " in flt
            ok &= has
            print(f"  {'✔' if has else '✘'} filtro FFmpeg {f}")
    print("Python:")
    for mod, desc in CHECKS:
        try:
            m = importlib.import_module(mod)
            print(f"  ✔ {mod:16s} {getattr(m, '__version__', ''):10s} {desc}")
        except Exception as e:  # noqa: BLE001
            opt = desc.startswith("opcional")
            ok &= opt
            print(f"  {'·' if opt else '✘'} {mod:16s} {'':10s} {desc} ({type(e).__name__})")
    print("Modelos e assets:")
    items = {
        "Parakeet TDT v3": ROOT / "models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8/tokens.txt",
        "YuNet (rosto)": ROOT / "models/face_detection_yunet_2023mar.onnx",
        "Banco de trilhas": ROOT / "assets/music/library.yaml",
        "Banco de SFX": ROOT / "assets/sfx/transicao",
        "Fontes": ROOT / "assets/fonts/Inter-Bold.otf",
    }
    for k, p in items.items():
        ok &= p.exists()
        print(f"  {'✔' if p.exists() else '✘'} {k}")
    try:
        import spacy
        spacy.load("pt_core_news_sm")
        print("  ✔ spaCy pt_core_news_sm")
    except Exception:  # noqa: BLE001
        print("  · spaCy pt_core_news_sm ausente (usa heurísticas)")
    print("\nTudo pronto ✅" if ok else "\nFaltam itens ✘ — rode ./setup.sh")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
