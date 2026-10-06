"""ETAPA 3 — Corte inteligente de silêncios com interpretação de contexto.

1. Detecção: RMS por janela na banda da voz + lacunas entre palavras do ASR.
2. Contexto — uma pausa é PRESERVADA (encurtada para `pausa_preservada_s`) quando:
   • pausa_antes_importante: energia sobe depois dela, ou a próxima fala traz número/revelação
   • continuidade_visual: o orador está se movendo/gesticulando durante a pausa
   • efeito_dramatico: vem logo após "então...", "mas...", "e aí..." (lista no YAML)
   • transicao_topico: separa frases de tópicos diferentes
3. Saída: lista de pausas com ação + motivos (revisao/cortes_silencio.yaml, editável),
   segmentos mantidos, gráfico de forma de onda e preview rápido opcional.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml
from scipy import signal

from .utils import ffmpeg, lin_to_db, log

SR = 16000


def rms_db(audio: np.ndarray, sr: int, win_ms: float, band: tuple[float, float]) -> np.ndarray:
    b, a = signal.butter(4, [band[0] / (sr / 2), min(band[1] / (sr / 2), 0.99)], "band")
    x = signal.lfilter(b, a, audio)
    win = int(sr * win_ms / 1000)
    n = len(x) // win
    return lin_to_db(np.sqrt(np.mean(x[: n * win].reshape(n, win) ** 2, axis=1) + 1e-12))


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    d = np.diff(np.concatenate([[0], mask.astype(int), [0]]))
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))


def detect(audio16k: np.ndarray, words: list[dict], frases: list[dict], dur: float,
           cfg: dict, frames=None) -> dict:
    sc = cfg["silencio"]
    ctx = sc["contexto"]
    hop = sc["janela_ms"] / 1000
    db = rms_db(audio16k, SR, sc["janela_ms"], tuple(sc["banda_voz_hz"]))
    thr = sc["limiar_db"]
    floor = float(np.percentile(db, 10))
    if sc["limiar_adaptativo"]:
        thr = min(max(thr, floor + sc["margem_sobre_ruido_db"]), float(np.percentile(db, 90)) - 6)
    energy_sil = db < thr
    n = len(db)
    t_of = lambda k: k * hop  # noqa: E731
    k_of = lambda t: int(np.clip(t / hop, 0, n))  # noqa: E731

    # Máscara de fala segundo o ASR
    asr_sil = np.ones(n, bool)
    for w in words:
        asr_sil[k_of(w["s"]):k_of(w["e"]) + 1] = False

    fonte = sc["fonte_vad"]
    if fonte == "hibrido" and words:
        gaps_mask = asr_sil.copy()
        frac = energy_sil[gaps_mask].mean() if gaps_mask.any() else 0
        if frac < 0.25:
            log.info("  energia não confiável nas pausas (%.0f%% silenciosas — música/ruído de fundo?) "
                     "→ usando só a transcrição", frac * 100)
            fonte = "transcricao"
    if fonte == "energia" or not words:
        mask = energy_sil
    elif fonte == "transcricao":
        mask = asr_sil
    else:
        # híbrido: a energia define as bordas; o ASR só veta trechos onde há palavra
        # "de verdade" (miolo da palavra, ignorando 0.12 s nas bordas, onde o ASR é impreciso)
        core = np.ones(n, bool)
        for w in words:
            a_, b_ = k_of(w["s"] + 0.12), k_of(w["e"] - 0.12)
            if b_ > a_:
                core[a_:b_] = False
        mask = energy_sil.copy()
        for a_, b_ in _runs(energy_sil):
            if (~core[a_:b_]).mean() > 0.3:
                mask[a_:b_] = False
    log.info("  limiar efetivo %.1f dB (piso %.1f dB), fonte VAD=%s", thr, floor, fonte)

    speech_ref = float(np.median([np.percentile(db[k_of(w["s"]):k_of(w["e"]) + 1], 80)
                                  for w in words if k_of(w["e"]) > k_of(w["s"])] or [thr + 20]))
    gaps = []
    for a, b in _runs(mask):
        s, e = t_of(a), min(dur, t_of(b))
        if e - s < sc["duracao_minima_s"]:
            continue
        # timestamps do ASR são imprecisos nas bordas: a palavra anterior é a última que
        # COMEÇA antes da pausa; a próxima é a seguinte a ela
        prev_w = next((w for w in reversed(words) if w["s"] < s - 0.04), None)
        next_w = words[prev_w["i"] + 1] if prev_w and prev_w["i"] + 1 < len(words) else \
            (words[0] if prev_w is None and words and words[0]["s"] >= s else None)
        g = {"id": len(gaps), "s": round(s, 3), "e": round(e, 3), "dur": round(e - s, 3),
             "antes": prev_w["w"] if prev_w else None, "depois": next_w["w"] if next_w else None,
             "acao": "cortar", "motivos": []}
        borda = prev_w is None or next_w is None
        if not borda:
            # --- pausa antes de informação importante
            if ctx["pausa_antes_importante"]["ativo"]:
                # fala logo após a pausa mais alta que o nível típico de fala = ênfase
                post = db[b:b + int(0.6 / hop)]
                if len(post) and np.percentile(post, 80) - speech_ref >= ctx["pausa_antes_importante"]["aumento_energia_db"]:
                    g["motivos"].append("ênfase (energia sobe) após a pausa")
                nf = frases[next_w["sent"]] if "sent" in next_w else None
                if next_w.get("num"):
                    g["motivos"].append(f"número a seguir ({next_w['w']})")
                if nf and nf["w0"] == next_w["i"] and (nf.get("gatilhos", {}).get("revelacao") or nf["impacto"] >= 0.85):
                    g["motivos"].append("frase de revelação/impacto a seguir")
            # --- efeito dramático
            if ctx["efeito_dramatico"]["ativo"]:
                # compara palavra a palavra (evita "e" casar com o fim de "teste")
                last = [x["w"].lower().strip(".,!?;: ") for x in words[max(0, prev_w["i"] - 2):prev_w["i"] + 1]]
                for p in ctx["efeito_dramatico"]["palavras"]:
                    pt = p.lower().split()
                    if last[-len(pt):] == pt or prev_w["w"].endswith("..."):
                        g["motivos"].append(f"suspense após '{p}'")
                        break
            # --- transição de tópico
            if ctx["transicao_topico"]["ativo"] and "sent" in next_w and frases[next_w["sent"]].get("novo_topico") \
                    and frases[next_w["sent"]]["w0"] == next_w["i"]:
                g["motivos"].append("transição de tópico")
            # --- continuidade visual
            if ctx["continuidade_visual"]["ativo"] and frames is not None:
                from .vision import motion_score
                m = motion_score(frames, s, e)
                g["movimento"] = round(m, 2)
                if m >= ctx["continuidade_visual"]["limiar_movimento"]:
                    g["motivos"].append(f"orador em movimento ({m:.1f})")
        else:
            g["motivos"].append("início/fim do vídeo")
        if g["motivos"] and not borda:
            g["acao"] = "preservar" if g["dur"] <= sc["pausa_preservada_s"] + 0.05 else "encurtar"
        gaps.append(g)
    keeps = keeps_from_gaps(gaps, dur, sc)
    cut = sum(g["dur"] for g in gaps if g["acao"] == "cortar")
    log.info("  %d pausas ≥%.2fs: %d cortadas, %d encurtadas, %d preservadas — removidos %.1fs de %.1fs",
             len(gaps), sc["duracao_minima_s"], sum(g["acao"] == "cortar" for g in gaps),
             sum(g["acao"] == "encurtar" for g in gaps), sum(g["acao"] == "preservar" for g in gaps),
             dur - sum(k[1] - k[0] for k in keeps), dur)
    return {"limiar_db": thr, "fonte": fonte, "pausas": gaps, "manter": keeps,
            "rms_db": db.tolist(), "hop": hop}


def keeps_from_gaps(gaps: list[dict], dur: float, sc: dict) -> list[list[float]]:
    """Converte as ações das pausas em segmentos mantidos [ini, fim] (tempo da fonte)."""
    removes = []
    for g in gaps:
        if g["acao"] == "preservar":
            continue
        s, e = g["s"], g["e"]
        if g["acao"] == "encurtar":
            keep = sc["pausa_preservada_s"]
            mid = s + sc["folga_depois_s"] + keep
            if mid < e - sc["folga_antes_s"]:
                removes.append((mid, e - sc["folga_antes_s"]))
            continue
        a = s + (sc["folga_depois_s"] if s > 0.01 else 0)
        b = e - (sc["folga_antes_s"] if e < dur - 0.01 else 0)
        if b - a > 0.05:
            removes.append((a, b))
    keeps, t = [], 0.0
    for a, b in sorted(removes):
        if a > t + 0.04:
            keeps.append([round(t, 3), round(a, 3)])
        t = max(t, b)
    if dur - t > 0.04:
        keeps.append([round(t, 3), round(dur, 3)])
    return keeps


def write_review(res: dict, path: Path) -> None:
    """YAML editável: troque `acao` para cortar | encurtar | preservar e rode com --usar-revisao."""
    head = ("# Revisão dos cortes de silêncio.\n# Edite 'acao' (cortar | encurtar | preservar) e rode novamente com"
            " --usar-revisao.\n")
    items = [{k: g[k] for k in ("id", "s", "e", "dur", "antes", "depois", "acao", "motivos")} for g in res["pausas"]]
    path.write_text(head + yaml.safe_dump({"limiar_db": round(float(res["limiar_db"]), 2), "pausas": items},
                                          allow_unicode=True, sort_keys=False), encoding="utf-8")


def load_review(path: Path, res: dict, dur: float, sc: dict) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    by_id = {p["id"]: p for p in data["pausas"]}
    for g in res["pausas"]:
        if g["id"] in by_id:
            g["acao"] = by_id[g["id"]]["acao"]
    res["manter"] = keeps_from_gaps(res["pausas"], dur, sc)
    log.info("  revisão manual aplicada (%s)", path.name)
    return res


def plot(res: dict, words: list[dict], out: Path, dur: float) -> None:
    """Gráfico: energia RMS, limiar, palavras e trechos cortados/preservados."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    db = np.array(res["rms_db"])
    t = np.arange(len(db)) * res["hop"]
    fig, ax = plt.subplots(figsize=(16, 3.6), dpi=110)
    ax.plot(t, db, lw=0.6, color="#555")
    ax.axhline(res["limiar_db"], color="#d33", lw=0.8, ls="--", label="limiar")
    for w in words:
        ax.axvspan(w["s"], w["e"], ymin=0.96, ymax=1, color="#2a7", lw=0)
    colors = {"cortar": "#e44", "encurtar": "#f90", "preservar": "#39f"}
    for g in res["pausas"]:
        ax.axvspan(g["s"], g["e"], color=colors[g["acao"]], alpha=0.25, lw=0)
    for k, c in colors.items():
        ax.plot([], [], color=c, lw=6, alpha=0.4, label=k)
    ax.set_xlim(0, dur)
    ax.set_ylim(max(-90, db.min()), db.max() + 3)
    ax.set_xlabel("tempo (s)")
    ax.set_ylabel("RMS (dB)")
    ax.legend(loc="lower right", ncol=4, fontsize=8)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def preview(src: Path, keeps: list[list[float]], out: Path, height: int = 480) -> None:
    """Preview rápido (baixa resolução) só com os cortes de silêncio aplicados."""
    expr = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in keeps)
    ffmpeg("-i", str(src), "-vf", f"select='{expr}',setpts=N/FRAME_RATE/TB,scale=-2:{height}",
           "-af", f"aselect='{expr}',asetpts=N/SR/TB", "-c:v", "libx264", "-preset", "ultrafast",
           "-crf", "32", "-c:a", "aac", "-b:a", "96k", str(out))
