"""Modelo "premium" de motion (HyperFrames) — nível de agência, com a identidade da Zeal.

Pedido do cliente: os motions anteriores estavam "de amador". Referência de MOVIMENTO:
referencias/motion2/ref.mp4 (linha de luz que revela o texto, máscaras, celular 3D com interface,
gráfico que se desenha, caminho de etapas, botão com cursor, transições iris/listras/chicote/esfera).
Paleta da marca (logo da Zeal): roxo #5D2E8C, ciano #24D0DC, branco; fundo quase preto.

Roteiro (YAML), `modelo: premium`:
  cenas:
    - {tipo: linha,   rotulo: "ZEAL · IA POR VOZ", titulo: "Sua clínica|atendendo *24h*", destaque: "sem perder|nenhum paciente.", dur: 3.4}
    - {tipo: logo,    nome: zeal, slogan: "assistente de IA por voz", transicao: iris}
    - {tipo: celular, rotulo: ..., titulo: ..., chamada_nome: "Maria", falas: [[pac, "..."], [ia, "..."]],
                      cartao: {titulo: "Consulta agendada", linhas: [[Quando, "Qui · 14:30"]]}, selos: [...], transicao: listras}
    - {tipo: grafico, titulo: ..., pontos: [1, 2, 3], projecao: 2, marcos: [{i: 2, texto: "Hoje"}], contadores: [{valor: 24, sufixo: h, legenda: "atendendo"}]}
    - {tipo: passos,  titulo: ..., passos: [{icone: tel, texto: "Paciente liga"}, ...]}
    - {tipo: cta,     titulo: "...", destaque: "...", botao: "Conheça a Zeal", url: zealtecnologia.com, transicao: esfera}
    - {tipo: texto,   titulo: "Frase *forte*", sub: "apoio"}
    - {tipo: numero,  valor: 24, sufixo: "h", legenda: "por dia"}
    - {tipo: cards,   titulo: "Alguns empregos|vão *sumir.*", itens: [[Digitação, chat], ...], ficam: [4]}
    - {tipo: ciclo,   titulo: "Repetição.|Tarefa *mecânica.*", tarefas: [Copiar, Colar, Repetir], repeticoes: 999}
    - {tipo: comparacao, titulo: "Em *1 hora.*", antes: Antes, antes_valor: "o dia todo", depois: "Com IA", depois_valor: "1 h"}
    - {tipo: soma,    titulo: "A IA veio|para *somar.*", a: Você, b: IA, resultado: "+ resultado"}
    - {tipo: timeline, titulo: "Editado|*100% por IA.*", chip: "Edição automática"}
  `|` quebra a linha; `*trecho*` = destaque (Black Jack ciano). Transições: iris, listras, chicote, esfera,
  dissolver, corte. Ícones: tel, ia, agenda, check, zap, user, chat, dente, relogio, grafico, whats.
"""
from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

from .utils import ROOT

HF = ROOT / "hyperframes"
MODELO_PREMIUM = HF / "modelos" / "motion_premium.html"
FONTES = ["Rubik-Medium.ttf", "Rubik-Bold.ttf", "Rubik-Black.ttf", "NotoSerif-BoldItalic.ttf"]
PALETA_ZEAL = {"fundo": "#07050d", "fundo2": "#12081f", "texto": "#ffffff", "acento": "#24d0dc", "marca": "#5d2e8c"}
DUR_PADRAO = {"linha": 3.4, "texto": 2.6, "logo": 2.8, "celular": 5.6, "grafico": 4.2, "passos": 4.6, "cta": 3.6, "numero": 2.8,
              "cards": 2.8, "ciclo": 2.8, "comparacao": 2.8, "soma": 2.8, "timeline": 2.6}
OV = {"iris": 0.7, "listras": 0.6, "chicote": 0.45, "esfera": 0.8, "dissolver": 0.4, "corte": 0.0}
FUNDO_PADRAO = {"linha": "escuro", "texto": "escuro", "logo": "profundo", "celular": "roxo", "grafico": "escuro",
                "passos": "roxo", "cta": "profundo", "numero": "escuro", "cards": "escuro", "ciclo": "roxo",
                "comparacao": "escuro", "soma": "profundo", "timeline": "roxo"}


def _rgb(h: str) -> str:
    h = h.lstrip("#")
    return ", ".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def montar_premium(roteiro: dict, pasta: Path, W: int, H: int) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "fonts").mkdir(exist_ok=True)
    for f in FONTES:
        shutil.copy2(ROOT / "assets" / "fonts" / f, pasta / "fonts" / f)
    shutil.copy2(HF / "node_modules" / "gsap" / "dist" / "gsap.min.js", pasta / "gsap.min.js")
    from .utils import arquivo_black_jack
    bj = arquivo_black_jack()
    if bj:
        shutil.copy2(bj, pasta / "fonts" / f"BlackJack{bj.suffix.lower()}")
        face = f'@font-face {{ font-family: "Black Jack"; src: url("fonts/BlackJack{bj.suffix.lower()}"); }}'
        css = '"Black Jack", cursive; font-weight: 400; font-size: 1.22em; letter-spacing: 0'
    else:
        face, css = "", '"Noto Serif", serif; font-style: italic; font-weight: 700; letter-spacing: -0.01em'
    pal = dict(PALETA_ZEAL, **(roteiro.get("paleta") or {}))
    t, cenas, blocos = 0.0, [], []
    for k, c in enumerate(roteiro["cenas"]):
        c = dict(c)
        d = float(c.get("dur", DUR_PADRAO.get(c["tipo"], 3.0)))
        tr = c.get("transicao", "corte" if k == 0 else "dissolver")
        ov = 0.0 if k == 0 else OV.get(tr, 0.4)
        c.update(t=round(t, 3), dur=d, ov=ov, transicao=tr)
        ini = round(t - ov, 3)
        fundo = c.get("fundo", FUNDO_PADRAO.get(c["tipo"], "escuro"))
        blocos.append(f'<section id="c{k}" class="clip" data-start="{ini}" data-duration="{round(d + ov, 3)}" '
                      f'data-track-index="{1 + k % 2}" style="z-index:{k + 1}"><div class="inner"><div class="bg {fundo}"></div>'
                      f'<div class="vinheta"></div><div class="palco"></div></div></section>')
        cenas.append(c)
        t += d
    doc = MODELO_PREMIUM.read_text(encoding="utf-8")
    for kk, v in {"__FONTE_DEST_FACE__": face, "__FONTE_DEST_CSS__": css, "__W__": str(W), "__H__": str(H),
                  "__DUR__": f"{t:.3f}", "__TITULO__": html.escape(roteiro.get("titulo", "motion")),
                  "__FUNDO__": pal["fundo"], "__FUNDO2__": pal["fundo2"], "__TEXTO__": pal["texto"],
                  "__ACENTO__": pal["acento"], "__MARCA__": pal["marca"],
                  "__ACENTO_RGB__": _rgb(pal["acento"]), "__MARCA_RGB__": _rgb(pal["marca"]),
                  "__CENAS_HTML__": "\n      ".join(blocos),
                  "__DADOS__": json.dumps({"dur": round(t, 3), "cenas": cenas, "poeira": roteiro.get("poeira", 46),
                                           "pre_roll": roteiro.get("pre_roll", 0.3)},
                                          ensure_ascii=False)}.items():
        doc = doc.replace(kk, v)
    (pasta / "index.html").write_text(doc, encoding="utf-8")
    (pasta / "hyperframes.json").write_text(json.dumps({"name": pasta.name}), encoding="utf-8")
    return pasta
