"""ETAPA 6 — Correção de cor em duas etapas.

PRIMÁRIA (técnica, por plano da fonte) → filtros FFmpeg aplicados no render de cada segmento:
  • balanço de branco gray-world (ganhos por canal limitados)         colorchannelmixer
  • exposição: gamma para levar a luma média ao alvo                  eq=gamma
  • contraste: estica pretos/brancos pelos percentis 0.5/99.5         colorlevels
  • tom de pele: aproxima a cor média do rosto da "skin tone line"     colorbalance (meios-tons)
  • normalização entre planos: o alvo de luma é a mediana dos planos

SECUNDÁRIA (estética) → LUT .cube 33³ gerada com colour-science e aplicada com lut3d.
  Looks em cor.looks no YAML (contraste, saturação, temperatura, split-toning...).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .utils import ROOT, log

SKIN_ANGLE = 123.0  # graus no plano Cb/Cr (vectorscope) — "skin tone line"


# ----------------------------------------------------------------------------- PRIMÁRIA
def _skin_angle(frame_bgr, face):
    h, w = frame_bgr.shape[:2]
    cx, cy, fw, fh = face
    x0, x1 = int((cx - fw * 0.25) * w), int((cx + fw * 0.25) * w)
    y0, y1 = int((cy - fh * 0.1) * h), int((cy + fh * 0.3) * h)
    roi = frame_bgr[max(0, y0):y1, max(0, x0):x1].reshape(-1, 3).astype(np.float32) / 255
    if len(roi) < 20:
        return None
    b, g, r = roi[:, 0].mean(), roi[:, 1].mean(), roi[:, 2].mean()
    return r, g, b


def analyze_shots(clips, frames, cfg: dict) -> dict[int, dict]:
    """Estatísticas por plano (média de amostras distribuídas pelos clipes do plano)."""
    from .vision import frame_stats
    pc = cfg["cor"]["primaria"]
    per_shot: dict[int, list] = {}
    for c in clips:
        per_shot.setdefault((c.src, c.shot), []).append(c)
    out = {}
    for key, cs in per_shot.items():
        ts = np.concatenate([np.linspace(c.v_in, c.v_out, 3) for c in cs])
        ts = ts[np.linspace(0, len(ts) - 1, min(len(ts), pc["amostras_por_plano"])).astype(int)]
        st = [frame_stats(frames.at(t)) for t in ts]
        agg = {k: float(np.median([s[k] for s in st])) for k in st[0]}
        faces = [c.face for c in cs if c.face]
        skin = None
        if faces:
            vals = [v for v in (_skin_angle(frames.at((c.v_in + c.v_out) / 2), c.face) for c in cs if c.face) if v]
            if vals:
                skin = tuple(float(x) for x in np.median(np.array(vals), axis=0))
        agg["pele_rgb"] = skin
        out[key] = agg
    return out


def primary_filters(shot_stats: dict, cfg: dict) -> dict:
    """Converte estatísticas em uma cadeia de filtros FFmpeg por plano."""
    pc = cfg["cor"]["primaria"]
    if not cfg["cor"]["ativo"]:
        return {k: {"filtro": "", "ajustes": {}} for k in shot_stats}
    lumas = [s["luma"] for s in shot_stats.values()]
    target = pc["luma_alvo"]
    if pc["normalizar_entre_planos"] and len(lumas) > 1:
        target = 0.5 * target + 0.5 * float(np.median(lumas))
    res = {}
    for key, s in shot_stats.items():
        parts, adj = [], {}
        gains = np.ones(3)
        if pc["balanco_branco"]:
            m = np.array([s["r"], s["g"], s["b"]])
            gray = m.mean()
            gains = 1 + np.clip((gray / np.maximum(m, 1e-3) - 1) * 0.6, -pc["ganho_wb_max"], pc["ganho_wb_max"])
            gains /= gains.mean() if gains.mean() > 0 else 1
            if np.max(np.abs(gains - 1)) > 0.01:
                parts.append(f"colorchannelmixer=rr={gains[0]:.4f}:gg={gains[1]:.4f}:bb={gains[2]:.4f}")
                adj["wb_ganhos"] = [round(float(g), 3) for g in gains]
        if pc["contraste_auto"]:
            lo, hi = s["p_low"], s["p_high"]
            imin = float(np.clip(lo * 0.85, 0, 0.12)) if lo > 0.03 else 0.0
            imax = float(np.clip(hi + (1 - hi) * 0.15, 0.85, 1)) if hi < 0.93 else 1.0
            if imin > 0 or imax < 1:
                parts.append(f"colorlevels=rimin={imin:.3f}:gimin={imin:.3f}:bimin={imin:.3f}:"
                             f"rimax={imax:.3f}:gimax={imax:.3f}:bimax={imax:.3f}")
                adj["niveis"] = [round(imin, 3), round(imax, 3)]
        if pc["exposicao"]:
            l = float(np.clip(s["luma"], 0.03, 0.97))
            gamma = float(np.log(l) / np.log(target)) if 0 < target < 1 else 1.0
            gamma = float(np.clip(gamma, 1 - pc["ajuste_exposicao_max"], 1 + pc["ajuste_exposicao_max"]))
            if abs(gamma - 1) > 0.02:
                # eq aplica v^(1/gamma): gamma > 1 clareia. gamma = ln(luma)/ln(alvo)
                parts.append(f"eq=gamma={gamma:.3f}")
                adj["gamma"] = round(gamma, 3)
        if pc["pele"] and s.get("pele_rgb"):
            r, g, b = np.array(s["pele_rgb"]) * gains
            y = 0.299 * r + 0.587 * g + 0.114 * b
            cb, cr = (b - y) * 0.564, (r - y) * 0.713
            ang = np.degrees(np.arctan2(cr, cb)) % 360
            mag = np.hypot(cb, cr)
            dev = ((SKIN_ANGLE - ang + 180) % 360) - 180
            if abs(dev) > 4 and mag > 0.01:
                tgt = np.radians(ang + dev * pc["pele_forca"])
                dcb, dcr = mag * np.cos(tgt) - cb, mag * np.sin(tgt) - cr
                dr, dg, db = 1.402 * dcr, -0.344 * dcb - 0.714 * dcr, 1.772 * dcb
                k = 2.5  # colorbalance é relativo; escala empírica
                parts.append(f"colorbalance=rm={np.clip(dr*k,-0.3,0.3):.3f}:gm={np.clip(dg*k,-0.3,0.3):.3f}:bm={np.clip(db*k,-0.3,0.3):.3f}")
                adj["pele_desvio_graus"] = round(float(dev), 1)
        res[key] = {"filtro": ",".join(parts), "ajustes": adj, "luma_antes": round(s["luma"], 3), "luma_alvo": round(target, 3)}
    for k, v in res.items():
        log.info("  plano %s: %s", k, v["ajustes"] or "sem ajuste")
    return res


# ----------------------------------------------------------------------------- LUT
def _apply_look(rgb: np.ndarray, p: dict) -> np.ndarray:
    x = rgb.copy()
    # temperatura / tint
    x[..., 0] *= 1 + p.get("temperatura", 0)
    x[..., 2] *= 1 - p.get("temperatura", 0)
    x[..., 1] *= 1 + p.get("tint", 0)
    x = np.clip(x, 0, 1)
    # curva S de contraste
    c = p.get("contraste", 0) * 2.2
    s = x * x * (3 - 2 * x)
    x = np.clip((1 - c) * x + c * s, 0, 1) if c >= 0 else x
    # pretos (lift > 0, crush < 0)
    bl = p.get("pretos", 0)
    x = bl + x * (1 - bl) if bl >= 0 else np.clip((x + bl) / (1 + bl), 0, 1)
    # split-toning
    L = (0.2126 * x[..., 0] + 0.7152 * x[..., 1] + 0.0722 * x[..., 2])[..., None]
    x = x + np.array(p.get("sombras", [0, 0, 0])) * (1 - L) ** 2 + np.array(p.get("luzes", [0, 0, 0])) * L ** 2
    x = np.clip(x, 0, 1)
    # saturação + vibrance
    L = (0.2126 * x[..., 0] + 0.7152 * x[..., 1] + 0.0722 * x[..., 2])[..., None]
    sat_px = (x.max(-1) - x.min(-1))[..., None]
    k = p.get("saturacao", 1.0) * (1 + p.get("vibrance", 0) * (1 - sat_px))
    return np.clip(L + (x - L) * k, 0, 1)


def make_lut(name: str, params: dict, intensity: float = 1.0, size: int = 33) -> Path:
    import colour
    out = ROOT / "assets" / "luts" / f"{name}_{int(intensity*100)}.cube"
    out.parent.mkdir(parents=True, exist_ok=True)
    lut = colour.LUT3D(size=size, name=name)
    table = lut.table
    looked = _apply_look(table, params)
    lut.table = table + (looked - table) * intensity
    colour.io.write_LUT(lut, str(out))
    return out


def lut_filter(cfg: dict) -> str:
    look = cfg["cor"]["look"]
    if not cfg["cor"]["ativo"] or not look:
        return ""
    params = cfg["cor"]["looks"][look]
    path = make_lut(look, params, cfg["cor"]["intensidade_look"])
    return f"lut3d=file='{_esc(path)}':interp=tetrahedral"


def _esc(p: Path) -> str:
    return str(p).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def histogram_report(pairs: list[tuple[np.ndarray, np.ndarray]], out_png: Path) -> dict:
    """Histogramas de luma e RGB antes/depois + gráfico. pairs: [(frame_antes, frame_depois)] BGR."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from .vision import frame_stats
    a = np.concatenate([p[0].reshape(-1, 3) for p in pairs])
    b = np.concatenate([p[1].reshape(-1, 3) for p in pairs])
    fig, axs = plt.subplots(1, 2, figsize=(12, 3.2), dpi=100, sharey=True)
    for ax, data, title in ((axs[0], a, "antes"), (axs[1], b, "depois")):
        for ch, col in ((2, "r"), (1, "g"), (0, "b")):
            ax.hist(data[:, ch], bins=64, range=(0, 255), color=col, alpha=0.35, histtype="stepfilled")
        y = 0.2126 * data[:, 2] + 0.7152 * data[:, 1] + 0.0722 * data[:, 0]
        ax.hist(y, bins=64, range=(0, 255), color="k", histtype="step", lw=1.2)
        ax.set_title(title)
        ax.set_yticks([])
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)
    sa = [frame_stats(p[0]) for p in pairs]
    sb = [frame_stats(p[1]) for p in pairs]
    agg = lambda st: {k: round(float(np.mean([s[k] for s in st])), 3) for k in st[0]}  # noqa: E731
    return {"antes": agg(sa), "depois": agg(sb)}
