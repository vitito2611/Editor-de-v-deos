"""Projeto Remotion da edição — para ver e editar junto (Studio / Player) e renderizar o final.

Divide a edição em:
  base.mp4   cortes, zooms, transições, cor, grão e o áudio masterizado (feito pelo FFmpeg — pesado)
  camadas    legendas, cards, contadores, títulos, B-roll e fotos (React, leves e editáveis)

Saída em remotion/public/projetos/<slug>/ (projeto.json + mídia) e a lista de composições em
remotion/src/projetos.gen.ts. No Studio (`cd remotion && npx remotion studio`) cada vídeo aparece
como uma composição com cada camada nomeada na timeline. O render final usa render-edicao.mjs.
Editar o projeto.json (texto, tempo, duração, `oculto: true`) e renderizar de novo NÃO refaz a base.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from .remotion_fx import DIR, cfg_of
from .subtitles import Placer, group_words
from .utils import ffmpeg, log

PUBLIC = DIR / "public" / "projetos"


def slug(nome: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", nome).strip("-")
    return ("Edicao-" + s)[:60]


VARIANTE = {"dinamico": "dinamico", "cinetico": "cinetico"}   # resto → "simples" (frase inteira, discreta)


def _legendas(words_out, g, faces, cfg, pular, estilos_log=None) -> list[dict]:
    """Blocos de legenda para o Remotion, respeitando o estilo de cada modelo: o estilo de cada bloco
    vem da mesma decisão das legendas ASS (base × impacto)."""
    from .subtitles import aplicar_fontes
    lc = dict(cfg["legendas"])
    estilos = aplicar_fontes(lc)
    st = estilos[lc["estilo_base"]]
    por_t = {round(r["t"], 2): r["estilo"] for r in (estilos_log or [])}
    placer = Placer(g, faces, lc)
    size = st.get("tamanho", 64) * (g.canvas_w / 1080 if g.canvas_h > g.canvas_w else g.canvas_h / 1080)
    ws = [w for w in words_out if not any(a - 0.05 <= w["s"] < b for a, b in pular)]
    grupos = group_words(ws, lc, st)
    out = []
    for k, grp in enumerate(grupos):
        t0 = grp[0]["s"]
        nxt = grupos[k + 1][0]["s"] if k + 1 < len(grupos) else grp[-1]["e"] + 0.4
        t1 = min(nxt, grp[-1]["e"] + 0.6)
        # a legenda termina onde começa um motion/card (não invade o texto da inserção)
        t1 = min([t1] + [a for a, _ in pular if a > t0 + 0.05])
        nchars = sum(len(w["w"]) + 1 for w in grp)
        nome = por_t.get(round(t0, 2), lc["estilo_base"])
        sb = estilos.get(nome, st)
        tam = sb.get("tamanho", 64)
        pos = sb.get("posicao", "peito")
        if pos == "centro":
            pos = "peito"          # preferência do cliente: legenda logo abaixo do rosto, sem cobrir a boca
        _, y = placer.anchor(pos, t0, tam * size / max(1, st.get("tamanho", 64)), nchars, 2)
        out.append({"id": f"L{k:03d}", "t": round(t0, 3), "dur": round(max(0.2, t1 - t0), 3),
                    "palavras": [{"w": w["w"], "s": round(w["s"], 3), "kw": round(w.get("kw", 0), 3)} for w in grp],
                    "y": round(y / g.canvas_h, 4), "estilo": VARIANTE.get(sb.get("animacao"), "simples"),
                    "tamanho": tam})
    return out


def exportar(nome: str, g, total: float, base: Path, lut: str, cfg: dict, words_out, faces,
             dyn_events: list[dict], rjobs: list[dict], card_spans, lut_fundo_card: bool = True,
             estilos_log=None) -> Path:
    """Escreve o projeto (mídia + projeto.json) e atualiza a lista de composições."""
    rc = cfg_of(cfg)
    sl = slug(nome)
    d = PUBLIC / sl
    if d.exists():
        shutil.rmtree(d)
    (d / "midia").mkdir(parents=True)
    shutil.copy2(base, d / "base.mp4")
    camadas = []
    cards_rem = {round(j["t"], 2): j for j in rjobs if j["tipo"] == "card"}
    for k, e in enumerate(dyn_events):
        arq = Path(e["arquivo"])
        dst = d / "midia" / f"{k:02d}_{e['tipo']}.mp4"
        # B-roll/fotos/fundos de card recebem a mesma cor (LUT) que o vídeo base
        # o fundo do card vem do próprio vídeo: se a cor já foi aplicada nos segmentos, não aplica de novo
        # motion (HyperFrames) tem a paleta própria do exemplo: não recebe o look da filmagem
        filtro = lut if (lut and e["tipo"] != "motion" and (e["tipo"] != "card" or lut_fundo_card)) else "null"
        ffmpeg("-i", str(arq), "-an", "-vf", filtro, "-c:v", "libx264", "-crf", "16", "-preset", "veryfast",
               "-pix_fmt", "yuv420p", str(dst))
        c = {"id": f"C{k:02d}", "tipo": "broll" if e["tipo"] in ("video", "angulo_ia", "motion") else e["tipo"],
             "t": round(e["t"], 3), "dur": round(e["dur"], 3), "arquivo": f"midia/{dst.name}",
             "corte_seco": bool(e.get("corte_seco")), "motivo": e.get("motivo", "")}
        if e["tipo"] == "foto":
            c["tipo"] = "broll"          # a foto já vem com Ken Burns renderizado em vídeo
            c["nome"] = f"Foto: {e.get('busca', '')}"
        elif e["tipo"] == "video":
            c["nome"] = f"B-roll: {e.get('busca', '')}"
        elif e["tipo"] == "motion":
            c["nome"] = f"Motion: {e.get('busca') or 'HyperFrames'}"
        elif e["tipo"] == "card":
            j = cards_rem.get(round(e["t"], 2))
            c["palavras"] = j["palavras"] if j else [{"w": t, "s": 0.12 * i} for i, t in enumerate((e.get("texto") or "").split())]
            c["y"] = j["y"] if j else 0.47
        camadas.append(c)
    for k, j in enumerate(x for x in rjobs if x["tipo"] != "card"):
        camadas.append(dict({kk: v for kk, v in j.items()}, id=f"M{k:02d}"))
    proj = {
        "nome": nome, "W": g.canvas_w, "H": g.canvas_h, "fps": round(float(g.fps), 3), "dur": round(total, 3),
        "raiz": f"projetos/{sl}/", "base": "base.mp4",
        "tema": dict(rc["tema"], fonte_legenda=_fonte_legenda(cfg),
                     tamanho_legenda=cfg["legendas"]["estilos"][cfg["legendas"]["estilo_base"]].get("tamanho", 64)),
        "legendas": _legendas(words_out, g, faces, cfg, card_spans, estilos_log),
        "camadas": sorted(camadas, key=lambda c: c["t"]),
    }
    pj = d / "projeto.json"
    pj.write_text(json.dumps(proj, ensure_ascii=False, indent=1), encoding="utf-8")
    gerar_lista()
    log.info("  projeto Remotion: %s (%d legendas, %d camadas) → Studio: cd remotion && npx remotion studio",
             sl, len(proj["legendas"]), len(proj["camadas"]))
    return pj


def _fonte_legenda(cfg) -> str:
    st = cfg["legendas"]["estilos"][cfg["legendas"]["estilo_base"]]
    return cfg["legendas"].get("fonte_base") or st.get("fonte", "Rubik")


def gerar_lista() -> None:
    itens = []
    for pj in sorted(PUBLIC.glob("*/projeto.json")):
        props = json.loads(pj.read_text(encoding="utf-8"))
        itens.append(f'  {{ id: {json.dumps(pj.parent.name)}, props: {json.dumps(props, ensure_ascii=False)} }},')
    (DIR / "src" / "projetos.gen.ts").write_text(
        "// Gerado por editor/projeto.py — um item por vídeo editado (não edite à mão).\n"
        'import type { Projeto } from "./Edicao";\n'
        "export const PROJETOS: { id: string; props: Projeto }[] = [\n" + "\n".join(itens) + "\n];\n",
        encoding="utf-8")


def renderizar(pj: Path, saida: Path, crf: int = 18) -> bool:
    log.info("  render final pelo Remotion (o mesmo do Studio)…")
    r = subprocess.run(["node", str(DIR / "render-edicao.mjs"), str(Path(pj).resolve()), str(saida.resolve()), str(crf)],
                       cwd=DIR, capture_output=True, text=True)
    if r.returncode != 0 or not saida.exists():
        log.warning("  render Remotion falhou → composição FFmpeg. %s", (r.stderr or r.stdout)[-800:])
        return False
    return True


def aplicar(pj: Path, alt: dict) -> dict:
    """Aplica as alterações salvas na página-estúdio (db "edicao/atual") ao projeto.json."""
    proj = json.loads(pj.read_text(encoding="utf-8"))
    n = 0
    for chave in ("camadas", "legendas"):
        mud = (alt.get(chave) or {})
        for item in proj[chave]:
            if item["id"] in mud:
                item.update(mud[item["id"]])
                n += 1
    pj.write_text(json.dumps(proj, ensure_ascii=False, indent=1), encoding="utf-8")
    gerar_lista()
    log.info("  %d itens alterados no projeto%s", n, f"; pedido: {alt['pedido']}" if alt.get("pedido") else "")
    return proj


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Projeto Remotion: aplicar edições da página e renderizar")
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("aplicar")
    a.add_argument("projeto", type=Path)
    a.add_argument("alteracoes", type=Path, help="JSON salvo pela página (doc edicao/atual)")
    r = sp.add_parser("renderizar")
    r.add_argument("projeto", type=Path)
    r.add_argument("saida", type=Path)
    r.add_argument("--audio-sem-trilha", type=Path, help="gera também <saida>_sem_trilha.mp4 trocando o áudio")
    x = ap.parse_args()
    if x.cmd == "aplicar":
        aplicar(x.projeto, json.loads(x.alteracoes.read_text(encoding="utf-8")))
    else:
        if renderizar(x.projeto, x.saida) and x.audio_sem_trilha:
            sem = x.saida.with_name(x.saida.stem.replace("_com_trilha", "") + "_sem_trilha.mp4")
            ffmpeg("-i", str(x.saida), "-i", str(x.audio_sem_trilha), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                   "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(sem))
            print(sem)


if __name__ == "__main__":
    from .utils import setup_logging
    setup_logging()
    main()
