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
    ok &= _extras()
    print("\nTudo pronto ✅" if ok else "\nFaltam itens ✘ — veja as dicas (→) acima")
    return 0 if ok else 1


def _cmd(args: list[str]) -> str:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=60, cwd=ROOT).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def _extras() -> bool:
    """Itens do passo a passo do Mac (docs/MAC.md): projeto, fontes, Remotion, HyperFrames e Drive."""
    import sys
    ok = True

    def linha(cond: bool, txt: str, dica: str = "", obrigatorio: bool = True):
        nonlocal ok
        if obrigatorio:
            ok &= cond
        print(f"  {'✔' if cond else ('✘' if obrigatorio else '·')} {txt}" + ("" if cond or not dica else f"\n      → {dica}"))

    print("Projeto:")
    ramo = _cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    linha(ramo == "claude/automated-video-editing-pipeline-5feprt", f"versão do projeto (branch: {ramo or '?'})",
          "git checkout claude/automated-video-editing-pipeline-5feprt && git pull")
    linha(sys.version_info >= (3, 10), f"Python {sys.version.split()[0]}", "brew install python@3.13")
    print("Fontes do cliente:")
    f = ROOT / "assets" / "fonts"
    linha((f / "Rubik-Bold.ttf").exists(), "Rubik Bold (legenda)", "git pull (vem com o projeto)")
    linha((f / "NotoSerif-BoldItalic.ttf").exists(), "Noto Serif (reserva do destaque)", "git pull")
    from .utils import arquivo_black_jack
    bj = arquivo_black_jack()
    linha(bool(bj), f"Black Jack (destaque){' — ' + bj.name if bj else ''}",
          "copie BlackJack.otf/.ttf para assets/fonts/ (fontsquirrel.com/fonts/blackjack). Sem ela o destaque sai em Noto Serif",
          obrigatorio=False)
    print("Remotion / HyperFrames (motion e estúdio):")
    node = _cmd(["node", "--version"]) if shutil.which("node") else ""
    linha(bool(node), f"Node.js {node}", "brew install node")
    linha((ROOT / "remotion/node_modules/@remotion/renderer").exists(), "Remotion instalado", "cd remotion && npm install")
    linha((ROOT / "hyperframes/node_modules/hyperframes").exists(), "HyperFrames instalado", "cd hyperframes && npm install")
    linha((ROOT / "hyperframes/node_modules/gsap/dist/gsap.min.js").exists(), "GSAP (animações do motion)", "cd hyperframes && npm install")
    chrome = _cmd(["npx", "hyperframes", "browser", "path"]) if node and (ROOT / "hyperframes").exists() else ""
    linha("chrome" in chrome.lower() or "headless" in chrome.lower(), "navegador de render do HyperFrames",
          "cd hyperframes && npx hyperframes browser ensure")
    linha((ROOT / ".claude/skills/hyperframes/SKILL.md").exists(), "skills do HyperFrames",
          "npx skills experimental_install", obrigatorio=False)
    print("Entrega no Google Drive:")
    from .entrega import pasta_drive
    pd = pasta_drive()
    linha(bool(pd), f"pasta 'Vídeos editados' sincronizada{': ' + str(pd) if pd else ''}",
          "instale o Google Drive para Desktop, entre na sua conta e confira no Finder: Meu Drive > "
          "Edição de vídeo - Claude > Vídeos editados (no app do Drive, a pasta deve estar 'disponível'/espelhada)")
    if sys.platform == "darwin":
        hw = "videotoolbox" in _cmd(["ffmpeg", "-hide_banner", "-hwaccels"])
        linha(hw, "decodificação por hardware do Mac (vídeo do iPhone mais rápido)", "brew reinstall ffmpeg", obrigatorio=False)
    return ok


if __name__ == "__main__":
    raise SystemExit(main())
