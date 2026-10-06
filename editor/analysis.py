"""Análise inicial do vídeo: metadados, qualidade de áudio e detecção de planos (shots).

Saída: dict serializável salvo em work/<video>/analise.json
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from .utils import ffmpeg, lin_to_db, load_audio, log, probe, run


def loudness_stats(path: Path) -> dict:
    """Loudness integrada (LUFS), LRA e true peak via filtro ebur128 do FFmpeg."""
    p = run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path), "-vn",
             "-af", "ebur128=peak=true", "-f", "null", "-"])
    txt = p.stderr.split("Summary:")[-1]
    def grab(key):
        m = re.search(rf"{key}:\s+(-?[\d.]+|-inf)", txt)
        return float(m.group(1)) if m and m.group(1) != "-inf" else None
    return {"lufs": grab("I"), "lra": grab("LRA"), "true_peak": grab("Peak")}


def detect_shots(path: Path, limiar: float = 0.3) -> list[float]:
    """Tempos (s) em que há troca de plano na fonte, via filtro scene do FFmpeg."""
    p = run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path), "-an",
             "-vf", f"scale=320:-2,select='gt(scene,{limiar})',showinfo", "-f", "null", "-"])
    return [float(x) for x in re.findall(r"pts_time:([\d.]+)", p.stderr)]


def audio_quality(audio: np.ndarray, sr: int) -> dict:
    """Piso de ruído, clipping e hum (50/60 Hz) estimados do áudio mono."""
    win = int(0.05 * sr)
    n = len(audio) // win
    if n == 0:
        return {}
    rms = np.sqrt(np.mean(audio[: n * win].reshape(n, win) ** 2, axis=1))
    rms_db = lin_to_db(rms)
    clip = float(np.mean(np.abs(audio) > 0.995))
    # Hum: energia em 50/60 Hz e harmônicos vs. vizinhança, em trechos de menor energia
    quiet_idx = np.argsort(rms)[: max(1, n // 10)]
    seg = np.concatenate([audio[i * win:(i + 1) * win] for i in quiet_idx])
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) + 1e-12
    freqs = np.fft.rfftfreq(len(seg), 1 / sr)
    def peak_ratio(f0):
        r = []
        for h in (1, 2, 3):
            f = f0 * h
            band = (freqs > f - 2) & (freqs < f + 2)
            ref = (freqs > f - 15) & (freqs < f + 15) & ~band
            if band.any() and ref.any():
                r.append(20 * np.log10(spec[band].max() / np.median(spec[ref])))
        return float(np.mean(r)) if r else 0.0
    h50, h60 = peak_ratio(50), peak_ratio(60)
    hum = None
    if max(h50, h60) > 12:
        hum = 50 if h50 > h60 else 60
    return {
        "piso_ruido_db": float(np.percentile(rms_db, 10)),
        "nivel_fala_db": float(np.percentile(rms_db, 90)),
        "snr_estimado_db": float(np.percentile(rms_db, 90) - np.percentile(rms_db, 10)),
        "clipping_frac": clip,
        "tem_clipping": clip > 1e-4,
        "hum_hz": hum,
        "hum_db": {"50": round(h50, 1), "60": round(h60, 1)},
    }


def analyze(path: Path, sr: int = 16000) -> dict:
    meta = probe(path)
    log.info("  %dx%d @ %.3f fps, %.1fs, áudio=%s", meta["largura"], meta["altura"],
             meta["fps_float"], meta["duracao"], meta["tem_audio"])
    res = {"meta": meta}
    if meta["tem_audio"]:
        res["loudness"] = loudness_stats(path)
        res["audio"] = audio_quality(load_audio(path, sr), sr)
        log.info("  loudness %.1f LUFS, piso de ruído %.1f dB, hum=%s, clipping=%s",
                 res["loudness"]["lufs"] or -99, res["audio"]["piso_ruido_db"],
                 res["audio"]["hum_hz"], res["audio"]["tem_clipping"])
    res["planos"] = detect_shots(path)
    res["orientacao"] = "vertical" if meta["altura"] > meta["largura"] else "horizontal"
    log.info("  %d trocas de plano detectadas", len(res["planos"]))
    return res


def shot_id(t: float, shots: list[float]) -> int:
    """Índice do plano ao qual o tempo t pertence."""
    return int(np.searchsorted(np.asarray(shots), t, side="right"))


def extract_frame(path: Path, t: float, out: Path, width: int = 640) -> Path:
    ffmpeg("-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
           "-vf", f"scale={width}:-2", str(out))
    return out
