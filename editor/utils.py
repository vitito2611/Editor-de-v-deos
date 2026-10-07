"""Utilitários compartilhados: execução do FFmpeg, ffprobe, logging e cronômetro."""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path

import numpy as np

try:
    from rich.logging import RichHandler
    _HANDLER = RichHandler(show_path=False, markup=False, rich_tracebacks=True)
except ImportError:  # rich é opcional
    _HANDLER = logging.StreamHandler()

ROOT = Path(__file__).resolve().parent.parent

log = logging.getLogger("editor")


def setup_logging(level: str = "INFO", logfile: Path | None = None) -> None:
    """Configura o log no terminal e, opcionalmente, em arquivo."""
    log.handlers.clear()
    log.setLevel(level)
    _HANDLER.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(_HANDLER)
    if logfile:
        fh = logging.FileHandler(logfile, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(fh)


class Timer:
    """Registra o tempo de cada etapa para o relatório final."""

    def __init__(self):
        self.etapas: list[tuple[str, float]] = []

    @contextmanager
    def etapa(self, nome: str):
        log.info("▶ %s", nome)
        t0 = time.time()
        yield
        dt = time.time() - t0
        self.etapas.append((nome, dt))
        log.info("✔ %s (%.1fs)", nome, dt)


def run(cmd: list[str], quiet: bool = True) -> subprocess.CompletedProcess:
    """Executa um comando; em erro mostra o final do stderr."""
    log.debug("$ %s", " ".join(map(str, cmd)))
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"Falhou: {' '.join(map(str, cmd[:6]))} ...\n{p.stderr[-2500:]}")
    return p


def ffmpeg(*args, quiet: bool = True) -> subprocess.CompletedProcess:
    return run(["ffmpeg", "-hide_banner", "-nostdin", "-y", "-loglevel", "error", *args], quiet)


def arquivo_black_jack() -> Path | None:
    """BlackJack.otf/.ttf em assets/fonts (licença Typadelic: uso livre, redistribuição proibida → não vai pro git)."""
    achados = sorted((ROOT / "assets" / "fonts").glob("[Bb]lack*[Jj]ack*.[ot]tf"))
    return achados[0] if achados else None


def probe(path: Path) -> dict:
    """Metadados essenciais do vídeo (duração, resolução, fps, áudio)."""
    p = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format",
             "-show_streams", str(path)])
    data = json.loads(p.stdout)
    v = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    if v is None:
        raise ValueError(f"{path} não tem stream de vídeo")
    fps = Fraction(v.get("avg_frame_rate") or v["r_frame_rate"])
    if fps == 0:
        fps = Fraction(v["r_frame_rate"])
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(sd["rotation"])
    w, h = int(v["width"]), int(v["height"])
    if abs(rot) in (90, 270):
        w, h = h, w
    return {
        "path": str(path),
        "duracao": float(data["format"]["duration"]),
        "largura": w,
        "altura": h,
        "fps": fps,
        "fps_float": float(fps),
        "codec_video": v["codec_name"],
        "tem_audio": a is not None,
        "taxa_audio": int(a["sample_rate"]) if a else None,
        "canais": int(a["channels"]) if a else 0,
        "bitrate": int(data["format"].get("bit_rate", 0)),
    }


def load_audio(path: Path, sr: int, mono: bool = True) -> np.ndarray:
    """Decodifica o áudio de qualquer arquivo para float32 via FFmpeg."""
    ch = 1 if mono else 2
    p = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-vn",
                        "-ac", str(ch), "-ar", str(sr), "-f", "f32le", "-"],
                       capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode()[-1500:])
    a = np.frombuffer(p.stdout, dtype=np.float32).copy()
    return a if mono else a.reshape(-1, 2)


def save_wav(path: Path, audio: np.ndarray, sr: int) -> None:
    import soundfile as sf
    sf.write(str(path), audio, sr, subtype="FLOAT")


def db_to_lin(db: float) -> float:
    return float(10 ** (db / 20))


def lin_to_db(x, floor: float = -120.0):
    return np.maximum(20 * np.log10(np.maximum(np.abs(x), 1e-12)), floor)


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=_json_default),
                    encoding="utf-8")


def _json_default(o):
    if isinstance(o, Fraction):
        return float(o)
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return str(o)
    raise TypeError(type(o))


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check_binaries() -> dict[str, bool]:
    return {b: shutil.which(b) is not None for b in ("ffmpeg", "ffprobe")}


def snap(t: float, fps: Fraction) -> float:
    """Arredonda um tempo para o frame mais próximo (evita drift áudio/vídeo)."""
    return float(round(Fraction(t).limit_denominator(100000) * fps) / fps)
