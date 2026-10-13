"""Entrega em qualidade alta sem o limite de 30 MB do chat: página privada (Artifact) com o vídeo dividido em partes
de até 14 MB (o Artifact aceita até 15 MB por arquivo e 256 MB por versão). A página baixa as partes, junta no
navegador e entrega UM arquivo .mp4 idêntico ao original (capability `downloads`), além de tocar o vídeo ali mesmo.

Uso: python -m editor.entrega_web <pasta_saida> "Título" com_trilha.mp4 sem_trilha.mp4
     → <pasta_saida>/{index.html, manifesto.json, partes/*} pronto para publicar.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

PARTE = 14 * 1024 * 1024
MODELO = Path(__file__).resolve().parent.parent / "assets" / "entrega" / "pagina.html"


def preparar(saida: Path, titulo: str, videos: list[tuple[str, Path]]) -> dict:
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "partes").mkdir(exist_ok=True)
    man = {"titulo": titulo, "videos": []}
    for k, (rotulo, arq) in enumerate(videos):
        dados = arq.read_bytes()
        partes = []
        for i in range(0, len(dados), PARTE):
            nome = f"partes/v{k}_{i // PARTE:02d}.mp4"
            (saida / nome).write_bytes(dados[i:i + PARTE])
            partes.append(nome)
        man["videos"].append({"rotulo": rotulo, "arquivo": arq.name, "bytes": len(dados), "partes": partes})
    (saida / "manifesto.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    html = MODELO.read_text(encoding="utf-8").replace("__TITULO__", titulo).replace("__MANIFESTO__", json.dumps(man, ensure_ascii=False))
    (saida / "index.html").write_text(html, encoding="utf-8")
    return man


if __name__ == "__main__":
    out, tit, *arqs = sys.argv[1:]
    vids = [("Com trilha" if "com" in Path(a).stem else "Sem trilha" if "sem" in Path(a).stem else Path(a).stem, Path(a)) for a in arqs]
    m = preparar(Path(out), tit, vids)
    print(json.dumps({v["rotulo"]: len(v["partes"]) for v in m["videos"]}))
