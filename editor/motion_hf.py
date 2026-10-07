"""Vídeos em motion com HyperFrames (HTML + GSAP → MP4), no estilo do exemplo do cliente
(referencias/motion_exemplo.mp4): fundo claro com brilho em gradiente, texto cinético palavra a
palavra com desfoque, ícones flutuantes, palavra soletrada, colagem em anel, celular, logo e abas
de capítulo. Fontes do cliente: Rubik (texto) + Noto Serif (destaque, `*palavra*`).

Uso direto:   python -m editor.motion_hf roteiro.yaml saida.mp4 [--vertical|--horizontal] [--rapido]
Na edição:    item do plano de dinamismo `{contem: "...", tipo: motion, roteiro: config/motion/x.yaml}`
              (o motion entra como inserção em tela cheia, a voz continua por baixo).

Roteiro (YAML):
  titulo: Meu motion
  paleta: {fundo: "#ffffff", texto: "#14102a", acento: "#7b3ff2", g1: "#c4a2ff", g2: "#f6a8e0", g3: "#ffd2b0"}
  capitulos: [Intro, Problema, Solução, Ação]      # opcional (abas embaixo)
  cenas:
    - {tipo: texto, frase: "Todo dia tem algo *novo* pra descobrir", dur: 3, capitulo: 0, icones: 6}
    - {tipo: soletrado, palavra: Simples, dur: 2.2}
    - {tipo: colagem, texto: "você só quer a *solução*", imagens: [a.jpg, b.jpg], dur: 3}
    - {tipo: celular, imagem: tela.jpg, rotulo: "Tudo no *celular*", dur: 3}
    - {tipo: numero, valor: 45000, sufixo: "", legenda: "pessoas no estádio", dur: 2.5}
    - {tipo: logo, nome: "Editor IA", dur: 2.5}
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import random
import re
import shutil
import subprocess
from pathlib import Path

import yaml

from .utils import ROOT, log

HF = ROOT / "hyperframes"
MODELO = HF / "modelos" / "motion_padrao.html"
FONTES = ["Rubik-Medium.ttf", "Rubik-Bold.ttf", "Rubik-Black.ttf", "NotoSerif-Bold.ttf",
          "NotoSerif-BoldItalic.ttf", "NotoSerif-BlackItalic.ttf"]
PALETA = {"fundo": "#ffffff", "texto": "#14102a", "acento": "#7b3ff2",
          "g1": "#c4a2ff", "g2": "#f6a8e0", "g3": "#ffd2b0"}


def _frase(txt: str) -> str:
    """Palavras viram <span class="p"> (entram uma a uma); trechos entre *asteriscos* (uma ou mais
    palavras) viram destaque em Noto Serif itálico."""
    out, dest = [], False
    for tok in txt.split():
        abre, fecha = tok.startswith("*"), tok.rstrip(".,!?;:").endswith("*") and len(tok.strip("*")) > 0
        limpo = tok.replace("*", "")
        cls = "p dest" if (dest or abre) else "p"
        out.append(f'<span class="{cls}">{html.escape(limpo)}</span>')
        if abre and not fecha:
            dest = True
        if fecha:
            dest = False
    return " ".join(out)


def _icones(n: int, rng: random.Random, pal: dict) -> str:
    """Pequenas formas com gradiente espalhadas em volta do texto (no exemplo: ícones 3D flutuando)."""
    formas = ["circle", "star", "pill", "ring"]
    out = []
    for i in range(n):
        # metade em cima, metade embaixo do texto — nunca na faixa central onde está a frase
        lado = -1 if i % 2 == 0 else 1
        x = 12 + 76 * ((i // 2 + rng.uniform(0.1, 0.9)) / max(1, (n + 1) // 2))
        y = 50 + lado * rng.uniform(14, 24)
        s = rng.randint(70, 130)
        f = formas[i % len(formas)]
        gid = f"gi{i}_{rng.randint(0, 99999)}"
        cor = [pal["g1"], pal["g2"], pal["g3"], pal["acento"]]
        grad = (f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{cor[i % 4]}"/>'
                f'<stop offset="1" stop-color="{cor[(i + 1) % 4]}"/></linearGradient></defs>')
        corpo = {"circle": f'<circle cx="50" cy="50" r="42" fill="url(#{gid})"/>',
                 "ring": f'<circle cx="50" cy="50" r="34" fill="none" stroke="url(#{gid})" stroke-width="14"/>',
                 "pill": f'<rect x="12" y="32" width="76" height="36" rx="18" fill="url(#{gid})"/>',
                 "star": f'<path d="M50 6 L61 38 L95 38 L67 58 L78 92 L50 72 L22 92 L33 58 L5 38 L39 38 Z" fill="url(#{gid})"/>'}[f]
        out.append(f'<svg class="icone" viewBox="0 0 100 100" style="--s:{s};left:calc({x:.1f}% - {s / 2} * var(--u));'
                   f'top:calc({y:.1f}% - {s / 2} * var(--u))">{grad}{corpo}</svg>')
    return "".join(out)


def montar(roteiro: dict, pasta: Path, W: int, H: int) -> Path:
    """Gera o projeto HyperFrames (index.html + fontes + imagens) e devolve a pasta."""
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "fonts").mkdir(exist_ok=True)
    (pasta / "assets").mkdir(exist_ok=True)
    for f in FONTES:
        shutil.copy2(ROOT / "assets" / "fonts" / f, pasta / "fonts" / f)
    shutil.copy2(HF / "node_modules" / "gsap" / "dist" / "gsap.min.js", pasta / "gsap.min.js")
    # destaque do cliente: Black Jack (manuscrita, sem itálico/negrito falso, maior); sem o arquivo → Noto Serif itálico
    from .utils import arquivo_black_jack
    bj = arquivo_black_jack()
    if bj:
        shutil.copy2(bj, pasta / "fonts" / f"BlackJack{bj.suffix.lower()}")
        dest_face = f'@font-face {{ font-family: "Black Jack"; src: url("fonts/BlackJack{bj.suffix.lower()}"); }}'
        dest_css = '"Black Jack", cursive; font-weight: 400; font-style: normal; font-size: 1.3em; line-height: 0.9'
    else:
        dest_face = ""
        dest_css = '"Noto Serif", serif; font-style: italic; font-weight: 700'
    pal = dict(PALETA, **(roteiro.get("paleta") or {}))
    rng = random.Random(7)
    t, cenas, blocos = 0.0, [], []
    for k, c in enumerate(roteiro["cenas"]):
        c = dict(c)
        d = float(c.get("dur", 2.5))
        c["t"], c["dur"] = round(t, 3), d
        tipo = c["tipo"]
        if tipo == "texto":
            corpo = f'<div class="frase" style="--tam:{c.get("tamanho", 92)}">{_frase(c["frase"])}</div>' + _icones(int(c.get("icones", 6)), rng, pal)
        elif tipo == "soletrado":
            letras = "".join(f'<span class="letra">{html.escape(ch)}</span>' for ch in c["palavra"])
            n = len(c["palavra"])
            tl_ = min(220, int((900 if H > W else 1500) / max(1, n) * 1.6))   # cabe na largura
            guias = "".join(f'<div class="guia" style="left:{50 + (i - (n - 2) / 2) * 8.3:.1f}%"></div>' for i in range(n - 1))
            corpo = guias + f'<div class="letras" style="--tl:{tl_}">{letras}</div>'
        elif tipo == "colagem":
            imgs = c.get("imagens") or []
            n = max(len(imgs), int(c.get("quantidade", 8)))
            r, f = (330, 170) if H > W else (360, 150)
            fotos = []
            for i in range(n):
                a = 2 * math.pi * i / n
                x, y = r + r * math.cos(a) - f / 2, r + r * math.sin(a) - f * 0.625
                if i < len(imgs):
                    src = Path(imgs[i])
                    dst = pasta / "assets" / f"foto{k}_{i}{src.suffix.lower()}"
                    shutil.copy2(src if src.is_absolute() else ROOT / src, dst)
                    fundo = f'background-image:url(assets/{dst.name})'
                else:
                    fundo = f'background:linear-gradient({rng.randint(0, 360)}deg,{pal["g1"]},{pal["g2"]},{pal["g3"]})'
                fotos.append(f'<div class="foto" style="--f:{f};left:calc({x:.0f} * var(--u));top:calc({y:.0f} * var(--u));{fundo}"></div>')
            corpo = (f'<div class="anel" style="--r:{r}">{"".join(fotos)}</div>'
                     f'<div class="centro">{_frase(c.get("texto", ""))}</div>')
        elif tipo == "celular":
            dentro = ""
            if not c.get("imagem"):
                # tela de app de assistente de voz (onda + mensagens), sem precisar de print
                msgs = c.get("mensagens") or [["eu", "Como fecho mais tratamentos?"], ["ia", "Vamos montar o plano juntos."]]
                barras = "".join('<div class="barra"></div>' for _ in range(12))
                bolhas = "".join(f'<div class="bolha {html.escape(q)}">{html.escape(t)}</div>' for q, t in msgs)
                dentro = (f'<div class="app"><div class="app-topo">{html.escape(c.get("app", "Assistente IA"))}</div>'
                          f'<div class="onda">{barras}</div>{bolhas}</div>')
            if c.get("imagem"):
                src = Path(c["imagem"])
                dst = pasta / "assets" / f"tela{k}{src.suffix.lower()}"
                shutil.copy2(src if src.is_absolute() else ROOT / src, dst)
                dentro = f'<img src="assets/{dst.name}" alt="">'
            rot = f'<div class="rotulo" style="top:6%">{_frase(c["rotulo"])}</div>' if c.get("rotulo") else ""
            corpo = rot + f'<div class="celular"><div class="tela">{dentro}</div><div class="ilha"></div></div>'
        elif tipo == "logo":
            corpo = ('<div class="logo"><svg class="marca" viewBox="0 0 150 150"><circle cx="75" cy="75" r="58" fill="none" '
                     f'stroke="{pal["acento"]}" stroke-width="18" stroke-linecap="round" stroke-dasharray="{2 * math.pi * 58:.2f}" '
                     f'stroke-dashoffset="{2 * math.pi * 58:.2f}" transform="rotate(-90 75 75)"/></svg>'
                     f'<span class="nome-logo">{html.escape(c["nome"])}</span></div>')
        elif tipo == "numero":
            lg = f'<div class="legenda-num">{html.escape(c["legenda"])}</div>' if c.get("legenda") else ""
            n_chars = len(f"{c['valor']:,}") + len(c.get("sufixo", ""))
            tn = min(300, int(1500 / max(1, n_chars))) if H > W else 300   # cabe na largura do vertical
            corpo = f'<div class="pilha"><div class="numero" style="--tn:{tn}">0</div>{lg}</div>'
        else:
            raise ValueError(f"tipo de cena desconhecido: {tipo}")
        blocos.append(f'<section id="c{k}" class="clip" data-start="{c["t"]}" data-duration="{d}" data-track-index="1">'
                      f'<div class="palco">{corpo}</div></section>')
        cenas.append({kk: c[kk] for kk in ("tipo", "t", "dur", "valor", "sufixo", "capitulo") if kk in c})
        t += d
    abas = "".join(f'<div class="aba">{html.escape(a)}</div>' for a in roteiro.get("capitulos") or [])
    doc = MODELO.read_text(encoding="utf-8")
    for k, v in {"__FONTE_DEST_FACE__": dest_face, "__FONTE_DEST_CSS__": dest_css, "__W__": str(W), "__H__": str(H), "__DUR__": f"{t:.3f}", "__TITULO__": html.escape(roteiro.get("titulo", "motion")),
                 "__FUNDO__": pal["fundo"], "__TEXTO__": pal["texto"], "__ACENTO__": pal["acento"],
                 "__G1__": pal["g1"], "__G2__": pal["g2"], "__G3__": pal["g3"],
                 "__CENAS_HTML__": "\n      ".join(blocos), "__ABAS_HTML__": abas,
                 "__DADOS__": json.dumps({"dur": round(t, 3), "cenas": cenas}, ensure_ascii=False)}.items():
        doc = doc.replace(k, v)
    (pasta / "index.html").write_text(doc, encoding="utf-8")
    (pasta / "hyperframes.json").write_text(json.dumps({"name": pasta.name}), encoding="utf-8")
    return pasta


def renderizar(roteiro: dict | Path, saida: Path, W: int = 1080, H: int = 1920, rapido: bool = False) -> Path | None:
    """Monta + renderiza (com cache pelo conteúdo do roteiro). Devolve o MP4 ou None se falhar."""
    if isinstance(roteiro, (str, Path)):
        roteiro = yaml.safe_load(Path(roteiro).read_text(encoding="utf-8"))
    from .utils import arquivo_black_jack
    cinema = roteiro.get("modelo", "cinema") == "cinema"   # padrão desde o vídeo 3 (escuro, fluido, ilustrado)
    modelo = MODELO_CINEMA if cinema else MODELO
    chave = hashlib.sha1(json.dumps([roteiro, W, H, rapido, modelo.stat().st_mtime, str(arquivo_black_jack()),
                                     Path(__file__).stat().st_mtime],
                                    sort_keys=True, default=str).encode()).hexdigest()[:12]
    pasta = HF / "projetos" / f"motion_{chave}"
    cache = pasta / "renders" / "video.mp4"
    if not cache.exists():
        (montar_cinema if cinema else montar)(roteiro, pasta, W, H)
        r = subprocess.run(["npx", "hyperframes", "lint", str(pasta)], cwd=HF, capture_output=True, text=True)
        if "error" in (r.stdout + r.stderr).lower() and r.returncode != 0:
            log.warning("  HyperFrames lint: %s", (r.stdout + r.stderr)[-1200:])
        log.info("  HyperFrames: renderizando motion (%d cenas)…", len(roteiro["cenas"]))
        r = subprocess.run(["npx", "hyperframes", "render", str(pasta), "-o", str(cache),
                            "--quality", "draft" if rapido else "high", "--fps", "30"],
                           cwd=HF, capture_output=True, text=True)
        if r.returncode != 0 or not cache.exists():
            log.warning("  HyperFrames falhou: %s", (r.stderr or r.stdout)[-1500:])
            return None
        log.info("  %s", " ".join((r.stdout or "").strip().splitlines()[-2:])[:300])
    saida.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cache, saida)
    return saida


def main():
    from .utils import setup_logging
    setup_logging()
    ap = argparse.ArgumentParser(description="Motion em HyperFrames a partir de um roteiro YAML")
    ap.add_argument("roteiro", type=Path)
    ap.add_argument("saida", type=Path)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--vertical", action="store_true", help="1080x1920 (padrão)")
    g.add_argument("--horizontal", action="store_true", help="1920x1080")
    ap.add_argument("--rapido", action="store_true", help="render rascunho (mais rápido)")
    a = ap.parse_args()
    W, H = (1920, 1080) if a.horizontal else (1080, 1920)
    out = renderizar(a.roteiro, a.saida, W, H, a.rapido)
    print(out or "falhou")


if __name__ == "__main__":
    main()


# ============================================================================= modelo "cinema"
# Pedido do cliente (vídeo 3): paleta escura, movimento fluido e ILUSTRAÇÕES por cena (não só texto).
MODELO_CINEMA = HF / "modelos" / "motion_cinema.html"
PALETA_CINEMA = {"fundo": "#060913", "texto": "#eef3ff", "acento": "#5ec8ff",
                 "g1": "#1e3a8a", "g2": "#0e7490", "g3": "#312e81"}


def _titulo(txt: str, tam: int = 92, top: float = 16) -> str:
    """Título com máscara por palavra (entra de baixo para cima); *trecho* = destaque."""
    if not txt:
        return ""
    spans = []
    for sp in _frase(txt).split("</span>"):
        if sp.strip():
            spans.append(f'<span class="m">{sp.strip()}</span></span>')
    return f'<div class="titulo" style="--tam:{tam};--ty:{top}%">{"".join(spans)}</div>'


def _gear(cx: float, cy: float, r: float, dentes: int, cls: str, cor: str) -> str:
    pts = []
    for i in range(dentes * 4):
        a = 2 * math.pi * i / (dentes * 4)
        rr = r * (1.0 if (i % 4) in (1, 2) else 0.82)
        pts.append(f"{cx + rr * math.cos(a):.1f},{cy + rr * math.sin(a):.1f}")
    return (f'<g class="gear {cls}"><polygon points="{" ".join(pts)}" fill="{cor}" opacity="0.92"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r * 0.34:.1f}" fill="#060913"/></g>')


def _cena_cinema(c: dict, k: int, pasta: Path, W: int, H: int, pal: dict, rng: random.Random) -> str:
    tipo = c["tipo"]
    tit = _titulo(c.get("titulo", c.get("frase", "")), int(c.get("tamanho", 88)), float(c.get("titulo_top", 14)))
    sub = f'<div class="sub" style="top:{c.get("sub_top", 86)}%">{html.escape(c["sub"])}</div>' if c.get("sub") else ""
    iy = c.get("ilu_y", 56)
    if tipo == "texto":
        corpo = _titulo(c.get("frase", c.get("titulo", "")), int(c.get("tamanho", 110)), float(c.get("titulo_top", 40)))
        return corpo + sub
    if tipo == "cards_somem":
        fica = set(c.get("ficam", [4]))
        cards = []
        for i in range(9):
            col, lin = i % 3, i // 3
            x, y = 45 + col * 290, 50 + lin * 210
            cards.append(f'<div class="card{" fica" if i in fica else ""}" style="left:calc({x} * var(--u));'
                         f'top:calc({y} * var(--u))"><div class="ic"></div>'
                         f'<div class="ln"></div><div class="ln c"></div></div>')
        return tit + f'<div class="ilu" style="--iy:{iy}%;--iw:920;--ih:700">{"".join(cards)}</div>' + sub
    if tipo == "engrenagens":
        g = (_gear(300, 330, 190, 12, "g1", pal["acento"]) + _gear(560, 520, 130, 9, "g2", pal["g2"]) +
             _gear(620, 230, 90, 7, "g3", "#7b8cff"))
        tarefas = "".join(f'<div class="tarefa" style="top:{78 + 0 * i}%;font-weight:700">↻ {html.escape(t)}</div>'
                          for i, t in enumerate(c.get("tarefas", ["Copiar", "Colar", "Repetir"])))
        return tit + f'<div class="ilu" style="--iy:{iy}%;--iw:860;--ih:760"><svg viewBox="0 0 860 760">{g}</svg></div>' + tarefas
    if tipo == "multiplica":
        cx = cy = 430
        lig, nos = [], []
        nos.append(f'<circle class="no no0" cx="{cx}" cy="{cy}" r="58" fill="{pal["acento"]}"/>'
                   f'<circle class="no no0" cx="{cx}" cy="{cy - 14}" r="18" fill="#060913"/>'
                   f'<path class="no no0" d="M{cx - 30} {cy + 34} q30 -40 60 0" stroke="#060913" stroke-width="12" fill="none"/>')
        n1 = 6
        for i in range(n1):
            a = 2 * math.pi * i / n1 - math.pi / 2
            x1, y1 = cx + 200 * math.cos(a), cy + 200 * math.sin(a)
            lig.append(f'<line class="lig" data-n="0" x1="{cx}" y1="{cy}" x2="{x1:.0f}" y2="{y1:.0f}" stroke="{pal["acento"]}" stroke-width="5" opacity="0.7"/>')
            nos.append(f'<circle class="no" data-n="0" cx="{x1:.0f}" cy="{y1:.0f}" r="30" fill="{pal["acento"]}"/>')
            for j in (-1, 1):
                b = a + j * 0.32
                x2, y2 = cx + 370 * math.cos(b), cy + 370 * math.sin(b)
                lig.append(f'<line class="lig" data-n="1" x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="#7b8cff" stroke-width="4" opacity="0.6"/>')
                nos.append(f'<circle class="no" data-n="1" cx="{x2:.0f}" cy="{y2:.0f}" r="20" fill="#9fb4ff"/>')
        cont = f'<div class="sub contador" style="top:{c.get("contador_top", 84)}%;font-weight:900;font-size:calc(120 * var(--u));color:var(--acento)">×1</div>'
        return tit + (f'<div class="ilu" style="--iy:{iy}%;--iw:860;--ih:860"><svg viewBox="0 0 860 860">{"".join(lig)}{"".join(nos)}</svg></div>'
                      + cont)
    if tipo == "relogio":
        rel = (f'<svg viewBox="0 0 400 400"><circle cx="200" cy="200" r="180" fill="none" stroke="rgba(160,200,255,0.18)" stroke-width="22"/>'
               f'<circle class="arco" cx="200" cy="200" r="180" fill="none" stroke="{pal["acento"]}" stroke-width="22" stroke-linecap="round" '
               f'stroke-dasharray="1131" stroke-dashoffset="1131" transform="rotate(-90 200 200)"/>'
               f'<line class="ponteiro" x1="200" y1="200" x2="200" y2="70" stroke="#ffffff" stroke-width="12" stroke-linecap="round"/>'
               f'<circle cx="200" cy="200" r="16" fill="#ffffff"/></svg>')
        a1, v1, a2, v2 = c.get("antes", "Antes"), c.get("antes_valor", "8 h"), c.get("depois", "Com IA"), c.get("depois_valor", "1 h")
        barras = (f'<div style="position:absolute;left:10%;right:10%;top:{c.get("barras_top", 70)}%;height:calc(380 * var(--u))">'
                  f'<div class="rot" style="top:0">{html.escape(a1)}</div>'
                  f'<div class="barra" style="top:calc(56 * var(--u));background:rgba(160,200,255,0.25)"></div>'
                  f'<div class="val" style="top:calc(68 * var(--u));right:0">{html.escape(v1)}</div>'
                  f'<div class="rot" style="top:calc(190 * var(--u))">{html.escape(a2)}</div>'
                  f'<div class="barra" style="top:calc(246 * var(--u));background:var(--acento)"></div>'
                  f'<div class="val" style="top:calc(258 * var(--u));left:calc(140 * var(--u))">{html.escape(v2)}</div></div>')
        return tit + f'<div class="ilu" style="--iy:{c.get("ilu_y", 44)}%;--iw:520;--ih:520">{rel}</div>' + barras
    if tipo == "soma":
        a, b, r = c.get("a", "Você"), c.get("b", "IA"), c.get("resultado", "Mais resultado")
        svg = (f'<svg viewBox="-430 -300 860 600">'
               f'<g class="bola"><circle r="150" fill="rgba(160,200,255,0.12)" stroke="#9fb4ff" stroke-width="5"/>'
               f'<text y="18" text-anchor="middle" font-family="Rubik" font-weight="700" font-size="56" fill="#eef3ff">{html.escape(a)}</text></g>'
               f'<g class="bola"><circle r="150" fill="rgba(94,200,255,0.18)" stroke="{pal["acento"]}" stroke-width="5"/>'
               f'<text y="18" text-anchor="middle" font-family="Rubik" font-weight="900" font-size="64" fill="{pal["acento"]}">{html.escape(b)}</text></g>'
               f'<g class="mais"><rect x="-14" y="-60" width="28" height="120" rx="14" fill="#ffffff"/><rect x="-60" y="-14" width="120" height="28" rx="14" fill="#ffffff"/></g>'
               f'<g class="fusao"><circle r="210" fill="url(#gf{k})"/><text y="20" text-anchor="middle" font-family="Rubik" font-weight="900" font-size="58" fill="#04101f">{html.escape(r)}</text></g>'
               f'<defs><radialGradient id="gf{k}"><stop offset="0" stop-color="#bfe9ff"/><stop offset="0.6" stop-color="{pal["acento"]}"/>'
               f'<stop offset="1" stop-color="#1b3f9e"/></radialGradient></defs></svg>')
        return tit + f'<div class="ilu" style="--iy:{iy}%;--iw:860;--ih:600">{svg}</div>' + sub
    if tipo == "celular":
        msgs = c.get("mensagens") or [["eu", "Como fecho mais tratamentos?"], ["ia", "Vamos montar o plano juntos:"]]
        itens = c.get("plano") or ["Diagnóstico explicado", "Plano em etapas", "Proposta de pagamento"]
        bolhas = "".join(f'<div class="bolha passo {html.escape(q)}">{html.escape(t)}</div>' for q, t in msgs)
        plano = ('<div class="plano passo">' + "".join(f'<div class="item"><span class="ok"></span>{html.escape(t)}</div>' for t in itens) + "</div>")
        app = (f'<div class="app"><div class="app-topo"><span class="orb"></span>{html.escape(c.get("app", "Assistente IA"))}</div>'
               f'<div class="onda">{"<i></i>" * 14}</div>{bolhas}{plano}</div>')
        rot = _titulo(c.get("rotulo", ""), int(c.get("tamanho", 72)), 5) if c.get("rotulo") else ""
        return rot + (f'<div class="ilu" style="--iy:{c.get("ilu_y", 57)}%;--iw:600;--ih:1180"><div class="celular"><div class="tela">{app}'
                      f'<div class="ilha"></div></div></div></div>')
    if tipo == "timeline":
        cores = [pal["acento"], "#7b8cff", "#2dd4bf"]
        trilhas = []
        for i in range(3):
            clipes, x = [], 0
            while x < 820:
                w = rng.randint(110, 230)
                clipes.append(f'<div class="clipe" style="left:calc({x} * var(--u));width:calc({min(w, 860 - x) - 10} * var(--u));'
                              f'background:{cores[(i + len(clipes)) % 3]};opacity:{0.55 + 0.15 * (i % 2)}"></div>')
                x += w
            trilhas.append(f'<div class="trilha" style="top:calc({i * 92} * var(--u))">{"".join(clipes)}</div>')
        chip = f'<div class="chip" style="right:0;top:calc(-120 * var(--u))">{html.escape(c.get("chip", "IA"))}</div>'
        return tit + (f'<div class="ilu" style="--iy:{iy}%;--iw:860;--ih:300">{"".join(trilhas)}'
                      f'<div class="agulha" style="height:calc(320 * var(--u))"></div>{chip}</div>') + sub
    raise ValueError(f"tipo de cena desconhecido no modelo cinema: {tipo}")


def montar_cinema(roteiro: dict, pasta: Path, W: int, H: int) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "fonts").mkdir(exist_ok=True)
    (pasta / "assets").mkdir(exist_ok=True)
    for f in FONTES:
        shutil.copy2(ROOT / "assets" / "fonts" / f, pasta / "fonts" / f)
    shutil.copy2(HF / "node_modules" / "gsap" / "dist" / "gsap.min.js", pasta / "gsap.min.js")
    from .utils import arquivo_black_jack
    bj = arquivo_black_jack()
    if bj:
        shutil.copy2(bj, pasta / "fonts" / f"BlackJack{bj.suffix.lower()}")
        dest_face = f'@font-face {{ font-family: "Black Jack"; src: url("fonts/BlackJack{bj.suffix.lower()}"); }}'
        dest_css = '"Black Jack", cursive; font-weight: 400; font-size: 1.3em; line-height: 0.9'
    else:
        dest_face, dest_css = "", '"Noto Serif", serif; font-style: italic; font-weight: 700'
    pal = dict(PALETA_CINEMA, **(roteiro.get("paleta") or {}))
    rng = random.Random(7)
    t, cenas, blocos = 0.0, [], []
    for k, c in enumerate(roteiro["cenas"]):
        c = dict(c)
        d = float(c.get("dur", 3.0))
        c["t"], c["dur"] = round(t, 3), d
        corpo = _cena_cinema(c, k, pasta, W, H, pal, rng)
        blocos.append(f'<section id="c{k}" class="clip" data-start="{c["t"]}" data-duration="{d}" data-track-index="1">'
                      f'<div class="palco">{corpo}</div></section>')
        cenas.append({kk: c[kk] for kk in ("tipo", "t", "dur", "fator") if kk in c})
        t += d
    doc = MODELO_CINEMA.read_text(encoding="utf-8")
    for kk, v in {"__FONTE_DEST_FACE__": dest_face, "__FONTE_DEST_CSS__": dest_css, "__W__": str(W), "__H__": str(H),
                  "__DUR__": f"{t:.3f}", "__TITULO__": html.escape(roteiro.get("titulo", "motion")),
                  "__FUNDO__": pal["fundo"], "__TEXTO__": pal["texto"], "__ACENTO__": pal["acento"],
                  "__G1__": pal["g1"], "__G2__": pal["g2"], "__G3__": pal["g3"],
                  "__CENAS_HTML__": "\n      ".join(blocos),
                  "__DADOS__": json.dumps({"dur": round(t, 3), "cenas": cenas}, ensure_ascii=False)}.items():
        doc = doc.replace(kk, v)
    (pasta / "index.html").write_text(doc, encoding="utf-8")
    (pasta / "hyperframes.json").write_text(json.dumps({"name": pasta.name}), encoding="utf-8")
    return pasta
