"""Modelo "cinema3d" de motion (HyperFrames + Three.js): cenas 3D com linguagem de cinema.

Pedido do cliente (vídeo 3, v4): "animação nível cinema", menos texto nos motions (1–3 palavras), mais
animação, tudo dentro da zona segura do Reels. Cada cena é um arquivo em hyperframes/modelos/cenas3d/<tipo>.js
com `function montarCena(ctx)` que devolve `desenhar(t)` (o 3D é desenhado a partir do tempo do HyperFrames,
então o render é determinístico). A tipografia vem por cima, com GSAP.

Roteiro (YAML), `modelo: cinema3d` (uma cena por motion inserido):
  cenas:
    - {tipo: vidros, texto: "Alguns vão|*sumir.*", ficam: [1, 3, 7], dur: 2.6}
  Campos comuns: texto ("|" quebra linha, *x* = destaque Black Jack ciano), texto_y (px em 1080x1920),
  tamanho (px), texto_t (s, entrada), texto_sai (s, saída), fundo ("roxo" | "escuro" | "transparente").
  `transparente` renderiza em MOV com alfa (ProRes 4444) para ir POR CIMA do vídeo (formato sobreposto).
"""
from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

from .utils import ROOT

HF = ROOT / "hyperframes"
MODELO = HF / "modelos" / "cinema3d.html"
CENAS = HF / "modelos" / "cenas3d"
FONTES = ["Rubik-Medium.ttf", "Rubik-Bold.ttf", "Rubik-Black.ttf", "NotoSerif-BoldItalic.ttf"]
ACENTO, MARCA = "#24d0dc", "#5d2e8c"
FUNDOS = {
    "roxo": "radial-gradient(ellipse 90% 60% at 50% 42%, #2a1450 0%, #150a2a 45%, #07040f 100%)",
    "escuro": "radial-gradient(ellipse 80% 55% at 50% 45%, #1a1030 0%, #0b0716 55%, #050309 100%)",
    "azul": "radial-gradient(ellipse 85% 60% at 50% 40%, #102a44 0%, #0a1426 50%, #04070e 100%)",
    "transparente": "transparent",
}


def _rgb(h: str) -> str:
    h = h.lstrip("#")
    return ", ".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def _texto(c: dict) -> str:
    txt = c.get("texto")
    if not txt:
        return ""
    linhas = []
    for l in str(txt).split("|"):
        l = html.escape(l.strip())
        l = re.sub(r"\*([^*]+)\*", r'<span class="dest">\1</span>', l)
        linhas.append(f'<span class="mask"><span class="ln">{l}</span></span>')
    y = float(c.get("texto_y", 470))
    tam = float(c.get("tamanho", 104))
    return (f'<div class="texto" data-t="{c.get("texto_t", 0.12)}" data-sai="{c.get("texto_sai", 99)}" '
            f'style="top:calc({y} * var(--u));font-size:calc({tam} * var(--u))">{"".join(linhas)}</div>')


def montar_cinema3d(roteiro: dict, pasta: Path, W: int, H: int) -> Path:
    if len(roteiro["cenas"]) != 1:
        raise ValueError("modelo cinema3d: uma cena por roteiro (cada motion é uma inserção)")
    c = dict(roteiro["cenas"][0])
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "fonts").mkdir(exist_ok=True)
    for f in FONTES:
        shutil.copy2(ROOT / "assets" / "fonts" / f, pasta / "fonts" / f)
    shutil.copy2(HF / "node_modules" / "gsap" / "dist" / "gsap.min.js", pasta / "gsap.min.js")
    tres = HF / "node_modules" / "three"
    (pasta / "lib" / "addons" / "environments").mkdir(parents=True, exist_ok=True)
    (pasta / "lib" / "addons" / "geometries").mkdir(parents=True, exist_ok=True)
    for f in ("three.module.min.js", "three.core.min.js"):
        shutil.copy2(tres / "build" / f, pasta / "lib" / f)
    for f in ("environments/RoomEnvironment.js", "geometries/RoundedBoxGeometry.js"):
        shutil.copy2(tres / "examples" / "jsm" / f, pasta / "lib" / "addons" / f)
    from .utils import arquivo_black_jack
    bj = arquivo_black_jack()
    if bj:
        shutil.copy2(bj, pasta / "fonts" / f"BlackJack{bj.suffix.lower()}")
        face = f'@font-face {{ font-family: "Black Jack"; src: url("fonts/BlackJack{bj.suffix.lower()}"); }}'
        css = '"Black Jack", cursive; font-weight: 400; font-size: 1.25em; letter-spacing: 0'
    else:
        face, css = "", '"Noto Serif", serif; font-style: italic; font-weight: 700; letter-spacing: -0.01em'
    dur = float(c.get("dur", 2.6))
    fundo = c.get("fundo", "roxo")
    cena_js = (CENAS / f"{c['tipo']}.js").read_text(encoding="utf-8")
    dados = {"dur": dur, "pre_roll": roteiro.get("pre_roll", 0.45), "cena": c, "W": W, "H": H}
    doc = MODELO.read_text(encoding="utf-8")
    for k, v in {"__FONTE_DEST_FACE__": face, "__FONTE_DEST_CSS__": css, "__W__": str(W), "__H__": str(H),
                 "__DUR__": f"{dur:.3f}", "__TITULO__": html.escape(roteiro.get("titulo", "motion")),
                 "__FUNDO__": FUNDOS.get(fundo, fundo), "__FUNDO_SOLIDO__": "transparent" if fundo == "transparente" else "#07040f",
                 "__ACENTO__": ACENTO, "__MARCA__": MARCA, "__ACENTO_RGB__": _rgb(ACENTO),
                 "__TEXTO_HTML__": _texto(c), "__CSS_CENA__": c.get("css", ""),
                 "__CENA_JS__": cena_js, "__DADOS__": json.dumps(dados, ensure_ascii=False)}.items():
        doc = doc.replace(k, v)
    (pasta / "index.html").write_text(doc, encoding="utf-8")
    (pasta / "hyperframes.json").write_text(json.dumps({"name": pasta.name}), encoding="utf-8")
    return pasta
