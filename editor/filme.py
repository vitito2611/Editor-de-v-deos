"""Layout "filme" (pedido do vídeo 1022, referência referencias/motion5/ref.mp4): o orador num card embaixo e,
em cima, cenas de filme motivacionais que trocam no ritmo da fala, tudo em preto e branco, com a legenda como
tipografia grande sobre a cena (blocos em lugares diferentes, palavra-chave na fonte manuscrita).

Cenas: só fontes com licença — vídeos do Mixkit (uso livre) e fotos do Openverse/Wikimedia para pessoas citadas.
Trechos de filmes de verdade (Hollywood) têm direitos autorais e não são usados.

Plano do vídeo:
  filme:
    ativo: true
    layout: {topo: [40, 140, 1000, 820], baixo: [40, 990, 1000, 540], raio: 34, foco_y: 0.47}
    cena_min_s: 1.8                      # troca de cena no começo de um bloco de legenda depois de ≥ 1,8 s
    cenas:                               # cenas ligadas a falas (a 1ª palavra-chave que aparece no bloco)
      - {contem: "Walt Disney", foto: "Walt Disney portrait"}
      - {contem: "família", busca: "family dinner table"}
    pool: ["man running at night", ...]  # cenas genéricas, em ordem, para o resto
    cor: {saturacao: 0, contraste: 0.25, ...}
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from . import stock
from .utils import ffmpeg, log

LAYOUT = {"tipo": "filme", "topo": [40, 140, 1000, 820], "baixo": [40, 990, 1000, 540], "raio": 34, "foco_y": 0.47}
COR_PB = {"look": "nenhum", "intensidade": 1.0, "exposicao": 0.0, "contraste": 0.22, "saturacao": 0.0, "vibrance": 0.0,
          "temperatura": 0.0, "tint": 0.0, "pretos": 0.06, "sombras": [0, 0, 0], "luzes": [0, 0, 0], "vinheta": 0.35, "grao": 0.35}
# ordem das posições dos blocos (índices de POSICOES em remotion/src/Filme.tsx): esquerda, direita, centro…
ORDEM_POS = [0, 1, 2, 3, 4, 5, 1, 0, 2, 4, 3, 5]


def _norm(s: str) -> str:
    return re.sub(r"[^\w]", "", s.lower())


def _blocos(legendas: list[dict], max_pal: int = 5, max_s: float = 2.4) -> list[dict]:
    """Reagrupa as palavras das legendas em blocos curtos de frase (quebra na pontuação, ≤ 5 palavras, ≤ 2,4 s)."""
    ws = [w for l in sorted(legendas, key=lambda l: l["t"]) for w in l["palavras"]]
    fim_leg = max((l["t"] + l["dur"] for l in legendas), default=0.0)
    blocos, cur = [], []
    for i, w in enumerate(ws):
        if cur and (len(cur) >= max_pal or w["s"] - cur[0]["s"] > max_s):
            blocos.append(cur)
            cur = []
        cur.append(w)
        # fim de frase fecha o bloco (mesmo com 1 palavra: "Rodriguez." não se junta à frase seguinte)
        if re.search(r"[.!?]$", w["w"]) or (re.search(r"[,;:]$", w["w"]) and len(cur) >= 2):
            blocos.append(cur)
            cur = []
    if cur:
        blocos.append(cur)
    # bloco de 1 palavra curta sem pontuação forte vai para o próximo
    out = []
    for k, b in enumerate(blocos):
        t0 = b[0]["s"]
        nxt = blocos[k + 1][0]["s"] if k + 1 < len(blocos) else fim_leg
        t1 = min(nxt, b[-1]["s"] + 0.9)
        out.append({"id": f"F{k:03d}", "t": round(t0, 3), "dur": round(max(0.35, t1 - t0), 3), "palavras": b,
                    "y": 0.5, "estilo": "filme", "pos": ORDEM_POS[k % len(ORDEM_POS)], "tamanho": 1})
    return out


def _clipe(src: Path, dst: Path, dur: float, desloc: float, caixa: list[int], foto: bool) -> bool:
    """Recorta/escala a cena para o tamanho do card (2× para nitidez em 1080)."""
    w, h = caixa[2], caixa[3]
    if foto:
        shutil.copy2(src, dst.with_suffix(src.suffix.lower()))
        return True
    vf = (f"scale='if(gt(a,{w}/{h}),-2,{w})':'if(gt(a,{w}/{h}),{h},-2)',crop={w}:{h},setsar=1,fps=30")
    try:
        ffmpeg("-ss", f"{desloc:.2f}", "-i", str(src), "-t", f"{dur + 0.4:.2f}", "-an", "-vf", vf, "-c:v", "libx264",
               "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(dst))
        return dst.exists()
    except Exception as e:  # noqa: BLE001
        log.warning("  cena falhou (%s): %s", src.name, e)
        return False


def aplicar(proj: dict, cfg: dict, d: Path) -> dict:
    fc = cfg.get("filme") or {}
    lay = dict(LAYOUT, **(fc.get("layout") or {}))
    proj["layout"] = lay
    proj["cor"] = dict(COR_PB, **(fc.get("cor") or {}))
    blocos = _blocos(proj.get("legendas") or [], fc.get("max_palavras", 5), fc.get("max_bloco_s", 2.4))
    proj["legendas"] = blocos
    total = float(proj["dur"])

    # onde cada cena começa: no início de um bloco, depois de ≥ cena_min_s (ou quando um bloco cita uma cena ligada)
    ligadas = [dict(c) for c in (fc.get("cenas") or [])]
    pool = list(fc.get("pool") or ["man running at night"])
    cmin = float(fc.get("cena_min_s", 1.8))
    cortes: list[tuple[float, dict | None]] = []
    usadas = set()
    for b in blocos:
        txt = _norm(" ".join(w["w"] for w in b["palavras"]))
        lig = next((c for i, c in enumerate(ligadas) if i not in usadas and _norm(c["contem"]) in txt), None)
        if lig:
            usadas.add(ligadas.index(lig))
        if not cortes:
            cortes.append((0.0, lig))
        elif lig and b["t"] - cortes[-1][0] < 1.2 and cortes[-1][1] is None:
            cortes[-1] = (cortes[-1][0], lig)          # cena ligada logo depois de um corte: troca a cena em vez de piscar
        elif (lig and b["t"] - cortes[-1][0] >= 1.2) or b["t"] - cortes[-1][0] >= cmin:
            cortes.append((b["t"], lig))
    camadas = [c for c in proj.get("camadas") or [] if c.get("tipo") != "broll" or c.get("formato")]
    ip, skip = 0, {}
    (d / "midia").mkdir(exist_ok=True)
    for k, (t0, lig) in enumerate(cortes):
        t1 = cortes[k + 1][0] if k + 1 < len(cortes) else total
        dur = max(0.4, t1 - t0)
        arq, nome, foto = None, "", False
        if lig and lig.get("foto"):
            r = stock.openverse_photo(lig["foto"]) or stock.openverse_photo(lig["foto"])   # 2ª tentativa: Openverse oscila
            if r:
                arq, nome, foto = r[0], f"Foto: {lig['foto']}", True
        if arq is None:
            q = (lig or {}).get("busca") or pool[ip % len(pool)]
            if not lig:
                ip += 1
            arq = stock.mixkit_video(q, skip=skip.get(q, 0), prefer_vertical=False)
            skip[q] = skip.get(q, 0) + 1
            nome = f"Cena: {q}"
        if arq is None:
            log.warning("  sem cena para o trecho %.1f–%.1f s", t0, t1)
            continue
        dst = d / "midia" / f"cena_{k:02d}.mp4"
        if not _clipe(Path(arq), dst, dur, 0.8, lay["topo"], foto):
            continue
        rel = f"midia/{dst.with_suffix(Path(arq).suffix.lower()).name}" if foto else f"midia/{dst.name}"
        camadas.append({"id": f"S{k:02d}", "tipo": "broll", "t": round(t0, 3), "dur": round(dur, 3), "arquivo": rel,
                        "corte_seco": True, "cor": True, "nome": nome,
                        "motivo": f"cena do layout filme ({(lig or {}).get('contem') or 'ritmo da fala'})"})
    proj["camadas"] = sorted(camadas, key=lambda c: c["t"])
    log.info("  layout filme: %d cenas, %d blocos de legenda", len(cortes), len(blocos))
    return proj
