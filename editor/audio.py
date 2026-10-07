"""ETAPA 7 — Correção e masterização de áudio.

Limpeza da voz (na fonte inteira, antes da montagem):
  noisereduce (perfil de ruído dos trechos mais silenciosos) → passa-altas → remoção de hum
  (50/60 Hz + harmônicos, só se detectado) → adeclip (só com clipping) → de-esser →
  EQ (corte de lama, presença 3-5 kHz, ar) → compressor → normalização para voz_lufs.
Montagem: recorta a voz limpa segundo a timeline, com micro-fades nos cortes.
Mix: voz + trilha (já com ducking) + SFX → master loudnorm (-14 LUFS, TP -1 dBTP) + limiter.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

from .utils import db_to_lin, ffmpeg, load_audio, log, run, save_wav


def _measure_lufs(x: np.ndarray, sr: int) -> float:
    import pyloudnorm as pyln
    m = pyln.Meter(sr)
    return float(m.integrated_loudness(x.astype(np.float64)))


def clean_voice(src: Path, analise: dict, cfg: dict, out_wav: Path) -> dict:
    ac = cfg["audio"]
    lc = ac["limpeza"]
    sr = ac["taxa_amostragem"]
    x = load_audio(src, sr)
    info = {}
    # 1) redução de ruído com perfil dos 10% de janelas mais silenciosas
    if lc["reducao_ruido"]:
        import noisereduce as nr
        win = int(0.05 * sr)
        n = len(x) // win
        rms = np.sqrt(np.mean(x[: n * win].reshape(n, win) ** 2, axis=1))
        idx = np.argsort(rms)[: max(4, n // 10)]
        noise = np.concatenate([x[i * win:(i + 1) * win] for i in sorted(idx)])
        x = nr.reduce_noise(y=x, sr=sr, y_noise=noise, stationary=True,
                            prop_decrease=lc["reducao_ruido_forca"], n_jobs=1).astype(np.float32)
        info["reducao_ruido"] = lc["reducao_ruido_forca"]
    tmp = out_wav.with_suffix(".nr.wav")
    save_wav(tmp, x, sr)
    # 2) cadeia FFmpeg
    eq = ac["eq"]
    cp = ac["compressor"]
    chain = [f"highpass=f={max(lc['passa_altas_hz'], eq['corte_grave_hz'])}:poles=2"]
    hum = lc["remover_hum"]
    if hum == "auto":
        hum = (analise.get("audio") or {}).get("hum_hz")
    if hum:
        for h in range(1, lc["harmonicos_hum"] + 1):
            chain.append(f"bandreject=f={int(hum) * h}:width_type=q:w=30")
        info["hum_removido_hz"] = int(hum)
    dc = lc["declip"]
    if dc is True or (dc == "auto" and (analise.get("audio") or {}).get("tem_clipping")):
        chain.append("adeclip")
        info["declip"] = True
    if lc["deesser"]:
        chain.append(f"deesser=i={lc['deesser_intensidade']}:m=0.5:f=0.5")
    chain += [f"equalizer=f={eq['lama_hz']}:t=q:w=1.2:g={eq['lama_db']}",
              f"equalizer=f={eq['presenca_hz']}:t=q:w=1.0:g={eq['presenca_db']}",
              f"equalizer=f={eq['ar_hz']}:t=h:w=0.7:g={eq['ar_db']}",
              f"acompressor=threshold={db_to_lin(cp['limiar_db']):.5f}:ratio={cp['razao']}:"
              f"attack={cp['ataque_ms']}:release={cp['release_ms']}:makeup={db_to_lin(cp['makeup_db']):.3f}"]
    ffmpeg("-i", str(tmp), "-af", ",".join(chain), "-ar", str(sr), "-ac", "1", "-c:a", "pcm_f32le", str(out_wav))
    tmp.unlink(missing_ok=True)
    # 3) loudness da voz
    import soundfile as sf
    y, _ = sf.read(str(out_wav), dtype="float32")
    lufs = _measure_lufs(y, sr)
    if np.isfinite(lufs):
        y = y * db_to_lin(ac["voz_lufs"] - lufs)
        peak = np.max(np.abs(y))
        if peak > 0.98:
            y *= 0.98 / peak
        save_wav(out_wav, y, sr)
    info.update({"cadeia_ffmpeg": chain, "voz_lufs_antes": round(lufs, 1), "voz_lufs_depois": ac["voz_lufs"]})
    log.info("  voz limpa: %s", ", ".join(c.split("=")[0] for c in chain))
    return info


def assemble(clips, voice: np.ndarray, sr: int, fps, xfade_ms: float) -> np.ndarray:
    """Monta a faixa de voz na ordem da timeline (frames exatos, micro-fade nos cortes)."""
    parts = []
    nf = int(sr * xfade_ms / 1000)
    ramp = np.linspace(0, 1, nf, dtype=np.float32) if nf > 1 else None
    for c in clips:
        if c.freeze_frames:
            parts.append(np.zeros(int(round(c.freeze_frames / float(fps) * sr)), np.float32))
        n = int(round(c.dur * sr))
        a = int(round(c.a_in * sr))
        seg = voice[a:a + n].copy()
        if len(seg) < n:
            seg = np.pad(seg, (0, n - len(seg)))
        if ramp is not None and n > 2 * nf:
            seg[:nf] *= ramp
            seg[-nf:] *= ramp[::-1]
        parts.append(seg)
    return np.concatenate(parts) if parts else np.zeros(0, np.float32)


def voice_envelope(voice: np.ndarray, sr: int, hop_s: float = 0.02, thr_db: float = -42) -> tuple[np.ndarray, np.ndarray]:
    """Envelope RMS (dB) da voz montada e máscara de atividade (para ducking)."""
    hop = int(sr * hop_s)
    n = max(1, len(voice) // hop)
    rms = np.sqrt(np.mean(voice[: n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    active = db > thr_db
    # fecha buracos curtos (entre sílabas) para o ducking não "bombear"
    k = int(0.25 / hop_s)
    act = np.convolve(active.astype(float), np.ones(k), "same") > 0
    return db, act


def mix_and_master(voice: np.ndarray, music: np.ndarray | None, sfx_events: list[dict], sr: int,
                   cfg: dict, plat: dict, work: Path, nome: str = "audio_master") -> tuple[Path, dict]:
    n = len(voice)
    mix = np.stack([voice, voice], 1).astype(np.float32)
    if music is not None:
        m = music[:n]
        if len(m) < n:
            m = np.pad(m, ((0, n - len(m)), (0, 0)))
        mix += m
    for ev in sfx_events:
        s = int(ev["t"] * sr)
        if s >= n:
            continue
        clip = ev["audio"] * db_to_lin(ev["ganho_db"])
        if s < 0:
            clip, s = clip[-s:], 0
        e = min(n, s + len(clip))
        mix[s:e] += clip[: e - s]
    pre = work / f"{nome}_pre.wav"
    save_wav(pre, mix, sr)
    mc = cfg["audio"]["master"]
    target = plat.get("lufs", mc["lufs"])
    # loudnorm em 2 passes (medição → aplicação linear) + limiter de segurança
    p = run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(pre), "-af",
             f"loudnorm=I={target}:TP={mc['true_peak_db']}:LRA={mc['lra']}:print_format=json", "-f", "null", "-"])
    meas = json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p.stderr, re.S).group(0))
    out = work / f"{nome}.wav"
    ffmpeg("-i", str(pre), "-af",
           f"loudnorm=I={target}:TP={mc['true_peak_db']}:LRA={mc['lra']}:measured_I={meas['input_i']}:"
           f"measured_TP={meas['input_tp']}:measured_LRA={meas['input_lra']}:measured_thresh={meas['input_thresh']}:"
           f"offset={meas['target_offset']}:linear=true,alimiter=limit={db_to_lin(mc['true_peak_db'] - 0.3):.4f}:level=false",
           "-ar", str(sr), "-c:a", "pcm_s24le", str(out))
    log.info("  master: entrada %.1f LUFS → alvo %s LUFS", float(meas["input_i"]), target)
    return out, {"entrada_lufs": float(meas["input_i"]), "alvo_lufs": target}
