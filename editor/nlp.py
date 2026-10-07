"""NLP leve sobre a transcrição (spaCy pt_core_news_sm + regras).

Produz para cada palavra: classe gramatical, lema, score de palavra-chave (0-1), gatilhos;
para cada frase: impacto (percentil 0-1), pergunta/exclamação, tópico; e para o vídeo:
tom (energético, informativo, emocional, dramático, sombrio), nome do orador e termos
"definidos" (candidatos a callout). Todas as listas de palavras vêm do YAML (gatilhos).
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

import numpy as np

from .utils import log

TOPIC_STARTERS = ("agora", "outra coisa", "segundo", "terceiro", "por fim", "além disso",
                  "enfim", "primeiro", "e outra", "mudando", "bom,", "beleza,", "então,")

TONE_LEX = {
    "energetico": ["incrível", "bora", "vamos", "rápido", "crescer", "cresceu", "explodir", "sucesso",
                   "ganhar", "energia", "agora", "simples", "fácil", "top", "absurdo", "melhor"],
    "emocional": ["sentir", "sinto", "amor", "coração", "vida", "família", "sonho", "carinho", "saudade",
                  "chorar", "gratidão", "história", "criação", "deus", "fé", "obrigado", "pai", "mãe"],
    "dramatico": ["nunca", "morte", "perder", "perdi", "medo", "problema", "crise", "faliu", "falir",
                  "guerra", "luta", "difícil", "dor", "pior", "parou", "erro", "fracasso"],
    "sombrio": ["escuro", "distância", "silêncio", "segredo", "sombra", "ninguém", "sozinho", "vazio"],
    "informativo": ["empresa", "negócio", "processo", "estratégia", "resultado", "dados", "passo",
                    "teste", "time", "mercado", "gestão", "marca", "cliente", "trabalho", "método"],
}

NUM_WORDS = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "três": 3, "quatro": 4, "cinco": 5, "seis": 6,
             "sete": 7, "oito": 8, "nove": 9, "dez": 10, "vinte": 20, "trinta": 30, "quarenta": 40,
             "cinquenta": 50, "cem": 100, "cento": 100, "mil": 1000, "milhão": 1e6, "milhões": 1e6,
             "bilhão": 1e9, "bilhões": 1e9}


@lru_cache(maxsize=1)
def _nlp():
    import spacy
    try:
        return spacy.load("pt_core_news_sm", disable=["ner"])
    except OSError:
        log.warning("spaCy pt_core_news_sm ausente — usando heurísticas sem POS")
        return None


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def clean(w: str) -> str:
    return re.sub(r"[^\w%-]", "", w.lower())


def _phrase_hits(text_l: str, phrases: list[str]) -> list[str]:
    hits = []
    for p in phrases:
        if p in "!?":
            if p in text_l:
                hits.append(p)
        elif re.search(rf"(?<!\w){re.escape(p.lower())}(?!\w)", text_l):
            hits.append(p)
    return hits


def parse_number(tok: str) -> float | None:
    t = tok.lower().strip(".,!?;:")
    t2 = t.replace(".", "").replace(",", ".")
    try:
        return float(t2.rstrip("%"))
    except ValueError:
        return NUM_WORDS.get(t)


def annotate(words: list[dict], cfg: dict) -> dict:
    """Enriquece as palavras e devolve frases, tópicos, tom e candidatos de motion."""
    g = cfg["gatilhos"]
    # ---- POS / lemas via spaCy, alinhando tokens às palavras por offset de caractere
    text, offsets = "", []
    for w in words:
        offsets.append(len(text))
        text += w["w"] + " "
    nlp = _nlp()
    pos = ["X"] * len(words)
    lemma = [clean(w["w"]) for w in words]
    stop = [False] * len(words)
    if nlp is not None and words:
        doc = nlp(text)
        starts = np.array(offsets)
        for tok in doc:
            i = int(np.searchsorted(starts, tok.idx, side="right") - 1)
            if 0 <= i < len(words) and not tok.is_punct and pos[i] == "X":
                pos[i], lemma[i], stop[i] = tok.pos_, tok.lemma_.lower(), tok.is_stop
    # ---- frases (pontuação do ASR ou pausa longa)
    sentences, cur = [], []
    for i, w in enumerate(words):
        cur.append(i)
        end_p = w["w"][-1:] in ".!?"
        gap = (words[i + 1]["s"] - w["e"]) if i + 1 < len(words) else 9
        if end_p or gap > 1.2 or i == len(words) - 1:
            sentences.append(cur)
            cur = []
    trig_all = {k: [x.lower() for x in v] for k, v in g.items()}
    # ---- score de palavra-chave
    base = {"NUM": 0.8, "PROPN": 0.62, "NOUN": 0.56, "ADJ": 0.48, "VERB": 0.44, "ADV": 0.25}
    for i, w in enumerate(words):
        c = clean(w["w"])
        num = parse_number(w["w"]) is not None and (c.isdigit() or c in NUM_WORDS and c not in ("um", "uma"))
        s = 0.0 if stop[i] and not num else base.get(pos[i], 0.3)
        if num:
            s = max(s, 0.8)
        if len(c) >= 7:
            s += 0.08
        if w["w"][-1:] in ".!":
            s += 0.12
        if any(c == strip_accents(t) or c == t for k in ("revelacao", "climax") for t in trig_all[k]):
            s += 0.25
        w.update({"i": i, "pos": pos[i], "lemma": lemma[i], "stop": stop[i], "num": bool(num),
                  "kw": round(min(1.0, s), 3)})
    # ---- frases: impacto, pergunta, gatilhos
    sents = []
    for sid, idx in enumerate(sentences):
        ws = [words[i] for i in idx]
        t = " ".join(w["w"] for w in ws)
        tl = t.lower()
        content = {words[i]["lemma"] for i in idx if not words[i]["stop"] and words[i]["pos"] in ("NOUN", "PROPN", "VERB", "ADJ", "NUM")}
        hits = {k: _phrase_hits(tl, v) for k, v in trig_all.items()}
        raw = (max(w["kw"] for w in ws) * 0.5 + 0.25 * bool(hits["climax"]) + 0.15 * bool(hits["revelacao"])
               + 0.2 * ("!" in t) + 0.1 * (len(ws) <= 5) + 0.12 * any(w["num"] for w in ws))
        for i in idx:
            words[i]["sent"] = sid
        sents.append({"id": sid, "w0": idx[0], "w1": idx[-1], "s": ws[0]["s"], "e": ws[-1]["e"],
                      "texto": t, "pergunta": t.rstrip().endswith("?"), "exclamacao": "!" in t,
                      "lemas": sorted(content), "gatilhos": {k: v for k, v in hits.items() if v},
                      "impacto_bruto": raw})
    if sents:
        raws = np.array([s["impacto_bruto"] for s in sents])
        ranks = raws.argsort().argsort() / max(1, len(raws) - 1)
        for s, r in zip(sents, ranks):
            s["impacto"] = round(float(r), 3)
    # ---- tópicos
    topic, topics = 0, []
    for k, s in enumerate(sents):
        if k > 0:
            prev = set().union(*[set(x["lemas"]) for x in sents[max(0, k - 2):k]])
            nxt = set().union(*[set(x["lemas"]) for x in sents[k:k + 2]])
            sim = len(prev & nxt) / max(1, len(prev | nxt))
            starter = s["texto"].lower().startswith(TOPIC_STARTERS)
            gap = s["s"] - sents[k - 1]["e"]
            s["sim_anterior"] = round(len(set(s["lemas"]) & set(sents[k - 1]["lemas"])) /
                                      max(1, len(set(s["lemas"]) | set(sents[k - 1]["lemas"]))), 3)
            if (sim <= cfg["silencio"]["contexto"]["transicao_topico"]["similaridade_max"]
                    and (starter or gap > 0.7)) or (starter and sim < 0.25):
                topic += 1
                s["novo_topico"] = True
        else:
            s["sim_anterior"] = 0.0
        s["topico"] = topic
        topics.append(topic)
    # ---- tom do vídeo
    allw = [strip_accents(clean(w["w"])) for w in words]
    scores = {}
    for mood, lex in TONE_LEX.items():
        lx = {strip_accents(x) for x in lex}
        scores[mood] = sum(1 for w in allw if w in lx) / max(1, len(allw)) * 100
    dur = (words[-1]["e"] - words[0]["s"]) if words else 1
    rate = len(words) / max(1, dur)
    scores["energetico"] += max(0, rate - 2.6) * 1.5 + 0.5 * sum("!" in s["texto"] for s in sents) / max(1, len(sents))
    tone = max(scores, key=scores.get) if max(scores.values()) > 0.4 else "informativo"
    # ---- orador se apresenta?  ("meu nome é Fulano", "eu sou o Fulano")
    nome = None
    m = re.search(r"(?:meu nome é|me chamo|eu sou (?:o|a))\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wáéíóúâêôãõç]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wáéíóúâêôãõç]+)?)", text)
    if m:
        nome = m.group(1)
    # ---- termos definidos (callout): "X é o contrário de...", "X é quando...", "X significa"
    callouts = []
    for s in sents:
        mm = re.match(r"^\s*([A-ZÁÉÍÓÚ][\wáéíóúâêôãõç]+)\s+(?:é|significa|seria)\s+(?:o|a|quando|um|uma|tipo)\b", s["texto"])
        if mm:
            term = mm.group(1)
            if term.lower() not in ("isso", "esse", "essa", "ele", "ela", "você", "eu", "não", "tudo", "o", "a", "e"):
                callouts.append({"termo": term, "s": s["s"], "sent": s["id"]})
    # termo isolado seguido de definição: "Pronoia." + "... é o contrário de ..." (padrão do ref1)
    for k, s in enumerate(sents[:-1]):
        toks = s["texto"].strip(" .!?").split()
        nxt = " ".join(sents[k + 1]["texto"].lower().split()[:6])
        if 1 <= len(toks) <= 2 and len(toks[-1]) >= 4 and re.search(r"\b(é|significa|seria)\s+(o|a|quando|um|uma)\b", nxt) \
                and not any(c["sent"] == k for c in callouts):
            callouts.append({"termo": " ".join(toks), "s": s["s"], "sent": s["id"]})
    callouts.sort(key=lambda c: c["s"])
    # ---- números para contador
    numeros = []
    mult_ok = set()
    for i, w in enumerate(words):
        if w["num"]:
            if i in mult_ok:          # "mil" já somado ao número anterior ("45 mil")
                continue
            v = parse_number(w["w"])
            nxt = clean(words[i + 1]["w"]) if i + 1 < len(words) else ""
            if nxt in ("mil", "milhões", "milhão", "bilhões") and v and v < 1000:
                v *= NUM_WORDS[nxt]
                mult_ok.add(i + 1)
                nxt = clean(words[i + 2]["w"]) if i + 2 < len(words) else ""
            unidade = nxt if nxt in ("anos", "dias", "meses", "km", "reais", "pessoas", "%", "por", "vezes", "mil", "milhões") else ""
            if "%" in w["w"] or nxt == "por":
                unidade = "%"
            numeros.append({"i": i, "valor": v, "unidade": unidade, "s": w["s"], "e": w["e"]})
    log.info("  %d palavras, %d frases, %d tópicos, tom=%s, %.1f palavras/s",
             len(words), len(sents), topic + 1, tone, rate)
    return {"palavras": words, "frases": sents, "tom": tone, "tom_scores": scores,
            "fala_ps": rate, "nome_orador": nome, "callouts": callouts, "numeros": numeros}
