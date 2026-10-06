"""ETAPA 10 — Motion graphics e efeitos visuais.

Elementos gerados como eventos ASS animados (libass: \\move, \\t, \\fad, desenho vetorial \\p1)
— mesma qualidade de um template de motion, sem render externo:
  • lower third   nome/descrição (auto: quando o orador se apresenta, ou nome no YAML)
  • callout       título de conceito definido na fala (ex.: "PRONOIA" do ref1), fonte manuscrita
  • contador      números falados (≥ min_valor) contam de 0 até o valor com easing
  • gancho        texto de abertura grande (ref4)
Overlays de imagem (Pillow + NumPy → PNG com alpha):
  • moldura de película (borda arredondada + perfurações, estilo Super 8)
Vídeo:
  • B-roll por palavra-chave (pasta assets/broll) com L-cut
Efeitos de corte (zoom, whip, flash, glitch) ficam em cinematic.py/render.py.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import numpy as np

from .subtitles import AssDoc, ass_color, esc, font_tags
from .utils import ROOT, log


def _norm(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s)


def _fmt_num(v: float) -> str:
    if v >= 1e6:
        return f"{v/1e6:.0f} mi" if v % 1e6 == 0 else f"{v/1e6:.1f} mi"
    return f"{int(round(v)):,}".replace(",", ".")


# ----------------------------------------------------------------------------- B-roll
def find_broll(words: list[dict], cfg: dict) -> list[dict]:
    """Casa palavras da fala com arquivos de assets/broll (tempo da FONTE)."""
    bc = cfg["motion"]["broll"]
    base = ROOT / bc["pasta"]
    if not bc["ativo"] or not base.exists():
        return []
    files = [f for f in base.iterdir() if f.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm")]
    if not files:
        return []
    index = {}
    for f in files:
        key = _norm(re.sub(r"[_-]?\d+$", "", f.stem))
        index.setdefault(key, []).append(f)
    out, last, used = [], -1e9, {}
    for w in words:
        for key in (_norm(w["w"]), _norm(w.get("lemma", ""))):
            if key and key in index and w["s"] - last >= bc["intervalo_min_s"]:
                opts = index[key]
                f = opts[used.get(key, 0) % len(opts)]
                used[key] = used.get(key, 0) + 1
                out.append({"s_src": max(0, w["s"] - 0.1), "e_src": w["s"] - 0.1 + bc["duracao_s"],
                            "arquivo": f, "palavra": w["w"]})
                last = w["s"]
                break
    log.info("  %d inserções de B-roll", len(out))
    return out


# ----------------------------------------------------------------------------- ASS motion
def build(doc: AssDoc, g, nlp_res: dict, words_out: list[dict], frases_out: list[dict], faces, cfg: dict,
          duration: float) -> list[dict]:
    mc = cfg["motion"]
    if not mc["ativo"]:
        return []
    W, H = g.canvas_w, g.canvas_h
    cx0, cy0, cw, ch = g.content_x, g.content_y, g.content_w, g.content_h
    k = (W / 1080) if H > W else (H / 1080)
    added = []

    def face_at(t):
        for a, b, f in faces:
            if a <= t < b:
                return f
        return None

    # ---- gancho
    gc = mc["gancho"]
    if gc["ativo"]:
        txt = gc["texto"] or (frases_out[0]["texto"] if frases_out else "")
        if txt:
            lines, cur = [], ""
            for wd in txt.split():
                if len(cur) + len(wd) > 24:
                    lines.append(cur.strip())
                    cur = ""
                cur += wd + " "
            lines.append(cur.strip())
            st = {"fonte": "Inter", "peso": "Bold", "tamanho": 58 * k, "cor": "#FFFFFF", "sombra": 3, "sombra_alpha": 0.6}
            doc.add(0.0, gc["duracao_s"], "{\\an5\\pos(%d,%d)\\fad(150,200)%s}" % (W / 2, H * 0.3, font_tags(st))
                    + "\\N".join(esc(x) for x in lines), layer=5)
            added.append({"tipo": "gancho", "t": 0.0, "texto": txt})
    # ---- lower third
    lt = mc["lower_third"]
    nome = lt["nome"] or nlp_res.get("nome_orador")
    if (lt["ativo"] is True and nome) or (lt["ativo"] == "auto" and nome):
        t0, t1 = lt["inicio_s"], lt["inicio_s"] + lt["duracao_s"]
        x = cx0 + cw * 0.07
        y = cy0 + ch * (0.62 if H > W and g.mode != "letterbox" else 0.78)
        bar_h = 110 * k
        doc.add(t0, t1, "{\\an7\\pos(%d,%d)\\p1\\bord0\\shad0\\1c%s\\fad(0,250)\\fscy0\\t(0,200,\\fscy100)}m 0 0 l %d 0 %d %d 0 %d{\\p0}"
                % (x, y, ass_color(lt["cor_barra"]), 10 * k, 10 * k, bar_h, bar_h), layer=6)
        st = {"fonte": "Inter", "peso": "Bold", "tamanho": 52 * k, "cor": lt["cor"], "sombra": 2}
        doc.add(t0 + 0.12, t1, "{\\an7\\move(%d,%d,%d,%d,0,260)\\fad(200,250)%s}%s"
                % (x - 30 * k, y, x + 26 * k, y, font_tags(st), esc(nome)), layer=6)
        if lt.get("descricao"):
            st2 = dict(st, peso="Regular", tamanho=34 * k)
            doc.add(t0 + 0.25, t1, "{\\an7\\move(%d,%d,%d,%d,0,300)\\fad(250,250)%s}%s"
                    % (x - 30 * k, y + 62 * k, x + 26 * k, y + 62 * k, font_tags(st2), esc(lt["descricao"])), layer=6)
        added.append({"tipo": "lower_third", "t": t0, "texto": nome})
    # ---- callouts (conceito definido)
    co = mc["callout"]
    if co["ativo"]:
        for c in nlp_res.get("callouts", [])[: co["max"]]:
            t = c.get("t_out")
            if t is None:
                continue
            f = face_at(t)
            y = (f[1] + f[3] * 0.85) * H if f else cy0 + ch * 0.45
            y = min(y, cy0 + ch * 0.8)
            st = {"fonte": co["fonte"], "peso": "Regular", "tamanho": co["tamanho"] * k, "cor": co["cor"],
                  "contorno": 0, "sombra": 3, "sombra_alpha": 0.5}
            doc.add(t, t + co["duracao_s"], "{\\an5\\pos(%d,%d)\\frz-3\\fad(60,200)\\fscx30\\fscy30"
                    "\\t(0,140,\\fscx110\\fscy110)\\t(140,220,\\fscx100\\fscy100)\\t(220,%d,\\fscx106\\fscy106)%s}%s"
                    % (W / 2, y, int(co["duracao_s"] * 1000), font_tags(st), esc(c["termo"].upper())), layer=6)
            added.append({"tipo": "callout", "t": round(t, 2), "texto": c["termo"]})
    # ---- contador animado
    cc = mc["contador"]
    if cc["ativo"]:
        nums = [n for n in nlp_res.get("numeros", []) if n.get("t_out") is not None and (n["valor"] or 0) >= cc["min_valor"]]
        for n in nums[: cc["max"]]:
            t0, d = n["t_out"], cc["duracao_s"]
            steps = 24
            st = {"fonte": "Inter", "peso": "Black", "tamanho": 120 * k, "cor": "#FFFFFF", "contorno": 0, "sombra": 4, "sombra_alpha": 0.6}
            stu = dict(st, peso="Bold", tamanho=48 * k)
            # abaixo da faixa de legenda do topo (0.18H) e acima do rosto
            y = cy0 + ch * 0.30 if not (g.mode == "letterbox" and H > W) else cy0 - 150 * k
            for i in range(steps):
                a = t0 + d * i / steps
                b = t0 + d * (i + 1) / steps if i < steps - 1 else t0 + d + 1.2
                p = 1 - (1 - (i + 1) / steps) ** 3   # ease-out cúbico
                val = _fmt_num(n["valor"] * p)
                unit = ("\\N{" + font_tags(stu) + "}" + esc(n["unidade"])) if n["unidade"] and n["unidade"] != "%" else ""
                pct = "%" if n["unidade"] == "%" else ""
                fade = "\\fad(80,0)" if i == 0 else ("\\fad(0,250)" if i == steps - 1 else "")
                doc.add(a, b, "{\\an5\\pos(%d,%d)%s%s}%s%s%s" % (W / 2, y, fade, font_tags(st), val, pct, unit), layer=7)
            added.append({"tipo": "contador", "t": round(t0, 2), "texto": f"{n['valor']:g} {n['unidade']}"})
    log.info("  motion graphics: %s", [a["tipo"] for a in added] or "nenhum")
    return added


# ----------------------------------------------------------------------------- overlays PNG
def film_border(g, out: Path) -> Path:
    """Moldura de película (Super 8): bordas pretas arredondadas + perfurações."""
    from PIL import Image, ImageDraw
    W, H = g.canvas_w, g.canvas_h
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = g.content_x, g.content_y, g.content_x + g.content_w, g.content_y + g.content_h
    m = int(min(g.content_w, g.content_h) * 0.035)
    mask = Image.new("L", (W, H), 255)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([x0 + m * 2.2, y0 + m, x1 - m, y1 - m], radius=m * 1.4, fill=0)
    black = Image.new("RGBA", (W, H), (8, 8, 8, 255))
    img = Image.composite(black, img, mask)
    d = ImageDraw.Draw(img)
    hole_w, hole_h = m * 1.1, m * 1.5
    n = max(3, int(g.content_h / (hole_h * 3)))
    for i in range(n):
        cy = y0 + (i + 0.5) * g.content_h / n
        d.rounded_rectangle([x0 + m * 0.5, cy - hole_h / 2, x0 + m * 0.5 + hole_w, cy + hole_h / 2],
                            radius=m * 0.3, fill=(235, 235, 225, 255))
    # textura sutil de poeira
    rng = np.random.default_rng(0)
    arr = np.array(img)
    for _ in range(int(W * H / 9000)):
        x, y = rng.integers(0, W), rng.integers(0, H)
        if arr[y, x, 3] == 0:
            arr[y:y + 2, x:x + 2] = (230, 230, 230, int(rng.integers(40, 110)))
    Image.fromarray(arr).save(out)
    return out
