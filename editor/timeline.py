"""Timeline (EDL) — a lista de clipes que forma o vídeo editado.

Cada Clip guarda trechos da FONTE separadamente para áudio (a_in/a_out) e vídeo
(v_in/v_out). Em um corte comum eles coincidem; J-cut e L-cut deslocam só o vídeo,
mantendo a duração total (o que um clipe ganha o vizinho perde).

Tempos de fonte são "encaixados" na grade de frames para que áudio e vídeo nunca
derivem. A posição no vídeo final (tempo de saída) é calculada por `layout_times`.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from fractions import Fraction

from .utils import snap


@dataclass
class Clip:
    src: int                      # índice do arquivo de entrada
    a_in: float                   # áudio: início na fonte (s)
    a_out: float                  # áudio: fim na fonte (s)
    v_in: float = None            # vídeo: início na fonte (s) — difere do áudio em J/L-cut
    v_out: float = None
    shot: int = 0                 # plano da fonte (detecção de cena)
    a_out_max: float = None       # até onde o fim pode ser estendido (silêncio removido)
    a_out_min: float = None       # mínimo sem cortar fala (fim da última palavra)
    zoom: float = 1.0
    anchor: tuple = (0.5, 0.42)   # ponto (normalizado) em torno do qual o zoom acontece (rosto)
    rel: tuple | None = None      # posição desejada do anchor no quadro de saída (match cut)
    face: tuple | None = None     # (cx, cy, w, h) normalizado na fonte
    freeze_frames: int = 0        # reaction cut: congela o último frame do clipe anterior
    transicao_in: str | None = None   # "whip" | "flash" (xfade com o clipe anterior)
    transicao_dur: float = 0.0
    glitch_frames: int = 0
    tags: list = field(default_factory=list)
    out_start: float = 0.0        # preenchido por layout_times (inclui freeze)

    def __post_init__(self):
        if self.v_in is None:
            self.v_in = self.a_in
        if self.v_out is None:
            self.v_out = self.a_out

    @property
    def dur(self) -> float:
        return self.a_out - self.a_in

    def to_dict(self):
        return asdict(self)


def snap_clips(clips: list[Clip], fps: Fraction) -> None:
    """Alinha todos os tempos à grade de frames (durações viram múltiplos de 1/fps)."""
    for c in clips:
        c.a_in, c.a_out = snap(c.a_in, fps), snap(c.a_out, fps)
        c.v_in, c.v_out = snap(c.v_in, fps), snap(c.v_out, fps)


def layout_times(clips: list[Clip], fps: Fraction) -> float:
    """Calcula out_start de cada clipe; retorna a duração total."""
    t = 0.0
    for c in clips:
        t += c.freeze_frames / float(fps)
        c.out_start = t
        t += c.dur
    return t


def src_to_out(clips: list[Clip], src: int, t: float) -> float | None:
    """Converte um tempo da fonte (áudio) para o tempo de saída; None se foi cortado."""
    for c in clips:
        if c.src == src and c.a_in - 1e-4 <= t < c.a_out:
            return c.out_start + (t - c.a_in)
    return None


def map_words(clips: list[Clip], words: list[dict], src: int = 0) -> list[dict]:
    """Palavras com tempos de saída (descarta as que caíram em trechos cortados)."""
    out = []
    for w in words:
        s = src_to_out(clips, src, w["s"])
        if s is None:
            mid = src_to_out(clips, src, (w["s"] + w["e"]) / 2)
            if mid is None:
                continue
            s = mid - (w["e"] - w["s"]) / 2
        e = src_to_out(clips, src, w["e"] - 1e-3)
        if e is None or e < s:
            e = s + (w["e"] - w["s"])
        nw = dict(w)
        nw["s"], nw["e"] = round(s, 3), round(e, 3)
        out.append(nw)
    return out
