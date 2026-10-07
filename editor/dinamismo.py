"""Dinamismo — sobreposições que tiram a tela do rosto do orador (B-roll, fotos, cards).

Referências do cliente: nenhuma cena dura mais que ~3 s. Este módulo planeja, em tempo de
saída, eventos visuais sobre o vídeo do orador (a voz continua por baixo = L-cut):

  video  B-roll de banco (Pexels) ligado à palavra-chave da frase
  foto   foto com movimento Ken Burns — pessoas/marcas citadas (Openverse/Wikimedia) ou Pexels
  card   frase de impacto em tipografia grande sobre o próprio vídeo desfocado (100% offline)

Plano manual opcional (dinamismo.plano no YAML / --config):
  - {contem: "Steve Jobs", tipo: foto, busca: "Steve Jobs"}
  - {contem: "zona de conforto", tipo: video, busca: "pessoa no sofá"}
  - {contem: "não existe perfil perfeito", tipo: card}
O plano manual tem prioridade; o automático completa respeitando o espaçamento.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import stock
from .subtitles import WEIGHTS, AssDoc, esc
from .utils import ffmpeg, log

DEFAULTS = {
    "ativo": False,
    "intervalo_s": 4.0,          # espaçamento médio entre sobreposições
    "gap_min_s": 1.2,            # mínimo de rosto entre duas sobreposições
    "dur_min_s": 1.3,
    "dur_max_s": 2.4,
    "inicio_livre_s": 1.0,       # gancho: mostra o rosto no começo
    "cobertura_max": 0.5,        # fração máxima do vídeo coberta por sobreposições
    "cards_max": 5,
    "card_impacto_min": 0.6,
    "card_palavras": [3, 9],
    "fotos_entidades": True,     # nomes próprios (pessoas/marcas) viram foto
    "pexels_api_key": None,
    "plano": [],
}

STOP_QUERY = {"coisa", "coisas", "gente", "vez", "vezes", "tempo", "tipo", "forma", "jeito", "parte", "dia",
              "isso", "aquilo", "perfil", "motivo", "pergunta", "caso", "lado", "fato"}


def _cfg(cfg):
    d = dict(DEFAULTS)
    d.update(cfg.get("dinamismo") or {})
    return d


def _find_phrase(words, phrase):
    toks = [re.sub(r"[^\wÀ-ú]", "", t.lower()) for t in phrase.split()]
    clean = [re.sub(r"[^\wÀ-ú]", "", w["w"].lower()) for w in words]
    for i in range(len(words) - len(toks) + 1):
        if clean[i:i + len(toks)] == toks:
            return i
    return None


def _entities(words):
    """Sequências de nomes próprios (ex.: 'Steve Jobs', 'Y Combinator', 'Zuckerberg')."""
    out, cur = [], []
    for i, w in enumerate(words):
        raw = w["w"].strip(".,!?;:")
        is_cap = raw[:1].isupper() and (i > 0 and words[i - 1]["w"][-1:] not in ".!?") and w.get("pos") in ("PROPN", "NOUN", "X")
        if is_cap and len(raw) > 0:
            cur.append(i)
        else:
            if cur:
                out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return [c for c in out if len(" ".join(words[i]["w"] for i in c)) >= 3]


def plan(words_out, frases_out, cfg, total) -> list[dict]:
    dc = _cfg(cfg)
    cands = []
    # 1) plano manual
    for item in dc["plano"] or []:
        i = _find_phrase(words_out, item.get("contem", "")) if item.get("contem") else None
        t = item.get("t", words_out[i]["s"] if i is not None else None)
        if t is None:
            continue
        cands.append({"t": max(0, t - 0.1), "tipo": item.get("tipo", "video"), "busca": item.get("busca") or item.get("contem"),
                      "busca_en": item.get("busca_en"), "escolha": item.get("escolha", 0),
                      "texto": item.get("texto"), "prio": 5, "dur": item.get("dur"), "motivo": "plano manual",
                      "arquivo_local": item.get("arquivo"), "credito": item.get("credito")})
    # 2) cards de frases de impacto
    pmin, pmax = dc["card_palavras"]
    for f in frases_out:
        if f.get("s") is None:
            continue
        n = f["w1"] - f["w0"] + 1
        if pmin <= n <= pmax and f.get("impacto", 0) >= dc["card_impacto_min"] and f["e"] - f["s"] <= 3.4:
            cands.append({"t": f["s"] - 0.05, "tipo": "card", "texto": f["texto"], "dur": f["e"] - f["s"] + 0.25,
                          "prio": 3 + f["impacto"], "sent": f["id"], "motivo": f"frase de impacto ({f['impacto']:.2f})"})
    # 3) entidades → foto
    if dc["fotos_entidades"] and dc.get("auto_palavras", True):
        for ent in _entities(words_out):
            name = " ".join(words_out[i]["w"].strip(".,!?;:") for i in ent)
            if name.lower() in ("eu", "então", "pô"):
                continue
            cands.append({"t": words_out[ent[0]]["s"] - 0.1, "tipo": "foto", "busca": name, "prio": 3.5,
                          "entidade": True, "motivo": f"nome próprio '{name}'"})
    # 4) palavra-chave mais forte de cada frase → B-roll em vídeo
    for f in (frases_out if dc.get("auto_palavras", True) else []):
        if f.get("s") is None:
            continue
        ws = [w for w in words_out if w.get("sent") == f["id"] and w.get("pos") == "NOUN"
              and re.sub(r"\W", "", w["w"].lower()) not in STOP_QUERY and len(w["w"]) >= 4]
        if not ws:
            continue
        w = max(ws, key=lambda x: x.get("kw", 0))
        cands.append({"t": w["s"] - 0.15, "tipo": "video", "busca": w.get("lemma") or w["w"].strip(".,!?"),
                      "prio": 1 + w.get("kw", 0), "motivo": f"palavra-chave '{w['w']}'"})
    # seleção gulosa por prioridade respeitando espaçamento e cobertura
    chosen = []
    covered = 0.0
    for c in sorted(cands, key=lambda c: -c["prio"]):
        d = c.get("dur") or (dc["dur_max_s"] if c["tipo"] == "foto" else (dc["dur_min_s"] + dc["dur_max_s"]) / 2)
        d = max(dc["dur_min_s"], min(d, 3.4 if c["tipo"] == "card" else dc["dur_max_s"]))
        a, b = max(dc["inicio_livre_s"], c["t"]), min(total - 0.3, c["t"] + d)
        if b - a < dc["dur_min_s"] * 0.8:
            continue
        manual = c.get("motivo") == "plano manual"
        gap = 0.0 if manual else dc["gap_min_s"]   # itens do plano podem encadear (ex.: duas fotos seguidas)
        if manual:   # encaixa no espaço livre: começa depois do que já está escolhido, se encostar
            for o in sorted(chosen, key=lambda o: o["t"]):
                if o["t"] <= a < o["t"] + o["dur"]:
                    a = o["t"] + o["dur"]
            b = max(b, a + dc["dur_min_s"])
        if any(a < o["t"] + o["dur"] + gap and o["t"] < b + gap for o in chosen):
            continue
        if c["tipo"] == "card" and sum(o["tipo"] == "card" for o in chosen) >= dc["cards_max"]:
            continue
        if covered + (b - a) > dc["cobertura_max"] * total:
            continue
        # densidade: não mais que 1 a cada intervalo_s * 0.6
        if not manual and any(abs(a - o["t"]) < dc["intervalo_s"] * 0.6 for o in chosen):
            continue
        c = dict(c, t=round(a, 3), dur=round(b - a, 3))
        chosen.append(c)
        covered += b - a
    chosen.sort(key=lambda c: c["t"])
    log.info("  dinamismo: %d sobreposições planejadas (%s), cobertura %.0f%%", len(chosen),
             {k: sum(c["tipo"] == k for c in chosen) for k in ("video", "foto", "card")}, 100 * covered / max(total, 1))
    return chosen


# ----------------------------------------------------------------------------- mídia
def fetch_and_render(events, cfg, g, montado: Path, work: Path) -> tuple[list[dict], list[dict]]:
    """Baixa a mídia de cada evento e pré-renderiza um clipe com o tamanho do conteúdo.
    Eventos sem mídia disponível viram card (se tiverem texto curto) ou são descartados."""
    out_dir = work / "dinamismo"
    out_dir.mkdir(exist_ok=True)
    for old in out_dir.glob("*.mp4"):
        old.unlink()
    W, H = g.content_w, g.content_h
    fps = float(g.fps)
    final, creditos = [], []
    vid_used: dict = {}
    for k, ev in enumerate(events):
        dst = out_dir / f"ev{k:02d}_{ev['tipo']}.mp4"
        ok = False
        if ev["tipo"] == "video":
            n = vid_used.get(ev["busca"], 0)
            vid_used[ev["busca"]] = n + 1
            src = stock.pexels_video(ev["busca"], cfg, min_dur=ev["dur"] + 0.6, skip=n)
            if not src:   # sem chave do Pexels → Mixkit (busca em inglês: campo busca_en do plano)
                src = stock.mixkit_video(ev.get("busca_en") or ev["busca"], skip=n)
            if src:
                ffmpeg("-ss", "0.4", "-i", str(src), "-t", f"{ev['dur']:.3f}", "-an", "-vf",
                       f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps:.6f},setsar=1,"
                       f"eq=saturation=1.05", "-c:v", "libx264", "-crf", "16", "-preset", "fast",
                       "-pix_fmt", "yuv420p", str(dst))
                ok = True
        elif ev["tipo"] == "foto":
            img, cred = None, None
            if ev.get("arquivo_local"):   # foto escolhida a dedo no plano (licença conferida)
                from .utils import ROOT
                f = Path(ev["arquivo_local"])
                img = f if f.is_absolute() else ROOT / f
                img = img if img.exists() else None
                cred = {"fonte": ev.get("credito") or str(f)} if img else None
            if img is None and not ev.get("entidade"):
                img = stock.pexels_photo(ev["busca"], cfg)
            if img is None:   # pessoas/marcas e fallback: Openverse (CC, inclui Wikimedia/Flickr)
                r = stock.openverse_photo(ev["busca"], skip=ev.get("escolha", 0))
                if r:
                    img, cred = r
            if img:
                n = max(2, int(ev["dur"] * fps))
                # Ken Burns: zoom lento 1.00 → 1.12 centrado; foto cobre o quadro
                ffmpeg("-loop", "1", "-i", str(img), "-t", f"{ev['dur']:.3f}", "-vf",
                       f"scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},"
                       f"zoompan=z='1+0.12*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={W}x{H}:fps={fps:.6f},"
                       "setsar=1,format=yuv420p", "-frames:v", str(n), "-c:v", "libx264", "-crf", "16",
                       "-preset", "fast", str(dst))
                ok = True
                if cred:
                    creditos.append(dict(cred, t=ev["t"], busca=ev["busca"]))
        if not ok and ev["tipo"] != "card":
            if ev.get("texto") or ev.get("motivo", "").startswith("nome"):
                ev = dict(ev, tipo="card", texto=ev.get("texto") or ev["busca"])
            else:
                log.info("  sem mídia para '%s' (rede/chave indisponível) → mantém o orador", ev.get("busca"))
                continue
        if ev["tipo"] == "card":
            # fundo = o próprio vídeo desfocado e escurecido (sempre disponível, sem rede)
            ffmpeg("-ss", f"{ev['t']:.3f}", "-i", str(montado), "-t", f"{ev['dur']:.3f}", "-an", "-vf",
                   f"gblur=sigma=28,eq=brightness=-0.22:saturation=0.85,scale={W}:{H},setsar=1",
                   "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p", str(dst))
        final.append(dict(ev, arquivo=dst))
    log.info("  dinamismo: %d sobreposições renderizadas (%s)", len(final),
             {k: sum(e["tipo"] == k for e in final) for k in ("video", "foto", "card")})
    return final, creditos


def ass_cards(doc: AssDoc, events, words_out, g, cfg, jobs: list | None = None):
    """Texto dos cards: tipografia grande, branca, pesos/tamanhos misturados, revelação por palavra.
    Com `jobs` (Remotion), o texto vira um job de render em vez de ASS; devolve os intervalos."""
    W, H = g.canvas_w, g.canvas_h
    k = (W / 1080) if H > W else (H / 1080)
    base = 66 * k
    spans = []
    for ev in events:
        if ev["tipo"] != "card":
            continue
        a, b = ev["t"], ev["t"] + ev["dur"]
        ws = [w for w in words_out if a - 0.05 <= w["s"] < b] or [{"w": t, "s": a, "kw": 0} for t in (ev.get("texto") or "").split()]
        if ev.get("texto") and ev.get("motivo") == "plano manual":
            # texto do plano manda: cada palavra entra quando é falada (ou em sequência), e a que
            # estiver em CAIXA ALTA no plano vira o destaque (ex.: "comenta SKILL")
            falado = {re.sub(r"[^\wÀ-ú]", "", w["w"].lower()): w for w in ws}
            toks = ev["texto"].split()
            novo = []
            for i, tk in enumerate(toks):
                w0 = falado.get(re.sub(r"[^\wÀ-ú]", "", tk.lower()))
                s0 = w0["s"] if w0 else a + 0.12 * i
                kw = 1.0 if (tk.isupper() and len(tk) > 1) else (w0.get("kw", 0) * 0.5 if w0 else 0)
                novo.append({"w": tk, "s": s0, "kw": kw})
            for i in range(1, len(novo)):        # mantém a ordem do texto
                novo[i]["s"] = max(novo[i]["s"], novo[i - 1]["s"] + 0.08)
            ws = novo
        if not ws:
            continue
        spans.append((a, b))
        if jobs is not None:
            jobs.append({"tipo": "card", "t": round(a, 3), "dur": round(b - a, 3),
                         "palavras": [{"w": w["w"], "s": round(max(0.0, w["s"] - a), 3), "kw": round(w.get("kw", 0), 3)} for w in ws],
                         "y": round((g.content_y + g.content_h * 0.47) / H, 4)})
            continue
        kw_i = max(range(len(ws)), key=lambda i: ws[i].get("kw", 0))
        # linhas: até 3 palavras por linha; a linha da palavra-chave fica gigante
        lines, cur = [], []
        for i, w in enumerate(ws):
            cur.append(i)
            if len(cur) == 3 or i == kw_i or i == len(ws) - 1 or (i + 1 == kw_i):
                lines.append(cur)
                cur = []
        for wi in range(len(ws)):
            s0 = a if wi == 0 else max(a, ws[wi]["s"])
            e0 = ws[wi + 1]["s"] if wi + 1 < len(ws) else b
            segs = []
            for li, ln in enumerate(lines):
                big = kw_i in ln
                sz = base * (1.9 if big else 0.95)
                weight = "Black" if big else ("Medium" if li % 2 == 0 else "SemiBold")
                ital = (not big) and li == len(lines) - 1 and len(lines) > 1
                txt = " ".join(("{\\1a&HFF&\\4a&HFF&}" if i > wi else "{\\1a&H00&\\4a&H80&}") +
                               esc(ws[i]["w"].upper() if big else ws[i]["w"]) for i in ln)
                segs.append("{\\fnInter\\b%d\\i%d\\fs%d\\1c&HFFFFFF&\\bord0\\shad4\\4c&H000000&\\4a&H80&}%s"
                            % (WEIGHTS[weight], 1 if ital else 0, int(sz), txt))
            anim = "\\fscx92\\fscy92\\t(0,220,\\fscx100\\fscy100)" if wi == 0 else ""
            fade = "\\fad(0,120)" if wi == len(ws) - 1 else ""
            doc.add(s0, max(e0, s0 + 0.05), "{\\an5\\pos(%d,%d)%s%s}" % (W / 2, g.content_y + g.content_h * 0.47, anim, fade)
                    + "\\N".join(segs), layer=8)
    return spans
