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
    for f in sorted(base.glob("*/*")):
        if f.suffix.lower() in (".wav", ".mp3", ".ogg", ".flac"):
            bank.setdefault(f.parent.name, []).append((f.name, load_audio(f, sr, mono=False)))
    return bank


def plan(clips, decisions: list[dict], words_out: list[dict], frases_out: list[dict], duration: float,
         cfg: dict, sr: int) -> list[dict]:
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
        for w in words_out:
            f = frases_out[w["sent"]] if "sent" in w and w["sent"] < len(frases_out) else None
            if w.get("kw", 0) >= sc["impacto"]["score_min"] and f and f.get("impacto", 0) >= 0.7:
                cand.append((w["s"] - 0.02, sc["impacto"]["categoria"], f"palavra-chave '{w['w']}'", 1))
    # --- atenção / humor
    for cat in ("atencao", "humor"):
        if sc[cat]["ativo"]:
            for f in frases_out:
                if f.get("s") is not None and f.get("gatilhos", {}).get(cat):
                    cand.append((f["s"] - 0.05, sc[cat]["categoria"], f"gatilho '{f['gatilhos'][cat][0]}'", 1))
    # --- seleção respeitando intervalo e densidade (prioridade maior primeiro)
    cand.sort(key=lambda x: (-x[3], x[0]))
    chosen: list[tuple] = []
    for c in cand:
        if c[0] < 0.3 or c[0] > duration - 0.3:
            continue
        if any(abs(c[0] - o[0]) < sc["intervalo_min_s"] for o in chosen):
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
