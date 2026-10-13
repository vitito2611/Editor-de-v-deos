"""Entrega em qualidade alta sem o limite de 30 MB do chat: página privada (Artifact) com o vídeo dividido em partes
de até 14 MB (o Artifact aceita até 15 MB por arquivo e 256 MB por versão). A página baixa as partes, junta no
navegador e entrega UM arquivo .mp4 idêntico ao original (capability `downloads`), além de tocar o vídeo ali mesmo.

Uso: python -m editor.entrega_web <pasta_saida> "Título" com_trilha.mp4 sem_trilha.mp4
     → codifica (1080x1920, ~6,3 Mbps 2-pass) e gera <pasta_saida>/{index.html, manifesto.json, partes/*}.
As duas versões têm a MESMA imagem: o vídeo é codificado uma vez só e a versão sem trilha só troca o áudio
(metade do tempo de codificação).
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

PARTE = 14 * 1024 * 1024
MODELO = Path(__file__).resolve().parent.parent / "assets" / "entrega" / "pagina.html"


def codificar(com: Path, sem: Path | None, pasta: Path, kbps: int = 6300) -> list[tuple[str, Path]]:
    """Codifica o vídeo uma vez (2-pass) e monta as duas versões trocando só o áudio."""
    from .utils import ffmpeg
    pasta.mkdir(parents=True, exist_ok=True)
    log_ = pasta / "2pass"
    v = pasta / "video.mp4"
    ffmpeg("-i", str(com), "-an", "-c:v", "libx264", "-preset", "slow", "-tune", "film", "-b:v", f"{kbps}k",
           "-pass", "1", "-passlogfile", str(log_), "-f", "mp4", "/dev/null")
    ffmpeg("-i", str(com), "-an", "-c:v", "libx264", "-preset", "slow", "-tune", "film", "-b:v", f"{kbps}k",
           "-maxrate", f"{kbps * 2}k", "-bufsize", f"{int(kbps * 2.5)}k", "-pass", "2", "-passlogfile", str(log_),
           "-pix_fmt", "yuv420p", "-profile:v", "high", str(v))
    out = []
    for rotulo, src, nome in (("Com trilha", com, "com.mp4"), ("Sem trilha", sem, "sem.mp4")):
        if src is None:
            continue
        ffmpeg("-i", str(v), "-i", str(src), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
               "-movflags", "+faststart", "-shortest", str(pasta / nome))
        out.append((rotulo, pasta / nome))
    v.unlink(missing_ok=True)
    for f in pasta.glob("2pass*"):
        f.unlink()
    return out


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
    out, tit, com, *resto = sys.argv[1:]
    vids = codificar(Path(com), Path(resto[0]) if resto else None, Path(out) / "hq")
    m = preparar(Path(out), tit, vids)
    print(json.dumps({v["rotulo"]: len(v["partes"]) for v in m["videos"]}))
