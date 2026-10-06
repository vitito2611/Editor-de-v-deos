"""Renderização: segmentos da timeline → montagem → composição final.

1. render_segments  cada clipe vira um arquivo com N frames exatos, já com zoom/reframe,
                    correção primária, glitch; freeze frames (reaction cut) idem. Em paralelo.
2. assemble         concat (cópia) dos segmentos; transições (whip/flash) via xfade.
3. compose          B-roll, LUT, layout (letterbox / blur / crop), grão, vinheta,
                    legendas+motion (ASS/libass), áudio masterizado → MP4 por plataforma.

A "geometria" descreve onde o conteúdo cai no quadro final, usada também pelas legendas
para não cobrir o rosto.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import numpy as np

from .utils import ROOT, ffmpeg, log


def _even(x: float) -> int:
    return max(2, int(round(x / 2)) * 2)


@dataclass
class Geometry:
    mode: str
    canvas_w: int
    canvas_h: int
    content_w: int
    content_h: int
    content_x: int
    content_y: int
    src_w: int
    src_h: int
    base_w: float
    base_h: float
    fps: Fraction


def compute_geometry(meta: dict, plat: dict, cfg: dict, scale: float = 1.0) -> Geometry:
    W, H = _even(plat["largura"] * scale), _even(plat["altura"] * scale)
    sw, sh = meta["largura"], meta["altura"]
    mode = cfg["layout"]["modo"]
    tv, sv = H > W, sh > sw
    if mode == "auto":
        mode = "original" if tv == sv else ("crop_rosto" if tv else "blur_fill")
    fps = Fraction(cfg["geral"]["fps_saida"]).limit_denominator(1001) if cfg["geral"]["fps_saida"] else meta["fps"]
    if mode in ("original", "crop_rosto"):
        ar = W / H
        bw, bh = (sh * ar, sh) if sw / sh > ar else (sw, sw / ar)
        return Geometry(mode, W, H, W, H, 0, 0, sw, sh, bw, bh, fps)
    if mode == "letterbox":
        cw = _even(W * cfg["layout"]["letterbox_largura"])
        ch = _even(cw * sh / sw)
        if ch > H:
            ch, cw = H, _even(H * sw / sh)
    else:  # blur_fill: conteúdo inteiro, "contain"
        if sw / sh > W / H:
            cw, ch = W, _even(W * sh / sw)
        else:
            ch, cw = H, _even(H * sw / sh)
    return Geometry(mode, W, H, cw, ch, (W - cw) // 2, (H - ch) // 2, sw, sh, sw, sh, fps)


def crop_window(c, g: Geometry, anchor_x_shot: float | None = None) -> tuple[int, int, int, int]:
    """Janela de recorte (x, y, w, h) na fonte para o clipe — zoom em torno do rosto."""
    W, H = g.src_w, g.src_h
    w, h = g.base_w / c.zoom, g.base_h / c.zoom
    ax, ay = c.anchor
    if g.mode == "crop_rosto":
        ax = anchor_x_shot if anchor_x_shot is not None else ax
        rel = c.rel or (0.5, ay)
    else:
        bx0, by0 = (W - g.base_w) / 2, (H - g.base_h) / 2
        rel = c.rel or ((ax * W - bx0) / g.base_w, (ay * H - by0) / g.base_h)
    x0 = float(np.clip(ax * W - rel[0] * w, 0, W - w))
    y0 = float(np.clip(ay * H - rel[1] * h, 0, H - h))
    w, h = _even(w), _even(h)
    return min(_even(x0), W - w), min(_even(y0), H - h), w, h


def face_in_canvas(c, win, g: Geometry):
    """Rosto do clipe em coordenadas normalizadas do CANVAS final (x, y, w, h) ou None."""
    if not c.face:
        return None
    x0, y0, w, h = win
    fx = (c.face[0] * g.src_w - x0) / w
    fy = (c.face[1] * g.src_h - y0) / h
    fw, fh = c.face[2] * g.src_w / w, c.face[3] * g.src_h / h
    return ((g.content_x + fx * g.content_w) / g.canvas_w, (g.content_y + fy * g.content_h) / g.canvas_h,
            fw * g.content_w / g.canvas_w, fh * g.content_h / g.canvas_h)


def shot_anchors(clips) -> dict:
    """Âncora horizontal estável por plano (mediana do rosto) — evita reframe 'nervoso'."""
    by: dict = {}
    for c in clips:
        if c.face:
            by.setdefault((c.src, c.shot), []).append(c.face[0])
    return {k: float(np.median(v)) for k, v in by.items()}


# ----------------------------------------------------------------------------- segmentos
def build_jobs(clips, sources: list[Path], g: Geometry, primary: dict, seg_dir: Path) -> list[dict]:
    fps = g.fps
    anchors = shot_anchors(clips)
    jobs = []
    for k, c in enumerate(clips):
        win = crop_window(c, g, anchors.get((c.src, c.shot)))
        c._win = win
        base = (f"fps={float(fps):.6f},crop={win[2]}:{win[3]}:{win[0]}:{win[1]},"
                f"scale={g.content_w}:{g.content_h}:flags=lanczos,setsar=1")
        pf = primary.get((c.src, c.shot), {}).get("filtro", "")
        filt = base + ("," + pf if pf else "")
        if c.glitch_frames:
            n = c.glitch_frames
            filt += (f",rgbashift=rh=14:bh=-14:gv=6:enable='lt(n,{n})',"
                     f"noise=alls=45:allf=t:enable='lt(n,{n})'")
        if c.freeze_frames and k > 0:
            p = clips[k - 1]
            jobs.append({"tipo": "freeze", "clip": k, "src": sources[p.src], "t": p.v_out - 1 / float(fps),
                         "frames": c.freeze_frames, "filtro": p._filt, "out": seg_dir / f"{len(jobs):04d}_freeze.mp4"})
        ext_b = c.transicao_dur / 2 if (c.transicao_in and k > 0 and not c.freeze_frames) else 0.0
        nxt = clips[k + 1] if k + 1 < len(clips) else None
        ext_a = nxt.transicao_dur / 2 if (nxt and nxt.transicao_in and not nxt.freeze_frames) else 0.0
        t0, t1 = c.v_in - ext_b, c.v_out + ext_a
        frames = int(round((c.v_out - c.v_in) * float(fps))) + int(round(ext_b * float(fps))) + int(round(ext_a * float(fps)))
        c._filt = filt
        jobs.append({"tipo": "clip", "clip": k, "src": sources[c.src], "t": max(0.0, t0), "frames": frames,
                     "filtro": filt, "out": seg_dir / f"{len(jobs):04d}_clip.mp4",
                     "transicao_in": c.transicao_in if ext_b else None, "trans_dur": c.transicao_dur if ext_b else 0})
    return jobs


def _render_job(j: dict, fps: Fraction, q: dict):
    eps = 0.3 / float(fps)
    if j["tipo"] == "freeze":
        vf = j["filtro"] + f",trim=end_frame=1,tpad=stop_mode=clone:stop_duration=5"
    else:
        vf = j["filtro"] + ",tpad=stop_mode=clone:stop_duration=1"  # garante N frames no fim da fonte
    ffmpeg("-ss", f"{max(0, j['t'] - eps):.4f}", "-i", str(j["src"]), "-an", "-vf", vf,
           "-frames:v", str(j["frames"]), "-r", str(fps), "-c:v", "libx264", "-preset", q["preset"],
           "-crf", str(q["crf"]), "-pix_fmt", "yuv420p", "-g", "60", "-bf", "0", str(j["out"]))


def render_segments(jobs: list[dict], fps: Fraction, threads: int, preview: bool) -> None:
    q = {"preset": "ultrafast", "crf": 26} if preview else {"preset": "fast", "crf": 13}
    with ThreadPoolExecutor(max_workers=threads) as ex:
        list(ex.map(lambda j: _render_job(j, fps, q), jobs))


def assemble(jobs: list[dict], fps: Fraction, out: Path, preview: bool) -> Path:
    """Concatena segmentos; nas transições usa xfade (slideleft = whip, fadewhite = flash)."""
    blocks, cur = [], []
    trans = []
    for j in jobs:
        if j.get("transicao_in") and cur:
            blocks.append(cur)
            trans.append((j["transicao_in"], j["trans_dur"]))
            cur = []
        cur.append(j)
    blocks.append(cur)
    bfiles = []
    for i, b in enumerate(blocks):
        lst = out.parent / f"bloco_{i:02d}.txt"
        lst.write_text("".join(f"file '{j['out'].resolve()}'\n" for j in b))
        bf = out.parent / f"bloco_{i:02d}.mp4"
        ffmpeg("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(bf))
        bfiles.append((bf, sum(j["frames"] for j in b)))
    if len(bfiles) == 1:
        bfiles[0][0].replace(out)
        return out
    args, fc, last = [], [], "[0:v]"
    for bf, _ in bfiles:
        args += ["-i", str(bf)]
    for i in range(1, len(bfiles)):
        tipo, d = trans[i - 1]
        # comprimento acumulado até aqui menos a duração desta transição
        offset = sum(n for _, n in bfiles[:i]) / float(fps) - sum(t[1] for t in trans[:i])
        tr = {"whip": "slideleft", "flash": "fadewhite"}.get(tipo, "fade")
        lab = f"[x{i}]"
        fc.append(f"{last}[{i}:v]xfade=transition={tr}:duration={d:.3f}:offset={offset:.4f}{lab}")
        last = lab
    q = ("ultrafast", 26) if preview else ("fast", 13)
    ffmpeg(*args, "-filter_complex", ";".join(fc), "-map", last, "-c:v", "libx264", "-preset", q[0],
           "-crf", str(q[1]), "-pix_fmt", "yuv420p", "-r", str(fps), str(out))
    return out


def _esc(p) -> str:
    return str(p).replace("\\", "/").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,")


def compose(video: Path, audio: Path, ass: Path | None, g: Geometry, cfg: dict, plat: dict, out: Path,
            lut: str, broll: list[dict], overlays: list[dict], preview: bool, duration: float) -> Path:
    inputs = ["-i", str(video), "-i", str(audio)]
    fc = []
    cur = "[0:v]"
    idx = 2
    # --- B-roll sobre o conteúdo (voz continua por baixo: L-cut)
    for b in broll:
        inputs += ["-ss", f"{b.get('ss', 0):.3f}", "-t", f"{b['dur']:.3f}", "-i", str(b["arquivo"])]
        d = b["dur"]
        fc.append(f"[{idx}:v]fps={float(g.fps):.6f},scale={g.content_w}:{g.content_h}:force_original_aspect_ratio=increase,"
                  f"crop={g.content_w}:{g.content_h},setsar=1,format=yuva420p,"
                  f"fade=t=in:st=0:d=0.12:alpha=1,fade=t=out:st={max(0, d - 0.12):.3f}:d=0.12:alpha=1,"
                  f"setpts=PTS-STARTPTS+{b['t']:.3f}/TB[br{idx}]")
        fc.append(f"{cur}[br{idx}]overlay=eof_action=pass:enable='between(t,{b['t']:.3f},{b['t'] + d:.3f})'[c{idx}]")
        cur = f"[c{idx}]"
        idx += 1
    # --- LUT (só no conteúdo — barras pretas permanecem pretas)
    if lut:
        fc.append(f"{cur}{lut}[lut]")
        cur = "[lut]"
    W, H = g.canvas_w, g.canvas_h
    if g.mode == "letterbox":
        fc.append(f"{cur}pad={W}:{H}:{g.content_x}:{g.content_y}:black[lay]")
        cur = "[lay]"
    elif g.mode == "blur_fill":
        fc.append(f"{cur}split[bg0][fg0];[bg0]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                  f"boxblur=24:2,eq=brightness=-0.06[bg1];[bg1][fg0]overlay={g.content_x}:{g.content_y}[lay]")
        cur = "[lay]"
    mc = cfg["motion"]
    post = []
    if mc.get("grao"):
        post.append(f"noise=alls={int(mc['grao'])}:allf=t")
    if mc.get("vinheta"):
        post.append("vignette=PI/5")
    if post:
        fc.append(f"{cur}{','.join(post)}[post]")
        cur = "[post]"
    for o in overlays:  # PNGs com alpha (ex.: moldura de película)
        inputs += ["-loop", "1", "-t", f"{duration:.3f}", "-i", str(o["arquivo"])]
        fc.append(f"[{idx}:v]scale={W}:{H},format=rgba[ov{idx}];{cur}[ov{idx}]overlay=0:0:shortest=1[o{idx}]")
        cur = f"[o{idx}]"
        idx += 1
    if ass:
        fc.append(f"{cur}ass=filename='{_esc(ass)}':fontsdir='{_esc(ROOT / 'assets' / 'fonts')}'[sub]")
        cur = "[sub]"
    fc.append(f"{cur}format=yuv420p[vout]")
    crf, preset = (cfg["preview"]["crf"], cfg["preview"]["preset"]) if preview else (plat["crf"], plat["preset"])
    # teto de bitrate (as plataformas recomprimem acima disso; grão de filme estouraria o arquivo)
    rate = ["-maxrate", f"{plat['maxrate_kbps']}k", "-bufsize", f"{plat['maxrate_kbps'] * 2}k"] if plat.get("maxrate_kbps") else []
    ffmpeg(*inputs, "-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "1:a", "-c:v", "libx264",
           "-preset", preset, "-crf", str(crf), *rate, "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(g.fps),
           "-c:a", "aac", "-b:a", f"{plat['audio_kbps']}k", "-ar", "48000", "-movflags", "+faststart",
           "-t", f"{duration:.3f}", str(out))
    return out
