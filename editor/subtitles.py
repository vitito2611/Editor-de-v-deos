"""ETAPA 5 — Legendas dinâmicas (ASS renderizado pelo libass dentro do FFmpeg).

• Agrupa 2-4 palavras por bloco, quebrando em pontuação e pausas naturais
• Estilos (config legendas.estilos): caixa_inferior, contorno_duplo, karaoke, centro_impacto,
  topo, minimal_peito, cinetico (ref1), lateral_misto (ref2/3), cinema (ref4), mono_dividido (ref5)
• Animações: fade, pop, slide, palavra (karaoke), palavra_misto, cinetico, digitacao
• Rotação automática de estilo/posição a cada X s ou troca de tópico
• Evita o rosto: estima a caixa do texto e reposiciona se cobrir o rosto do orador
• Palavras-chave (score NLP) destacadas com cor e escala
"""
from __future__ import annotations

from pathlib import Path

from .utils import hex_to_rgb, log

WEIGHTS = {"Thin": 100, "Light": 300, "Regular": 400, "Medium": 500, "SemiBold": 600,
           "Bold": 700, "ExtraBold": 800, "Black": 900}


# ----------------------------------------------------------------------------- ASS helpers
def ass_color(hexc: str, alpha: float = 0.0) -> str:
    """'#RRGGBB' + alpha(0=opaco, 1=transparente) → &HAABBGGRR&"""
    r, g, b = hex_to_rgb(hexc)
    return f"&H{int(alpha * 255):02X}{b:02X}{g:02X}{r:02X}&"


def ass_time(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def esc(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")")


class AssDoc:
    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.events: list[str] = []

    def add(self, start: float, end: float, text: str, layer: int = 1, style: str = "Plain"):
        if end - start < 0.02:
            return
        self.events.append(f"Dialogue: {layer},{ass_time(start)},{ass_time(end)},{style},,0,0,0,,{text}")

    def write(self, path: Path):
        head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {self.w}
PlayResY: {self.h}
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Plain,Inter,60,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1
Style: Box,Inter,60,&H00FFFFFF,&H00FFFFFF,&H64000000,&H00000000,0,0,0,0,100,100,0,0,3,14,0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        path.write_text(head + "\n".join(self.events) + "\n", encoding="utf-8")


def font_tags(st: dict, size: float | None = None, weight: str | None = None, italic: bool = False) -> str:
    w = WEIGHTS.get(weight or st.get("peso", "Bold"), 700)
    t = f"\\fn{st.get('fonte', 'Inter')}\\b{w}\\i{1 if italic else 0}\\fs{int(size or st['tamanho'])}"
    t += f"\\1c{ass_color(st.get('cor', '#FFFFFF'))}"
    bord = st.get("contorno", 0)
    t += f"\\bord{bord}\\3c{ass_color(st.get('contorno_cor', '#000000'))}"
    sh = st.get("sombra", 0)
    t += f"\\shad{sh}\\4c{ass_color('#000000', 1 - st.get('sombra_alpha', 0.7))}" if sh else "\\shad0"
    return t


# ----------------------------------------------------------------------------- agrupamento
def group_words(words: list[dict], lc: dict, st: dict) -> list[list[dict]]:
    pmax = st.get("palavras_max", lc["palavras_max"])
    cmax = st.get("caracteres_max", lc["caracteres_max"])
    groups, cur = [], []
    for i, w in enumerate(words):
        if cur:
            chars = sum(len(x["w"]) + 1 for x in cur) + len(w["w"])
            prev = cur[-1]
            punct = prev["w"][-1:] in ".!?" or (lc["respeitar_pontuacao"] and prev["w"][-1:] in ",;:" and len(cur) >= lc["palavras_min"])
            gap = w["s"] - prev["e"] > lc["pausa_quebra_s"]
            new_sent = w.get("sent") != prev.get("sent")
            if len(cur) >= pmax or chars > cmax or punct or gap or new_sent:
                groups.append(cur)
                cur = []
        cur.append(w)
    if cur:
        groups.append(cur)
    # junta blocos de 1 palavra curtos ao anterior quando possível
    out = []
    for g in groups:
        if out and len(g) == 1 and len(out[-1]) < pmax and g[0].get("sent") == out[-1][-1].get("sent") \
                and g[0]["s"] - out[-1][-1]["e"] < lc["pausa_quebra_s"]:
            out[-1].append(g[0])
        else:
            out.append(g)
    return out


# ----------------------------------------------------------------------------- geometria
class Placer:
    """Calcula posições evitando o rosto (faces: [(t0, t1, (cx, cy, w, h) normalizado no canvas)])."""

    def __init__(self, g, faces, lc):
        self.g, self.faces, self.lc = g, faces, lc
        self.vertical = g.canvas_h > g.canvas_w

    def face_at(self, t):
        for a, b, f in self.faces:
            if a <= t < b:
                return f
        return None

    def anchor(self, pos: str, t: float, size: float, nchars: int, nlines: int = 1) -> tuple[float, float]:
        g = self.g
        W, H = g.canvas_w, g.canvas_h
        cx0, cy0, cw, ch = g.content_x, g.content_y, g.content_w, g.content_h
        f = self.face_at(t)
        m = self.lc["margem_px"] * W / 1080
        lb = g.mode == "letterbox" and self.vertical
        if pos == "inferior":
            # letterbox vertical: na barra preta logo abaixo do quadro; senão acima da UI da plataforma
            y = cy0 + ch + size * 1.1 if lb else H * (0.70 if self.vertical else 0.86)
            p = (W / 2, y)
        elif pos == "superior":
            y = cy0 - size * 1.1 if lb else H * (0.18 if self.vertical else 0.12)
            p = (W / 2, y)
        elif pos == "centro":
            p = (W / 2, cy0 + ch * 0.5)
        elif pos == "peito":
            y = (f[1] * H + f[3] * H * 1.25) if f else cy0 + ch * 0.68
            lo_y, hi_y = (0.56, 0.80) if self.vertical else (0.55, 0.9)
            p = (W / 2, min(max(y, cy0 + ch * lo_y), cy0 + ch * hi_y))
        elif pos == "lateral":
            if f:
                side = 1 if f[0] < 0.5 else -1
                x = f[0] * W + side * (f[2] * W * 0.5 + cw * 0.22)
                x = min(max(x, cx0 + cw * 0.22), cx0 + cw * 0.78)
                y = min(max(f[1] * H - f[3] * H * 0.1, cy0 + ch * 0.25), cy0 + ch * 0.75)
            else:
                x, y = cx0 + cw * 0.72, cy0 + ch * 0.45
            p = (x, y)
        elif pos == "cinema":
            p = (W / 2, cy0 + ch * 0.9)
        else:
            p = (W / 2, cy0 + ch * 0.5)
        if pos == "peito" and f and self.lc.get("evitar_rosto") and self._overlap(p, size, nchars, nlines, f):
            # preferência do cliente: legenda logo ABAIXO do rosto — desce, nunca sobe para o topo
            for k in (0.80, 0.84, 0.88):
                q = (W / 2, cy0 + ch * k)
                if not self._overlap(q, size, nchars, nlines, f):
                    return q
            return (W / 2, cy0 + ch * 0.84)
        if self.lc.get("evitar_rosto") and f and pos in ("inferior", "superior", "centro"):
            if self._overlap(p, size, nchars, nlines, f):
                for alt in ("inferior", "superior", "centro"):
                    if alt != pos:
                        q = self.anchor(alt, -1, size, nchars, nlines)
                        if not self._overlap(q, size, nchars, nlines, f):
                            return q
        return p

    def _overlap(self, p, size, nchars, nlines, f):
        W, H = self.g.canvas_w, self.g.canvas_h
        tw, th = nchars * size * 0.55, nlines * size * 1.15
        fx0, fx1 = (f[0] - f[2] * 0.6) * W, (f[0] + f[2] * 0.6) * W
        fy0, fy1 = (f[1] - f[3] * 0.6) * H, (f[1] + f[3] * 0.7) * H
        return not (p[0] + tw / 2 < fx0 or p[0] - tw / 2 > fx1 or p[1] + th / 2 < fy0 or p[1] - th / 2 > fy1)


# ----------------------------------------------------------------------------- renderizadores de estilo
def _word_txt(w: dict, st: dict, lc: dict) -> str:
    t = w["w"]
    if st.get("caixa_alta"):
        t = t.upper()
    if st.get("minusculas") or lc.get("minusculas"):
        t = t.lower()
    return esc(t)


def _is_kw(w, lc):
    return lc["destaque"]["ativo"] and w.get("kw", 0) >= lc["destaque"]["score_min"]


def _anim(anim: str, x: float, y: float) -> str:
    if anim == "pop":
        return f"\\an5\\pos({x:.0f},{y:.0f})\\fad(40,60)\\fscx40\\fscy40\\t(0,110,\\fscx108\\fscy108)\\t(110,170,\\fscx100\\fscy100)"
    if anim == "slide":
        return f"\\an5\\move({x:.0f},{y + 45:.0f},{x:.0f},{y:.0f},0,150)\\fad(90,60)"
    if anim == "fade":
        return f"\\an5\\pos({x:.0f},{y:.0f})\\fad(130,90)"
    return f"\\an5\\pos({x:.0f},{y:.0f})"


def render_group(doc: AssDoc, grp: list[dict], start: float, end: float, st: dict, lc: dict, placer: Placer,
                 style_name: str, color_cycle: list[int]):
    anim = st.get("animacao", "fade")
    txts = [_word_txt(w, st, lc) for w in grp]
    nchars = sum(len(t) + 1 for t in txts)
    size = st["tamanho"] * doc.w / 1080 if doc.h > doc.w else st["tamanho"] * doc.h / 1080 * 1.0
    pos = st.get("posicao", "inferior")
    hl = lc["destaque"]
    hl_scale = int(100 * hl["escala"])

    def styled_words(active: int | None = None, reveal: int | None = None, future_color: str | None = None):
        parts = []
        for i, (w, t) in enumerate(zip(grp, txts)):
            tags = ""
            if reveal is not None and i > reveal:
                tags += "\\alpha&HFF&"
            elif future_color and active is not None and i > active:
                tags += f"\\1c{ass_color(future_color)}"
            elif active is not None and i == active and st.get("cor_ativa"):
                tags += f"\\1c{ass_color(st['cor_ativa'])}\\fscx{hl_scale}\\fscy{hl_scale}"
            elif _is_kw(w, lc):
                tags += f"\\1c{ass_color(hl['cor'])}\\fscx{hl_scale}\\fscy{hl_scale}"
            reset = f"\\1c{ass_color(st.get('cor', '#FFFFFF'))}\\fscx100\\fscy100\\alpha&H00&"
            parts.append(("{" + tags + "}" if tags else "") + t + ("{" + reset + "}" if tags else ""))
        return " ".join(parts)

    # ---------- dinâmico SEM cor: varia só fonte, peso, tamanho e itálico (pedido do cliente)
    if anim == "dinamico":
        render_dinamico(doc, grp, start, end, st, lc, placer, size, txts)
        return
    # ---------- estilos de layout especial
    if anim == "palavra_misto":       # ref2/ref3 — linhas com pesos/tamanhos diferentes
        kw_i = max(range(len(grp)), key=lambda i: grp[i].get("kw", 0))
        big = st.get("tamanho_destaque", st["tamanho"] * 1.5) * size / st["tamanho"]
        has_kw = grp[kw_i].get("kw", 0) >= lc["destaque"]["score_min"] and len(grp) > 1
        lines = [list(range(0, kw_i)), [kw_i], list(range(kw_i + 1, len(grp)))] if has_kw else [list(range(len(grp)))]
        lines = [ln for ln in lines if ln]
        x, y = placer.anchor("lateral", start, size, max(len(txts[i]) for i in range(len(grp))) + 6, len(lines))
        ital_line = 2 if has_kw and (start * 7) % 3 < 1 else -1  # às vezes a linha final em itálico (ref2)
        for wi, w in enumerate(grp):
            s0 = start if wi == 0 else w["s"]
            e0 = grp[wi + 1]["s"] if wi + 1 < len(grp) else end
            segs = []
            for li, ln in enumerate(lines):
                is_big = has_kw and ln == [kw_i]
                ftag = font_tags(st, big if is_big else size, "ExtraBold" if is_big else st.get("peso"),
                                 italic=(li == len(lines) - 1 and ital_line > 0 and not is_big))
                words_txt = []
                for i in ln:
                    col = st.get("cor", "#FFFFFF") if i <= wi else st.get("cor_futura", "#9A9A9A")
                    words_txt.append("{\\1c" + ass_color(col) + "}" + txts[i])
                segs.append("{" + ftag + "}" + " ".join(words_txt))
            intro = "\\fad(90,0)" if wi == 0 else ""
            outro = "\\fad(0,80)" if wi == len(grp) - 1 else ""
            doc.add(s0, e0, "{\\an5\\pos(%d,%d)%s%s}" % (x, y, intro, outro) + "\\N".join(segs), layer=2)
        return
    if anim == "cinetico":            # ref1 — frase de impacto, tamanhos misturados, revelação por palavra
        lines, cur = [], []
        for i, w in enumerate(grp):
            cur.append(i)
            if len(cur) >= (1 if w.get("kw", 0) >= 0.6 else 3) or i == len(grp) - 1:
                lines.append(cur)
                cur = []
        x, y = placer.anchor("centro", start, size, 14, len(lines))
        for wi, w in enumerate(grp):
            s0 = start if wi == 0 else w["s"]
            e0 = grp[wi + 1]["s"] if wi + 1 < len(grp) else end
            segs = []
            for li, ln in enumerate(lines):
                kwline = any(grp[i].get("kw", 0) >= 0.6 for i in ln)
                fs = size * (1.15 if kwline else 0.62)
                body = " ".join(("{\\alpha&HFF&}" if i > wi else "{\\alpha&H00&}") + txts[i] for i in ln)
                segs.append("{" + font_tags(st, fs, "Bold" if kwline else "SemiBold") + "}" + body)
            doc.add(s0, e0, "{\\an5\\pos(%d,%d)%s}" % (x, y, "\\fad(0,120)" if wi == len(grp) - 1 else "") +
                    "\\N".join(segs), layer=2)
        return
    if anim == "digitacao" or pos == "dividida":   # ref5 — mono dividido esquerda/direita
        half = max(1, (len(grp) + 1) // 2)
        cols = st.get("cor_destaque_lista", ["#3BE36B"])
        g = placer.g
        y = g.content_y + g.content_h * 0.5
        for side, idxs in ((0.25, range(0, half)), (0.75, range(half, len(grp)))):
            idxs = list(idxs)
            if not idxs:
                continue
            x = g.content_x + g.content_w * side
            for k, wi in enumerate(idxs):
                s0 = (start if k == 0 and side == 0.25 else grp[wi]["s"])
                e0 = end
                body = []
                for i in idxs:
                    tag = "\\alpha&HFF&" if i > wi else "\\alpha&H00&"
                    if _is_kw(grp[i], lc):
                        tag += f"\\1c{ass_color(cols[color_cycle[0] % len(cols)])}\\b1"
                    else:
                        tag += f"\\1c{ass_color(st.get('cor', '#FFFFFF'))}\\b0"
                    body.append("{" + tag + "}" + txts[i])
                nxt = grp[idxs[k + 1]]["s"] if k + 1 < len(idxs) else end
                doc.add(s0, nxt if k + 1 < len(idxs) else e0,
                        "{\\an5\\pos(%d,%d)%s%s}" % (x, y, font_tags(st, size), "\\fad(0,100)" if k + 1 == len(idxs) else "")
                        + " ".join(body), layer=2)
        if any(_is_kw(w, lc) for w in grp):
            color_cycle[0] += 1
        return

    # ---------- estilos de bloco (1 linha)
    # auto-ajuste: o bloco nunca passa de 88% da largura do quadro
    est_w = nchars * size * (0.62 if st.get("caixa_alta") else 0.54) * (hl["escala"] if hl["ativo"] else 1)
    if est_w > doc.w * 0.88:
        size *= doc.w * 0.88 / est_w
    x, y = placer.anchor(pos, start, size, nchars)
    base = font_tags(st, size)
    box = st.get("fundo")
    style = "Box" if box else "Plain"
    if box:
        base += f"\\bord{int(size * 0.28)}\\3c{ass_color(box)}\\3a&H{int((1 - st.get('fundo_alpha', 0.5)) * 255):02X}&\\shad0"
    if anim == "palavra":             # karaoke / word-by-word highlight
        for wi, w in enumerate(grp):
            s0 = start if wi == 0 else w["s"]
            e0 = grp[wi + 1]["s"] if wi + 1 < len(grp) else end
            intro = _anim("pop", x, y) if wi == 0 else f"\\an5\\pos({x:.0f},{y:.0f})"
            doc.add(s0, e0, "{" + intro + base + "}" + styled_words(active=wi), layer=2, style=style)
        return
    tags = _anim(anim, x, y) + base
    if st.get("contorno_externo"):   # contorno duplo: camada de baixo com contorno largo branco
        outer = tags.replace(f"\\bord{st.get('contorno', 0)}", f"\\bord{st['contorno_externo']}") \
                    .replace(f"\\3c{ass_color(st.get('contorno_cor', '#000000'))}", f"\\3c{ass_color(st['contorno_externo_cor'])}")
        doc.add(start, end, "{" + outer + "}" + styled_words(), layer=1, style=style)
    doc.add(start, end, "{" + tags + "}" + styled_words(), layer=2, style=style)


_DIN = {"n": 0}
# esconder/mostrar palavra sem perder a translucidez do contorno e da sombra
HIDE = "\\1a&HFF&\\3a&HFF&\\4a&HFF&"


def show_tags(st) -> str:
    return "\\1a&H00&\\3a&H%02X&\\4a&H90&" % st.get("contorno_alpha", 0x70)


def render_dinamico(doc: AssDoc, grp, start, end, st, lc, placer, size, txts):
    """Legenda dinâmica monocromática (branco + contorno/sombra discretos para leitura).

    Alterna 3 variações conforme o conteúdo:
      revelar   palavras surgem uma a uma; a palavra falada fica em Black e "pula" (escala)
      empilhado linha pequena regular + palavra-chave GIGANTE em Black + linha em itálico
      impacto   palavra-chave sozinha, caixa alta, enorme, com pop
    """
    _DIN["n"] += 1
    kw_i = max(range(len(grp)), key=lambda i: grp[i].get("kw", 0))
    kw = grp[kw_i].get("kw", 0)
    big = size * st.get("escala_destaque", 1.9)
    stroke = f"\\bord{st.get('contorno', 3)}\\3c&H000000&\\3a&H{st.get('contorno_alpha', 0x70):02X}&" \
             f"\\shad{st.get('sombra', 3)}\\4c&H000000&\\4a&H90&\\1c&HFFFFFF&"

    def ft(sz, weight, italic=False):
        return "\\fn%s\\b%d\\i%d\\fs%d" % (st.get("fonte", "Inter"), WEIGHTS[weight], 1 if italic else 0, int(sz)) + stroke

    if kw >= st.get("impacto_kw_min", 0.78) and len(grp) <= 2 and _DIN["n"] % 3 == 0:
        variant = "impacto"
    elif kw >= st.get("empilhado_kw_min", 0.6) and len(grp) >= 2:
        variant = "empilhado"
    else:
        variant = "revelar"
    x, y = placer.anchor(st.get("posicao", "inferior"), start, size, sum(len(t) + 1 for t in txts),
                         2 if variant == "empilhado" else 1)
    if variant == "impacto":
        t = txts[kw_i].upper().strip(".,!?;:")
        doc.add(start, end, "{\\an5\\pos(%d,%d)\\fad(30,80)\\fscx30\\fscy30\\t(0,90,\\fscx118\\fscy118)"
                "\\t(90,160,\\fscx100\\fscy100)%s}%s" % (x, y, ft(big * 1.15, "Black"), t), layer=3)
        return
    if variant == "empilhado":
        before = [i for i in range(len(grp)) if i < kw_i]
        after = [i for i in range(len(grp)) if i > kw_i]
        for wi in range(len(grp)):
            s0 = start if wi == 0 else grp[wi]["s"]
            e0 = grp[wi + 1]["s"] if wi + 1 < len(grp) else end
            def seg(ids, sz, weight, italic=False):
                return "{%s}" % ft(sz, weight, italic) + " ".join(
                    ("{%s}" % HIDE if i > wi else "{%s}" % show_tags(st)) + txts[i] for i in ids)
            lines = []
            if before:
                lines.append(seg(before, size * 0.78, "Medium"))
            kalpha = "{%s}" % HIDE if kw_i > wi else ""
            pop = "\\fscx70\\fscy70\\t(0,100,\\fscx108\\fscy108)\\t(100,160,\\fscx100\\fscy100)" if wi == kw_i else ""
            lines.append("{%s%s}%s%s" % (ft(big, "Black"), pop, kalpha, txts[kw_i].upper()))
            if after:
                lines.append(seg(after, size * 0.82, "SemiBold", italic=True))
            fade = "\\fad(60,0)" if wi == 0 else ("\\fad(0,90)" if wi == len(grp) - 1 else "")
            doc.add(s0, e0, "{\\an5\\pos(%d,%d)%s}" % (x, y, fade) + "\\N".join(lines), layer=3)
        return
    # revelar: palavra a palavra; a atual em Black maior, as anteriores em Bold
    for wi in range(len(grp)):
        s0 = start if wi == 0 else grp[wi]["s"]
        e0 = grp[wi + 1]["s"] if wi + 1 < len(grp) else end
        parts = []
        for i, t in enumerate(txts):
            if i > wi:
                parts.append("{%s%s}%s" % (ft(size, "Bold"), HIDE, t))
            elif i == wi:
                parts.append("{%s\\fscx85\\fscy85\\t(0,90,\\fscx112\\fscy112)\\t(90,150,\\fscx104\\fscy104)}%s"
                             % (ft(size * 1.12, "Black"), t))
            else:
                parts.append("{%s}%s" % (ft(size, "Bold"), t))
        fade = "\\fad(0,80)" if wi == len(grp) - 1 else ""
        doc.add(s0, e0, "{\\an5\\pos(%d,%d)%s}" % (x, y, fade) + " ".join(parts), layer=3)


def build(words_out: list[dict], frases_out: list[dict], g, faces, cfg: dict, doc: AssDoc,
          pular: list[tuple[float, float]] | None = None) -> list[dict]:
    lc = dict(cfg["legendas"])
    lc["evitar_rosto"] = cfg["legendas"]["evitar_rosto"]
    if not lc["ativo"] or not words_out:
        return []
    styles = lc["estilos"]
    placer = Placer(g, faces, lc)
    base_name, imp_name = lc["estilo_base"], lc["estilo_impacto"]
    groups = group_words(words_out, lc, styles[base_name])
    rot = lc["rotacao"]
    rot_list = rot.get("estilos") or [base_name]
    cur_style, rot_i, last_switch, last_impact = base_name, 0, 0.0, -1e9
    color_cycle = [0]
    log_rows = []
    for gi, grp in enumerate(groups):
        start = grp[0]["s"]
        end = min(groups[gi + 1][0]["s"] if gi + 1 < len(groups) else grp[-1]["e"] + 0.6, grp[-1]["e"] + 0.5)
        end = max(end, start + 0.3)
        f = frases_out[grp[0]["sent"]] if grp[0].get("sent") is not None and grp[0]["sent"] < len(frases_out) else {}
        # trechos cobertos por cards de texto (motion) não repetem a legenda
        if pular and any(a <= (start + end) / 2 < b for a, b in pular):
            continue
        name = cur_style
        # rotação por tempo ou tópico
        if rot.get("ativo"):
            new_topic = f.get("novo_topico") and f.get("w0") == grp[0].get("i")
            if start - last_switch >= rot["a_cada_s"] or (rot.get("em_topico") and new_topic):
                rot_i = (rot_i + 1) % len(rot_list)
                cur_style, last_switch = rot_list[rot_i], start
            name = cur_style
        # impacto
        if f.get("impacto", 0) >= lc["impacto_score_min"] and max(w.get("kw", 0) for w in grp) >= 0.6 \
                and start - last_impact >= lc["impacto_intervalo_min_s"]:
            name = imp_name
            last_impact = start
        st = styles[name]
        if name != base_name and st.get("palavras_max") and len(grp) > st["palavras_max"]:
            pass
        render_group(doc, grp, start, end, st, lc, placer, name, color_cycle)
        log_rows.append({"t": round(start, 2), "texto": " ".join(w["w"] for w in grp), "estilo": name})
    log.info("  %d blocos de legenda; estilos usados: %s", len(groups),
             {k: sum(r["estilo"] == k for r in log_rows) for k in {r["estilo"] for r in log_rows}})
    return log_rows
