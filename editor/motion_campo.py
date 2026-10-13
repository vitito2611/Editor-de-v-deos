"""Modelo "campo" de motion (HyperFrames + Three.js) — linguagem "ONE SECOND / field guide".

Pedido do cliente (vídeo 4): motion de nível profissional baseado em referencias/motion3/ref.mp4 — preto com
estrelas, HUD (cantos, rótulos mono, timecode, barra de progresso), número gigante contando com zero-fantasma,
legenda em script (Black Jack), objetos 3D feitos de pontos com halo. Uma cena por motion inserido; cada cena é
hyperframes/modelos/cenas_campo/<tipo>.js com `montarCena(ctx)` → `desenhar(t)` (HUD e 3D são função do tempo).

Roteiro (YAML), `modelo: campo`:
  cenas:
    - {tipo: headline, rotulo: "...", linha: "Como vão ser os próximos", numero: 10, unidade: "anos",
       script: "na odontologia.", dur: 3.6}
  Pouco texto: o número/objeto conta a história; a frase vai no máximo em 1 linha de script.
"""
from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

from .utils import ROOT

HF = ROOT / "hyperframes"
MODELO = HF / "modelos" / "campo.html"
CENAS = HF / "modelos" / "cenas_campo"
FONTES = ["Rubik-Medium.ttf", "Rubik-Bold.ttf", "Rubik-Black.ttf", "JetBrainsMono-Regular.ttf", "JetBrainsMono-Bold.ttf",
          "NotoSerif-Italic.ttf"]


def montar_campo(roteiro: dict, pasta: Path, W: int, H: int) -> Path:
    if len(roteiro["cenas"]) != 1:
        raise ValueError("modelo campo: uma cena por roteiro (cada motion é uma inserção)")
    c = dict(roteiro["cenas"][0])
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "fonts").mkdir(exist_ok=True)
    for f in FONTES:
        shutil.copy2(ROOT / "assets" / "fonts" / f, pasta / "fonts" / f)
    shutil.copy2(HF / "node_modules" / "gsap" / "dist" / "gsap.min.js", pasta / "gsap.min.js")
    tres = HF / "node_modules" / "three"
    (pasta / "lib").mkdir(exist_ok=True)
    for f in ("three.module.min.js", "three.core.min.js"):
        shutil.copy2(tres / "build" / f, pasta / "lib" / f)
    from .utils import arquivo_black_jack
    bj = arquivo_black_jack()
    if bj:
        shutil.copy2(bj, pasta / "fonts" / f"BlackJack{bj.suffix.lower()}")
        face = f'@font-face {{ font-family: "Black Jack"; src: url("fonts/BlackJack{bj.suffix.lower()}"); }}'
        css = '"Black Jack", cursive; font-weight: 400; letter-spacing: 0'
    else:   # reserva: itálico serifado (o mesmo papel da referência)
        face, css = "", '"Noto Serif", serif; font-style: italic; font-weight: 400; letter-spacing: -0.01em'
    dur = float(c.get("dur", 3.0))
    dados = {"dur": dur, "pre_roll": roteiro.get("pre_roll", 0.3), "cena": c, "W": W, "H": H}
    doc = MODELO.read_text(encoding="utf-8")
    for k, v in {"__FONTE_DEST_FACE__": face, "__FONTE_DEST_CSS__": css, "__W__": str(W), "__H__": str(H),
                 "__DUR__": f"{dur:.3f}", "__TITULO__": html.escape(roteiro.get("titulo", "motion")),
                 "__CSS_CENA__": c.get("css", ""), "__CENA_JS__": (CENAS / f"{c['tipo']}.js").read_text(encoding="utf-8"),
                 "__DADOS__": json.dumps(dados, ensure_ascii=False)}.items():
        doc = doc.replace(k, v)
    (pasta / "index.html").write_text(doc, encoding="utf-8")
    (pasta / "hyperframes.json").write_text(json.dumps({"name": pasta.name}), encoding="utf-8")
    return pasta
