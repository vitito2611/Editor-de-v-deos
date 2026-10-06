"""Relatório de cada execução: o que foi feito, onde e por quê.

Gera em output/:
  <nome>_relatorio.md    resumo legível (tabelas de cortes, técnicas, cor, áudio, SFX, trilha)
  <nome>_relatorio.json  tudo em formato estruturado
  <nome>_contato.jpg     contact sheet do vídeo final (1 frame a cada 2 s)
  <nome>_histograma.png  histogramas de cor antes/depois
  <nome>_silencio.png    gráfico de energia com os cortes de silêncio
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np

from .utils import ffmpeg, log, write_json


def _frame(path: Path, t: float, width: int = 320) -> np.ndarray | None:
    p = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
                        "-vf", f"scale={width}:-2", "-pix_fmt", "bgr24", "-f", "rawvideo", "-"], capture_output=True)
    if not p.stdout:
        return None
    pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                         "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    w, h = map(int, pr.stdout.strip().split(","))
    hh = int(round(h * width / w / 2) * 2)
    return np.frombuffer(p.stdout, np.uint8)[: width * hh * 3].reshape(hh, width, 3)


def write_report(rep: dict, src: Path, clips, out: Path, work: Path, cfg: dict, frames) -> Path:
    from . import color
    base = out.with_suffix("")
    # --- contact sheet
    try:
        ffmpeg("-i", str(out), "-vf", "fps=1/2,scale=240:-2,tile=8x6", "-frames:v", "1", "-q:v", "3", f"{base}_contato.jpg")
    except RuntimeError:
        pass
    # --- histogramas antes/depois (conteúdo sem barras)
    try:
        pairs = []
        idx = np.linspace(0, len(clips) - 1, min(6, len(clips))).astype(int)
        for i in idx:
            c = clips[i]
            a = frames.at((c.v_in + c.v_out) / 2)
            b = _frame(out, c.out_start + c.dur / 2)
            if b is not None:
                # recorta só a área de conteúdo (sem tarjas) para comparar com a fonte
                cx, cy, cw, ch, W, H = rep["cor"]["conteudo"]
                k = b.shape[1] / W
                b = b[int(cy * k):int((cy + ch) * k), int(cx * k):int((cx + cw) * k)]
                pairs.append((a, b))
        if pairs:
            rep["cor"]["histograma"] = color.histogram_report(pairs, Path(f"{base}_histograma.png"))
    except Exception as e:  # relatório nunca derruba o pipeline
        log.warning("histograma: %s", e)
    if (work / "silencio.png").exists():
        shutil.copy(work / "silencio.png", f"{base}_silencio.png")
    write_json(Path(f"{base}_relatorio.json"), rep)
    # --- markdown
    an = rep["analise"]
    m = an["meta"]
    L = [f"# Relatório de edição — {Path(rep['entrada'][0]).name}", "",
         f"Estilo **{rep['estilo']}** · plataforma **{rep['plataforma']}**" + (" · PREVIEW" if rep["preview"] else ""), "",
         "## Entrada → saída", "",
         "| | entrada | saída |", "|---|---|---|",
         f"| duração | {m['duracao']:.1f}s | {rep['saida']['duracao']:.1f}s |",
         f"| resolução | {m['largura']}x{m['altura']} @ {m['fps_float']:.2f} | {rep['saida']['resolucao']} |",
         f"| loudness | {an.get('loudness', {}).get('lufs')} LUFS | {rep['saida']['lufs']} LUFS (TP {rep['saida']['true_peak']}) |", "",
         "## Corte de silêncios", "",
         f"Limiar efetivo {rep['silencio']['limiar_db']:.1f} dB, fonte VAD `{rep['silencio'].get('fonte')}`.", "",
         "| início | dur | ação | antes → depois | motivos |", "|---|---|---|---|---|"]
    for g in rep["silencio"]["pausas"]:
        L.append(f"| {g['s']:.2f} | {g['dur']:.2f} | {g['acao']} | {g['antes']} → {g['depois']} | {'; '.join(g['motivos'])} |")
    L += ["", "## Técnicas de corte", "", "| t (saída) | técnica | aplicada | motivo |", "|---|---|---|---|"]
    for d in rep["tecnicas"]["decisoes"]:
        L.append(f"| {d['t_saida']:.2f} | {d['tecnica']} | {'✅' if d['aplicar'] else '—'} | {d['motivo']} |")
    L += ["", "## Cor", "", f"Layout `{rep['cor']['layout']}`, look `{rep['cor']['look']}`.", ""]
    for k, v in rep["cor"]["primaria"].items():
        L.append(f"- plano {k}: luma {v.get('luma_antes')} → alvo {v.get('luma_alvo')}; ajustes {v['ajustes']}")
    if "histograma" in rep["cor"]:
        h = rep["cor"]["histograma"]
        L.append(f"- média antes {h['antes']} / depois {h['depois']}")
    L += ["", "## Áudio", "", f"- cadeia de limpeza: `{' → '.join(c.split('=')[0] for c in rep['audio_limpeza']['cadeia_ffmpeg'])}`",
          f"- master: {rep['audio_master']}"]
    if "musica" in rep:
        L.append(f"- trilha ({rep['musica']['humor']}): " + ", ".join(
            f"{Path(s['faixa']).name} [{s['ini']:.0f}-{s['fim']:.0f}s]" for s in rep["musica"]["trechos"]))
    L += ["", "## Efeitos sonoros", "", "| t | categoria | arquivo | motivo |", "|---|---|---|---|"]
    for e in rep["sfx"]:
        L.append(f"| {e['t']:.2f} | {e['categoria']} | {e['arquivo']} | {e['motivo']} |")
    L += ["", "## Legendas e motion", ""]
    est = {}
    for r in rep["legendas"]:
        est[r["estilo"]] = est.get(r["estilo"], 0) + 1
    L.append(f"- {len(rep['legendas'])} blocos; estilos: {est}")
    for mo in rep["motion"]:
        L.append(f"- {mo['tipo']} em {mo['t']}s: {mo['texto']}")
    for b in rep.get("broll", []):
        L.append(f"- B-roll em {b['t']}s: {Path(b['arquivo']).name}")
    L += ["", "## Tempo por etapa", "", "| etapa | s |", "|---|---|"]
    L += [f"| {n} | {t:.1f} |" for n, t in rep["tempos"]]
    md = Path(f"{base}_relatorio.md")
    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    log.info("  relatório: %s", md)
    return md
