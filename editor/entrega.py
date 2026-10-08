"""Entrega na pasta "Vídeos editados" do Google Drive (pedido do cliente).

Na nuvem não há como subir vídeo grande no Drive (o conector só aceita o arquivo dentro da chamada).
No Mac do cliente, o Google Drive para Desktop sincroniza uma pasta local — basta salvar lá:
  ~/Library/CloudStorage/GoogleDrive-<email>/Meu Drive/Edição de vídeo - Claude/Vídeos editados
(Windows: G:\\Meu Drive\\...). A variável EDITOR_PASTA_DRIVE força outro caminho.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from .utils import log

PASTA = "Vídeos editados"
PAI = "Edição de vídeo - Claude"


def pasta_drive() -> Path | None:
    if os.environ.get("EDITOR_PASTA_DRIVE"):
        p = Path(os.environ["EDITOR_PASTA_DRIVE"]).expanduser()
        return p if p.is_dir() else None
    raizes = []
    cs = Path.home() / "Library" / "CloudStorage"
    if cs.is_dir():
        raizes += sorted(cs.glob("GoogleDrive-*"))
    raizes += [Path(f"{l}:/") for l in "GHIJ" if Path(f"{l}:/").exists()]          # Windows
    for r in raizes:
        for meu in ("Meu Drive", "My Drive"):
            alvo = r / meu / PAI / PASTA
            if alvo.is_dir():
                return alvo
        achados = list(r.glob(f"*/**/{PASTA}"))[:1]
        if achados:
            return achados[0]
    return None


def entregar(arquivos: list[Path], nome_base: str) -> list[Path]:
    """Copia os vídeos finais para a pasta do Drive (o Drive para Desktop faz o upload sozinho)."""
    destino = pasta_drive()
    if destino is None:
        log.warning("  pasta \"%s\" do Google Drive não encontrada neste computador — instale o Google Drive "
                    "para Desktop (ou defina EDITOR_PASTA_DRIVE). Vídeos ficaram em output/.", PASTA)
        return []
    feitos = []
    for a in arquivos:
        if not a or not Path(a).exists():
            continue
        sufixo = "sem trilha" if "sem_trilha" in Path(a).stem else "com trilha"
        dst = destino / f"{nome_base} ({sufixo}).mp4"
        shutil.copy2(a, dst.with_suffix(".parcial"))     # o Drive só vê o arquivo pronto
        dst.with_suffix(".parcial").replace(dst)
        feitos.append(dst)
        log.info("  ☁ Drive: %s", dst)
    return feitos
