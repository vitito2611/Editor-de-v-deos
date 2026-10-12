"""Entrega numa pasta local do Finder (pedido do cliente: NÃO usar mais o Google Drive).

Padrão: ~/Desktop/Vídeos editados (no Finder aparece como Mesa > Vídeos editados), criada se não existir.
A variável EDITOR_PASTA força outro caminho.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from .utils import log

PASTA = "Vídeos editados"


def pasta_destino() -> Path:
    p = os.environ.get("EDITOR_PASTA") or os.environ.get("EDITOR_PASTA_DRIVE")
    p = Path(p).expanduser() if p else Path.home() / "Desktop" / PASTA
    p.mkdir(parents=True, exist_ok=True)
    return p


def entregar(arquivos: list[Path], nome_base: str) -> list[Path]:
    """Copia os vídeos finais (com e sem trilha) para a pasta do Finder."""
    destino = pasta_destino()
    feitos = []
    for a in arquivos:
        if not a or not Path(a).is_file():
            continue
        sufixo = "sem trilha" if "sem_trilha" in Path(a).stem else "com trilha"
        dst = destino / f"{nome_base} ({sufixo}).mp4"
        shutil.copy2(a, dst.with_suffix(".parcial"))     # o Finder só vê o arquivo pronto
        dst.with_suffix(".parcial").replace(dst)
        feitos.append(dst)
        log.info("  📁 %s", dst)
    return feitos
