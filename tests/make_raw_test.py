"""Cria um vídeo "bruto" de teste a partir de um vídeo já editado.

Os vídeos de referência já vêm sem pausas. Para testar o corte de silêncios, este script
insere pausas artificiais (0.5–1.8 s, com ruído de sala a -55 dB e o quadro congelado
com leve movimento) entre frases — simulando a gravação crua de um talking-head.

Uso: python tests/make_raw_test.py entrada.mp4 saida.mp4 [--max-s 40]
"""
import argparse
import random
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from editor.config import load_config  # noqa: E402
from editor.transcribe import transcribe  # noqa: E402
from editor.utils import load_audio, probe  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entrada")
    ap.add_argument("saida")
    ap.add_argument("--max-s", type=float, default=40)
    a = ap.parse_args()
    src = Path(a.entrada)
    meta = probe(src)
    cfg = load_config()
    cfg["transcricao"]["motor"] = "parakeet"
    words = transcribe(load_audio(src, 16000), cfg["transcricao"])
    # pontos de inserção: fim de palavras com pontuação ou vírgula
    pts = [w["e"] for w in words if w["w"][-1:] in ".,!?" and w["e"] < a.max_s - 1]
    random.seed(3)
    tmp = Path(tempfile.mkdtemp())
    parts, t = [], 0.0
    fps = meta["fps_float"]
    for k, p in enumerate(pts + [a.max_s]):
        p = min(p + 0.04, meta["duracao"])
        seg = tmp / f"s{k:03d}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(src), "-t", f"{p - t:.3f}",
                        "-vf", f"fps={fps},scale={meta['largura']}:{meta['altura']}", "-af", "aresample=48000",
                        "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-c:a", "pcm_s16le", "-ac", "2",
                        seg.with_suffix(".mkv")], check=True)
        parts.append(seg.with_suffix(".mkv"))
        if p >= a.max_s:
            break
        dur = random.choice([0.25, 0.6, 0.8, 1.1, 1.5, 1.8])
        gap = tmp / f"g{k:03d}.mkv"
        # quadro final com leve zoom lento (simula orador parado/respirando) + room tone
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0, p - 0.05):.3f}", "-i", str(src),
                        "-f", "lavfi", "-i", f"anoisesrc=color=pink:amplitude=0.002:r=48000:d={dur}",
                        "-filter_complex", f"[0:v]trim=end_frame=1,tpad=stop_mode=clone:stop_duration={dur},"
                        f"fps={fps},scale={meta['largura']}:{meta['altura']}[v]",
                        "-map", "[v]", "-map", "1:a", "-t", f"{dur}", "-c:v", "libx264", "-crf", "16",
                        "-preset", "veryfast", "-c:a", "pcm_s16le", "-ac", "2", str(gap)], check=True)
        parts.append(gap)
        t = p
    lst = tmp / "l.txt"
    lst.write_text("".join(f"file '{x}'\n" for x in parts))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-c:a", "aac", "-b:a", "192k",
                    a.saida], check=True)
    print("ok", a.saida, probe(Path(a.saida))["duracao"])


if __name__ == "__main__":
    main()
