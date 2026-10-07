"""ETAPA 8 — Efeitos sonoros estratégicos.

Momentos detectados (tudo em tempo de saída):
  transição  → whoosh/swipe nos cortes marcados (smash, troca de tópico, reset de zoom,
               transições visuais). O pico do whoosh cai exatamente no corte.
  impacto    → punch/hit/boom em palavras-chave de alto score e smash cuts
  atenção    → ding/notificação no início de frases com gatilhos ("primeiro", "dica"...)
  humor      → boing/queda após gatilhos de humor (opcional)
  ambiente   → room tone contínuo por baixo (opcional, cobre "buracos" digitais)
Regras: intervalo mínimo entre SFX, máximo por minuto, volume relativo à voz com variação.
"""
from __future__ import annotations

import random

import numpy as np

from .utils import ROOT, load_audio, log


def load_bank(cfg: dict, sr: int) -> dict[str, list[tuple[str, np.ndarray]]]:
    base = ROOT / cfg["sfx"]["pasta"]
    bank: dict[str, list] = {}
    # efeitos vetados pelo cliente (nome do arquivo ou trecho dele) nunca entram no banco
    proibidos = [str(p).lower() for p in cfg["sfx"].get("proibidos") or []]
    files = [f for f in sorted(base.glob("*/*")) if f.suffix.lower() in (".wav", ".mp3", ".ogg", ".flac")
             and not any(p in f.name.lower() for p in proibidos)]
    for cat in {f.parent.name for f in files}:
        cf = [f for f in files if f.parent.name == cat]
        reais = [f for f in cf if not f.name.endswith(".wav") or f.name.startswith("mx_")]
        # efeitos reais (ex.: Mixkit) têm prioridade; os sintetizados só entram se não houver
        for f in (reais or cf):
            bank.setdefault(cat, []).append((f.name, _prep(load_audio(f, sr, mono=False), cat, sr)))
    return bank


# duração máxima útil por categoria (efeitos de banco costumam ter caudas longas)
MAX_S = {"transicao": 1.4, "impacto": 2.2, "atencao": 0.9, "humor": 1.6, "glitch": 0.9, "riser": 2.4, "ambiente": 600}


def _prep(a: np.ndarray, cat: str, sr: int) -> np.ndarray:
    """Remove silêncio inicial, corta no tamanho da categoria com fade e normaliza o pico."""
    env = np.abs(a).max(axis=1) if a.ndim == 2 else np.abs(a)
    nz = np.where(env > 0.01)[0]
    if len(nz):
        a = a[max(0, nz[0] - int(0.005 * sr)):]
    if cat == "riser":            # riser: usa o FINAL (a subida até o pico)
        pk = int(np.argmax(np.convolve(np.abs(a).mean(-1) if a.ndim == 2 else np.abs(a), np.ones(1024) / 1024, "same")))
        a = a[max(0, pk - int(MAX_S[cat] * sr)):pk + int(0.15 * sr)]
    n = int(MAX_S.get(cat, 2.0) * sr)
    if len(a) > n:
        a = a[:n].copy()
        f = int(0.15 * sr)
        a[-f:] *= np.linspace(1, 0, f)[:, None] if a.ndim == 2 else np.linspace(1, 0, f)
    pk = np.max(np.abs(a)) or 1
    return (a / pk * 0.89).astype(np.float32)


def plan(clips, decisions: list[dict], words_out: list[dict], frases_out: list[dict], duration: float,
         cfg: dict, sr: int, extras: list[tuple] | None = None) -> list[dict]:
    sc = cfg["sfx"]
    if not sc["ativo"]:
        return []
    bank = load_bank(cfg, sr)
    rnd = random.Random(11)
    cand: list[tuple[float, str, str, float]] = []   # (tempo, categoria, motivo, prioridade)
    # --- transições nos cortes marcados
    if sc["transicao"]["ativo"]:
        for k, c in enumerate(clips[1:], 1):
            # match cut é para ser invisível: nunca recebe whoosh
            hit = [t for t in c.tags if t in ("smash_cut", "zoom_reset", "whip", "flash")]
            topic = any(d["limite"] == k - 1 and d["tecnica"] == "jump_zoom" and d["params"].get("reset") and d["aplicar"]
                        for d in decisions)
            if hit or topic:
                cand.append((c.out_start, sc["transicao"]["categoria"], f"corte ({', '.join(hit) or 'tópico'})", 2))
    # --- impacto: smash cuts e palavras-chave fortes
    if sc["impacto"]["ativo"]:
        for c in clips:
            if "smash_cut" in c.tags:
                cand.append((c.out_start, sc["impacto"]["categoria"], "smash cut", 3))
        for w in (words_out if sc["impacto"].get("palavras", True) else []):
            f = frases_out[w["sent"]] if "sent" in w and w["sent"] < len(frases_out) else None
            if w.get("kw", 0) >= sc["impacto"]["score_min"] and f and f.get("impacto", 0) >= 0.7:
                cand.append((w["s"] - 0.02, sc["impacto"]["categoria"], f"palavra-chave '{w['w']}'", 1))
    # --- atenção / humor
    for cat in ("atencao", "humor"):
        if sc[cat]["ativo"]:
            for f in frases_out:
                if f.get("s") is not None and f.get("gatilhos", {}).get(cat):
                    cand.append((f["s"] - 0.05, sc[cat]["categoria"], f"gatilho '{f['gatilhos'][cat][0]}'", 1))
    # --- riser antes de smash cut e glitch sonoro junto do glitch visual
    for c in clips:
        if "smash_cut" in c.tags and bank.get("riser") and sc.get("riser", {}).get("ativo", True):
            cand.append((c.out_start, "riser", "subida antes do smash cut", 2.8))
        if "glitch" in c.tags and bank.get("glitch"):
            cand.append((c.out_start + 0.01, "glitch", "glitch visual", 2.7))
    # --- eventos externos (sobreposições de B-roll/foto/card, punch-ins): (t, categoria, motivo, prio)
    cand += list(extras or [])
    # --- seleção respeitando intervalo e densidade (prioridade maior primeiro)
    cand.sort(key=lambda x: (-x[3], x[0]))
    chosen: list[tuple] = []
    for c in cand:
        if c[0] < 0.3 or c[0] > duration - 0.3:
            continue
        # riser e glitch acompanham o impacto no mesmo corte: não contam no espaçamento
        camada = ("riser", "glitch")
        if any(abs(c[0] - o[0]) < sc["intervalo_min_s"] and (c[1] in camada) == (o[1] in camada) for o in chosen):
            continue
        minute = [o for o in chosen if abs(o[0] - c[0]) < 30]
        if len(minute) >= sc["max_por_minuto"]:
            continue
        chosen.append(c)
    chosen.sort()
    events, last_file = [], {}
    for t, cat, why, _ in chosen:
        opts = bank.get(cat) or []
        if not opts:
            continue
        pool = [o for o in opts if o[0] != last_file.get(cat)] or opts
        if cat == "transicao":
            pool = [o for o in pool if not o[0].startswith("riser")] or pool
        name, audio = rnd.choice(pool)
        last_file[cat] = name
        start = t
        if cat == "transicao":     # alinha o pico de energia do whoosh com o corte
            env = np.abs(audio.mean(1))
            pk = int(np.argmax(np.convolve(env, np.ones(512) / 512, "same")))
            start = t - pk / sr
        elif cat == "riser":       # o riser TERMINA no corte
            start = t - len(audio) / sr + 0.1
        gain = sc["volume_rel_voz_db"] + rnd.uniform(-sc["variacao_volume_db"], sc["variacao_volume_db"])
        if cat == "impacto" and "palavra" in why:
            gain -= 4   # impactos em palavras são mais discretos que no smash cut
        events.append({"t": round(start, 3), "categoria": cat, "arquivo": name, "motivo": why,
                       "ganho_db": round(gain, 1), "audio": audio})
    if sc["ambiente"]["ativo"] and bank.get(sc["ambiente"]["categoria"]):
        name, a = bank[sc["ambiente"]["categoria"]][0]
        reps = int(np.ceil(duration * sr / len(a)))
        events.append({"t": 0.0, "categoria": "ambiente", "arquivo": name, "motivo": "room tone",
                       "ganho_db": sc["ambiente"]["volume_db"], "audio": np.concatenate([a] * reps)[: int(duration * sr)]})
    log.info("  %d efeitos sonoros: %s", len(events),
             {c: sum(e["categoria"] == c for e in events) for c in {e["categoria"] for e in events}})
    return events
