"""Transcrição com timestamp por palavra.

Motores:
  parakeet       — NVIDIA Parakeet TDT 0.6B v3 (multilíngue, inclui PT) via sherpa-onnx.
                   Offline, rápido em CPU, pontuação e capitalização nativas.
  faster_whisper — Whisper (CTranslate2). Requer baixar o modelo do HuggingFace.
  auto           — usa faster_whisper se o modelo estiver em cache/baixável, senão parakeet.

Saída: lista de palavras [{"w": str, "s": float, "e": float}] em tempo da fonte.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .utils import ROOT, lin_to_db, log

SR = 16000


def _split_points(audio: np.ndarray, max_s: float) -> list[tuple[int, int]]:
    """Fatia o áudio em blocos <= max_s cortando no ponto mais silencioso perto do limite."""
    win = int(0.02 * SR)
    n = len(audio) // win
    rms = lin_to_db(np.sqrt(np.mean(audio[: n * win].reshape(n, win) ** 2, axis=1)))
    chunks, start = [], 0
    max_n = int(max_s * SR)
    while start < len(audio):
        if len(audio) - start <= max_n:
            chunks.append((start, len(audio)))
            break
        lo = (start + int(max_n * 0.6)) // win
        hi = (start + max_n) // win
        cut = (lo + int(np.argmin(rms[lo:hi]))) * win
        chunks.append((start, cut))
        start = cut
    return chunks


class ParakeetEngine:
    def __init__(self, model_dir: Path, threads: int = 4):
        import sherpa_onnx
        d = Path(model_dir)
        if not d.is_absolute():
            d = ROOT / d
        if not (d / "tokens.txt").exists():
            raise FileNotFoundError(f"Modelo Parakeet não encontrado em {d} (rode setup.sh)")
        self.rec = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(d / "encoder.int8.onnx"), decoder=str(d / "decoder.int8.onnx"),
            joiner=str(d / "joiner.int8.onnx"), tokens=str(d / "tokens.txt"),
            model_type="nemo_transducer", num_threads=threads)

    def transcribe(self, audio: np.ndarray, max_s: float, max_word: float) -> list[dict]:
        words: list[dict] = []
        for a, b in _split_points(audio, max_s):
            st = self.rec.create_stream()
            st.accept_waveform(SR, audio[a:b])
            self.rec.decode_stream(st)
            r = st.result
            off = a / SR
            durs = list(getattr(r, "durations", []) or [])
            # Tokens BPE: um token que começa com espaço inicia uma palavra nova
            cur = None
            for k, (tok, ts) in enumerate(zip(r.tokens, r.timestamps)):
                tend = ts + (durs[k] if k < len(durs) and durs[k] > 0 else 0.08)
                if cur is not None and not any(ch.isalnum() for ch in tok):
                    # pontuação é emitida atrasada (dentro da pausa): anexa o texto sem estender o fim
                    cur["w"] += tok.strip()
                    continue
                if tok.startswith(" ") or cur is None:
                    if cur:
                        words.append(cur)
                    cur = {"w": tok.strip(), "s": off + ts, "e": off + tend}
                else:
                    cur["w"] += tok
                    cur["e"] = off + tend
            if cur:
                words.append(cur)
        return _fix_ends(words, max_word)


class FasterWhisperEngine:
    def __init__(self, model: str, compute: str, threads: int = 4):
        from faster_whisper import WhisperModel
        self.m = WhisperModel(model, device="cpu", compute_type=compute, cpu_threads=threads)

    def transcribe(self, audio: np.ndarray, max_s: float, max_word: float, lang="pt") -> list[dict]:
        segs, _ = self.m.transcribe(audio, language=lang, word_timestamps=True, vad_filter=False)
        words = [{"w": w.word.strip(), "s": float(w.start), "e": float(w.end)}
                 for s in segs for w in (s.words or [])]
        return _fix_ends(words, max_word)


def _fix_ends(words: list[dict], max_word: float) -> list[dict]:
    """Garante fim > início, sem sobreposição e duração máxima por palavra."""
    words = [w for w in words if w["w"]]
    for i, w in enumerate(words):
        nxt = words[i + 1]["s"] if i + 1 < len(words) else w["e"] + 1
        w["e"] = min(max(w["e"], w["s"] + 0.05), w["s"] + max_word, max(nxt, w["s"] + 0.05))
        w["s"], w["e"] = round(w["s"], 3), round(w["e"], 3)
    return words


def get_engine(cfg: dict, threads: int):
    motor = cfg["motor"]
    if motor in ("auto", "faster_whisper"):
        try:
            eng = FasterWhisperEngine(cfg["faster_whisper_modelo"], cfg["faster_whisper_compute"], threads)
            log.info("  motor: faster-whisper (%s)", cfg["faster_whisper_modelo"])
            return eng
        except Exception as e:  # sem rede para o HuggingFace, por ex.
            if motor == "faster_whisper":
                raise
            log.info("  faster-whisper indisponível (%s) → usando Parakeet", type(e).__name__)
    log.info("  motor: Parakeet TDT v3 (sherpa-onnx)")
    return ParakeetEngine(cfg["parakeet_dir"], threads)


def transcribe(audio16k: np.ndarray, cfg: dict, threads: int = 4) -> list[dict]:
    eng = get_engine(cfg, threads)
    return eng.transcribe(audio16k, cfg["bloco_max_s"], cfg["duracao_palavra_max_s"])


def apply_corrections(words: list[dict], corr: dict) -> list[dict]:
    """Aplica o glossário (sem diferenciar maiúsculas; preserva pontuação e capitalização)."""
    if not corr:
        return words
    low = {str(k).lower(): str(v) for k, v in corr.items()}
    for w in words:
        core = w["w"].strip(".,!?;:…")
        rep = low.get(core.lower())
        if rep:
            if core[:1].isupper():
                rep = rep[:1].upper() + rep[1:]
            w["w"] = w["w"].replace(core, rep, 1)
    return words


def to_srt(words: list[dict], path: Path, per_line: int = 7) -> None:
    """Exporta SRT simples (útil para revisão / upload nas plataformas)."""
    import srt
    from datetime import timedelta
    subs = []
    for i in range(0, len(words), per_line):
        g = words[i:i + per_line]
        subs.append(srt.Subtitle(len(subs) + 1, timedelta(seconds=g[0]["s"]),
                                 timedelta(seconds=g[-1]["e"]), " ".join(w["w"] for w in g)))
    path.write_text(srt.compose(subs), encoding="utf-8")
