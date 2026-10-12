"""Entrega na pasta "Vídeos editados" do Google Drive (o cliente voltou ao Drive: a pasta local ocupava espaço).

No Mac, o Google Drive para Desktop sincroniza:
  ~/Library/CloudStorage/GoogleDrive-<email>/Meu Drive/Edição de vídeo - Claude/Vídeos editados
Depois do upload o arquivo fica só na nuvem (modo "streaming"), sem ocupar o disco.
Sem o Drive instalado: ~/Desktop/Vídeos editados. A variável EDITOR_PASTA força outro caminho.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from .utils import log

PASTA = "Vídeos editados"
PAI = "Edição de vídeo - Claude"


def pasta_drive() -> Path | None:
    raizes = []
    cs = Path.home() / "Library" / "CloudStorage"
    if cs.is_dir():
        raizes += sorted(cs.glob("GoogleDrive-*"))
    raizes += [Path(f"{l}:/") for l in "GHIJ" if Path(f"{l}:/").exists()]          # Windows
    for r in raizes:
        for meu in ("Meu Drive", "My Drive"):
            if (r / meu).is_dir():
                alvo = r / meu / PAI / PASTA
                alvo.mkdir(parents=True, exist_ok=True)
                return alvo
    return None


def pasta_destino() -> Path:
    p = os.environ.get("EDITOR_PASTA") or os.environ.get("EDITOR_PASTA_DRIVE")
    if p:
        p = Path(p).expanduser()
    else:
        p = pasta_drive()
        if p is None:
            p = Path.home() / "Desktop" / PASTA
            log.warning("  Google Drive para Desktop não encontrado — salvando em %s", p)
    p.mkdir(parents=True, exist_ok=True)
    return p


def entregar(arquivos: list[Path], nome_base: str) -> list[Path]:
    """Copia os vídeos finais (com e sem trilha) para a pasta do Drive (o Drive para Desktop sobe sozinho)."""
    destino = pasta_destino()
    feitos = []
    for a in arquivos:
        if not a or not Path(a).is_file():
            continue
        sufixo = "sem trilha" if "sem_trilha" in Path(a).stem else "com trilha"
        dst = destino / f"{nome_base} ({sufixo}).mp4"
        shutil.copy2(a, dst.with_suffix(".parcial"))     # o Drive só vê o arquivo pronto
        dst.with_suffix(".parcial").replace(dst)
        feitos.append(dst)
        log.info("  📁 %s", dst)
    return feitos
