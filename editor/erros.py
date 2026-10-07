"""Erros de gravação — recomeços, gaguejadas e muletas (antes só as pausas eram cortadas).

Detecta na transcrição (tempo da FONTE) e devolve trechos a remover:
  • recomeço     "o time, o time do povo"  → corta a 1ª tentativa ("o time,")
                 "hoje eu vou… hoje eu vou falar" (2+ palavras repetidas logo em seguida)
  • gaguejada    "que que", "o o", "eu eu" (só palavras curtas/funcionais — "muito, muito"
                 e "nunca, nunca" são ênfase e ficam)
  • muleta       "é…", "hã", "ahn", "hum", "tipo assim" isolados entre pausas
  • frase abandonada  começo de frase que é recomeçado igual logo depois de uma pausa
As bordas do corte são ajustadas para o ponto de menor energia (sem "click" nem sílaba cortada).
Tudo vai para o relatório e para revisao/cortes_silencio.yaml (dá para desfazer um a um).
"""
from __future__ import annotations

import re

import numpy as np

from .utils import log

FUNCIONAIS = {"o", "a", "os", "as", "um", "uma", "de", "do", "da", "dos", "das", "que", "eu", "e", "é",
              "no", "na", "em", "pra", "pro", "se", "me", "te", "ele", "ela", "isso", "esse", "essa",
              "tá", "aí", "com", "por", "mas", "não", "vai", "vou"}
ENFASE = {"muito", "nunca", "sempre", "não", "sim", "nada", "tudo", "bem", "mais", "super", "vai"}
MULETAS = {"é", "éé", "ééé", "hã", "hãã", "ahn", "ah", "eh", "hum", "hmm", "uh", "humm", "ãh", "ã"}
MULETAS_2 = {("tipo", "assim"), ("né", "tipo")}

DEFAULTS = {"ativo": True, "recomeco": True, "gaguejada": True, "muletas": True,
            "frase_abandonada": True, "janela_palavras": 10, "pausa_recomeco_s": 0.2}


def _n(w: str) -> str:
    return re.sub(r"[^\wÀ-ú]", "", w.lower())


def detectar(words: list[dict], cfg: dict) -> list[dict]:
    ec = dict(DEFAULTS, **(cfg.get("erros") or {}))
    if not ec["ativo"] or len(words) < 2:
        return []
    t = [_n(w["w"]) for w in words]
    cortes: list[dict] = []
    usado = np.zeros(len(words), bool)

    def add(i0, i1, tipo, txt):
        """remove as palavras i0..i1-1 (a 1ª tentativa); a fala segue em i1."""
        if i1 <= i0 or usado[i0:i1].any():
            return
        usado[i0:i1] = True
        cortes.append({"tipo": tipo, "s": round(words[i0]["s"], 3), "e": round(words[i1]["s"], 3),
                       "texto": " ".join(w["w"] for w in words[i0:i1]), "antes_de": words[i1]["w"],
                       "motivo": txt, "aplicar": True})

    n = len(words)
    # 1) recomeço: bloco de k palavras repetido logo em seguida (k = 4..2)
    if ec["recomeco"]:
        for k in (4, 3, 2):
            for i in range(n - 2 * k + 1):
                a = t[i:i + k]
                if not all(a) or usado[i:i + k].any():
                    continue
                if t[i + k:i + 2 * k] == a and not (k == 2 and a[0] == a[1]):
                    add(i, i + k, "recomeço", f"'{' '.join(w['w'] for w in words[i:i + k])}' repetido em seguida")
    # 2) frase abandonada: as 2–3 primeiras palavras de um trecho reaparecem depois de uma pausa,
    #    dentro de poucas palavras ("Hoje eu vou… [pausa] Hoje eu vou falar")
    if ec["frase_abandonada"]:
        for i in range(n - 3):
            if usado[i]:
                continue
            a = t[i:i + 2]
            if not all(a) or a[0] in ENFASE:
                continue
            for j in range(i + 3, min(n - 1, i + ec["janela_palavras"])):
                if t[j:j + 2] == a and not usado[i:j].any():
                    pausa = words[j]["s"] - words[j - 1]["e"]
                    if pausa >= ec["pausa_recomeco_s"] or words[j - 1]["w"][-1:] in ",.…-":
                        add(i, j, "frase abandonada",
                            f"recomeçou '{words[j]['w']} {words[j + 1]['w']}' depois de pausa de {pausa:.2f}s")
                    break
    # 3) gaguejada: palavra curta/funcional repetida ("que que", "o o")
    if ec["gaguejada"]:
        for i in range(n - 1):
            if t[i] and t[i] == t[i + 1] and t[i] in FUNCIONAIS and t[i] not in ENFASE:
                add(i, i + 1, "gaguejada", f"'{words[i]['w']} {words[i + 1]['w']}'")
    # 4) muletas isoladas
    if ec["muletas"]:
        for i in range(n):
            pre = words[i]["s"] - words[i - 1]["e"] if i else 1.0
            pos = words[i + 1]["s"] - words[i]["e"] if i + 1 < n else 1.0
            alongada = words[i]["w"].endswith(("…", "...")) or words[i]["e"] - words[i]["s"] > 0.45
            if t[i] in MULETAS and i + 1 < n and (max(pre, pos) >= 0.15 or alongada) and t[i] != "é" or \
                    (t[i] == "é" and alongada and i + 1 < n):
                add(i, i + 1, "muleta", f"'{words[i]['w']}' isolado")
            elif i + 2 < n and (t[i], t[i + 1]) in MULETAS_2:
                add(i, i + 2, "muleta", f"'{words[i]['w']} {words[i + 1]['w']}'")
    cortes.sort(key=lambda c: c["s"])
    if cortes:
        log.info("  erros de gravação: %d (%s)", len(cortes),
                 {k: sum(c["tipo"] == k for c in cortes) for k in sorted({c["tipo"] for c in cortes})})
        for c in cortes:
            log.info("    %.2fs %-16s \"%s\" → %s", c["s"], c["tipo"], c["texto"], c["motivo"])
    else:
        log.info("  erros de gravação: nenhum")
    return cortes


def _vale(db: np.ndarray, hop: float, t: float, raio: float = 0.09) -> float:
    """Ponto de menor energia perto de t (corte sem estalo)."""
    a, b = max(0, int((t - raio) / hop)), min(len(db), int((t + raio) / hop) + 1)
    if b <= a:
        return t
    return (a + int(np.argmin(db[a:b]))) * hop


def aplicar(keeps: list[list[float]], cortes: list[dict], db=None, hop: float = 0.02) -> list[list[float]]:
    """Subtrai os trechos com erro dos segmentos mantidos."""
    rem = []
    for c in cortes:
        if not c.get("aplicar", True):
            continue
        s, e = c["s"] - 0.03, c["e"] - 0.03
        if db is not None:
            s, e = _vale(db, hop, s), _vale(db, hop, e)
        if e - s > 0.06:
            rem.append((s, e))
    out = []
    for a, b in keeps:
        segs = [(a, b)]
        for s, e in rem:
            nxt = []
            for x, y in segs:
                if e <= x or s >= y:
                    nxt.append((x, y))
                    continue
                if s - x > 0.05:
                    nxt.append((x, s))
                if y - e > 0.05:
                    nxt.append((e, y))
            segs = nxt
        out += [[round(x, 3), round(y, 3)] for x, y in segs]
    return out
