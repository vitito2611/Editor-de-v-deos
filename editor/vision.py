"""Visão computacional: rosto (YuNet/OpenCV), movimento e similaridade de composição.

Tudo trabalha em proxies de baixa resolução decodificados pelo FFmpeg para ser rápido.
Coordenadas de rosto são normalizadas (0-1) em relação ao quadro da fonte.
"""
from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from .utils import ROOT, log

YUNET = ROOT / "models" / "face_detection_yunet_2023mar.onnx"
PROXY_W = 320


class FrameReader:
    """Lê frames do vídeo em tempos arbitrários (proxy em memória, ~4 fps)."""

    def __init__(self, path: Path, fps: float = 4.0, width: int = PROXY_W):
        self.fps = fps
        self.width = width
        p = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height", "-of", "csv=p=0", str(path)],
                           capture_output=True, text=True)
        w, h = map(int, p.stdout.strip().split(",")[:2])
        self.h = int(round(h * width / w / 2) * 2)
        raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-an",
                              "-vf", f"fps={fps},scale={width}:{self.h}", "-pix_fmt", "bgr24",
                              "-f", "rawvideo", "-"], capture_output=True).stdout
        n = len(raw) // (width * self.h * 3)
        self.frames = np.frombuffer(raw[: n * width * self.h * 3], np.uint8).reshape(n, self.h, width, 3)
        log.debug("FrameReader: %d frames proxy", n)

    def at(self, t: float) -> np.ndarray:
        i = int(np.clip(round(t * self.fps), 0, len(self.frames) - 1))
        return self.frames[i]

    def range(self, t0: float, t1: float) -> np.ndarray:
        i0 = int(np.clip(np.floor(t0 * self.fps), 0, len(self.frames) - 1))
        i1 = int(np.clip(np.ceil(t1 * self.fps), i0 + 1, len(self.frames)))
        return self.frames[i0:i1]


@lru_cache(maxsize=4)
def _detector(w: int, h: int):
    if not YUNET.exists():
        return None
    return cv2.FaceDetectorYN.create(str(YUNET), "", (w, h), 0.7, 0.3, 50)


def detect_face(frame: np.ndarray) -> tuple[float, float, float, float] | None:
    """Maior rosto do frame como (cx, cy, w, h) normalizados, ou None."""
    h, w = frame.shape[:2]
    det = _detector(w, h)
    if det is None:
        return None
    _, faces = det.detect(frame)
    if faces is None or len(faces) == 0:
        return None
    x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])[:4]
    return ((x + fw / 2) / w, (y + fh / 2) / h, fw / w, fh / h)


def face_in_range(fr: FrameReader, t0: float, t1: float, samples: int = 3):
    """Rosto mediano em [t0,t1] (None se não houver rosto na maioria das amostras)."""
    ts = np.linspace(t0, max(t0, t1 - 1e-3), samples)
    found = [f for f in (detect_face(fr.at(t)) for t in ts) if f is not None]
    if len(found) < max(1, samples // 2):
        return None
    return tuple(float(v) for v in np.median(np.array(found), axis=0))


def motion_score(fr: FrameReader, t0: float, t1: float) -> float:
    """Média da diferença absoluta entre frames consecutivos (0-255) — gesto/movimento."""
    frames = fr.range(t0, t1)
    if len(frames) < 2:
        return 0.0
    g = frames.mean(axis=3)
    return float(np.mean(np.abs(np.diff(g, axis=0))))


def composition_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Correlação de histogramas HSV (0-1) entre dois frames — base do match cut."""
    ha = cv2.calcHist([cv2.cvtColor(a, cv2.COLOR_BGR2HSV)], [0, 1], None, [30, 32], [0, 180, 0, 256])
    hb = cv2.calcHist([cv2.cvtColor(b, cv2.COLOR_BGR2HSV)], [0, 1], None, [30, 32], [0, 180, 0, 256])
    cv2.normalize(ha, ha)
    cv2.normalize(hb, hb)
    return float(max(0.0, cv2.compareHist(ha, hb, cv2.HISTCMP_CORREL)))


def frame_stats(frame_bgr: np.ndarray) -> dict:
    """Médias por canal (0-1), luma e percentis — usado pela correção de cor."""
    f = frame_bgr.astype(np.float32) / 255.0
    b, g, r = f[..., 0], f[..., 1], f[..., 2]
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return {"r": float(r.mean()), "g": float(g.mean()), "b": float(b.mean()),
            "luma": float(y.mean()), "p_low": float(np.percentile(y, 0.5)),
            "p_high": float(np.percentile(y, 99.5))}
