"""ETAPA 9 — Trilha sonora variada com ducking e beats.

• Escolhe o humor (YAML ou tom detectado na transcrição) e faixas da pasta assets/music/<humor>/
• Troca de faixa a cada 60-90 s (no início de frase mais próximo) com crossfade equal-power
• Beats por faixa: metadados do library.yaml ou librosa.beat_track (arquivos reais)
• Ducking: a trilha abaixa `ducking_db` sob a voz (envelope com ataque/release suaves)
• Dinâmica: sobe até `dinamica_max_db` nos trechos de maior energia da fala
• Smash cut: silencia a trilha por `corte_musica_s` antes do impacto
"""
from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import yaml
from scipy import signal

from .utils import ROOT, db_to_lin, load_audio, log

MOOD_FALLBACK = {
    "energetico": ["energetico", "informativo"],
    "informativo": ["informativo", "energetico", "emocional"],
    "emocional": ["emocional", "informativo"],
    "dramatico": ["dramatico", "sombrio", "emocional"],
    "sombrio": ["sombrio", "dramatico"],
}


def library(cfg: dict) -> dict:
    base = ROOT / cfg["musica"]["pasta"]
    meta = {}
    if (base / "library.yaml").exists():
        meta = yaml.safe_load((base / "library.yaml").read_text()) or {}
    lib: dict[str, list[dict]] = {}
    for f in sorted(base.glob("*/*")):
        if f.suffix.lower() not in (".wav", ".mp3", ".flac", ".ogg", ".m4a"):
            continue
        key = f"{f.parent.name}/{f.name}"
        lib.setdefault(f.parent.name, []).append({"path": f, **meta.get(key, {})})
    return lib


def track_beats(entry: dict, audio: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
    """Tempos de beat (s) e força (0-1) da faixa."""
    if entry.get("bpm") and entry.get("compasso_s"):
        period = 60 / entry["bpm"]
        bt = np.arange(0, len(audio) / sr, period)
        strength = np.array([1.0 if i % 4 == 0 else (0.7 if i % 4 == 2 else 0.45) for i in range(len(bt))])
        # compassos de baixa energia na faixa → beats mais fracos
        en = entry.get("energia_por_compasso")
        if en:
            bar = entry["compasso_s"]
            strength *= np.array([0.5 + 0.5 * en[min(len(en) - 1, int(t / bar))] for t in bt])
        return bt, strength / strength.max()
    import librosa
    y = audio.mean(1) if audio.ndim == 2 else audio
    y = librosa.resample(y, orig_sr=sr, target_sr=22050)
    tempo, frames = librosa.beat.beat_track(y=y, sr=22050)
    onset = librosa.onset.onset_strength(y=y, sr=22050)
    bt = librosa.frames_to_time(frames, sr=22050)
    st = onset[np.clip(frames, 0, len(onset) - 1)]
    st = st / (np.percentile(st, 95) or 1)
    return bt, np.clip(st, 0, 1)


def choose_mood(cfg: dict, tone: str, lib: dict) -> str:
    mood = cfg["musica"]["humor"]
    if mood == "auto":
        mood = tone
    for m in MOOD_FALLBACK.get(mood, [mood]) + list(lib):
        if m in lib:
            return m
    raise FileNotFoundError("Nenhuma trilha em assets/music — rode: python -m editor.assets_gen")


def plan(duration: float, tone: str, frases_out: list[dict], cfg: dict, sr: int) -> dict:
    """Escolhe faixas/trechos e devolve o plano (sem ducking ainda) e os beats em tempo de saída."""
    mc = cfg["musica"]
    lib = library(cfg)
    mood = choose_mood(cfg, tone, lib)
    rnd = random.Random(mc["semente"])
    tracks = lib[mood][:]
    rnd.shuffle(tracks)
    # pontos de troca: a cada 60-90 s, no início de frase mais próximo
    bounds, t = [0.0], 0.0
    starts = [f["s"] for f in frases_out]
    while True:
        step = rnd.uniform(*mc["trocar_a_cada_s"])
        if t + step >= duration - 15:
            break
        cand = min(starts, key=lambda s: abs(s - (t + step))) if starts else t + step
        t = cand if cand > t + 30 else t + step
        bounds.append(t)
    bounds.append(duration)
    segs = []
    for i in range(len(bounds) - 1):
        # alterna entre variantes do humor; se só houver uma, usa outro trecho da mesma faixa
        entry = tracks[i % len(tracks)]
        segs.append({"faixa": str(entry["path"].relative_to(ROOT)), "entry": entry,
                     "ini": bounds[i], "fim": bounds[i + 1], "offset": 0.0 if i < len(tracks) else 30.0 * (i // len(tracks))})
    log.info("  humor=%s, %d trecho(s): %s", mood, len(segs), [Path(s["faixa"]).name for s in segs])
    beats = []
    cache = {}
    for s in segs:
        p = s["entry"]["path"]
        if p not in cache:
            a = load_audio(p, sr, mono=False)
            cache[p] = (a, *track_beats(s["entry"], a, sr))
        a, bt, st = cache[p]
        for b, w in zip(bt, st):
            tout = s["ini"] + (b - s["offset"])
            if s["ini"] <= tout < s["fim"]:
                beats.append((round(float(tout), 4), float(w)))
    return {"humor": mood, "trechos": segs, "beats": beats, "_cache": cache}


def render(pl: dict, duration: float, voice_db: np.ndarray, voice_act: np.ndarray, hop: float,
           smash_times: list[float], cfg: dict, sr: int) -> np.ndarray:
    mc = cfg["musica"]
    n = int(duration * sr)
    out = np.zeros((n, 2), np.float32)
    xf = int(mc["crossfade_s"] * sr)
    for i, s in enumerate(pl["trechos"]):
        a = pl["_cache"][s["entry"]["path"]][0]
        a0 = int((s["ini"] - (mc["crossfade_s"] / 2 if i > 0 else 0)) * sr)
        a1 = min(n, int((s["fim"] + (mc["crossfade_s"] / 2 if i < len(pl["trechos"]) - 1 else 0)) * sr))
        off = int((s["offset"] - (s["ini"] - a0 / sr)) * sr)
        need = a1 - a0
        src = np.concatenate([a] * (2 + need // max(1, len(a))))  # faz loop se a faixa for curta
        piece = src[max(0, off): max(0, off) + need].copy()
        if len(piece) < need:
            piece = np.pad(piece, ((0, need - len(piece)), (0, 0)))
        if i > 0 and xf:   # crossfade equal-power
            piece[:xf] *= np.sin(np.linspace(0, np.pi / 2, xf))[:, None]
        if i < len(pl["trechos"]) - 1 and xf:
            piece[-xf:] *= np.cos(np.linspace(0, np.pi / 2, xf))[:, None]
        out[a0:a1] += piece[: a1 - a0]
    # --- curva de ganho (dB) por janela de hop
    m = len(voice_act)
    g = np.full(m, mc["volume_db"], np.float64)
    g[voice_act] += mc["ducking_db"]
    if mc["dinamica_energia"] and m > 10:
        k = int(4 / hop)
        energy = np.convolve(np.where(voice_act, np.clip(voice_db, -60, 0), -60), np.ones(k) / k, "same")
        hi = np.percentile(energy, 75)
        boost = np.clip((energy - hi) / 6, 0, 1) * mc["dinamica_max_db"]
        g += boost
    for t in smash_times:
        a = int(max(0, t - cfg["cortes"]["smash_cut"]["corte_musica_s"]) / hop)
        b = int(t / hop)
        g[a:b] = -80
    # suavização ataque/release (one-pole assimétrico em dB)
    att = np.exp(-hop / max(1e-3, mc["ducking_ataque_s"]))
    rel = np.exp(-hop / max(1e-3, mc["ducking_release_s"]))
    sm = np.empty_like(g)
    sm[0] = g[0]
    for i in range(1, m):
        c = att if g[i] < sm[i - 1] else rel
        sm[i] = c * sm[i - 1] + (1 - c) * g[i]
    for t in smash_times:   # volta seca no impacto
        b = int(t / hop)
        if b < m:
            sm[b:b + 3] = g[b:b + 3]
    gain = np.interp(np.arange(n) / sr, np.arange(m) * hop, 10 ** (sm / 20)).astype(np.float32)
    out *= gain[:, None]
    fi, fo = int(mc["fade_in_s"] * sr), int(mc["fade_out_s"] * sr)
    if fi:
        out[:fi] *= np.linspace(0, 1, fi)[:, None]
    if fo:
        out[-fo:] *= np.linspace(1, 0, fo)[:, None]
    return out
