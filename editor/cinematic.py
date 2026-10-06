"""ETAPA 4 — Técnicas de corte cinematográfico e viral.

Fluxo:
  build_clips()      segmentos mantidos → clipes (divide nas trocas de plano e em falas longas)
  decide()           analisa cada fronteira entre clipes e gera DECISÕES com motivo
  apply()            aplica as decisões aprovadas aos clipes
  decide_beats()     (depois da trilha escolhida) move cortes para os beats fortes

Cada decisão: {id, tecnica, limite, t_saida, motivo, params, aplicar}
  modo "sugestao": decisões vão para revisao/tecnicas.yaml (aplicar: true/false) e o
  pipeline para; rode de novo com --usar-revisao para aplicar só as aprovadas.

Técnicas (todas liga/desliga no YAML, com intervalo mínimo entre aplicações):
  j_cut        áudio da próxima fala entra antes da imagem (falas tematicamente ligadas)
  l_cut        imagem troca, áudio anterior continua (após pergunta/afirmação forte)
  match_cut    composição parecida entre planos diferentes → alinha o rosto
  smash_cut    corte seco no clímax: salto de enquadramento + corte na trilha + impacto
  jump_zoom    cada jump cut do mesmo plano aproxima 2-3% (ou alterna aberto/fechado)
  beat_cut     corte encaixado no beat forte mais próximo da trilha
  reaction_cut congela 3-6 frames antes de uma revelação/número
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml


def _plain(obj):
    """Converte tipos numpy em tipos Python (para YAML)."""
    import json
    return json.loads(json.dumps(obj, default=float))

from .analysis import shot_id
from .timeline import Clip, layout_times, snap_clips
from .utils import log


# ----------------------------------------------------------------------------- clipes
def build_clips(keeps: list[list[float]], words: list[dict], frases: list[dict], shots: list[float],
                dur: float, cfg: dict, src: int = 0) -> list[Clip]:
    jz = cfg["cortes"]["jump_zoom"]
    max_len = jz.get("dividir_clipes_longos_s", 0) or 0
    clips: list[Clip] = []
    sent_starts = [words[f["w0"]]["s"] for f in frases] if words else []
    for k, (a, b) in enumerate(keeps):
        # pontos de divisão: trocas de plano da fonte + início de frase em falas longas
        cuts = [t for t in shots if a + 0.3 < t < b - 0.3]
        if max_len > 0:
            last = a
            for t in sent_starts:
                if a < t < b and t - last >= max_len and b - t >= 1.5:
                    cuts.append(t - 0.02)
                    last = t
        pts = [a] + sorted(set(round(c, 3) for c in cuts)) + [b]
        for i in range(len(pts) - 1):
            s, e = pts[i], pts[i + 1]
            nxt = keeps[k + 1][0] if (i == len(pts) - 2 and k + 1 < len(keeps)) else (e if i < len(pts) - 2 else dur)
            in_words = [w for w in words if s <= (w["s"] + w["e"]) / 2 < e]
            c = Clip(src=src, a_in=s, a_out=e, shot=shot_id((s + e) / 2, shots),
                     a_out_max=nxt, a_out_min=(in_words[-1]["e"] + 0.03 if in_words else s + 0.2))
            c.tags.append("divisao_plano" if i > 0 and pts[i] in cuts and pts[i] in shots else
                          ("divisao_frase" if i > 0 else "silencio"))
            clips.append(c)
    return clips


def attach_faces(clips: list[Clip], frames) -> None:
    from .vision import face_in_range
    for c in clips:
        c.face = face_in_range(frames, c.v_in, c.v_out, samples=3)
        if c.face:
            c.anchor = (c.face[0], c.face[1])


# ----------------------------------------------------------------------------- helpers
def _words_in(words, a, b):
    # usa o centro da palavra: o início do ASR costuma vir adiantado ~0.1-0.3 s
    return [w for w in words if a <= (w["s"] + w["e"]) / 2 < b]


def _sentence_of(frases, words, w):
    return frases[w["sent"]] if w and "sent" in w else None


def _jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / max(1, len(a | b))


class _Spacer:
    """Respeita o intervalo mínimo entre aplicações de cada técnica."""

    def __init__(self):
        self.last: dict[str, float] = {}

    def ok(self, name: str, t: float, gap: float) -> bool:
        return t - self.last.get(name, -1e9) >= gap

    def mark(self, name: str, t: float):
        self.last[name] = t


# ----------------------------------------------------------------------------- decisões
def decide(clips: list[Clip], words: list[dict], frases: list[dict], cfg: dict, frames=None,
           broll_spans: list[tuple[float, float]] | None = None) -> list[dict]:
    cc = cfg["cortes"]
    trig = cfg["gatilhos"]
    layout_times(clips, 30)
    sp = _Spacer()
    dec: list[dict] = []
    zoom_level, alt = 1.0, False

    def add(tec, k, motivo, **params):
        dec.append({"id": len(dec), "tecnica": tec, "limite": k, "t_fonte": round(clips[k].a_out, 2),
                    "t_saida": round(clips[k + 1].out_start if k + 1 < len(clips) else 0, 2),
                    "motivo": motivo, "params": params, "aplicar": True})

    for k in range(len(clips) - 1):
        A, B = clips[k], clips[k + 1]
        T = B.out_start
        wa = _words_in(words, A.a_in, A.a_out)
        wb = _words_in(words, B.a_in, B.a_out)
        last_w = wa[-1] if wa else None
        first_w = wb[0] if wb else None
        sa = _sentence_of(frases, words, last_w)
        sb = _sentence_of(frases, words, first_w)
        same_shot = A.src == B.src and A.shot == B.shot
        new_sentence = bool(sb and first_w and sb["w0"] == first_w["i"])
        new_topic = bool(new_sentence and sb.get("novo_topico"))
        first_txt = " ".join(w["w"] for w in wb[:4]).lower()

        # ---------------- SMASH CUT (clímax / punch line)
        smash = False
        if cc["smash_cut"]["ativo"] and sb and new_sentence:
            hit = sb.get("gatilhos", {}).get("climax")
            if (hit or sb["impacto"] >= 0.92) and sp.ok("smash", T, cc["smash_cut"]["intervalo_min_s"]):
                smash = True
                sp.mark("smash", T)
                add("smash_cut", k, f"clímax/punch line: \"{sb['texto'][:60]}\"" + (f" (gatilho {hit})" if hit else ""),
                    zoom=cc["smash_cut"]["zoom"], corte_musica_s=cc["smash_cut"]["corte_musica_s"])

        # ---------------- JUMP CUT COM ZOOM
        if cc["jump_zoom"]["ativo"] and not smash:
            if same_shot:
                if cc["jump_zoom"]["resetar_em_topico"] and new_topic:
                    zoom_level, alt = 1.0, False
                    add("jump_zoom", k, "troca de tópico → volta ao plano aberto", zoom=1.0, reset=True)
                elif cc["jump_zoom"]["modo"] == "alternado":
                    alt = not alt
                    zoom_level = cc["jump_zoom"]["zoom_alternado"] if alt else 1.0
                    add("jump_zoom", k, "jump cut no mesmo plano → alterna aberto/fechado", zoom=zoom_level)
                else:
                    zoom_level = round(zoom_level + cc["jump_zoom"]["incremento"], 4)
                    if zoom_level > cc["jump_zoom"]["zoom_max"]:
                        zoom_level = 1.0
                        add("jump_zoom", k, "zoom máximo atingido → reinicia no plano aberto", zoom=1.0, reset=True)
                    else:
                        add("jump_zoom", k, f"jump cut no mesmo plano → zoom progressivo {zoom_level:.3f}", zoom=zoom_level)
            else:
                zoom_level, alt = 1.0, False
        elif smash:
            zoom_level = cc["smash_cut"]["zoom"]

        # ---------------- MATCH CUT (planos diferentes com composição parecida)
        if cc["match_cut"]["ativo"] and not same_shot and frames is not None:
            from .vision import composition_similarity
            # proxy a 4 fps: amostra 0.3 s para dentro de cada plano (senão os dois lados caem no mesmo frame)
            fa = frames.at(max(A.v_in, A.v_out - 0.3))
            fb = frames.at(min(B.v_out, B.v_in + 0.3))
            sim = composition_similarity(fa, fb)
            dist = None
            if A.face and B.face:
                dist = float(np.hypot(A.face[0] - B.face[0], A.face[1] - B.face[1]))
            if sim >= cc["match_cut"]["similaridade_min"] and dist is not None and dist <= cc["match_cut"]["distancia_rosto_max"]:
                add("match_cut", k, f"composição similar entre planos (histograma {sim:.2f}"
                    + (f", rosto Δ{dist:.2f})" if dist is not None else ")"),
                    alinhar=bool(cc["match_cut"]["alinhar_rosto"] and A.face and B.face))

        # ---------------- J-CUT / L-CUT
        def split_safe(opt):
            if not same_shot or opt.get("permitir_mesmo_plano"):
                return True, "planos diferentes" if not same_shot else "permitido no YAML"
            if broll_spans and any(s - 0.3 <= A.a_out <= e + 0.3 for s, e in broll_spans):
                return True, "coberto por B-roll"
            if A.face is None and B.face is None:
                return True, "sem rosto visível"
            return False, "mesmo plano com rosto visível (risco de dessincronia labial)"

        if cc["j_cut"]["ativo"] and sa and sb and new_sentence and sp.ok("j_cut", T, cc["j_cut"]["intervalo_min_s"]):
            sim = _jaccard(sa["lemas"], sb["lemas"])
            con = next((c for c in cc["j_cut"]["conectivos"] if first_txt.startswith(c + " ") or first_txt.startswith(c + ",")), None)
            if sim >= cc["j_cut"]["similaridade_min"] or con:
                ok, why = split_safe(cc["j_cut"])
                d = float(np.clip(0.5 + sim * 2, cc["j_cut"]["overlap_min_s"], cc["j_cut"]["overlap_max_s"]))
                d = min(d, B.dur * 0.4)
                motivo = f"falas ligadas (similaridade {sim:.2f}" + (f", conectivo '{con}'" if con else "") + f"); {why}"
                if ok and d >= cc["j_cut"]["overlap_min_s"] * 0.6:
                    sp.mark("j_cut", T)
                    add("j_cut", k, motivo, overlap=round(d, 3))
                else:
                    dec.append({"id": len(dec), "tecnica": "j_cut", "limite": k, "t_fonte": round(A.a_out, 2), "t_saida": round(T, 2),
                                "motivo": motivo + " → NÃO aplicado", "params": {"overlap": round(d, 3)}, "aplicar": False})
        if cc["l_cut"]["ativo"] and sa and (sa["pergunta"] or sa["exclamacao"] or sa["impacto"] >= 0.85) \
                and last_w and last_w["i"] == sa["w1"] and sp.ok("l_cut", T, cc["l_cut"]["intervalo_min_s"]) \
                and not any(d_["limite"] == k and d_["tecnica"] == "j_cut" and d_["aplicar"] for d_ in dec):
            ok, why = split_safe(cc["l_cut"])
            d = float(np.clip(0.3 + 0.5 * sa["impacto"], cc["l_cut"]["overlap_min_s"], cc["l_cut"]["overlap_max_s"]))
            d = min(d, A.dur * 0.4)
            tipo = "pergunta retórica" if sa["pergunta"] else ("exclamação" if sa["exclamacao"] else "afirmação forte")
            motivo = f"{tipo} precisa respirar: \"{sa['texto'][-50:]}\"; {why}"
            if ok:
                sp.mark("l_cut", T)
                add("l_cut", k, motivo, overlap=round(d, 3))
            else:
                dec.append({"id": len(dec), "tecnica": "l_cut", "limite": k, "t_fonte": round(A.a_out, 2), "t_saida": round(T, 2),
                            "motivo": motivo + " → NÃO aplicado", "params": {"overlap": round(d, 3)}, "aplicar": False})

        # ---------------- REACTION CUT (freeze antes de revelação/número)
        if cc["reaction_cut"]["ativo"] and wb and sp.ok("reaction", T, cc["reaction_cut"]["intervalo_min_s"]):
            head = wb[:3]
            rev = [t for t in trig["revelacao"] if t.lower() in first_txt]
            num = next((w for w in head if w.get("num")), None)
            if (rev or num) and new_sentence:
                n = int(np.clip(round(cc["reaction_cut"]["frames_min"] + (sb["impacto"] if sb else 0.5) *
                                      (cc["reaction_cut"]["frames_max"] - cc["reaction_cut"]["frames_min"])),
                                cc["reaction_cut"]["frames_min"], cc["reaction_cut"]["frames_max"]))
                sp.mark("reaction", T)
                add("reaction_cut", k, f"antecipação antes de " + (f"revelação ('{rev[0]}')" if rev else f"número ('{num['w']}')"),
                    frames=n)

        # ---------------- TRANSIÇÕES VISUAIS (Etapa 10)
        tr = cc.get("transicoes", {})
        if new_topic and not smash:   # smash cut já é o "impacto" do corte: não empilha transição
            for nome, chave in (("whip", "whip_pan"), ("flash", "flash_branco")):
                o = tr.get(chave, {})
                if o.get("ativo") and sp.ok(chave, T, o["intervalo_min_s"]) and A.dur > 0.6 and B.dur > 0.6:
                    sp.mark(chave, T)
                    add("transicao", k, f"troca de tópico → {chave}", tipo=nome, dur=o["duracao_s"])
                    break
        if smash and tr.get("glitch", {}).get("ativo") and sp.ok("glitch", T, tr["glitch"]["intervalo_min_s"]):
            sp.mark("glitch", T)
            add("glitch", k, "impacto do smash cut", frames=tr["glitch"]["frames"])
    return dec


def apply(clips: list[Clip], decisions: list[dict], fps) -> None:
    """Aplica as decisões aprovadas. Zoom é propagado aos clipes seguintes do mesmo plano."""
    by_k: dict[int, list[dict]] = {}
    for d in decisions:
        if d["aplicar"]:
            by_k.setdefault(d["limite"], []).append(d)
    zoom = 1.0
    for k, c in enumerate(clips):
        if k == 0:
            c.zoom = 1.0
            continue
        ds = by_k.get(k - 1, [])
        A = clips[k - 1]
        same_shot = A.src == c.src and A.shot == c.shot
        if not same_shot:
            zoom = 1.0
        for d in ds:
            t, p = d["tecnica"], d["params"]
            if t in ("jump_zoom", "smash_cut"):
                zoom = p["zoom"]
                c.tags.append(t if not p.get("reset") else "zoom_reset")
            elif t == "j_cut":
                o = p["overlap"]
                A.v_out += o
                c.v_in += o
                c.tags.append("j_cut")
            elif t == "l_cut":
                o = p["overlap"]
                A.v_out -= o
                c.v_in -= o
                c.tags.append("l_cut")
            elif t == "reaction_cut":
                c.freeze_frames = p["frames"]
                c.tags.append("reaction_cut")
            elif t == "match_cut":
                c.tags.append("match_cut")
                if p.get("alinhar") and A.face and c.face:
                    # posição do rosto de A no quadro de saída → B herda a mesma posição
                    za = A.zoom
                    ax, ay = A.anchor
                    rel = A.rel or (ax, ay)
                    fx = rel[0] + (A.face[0] - ax) * za
                    fy = rel[1] + (A.face[1] - ay) * za
                    zoom = max(zoom, 1.06)  # precisa de margem para reposicionar
                    c.rel = (float(np.clip(fx, 0.1, 0.9)), float(np.clip(fy, 0.1, 0.9)))
            elif t == "transicao":
                c.transicao_in = p["tipo"]
                c.transicao_dur = p["dur"]
                c.tags.append(p["tipo"])
            elif t == "glitch":
                c.glitch_frames = p["frames"]
                c.tags.append("glitch")
        c.zoom = zoom
    snap_clips(clips, fps)
    layout_times(clips, fps)


def apply_beats(clips: list[Clip], beat_decisions: list[dict], fps) -> None:
    """Aplica os beat cuts aprovados (estende/apara o fim do clipe A)."""
    for d in beat_decisions:
        if d["aplicar"]:
            A = clips[d["limite"]]
            A.a_out += d["params"]["delta"]
            A.v_out += d["params"]["delta"]
            clips[d["limite"] + 1].tags.append("beat_cut")
    snap_clips(clips, fps)
    layout_times(clips, fps)


def decide_beats(clips: list[Clip], beats_out: list[tuple[float, float]], cfg: dict, decisions: list[dict]) -> list[dict]:
    """Encaixa cortes nos beats fortes da trilha (tempos de saída).

    Só mexe no FIM do clipe A: estende (usando silêncio que tinha sido removido) ou apara
    (sem cortar a última palavra). beats_out: [(tempo, força 0-1)].
    """
    bc = cfg["cortes"]["beat_cut"]
    if not bc["ativo"] or not beats_out:
        return []
    bt = np.array([b for b, s in beats_out if s >= bc["energia_beat_min"]])
    if not len(bt):
        return []
    impact_k = {d["limite"] for d in decisions if d["aplicar"] and (
        d["tecnica"] in ("smash_cut", "reaction_cut", "transicao")
        or (d["tecnica"] == "jump_zoom" and d["params"].get("reset")))}
    out, shift = [], 0.0
    for k in range(len(clips) - 1):
        A = clips[k]
        if bc["aplicar_em"] == "impacto" and k not in impact_k:
            continue
        T = A.out_start + A.dur + shift  # instante do corte no vídeo final
        j = int(np.argmin(np.abs(bt - T)))
        delta = float(bt[j] - T)
        if abs(delta) > bc["tolerancia_s"] or abs(delta) < 1 / 60:
            continue
        lo = (A.a_out_min or A.a_in + 0.2) - A.a_out
        hi = (A.a_out_max if A.a_out_max is not None else A.a_out) - A.a_out
        if A.src == clips[k + 1].src and A.a_out_max is not None:
            hi = min(hi, clips[k + 1].a_in - A.a_out) if clips[k + 1].a_in > A.a_out else min(hi, 0)
        if not (lo <= delta <= hi):
            continue
        shift += delta
        out.append({"id": len(decisions) + len(out), "tecnica": "beat_cut", "limite": k,
                     "t_saida": round(T, 2), "motivo": f"corte movido {delta*1000:+.0f} ms para o beat em {bt[j]:.2f}s",
                     "params": {"delta": round(delta, 4)}, "aplicar": True})
    return out


# ----------------------------------------------------------------------------- revisão / log
def write_review(decisions: list[dict], path: Path) -> None:
    head = ("# Sugestões de técnicas de corte. Mude 'aplicar' para true/false e rode com --usar-revisao.\n")
    path.write_text(head + yaml.safe_dump(_plain(decisions), allow_unicode=True, sort_keys=False), encoding="utf-8")


def load_review(path: Path, decisions: list[dict]) -> list[dict]:
    """Casa cada decisão com a revisada pela técnica + tempo na FONTE (estável mesmo se os
    cortes de silêncio mudarem e os índices dos clipes se deslocarem)."""
    rev = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    for d in decisions:
        cands = [r for r in rev if r["tecnica"] == d["tecnica"] and "t_fonte" in r and "t_fonte" in d
                 and abs(r["t_fonte"] - d["t_fonte"]) < 0.35]
        if cands:
            d["aplicar"] = bool(min(cands, key=lambda r: abs(r["t_fonte"] - d["t_fonte"]))["aplicar"])
    log.info("  revisão de técnicas aplicada (%s)", path.name)
    return decisions


def summarize(decisions: list[dict]) -> dict:
    s: dict[str, list[int]] = {}
    for d in decisions:
        s.setdefault(d["tecnica"], [0, 0])[0 if d["aplicar"] else 1] += 1
    return {k: {"aplicadas": v[0], "nao_aplicadas": v[1]} for k, v in s.items()}
