"""Modelo "produto" de motion (HyperFrames + GSAP) — linguagem de lançamento de produto (referência "Alan").

Pedido do cliente (vídeo 4, 2ª rodada): "não gostei dos motions, se baseie nesse novo vídeo" (referencias/motion4/ref.mp4):
fundo claro com grade, palavras que escurecem, marca-texto, cards de interface ligados por setas, hub, listas com
barras, varredura de cor, explosão com anel. Cada cena é hyperframes/modelos/cenas_produto/<tipo>.js com
`function cena()` usando as peças do modelo (rotulo, titulo, card, seta, conta, varredura, explosao, camera).
"""
from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

from .utils import ROOT

HF = ROOT / "hyperframes"
MODELO = HF / "modelos" / "produto.html"
CENAS = HF / "modelos" / "cenas_produto"
FONTES = ["Rubik-Medium.ttf", "Rubik-Bold.ttf", "Rubik-Black.ttf", "JetBrainsMono-Regular.ttf", "JetBrainsMono-Bold.ttf",
          "NotoSerif-Italic.ttf"]


def montar_produto(roteiro: dict, pasta: Path, W: int, H: int) -> Path:
    if len(roteiro["cenas"]) != 1:
        raise ValueError("modelo produto: uma cena por roteiro (cada motion é uma inserção)")
    c = dict(roteiro["cenas"][0])
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "fonts").mkdir(exist_ok=True)
    for f in FONTES:
        shutil.copy2(ROOT / "assets" / "fonts" / f, pasta / "fonts" / f)
    shutil.copy2(HF / "node_modules" / "gsap" / "dist" / "gsap.min.js", pasta / "gsap.min.js")
    from .utils import arquivo_black_jack
    bj = arquivo_black_jack()
    if bj:
        shutil.copy2(bj, pasta / "fonts" / f"BlackJack{bj.suffix.lower()}")
        face = f'@font-face {{ font-family: "Black Jack"; src: url("fonts/BlackJack{bj.suffix.lower()}"); }}'
        css = '"Black Jack", cursive; font-weight: 400; letter-spacing: 0'
    else:   # reserva: itálico serifado (o mesmo papel da referência)
        face, css = "", '"Noto Serif", serif; font-style: italic; font-weight: 400; letter-spacing: -0.01em'
    dur = float(c.get("dur", 3.0))
    dados = {"dur": dur, "pre_roll": roteiro.get("pre_roll", 0.25), "cena": c, "W": W, "H": H}
    doc = MODELO.read_text(encoding="utf-8")
    for k, v in {"__FONTE_DEST_FACE__": face, "__FONTE_DEST_CSS__": css, "__W__": str(W), "__H__": str(H),
                 "__DUR__": f"{dur:.3f}", "__TITULO__": html.escape(roteiro.get("titulo", "motion")),
                 "__CSS_CENA__": c.get("css", ""), "__CENA_JS__": (CENAS / f"{c['tipo']}.js").read_text(encoding="utf-8"),
                 "__DADOS__": json.dumps(dados, ensure_ascii=False)}.items():
        doc = doc.replace(k, v)
    (pasta / "index.html").write_text(doc, encoding="utf-8")
    (pasta / "hyperframes.json").write_text(json.dumps({"name": pasta.name}), encoding="utf-8")
    return pasta
