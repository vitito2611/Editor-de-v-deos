"""Página de revisão (Artifact) — o cliente assiste à prévia e vê a linha do tempo da edição.

Uso: python -m editor.pagina <relatorio.json> <video.mp4> <saida.html> [--titulo "..."]
O vídeo é publicado junto com a página (arquivo "video.mp4"); clicar num item da linha do
tempo pula o player para aquele momento. Comentários na página voltam para o Claude.
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

ROTULO = {"video": "B-roll", "foto": "Foto", "card": "Card Remotion", "contador": "Contador Remotion",
          "callout": "Título Remotion", "gancho": "Gancho Remotion", "angulo_ia": "Ângulo IA",
          "transicao": "Transição", "corte": "Corte"}


def _fmt(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:04.1f}"


def eventos(rep: dict) -> list[dict]:
    ev = []
    for e in rep.get("dinamismo", []):
        o = e.get("texto") or e.get("busca") or ""
        ev.append({"t": e["t"], "dur": e["dur"], "tipo": e["tipo"], "o_que": o, "por": e.get("motivo", "")})
    for e in rep.get("remotion", []):
        if e["tipo"] == "card":
            continue  # o card já aparece pelo dinamismo
        ev.append({"t": e["t"], "dur": e["dur"], "tipo": e["tipo"], "o_que": "", "por": "número/termo falado"})
    for m in rep.get("motion", []) or []:
        if m.get("remotion"):
            for x in ev:
                if x["tipo"] == m["tipo"] and abs(x["t"] - m["t"]) < 0.3:
                    txt = m.get("texto", "")
                    num, _, resto = txt.partition(" ")
                    if num.replace(".", "").isdigit():   # 45000 → 45.000
                        txt = f"{float(num):,.0f}".replace(",", ".") + (" " + resto if resto else "")
                    x["o_que"] = txt
    for d in (rep.get("tecnicas") or {}).get("decisoes", []):
        if d.get("aplicar") and d.get("t_saida") is not None and d["tecnica"] not in ("jump_zoom",):
            ev.append({"t": d["t_saida"], "dur": 0.3, "tipo": "transicao", "o_que": {"flash": "flash branco", "whip": "whip pan", "glitch": "glitch"}.get(
                           (d.get("params") or {}).get("tipo"), d["tecnica"].replace("_", " ")),
                       "por": d.get("motivo", "")})
    return sorted(ev, key=lambda x: x["t"])


def build(rep: dict, titulo: str, sub: str) -> str:
    itens = []
    for e in eventos(rep):
        rot = ROTULO.get(e["tipo"], e["tipo"])
        itens.append(
            f'<li><button type="button" class="ev" data-t="{e["t"]:.2f}">'
            f'<span class="tc">{_fmt(e["t"])}</span>'
            f'<span class="tag t-{html.escape(e["tipo"])}">{html.escape(rot)}</span>'
            f'<span class="oq">{html.escape(str(e["o_que"]))}</span>'
            f'<span class="por">{html.escape(str(e["por"]))}</span></button></li>')
    saida = rep.get("saida", {})
    dados = (f'{saida.get("duracao", 0):.1f} s · {saida.get("lufs", 0) or 0:.1f} LUFS · '
             f'{len(rep.get("sfx", []))} efeitos sonoros · {len(itens)} inserções')
    return TEMPLATE.replace("{{TITULO}}", html.escape(titulo)).replace("{{SUB}}", html.escape(sub)) \
        .replace("{{DADOS}}", html.escape(dados)).replace("{{ITENS}}", "\n".join(itens))


TEMPLATE = """<title>{{TITULO}}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Archivo:wght@500;800&display=swap">
<style>
/* Layout: sala de edição — monitor 9:16 fixo à esquerda, linha do tempo da edição à direita (empilha no celular) */
:root {
  --bg: #0f1112; --painel: #171a1c; --linha: #2a2f33; --fg: #eceeee; --suave: #9aa3a8; --acento: #e8e2d6;
  --f-titulo: "Archivo", "Helvetica Neue", Arial, sans-serif;
  --f-mono: "JetBrains Mono", ui-monospace, Menlo, monospace;
  color-scheme: dark;
}
body { background: var(--bg); color: var(--fg); font-family: var(--f-titulo); }
.wrap { max-width: 1080px; margin: 0 auto; padding-inline: 16px; padding-block: 24px 48px; display: grid; gap: 24px; }
header h1 { font-weight: 800; font-size: clamp(1.6rem, 4vw, 2.4rem); margin: 0; letter-spacing: -0.01em; text-wrap: balance; }
header p { margin: 6px 0 0; color: var(--suave); max-width: 65ch; line-height: 1.5; }
.dados { font-family: var(--f-mono); font-size: 0.78rem; color: var(--suave); letter-spacing: 0.04em; margin-top: 10px; }
.sala { display: grid; grid-template-columns: minmax(0, 340px) minmax(0, 1fr); gap: 28px; align-items: start; }
.monitor { position: sticky; top: calc(env(safe-area-inset-top, 0px) + 16px); }
video { width: 100%; max-width: 100%; aspect-ratio: 9 / 16; background: #000; border: 1px solid var(--linha); border-radius: 6px; display: block; }
.tempo { font-family: var(--f-mono); font-size: 0.85rem; color: var(--acento); margin-top: 8px; font-variant-numeric: tabular-nums; }
h2 { font-size: 0.75rem; font-family: var(--f-mono); text-transform: uppercase; letter-spacing: 0.12em; color: var(--suave); margin: 0 0 10px; font-weight: 400; }
ol { list-style: none; margin: 0; padding: 0; display: grid; gap: 2px; }
.ev { all: unset; box-sizing: border-box; cursor: pointer; width: 100%; display: grid;
  grid-template-columns: 4.2rem 9.5rem minmax(0, 1fr); column-gap: 12px; row-gap: 2px; padding: 10px 12px;
  border-left: 2px solid transparent; border-radius: 2px; }
.ev:hover, .ev:focus-visible { background: var(--painel); }
.ev:focus-visible { outline: 1px solid var(--acento); }
.ev.ativo { background: var(--painel); border-left-color: var(--acento); }
.tc { font-family: var(--f-mono); font-variant-numeric: tabular-nums; color: var(--acento); font-size: 0.9rem; }
.tag { font-family: var(--f-mono); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--suave); padding-top: 2px; }
.t-card, .t-contador, .t-callout, .t-gancho { color: var(--fg); font-weight: 700; }
.oq { font-weight: 500; overflow-wrap: anywhere; }
.por { grid-column: 3; color: var(--suave); font-size: 0.82rem; }
.nota { border-top: 1px solid var(--linha); padding-top: 16px; color: var(--suave); line-height: 1.6; max-width: 65ch; font-size: 0.92rem; }
@media (max-width: 720px) {
  .sala { grid-template-columns: minmax(0, 1fr); }
  .monitor { position: static; max-width: 300px; margin: 0 auto; width: 100%; }
  .ev { grid-template-columns: 3.6rem minmax(0, 1fr); }
  .tag { grid-column: 2; }
  .oq, .por { grid-column: 2; }
}
@media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto !important; } }
</style>
<div class="wrap">
  <header>
    <h1>{{TITULO}}</h1>
    <p>{{SUB}}</p>
    <div class="dados">{{DADOS}}</div>
  </header>
  <div class="sala">
    <div class="monitor">
      <video id="v" src="video.mp4" controls playsinline preload="metadata"></video>
      <div class="tempo" id="tempo">0:00.0</div>
    </div>
    <section>
      <h2>Linha do tempo da edição · toque para ir ao momento</h2>
      <ol id="lista">
{{ITENS}}
      </ol>
    </section>
  </div>
  <p class="nota">Quer mudar algo? Deixe um comentário nesta página dizendo o tempo e o que trocar
  (ex.: “0:16 troca a foto”, “tira o card de 0:29”). Eu ajusto, renderizo de novo e atualizo este mesmo link.</p>
</div>
<script>
(function () {
  var v = document.getElementById("v"), tempo = document.getElementById("tempo");
  var evs = Array.prototype.slice.call(document.querySelectorAll(".ev"));
  function fmt(t) { var m = Math.floor(t / 60), s = (t % 60).toFixed(1); return m + ":" + (s < 10 ? "0" : "") + s; }
  evs.forEach(function (b) {
    b.addEventListener("click", function () {
      v.currentTime = parseFloat(b.dataset.t); var p = v.play(); if (p && p.catch) p.catch(function () {});
    });
  });
  v.addEventListener("timeupdate", function () {
    tempo.textContent = fmt(v.currentTime);
    var atual = null;
    evs.forEach(function (b) { if (parseFloat(b.dataset.t) <= v.currentTime + 0.05) atual = b; });
    evs.forEach(function (b) { b.classList.toggle("ativo", b === atual); });
  });
})();
</script>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("relatorio", type=Path)
    ap.add_argument("video", type=Path)
    ap.add_argument("saida", type=Path)
    ap.add_argument("--titulo", default="Revisão da edição")
    ap.add_argument("--sub", default="")
    a = ap.parse_args()
    rep = json.loads(a.relatorio.read_text(encoding="utf-8"))
    a.saida.parent.mkdir(parents=True, exist_ok=True)
    a.saida.write_text(build(rep, a.titulo, a.sub), encoding="utf-8")
    print(a.saida)


if __name__ == "__main__":
    main()


# ----------------------------------------------------------------------------- estúdio (edição em conjunto)
# Mesa de edição: escura de propósito (como todo editor de vídeo, a imagem é a referência de cor), grafite
# com leve viés violeta da Zeal, ciano só para o que está ativo (agulha, seleção, botão principal).
ESTUDIO_CSS = """
:root {
  /* layout: monitor 9:16 à esquerda + painel de abas à direita; linha do tempo larga embaixo */
  --fundo: #121018; --mesa: #1a1722; --campo: #24202f; --linha: #34304180; --texto: #ece9f4; --suave: #a39db4;
  --acento: #3fd6e0; --acento-esc: #0a2a2e; --perigo: #ff7a7a;
  --c-motion: #7c5cc4; --c-broll: #4b7bb8; --c-texto: #c08a3e; --c-legenda: #3f8f86; --c-sfx: #d06a9a;
  --f-ui: "Rubik", system-ui, sans-serif; --f-num: "JetBrains Mono", ui-monospace, monospace;
  --nome-w: 118px; color-scheme: dark;
}
html, body { background: var(--fundo); color: var(--texto); }
body { font-family: var(--f-ui); font-size: 14px; padding-inline: 16px; padding-block: 12px 28px; }
button, input, select, textarea { font: inherit; color: inherit; }
button { cursor: pointer; }
button:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible, [role=button]:focus-visible { outline: 2px solid var(--acento); outline-offset: 2px; }
.estudio { max-width: 1320px; margin: 0 auto; display: flex; flex-direction: column; gap: 12px; }
.barra { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px; }
.titulo { display: flex; align-items: baseline; gap: 10px; min-width: 0; }
.titulo h1 { font-size: 18px; font-weight: 700; margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; text-wrap: balance; }
.selo { font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--acento); font-weight: 700; }
.acoes-topo { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.salvo { font-size: 12px; color: var(--suave); font-variant-numeric: tabular-nums; }
.salvo.pend { color: var(--acento); }
.primario { background: var(--acento); color: #061318; border: 0; border-radius: 8px; padding: 9px 16px; font-weight: 700; }
.primario:disabled { background: var(--campo); color: var(--suave); cursor: not-allowed; }
.fantasma { background: transparent; border: 1px solid var(--linha); border-radius: 8px; padding: 7px 12px; color: var(--texto); }
.fantasma:hover:not(:disabled) { border-color: var(--suave); }
.fantasma:disabled { opacity: 0.45; cursor: not-allowed; }
.fantasma.ativo { border-color: var(--acento); color: var(--acento); }
.pequeno { padding: 4px 10px; font-size: 12px; }
.link { background: none; border: 0; padding: 0; color: var(--acento); font-size: 12px; }
.link:disabled { color: var(--suave); }
.link.perigo { color: var(--perigo); }
.aviso { display: flex; flex-wrap: wrap; gap: 12px; font-size: 13px; padding: 8px 12px; border-radius: 8px; background: var(--acento-esc); color: var(--texto); }
.st-renderizando { color: var(--acento); } .st-pronto { color: #7be0a0; } .st-erro { color: var(--perigo); }
.topo { display: grid; grid-template-columns: minmax(240px, 380px) minmax(0, 1fr); gap: 16px; align-items: start; }
.monitor { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.sob-monitor { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.tc { font-family: var(--f-num); font-size: 12px; color: var(--suave); font-variant-numeric: tabular-nums; }
.painel { background: var(--mesa); border-radius: 12px; display: flex; flex-direction: column; min-width: 0; max-height: 78vh; }
.abas { display: flex; gap: 2px; padding: 6px; border-bottom: 1px solid var(--linha); overflow-x: auto; }
.abas button { background: none; border: 0; border-radius: 6px; padding: 7px 12px; color: var(--suave); font-weight: 500; white-space: nowrap; }
.abas button.on { background: var(--campo); color: var(--texto); }
.conteudo { padding: 12px 14px; overflow-y: auto; flex: 1; min-height: 0; }
.grupo { display: flex; flex-direction: column; gap: 10px; }
.grupo h2 { font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--suave); margin: 8px 0 0; font-weight: 700; }
.dim { color: var(--suave); font-style: normal; font-weight: 400; letter-spacing: 0; text-transform: none; }
.nota { font-size: 12px; color: var(--suave); margin: 0; line-height: 1.45; }
.desl { display: grid; grid-template-columns: 112px minmax(0, 1fr) 72px; align-items: center; gap: 10px; }
.desl label { font-size: 13px; }
.desl output { font-family: var(--f-num); font-size: 12px; color: var(--suave); text-align: right; font-variant-numeric: tabular-nums; }
input[type=range] { width: 100%; accent-color: var(--acento); }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { background: var(--campo); border: 1px solid transparent; border-radius: 20px; padding: 5px 12px; font-size: 12px; text-transform: capitalize; }
.chip.on { border-color: var(--acento); color: var(--acento); }
.linha-botoes, .marcas { display: flex; flex-wrap: wrap; gap: 8px; }
.campo-linha { display: grid; grid-template-columns: 112px minmax(0, 1fr); gap: 10px; align-items: center; }
select, textarea, input[type=number] { background: var(--campo); border: 1px solid var(--linha); border-radius: 8px; padding: 7px 9px; width: 100%; box-sizing: border-box; }
textarea { resize: vertical; line-height: 1.4; }
.check { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.lista { display: flex; flex-direction: column; gap: 2px; }
.item { display: grid; grid-template-columns: auto auto minmax(0, 1fr) auto; align-items: center; gap: 8px; background: none; border: 0; border-radius: 6px;
  padding: 6px 8px; text-align: left; color: var(--texto); }
button.item { grid-template-columns: 56px minmax(0, 1fr); }
.item:hover { background: var(--campo); }
.item.agora { background: var(--acento-esc); }
.item .tx, .sfx-item .tx { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; font-size: 13px; }
.botao-tx { background: none; border: 0; padding: 0; text-align: left; display: flex; align-items: center; gap: 8px; }
.item.editado .tx::after, .item.editado .botao-tx::after { content: "editado"; margin-left: 6px; font-size: 10px; color: var(--acento); }
.oculto { opacity: 0.45; }
.pino { width: 8px; height: 8px; border-radius: 2px; flex: none; background: var(--c-texto); }
.pino.p-motion { background: var(--c-motion); } .pino.p-broll, .pino.p-foto { background: var(--c-broll); }
.sfx-item { display: grid; grid-template-columns: auto 52px minmax(0, 1fr) 90px 26px; align-items: center; gap: 8px; padding: 4px 6px; }
.sfx-item output { font-family: var(--f-num); font-size: 11px; color: var(--suave); text-align: right; }
.sfx-item.cortado { opacity: 0.4; }
.ficha { display: flex; flex-direction: column; gap: 8px; padding: 12px; border-radius: 10px; background: var(--campo); }
.ficha-topo { display: flex; align-items: center; gap: 12px; }
.ficha-topo .fechar { margin-left: auto; }
.tag { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--acento); }
.ficha label, .rot-mini { font-size: 12px; color: var(--suave); }
.ficha select, .ficha textarea, .ficha input[type=number] { background: var(--mesa); }
.palavras { display: flex; flex-wrap: wrap; gap: 4px; }
.pal { background: var(--mesa); border: 1px solid var(--linha); border-radius: 6px; padding: 3px 8px; font-size: 13px; }
.pal.on { border-color: var(--acento); color: var(--acento); }
.linha { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.num { display: flex; flex-direction: column; gap: 4px; }
.pedido { border-top: 1px solid var(--linha); padding: 10px 14px 14px; display: flex; flex-direction: column; gap: 6px; }
.pedido label { font-size: 12px; color: var(--suave); }
.pedido em { font-style: normal; opacity: 0.8; }
.pedido button { align-self: flex-end; }
/* linha do tempo */
.timeline { background: var(--mesa); border-radius: 12px; padding: 8px 10px 12px; user-select: none; }
.tl-topo { display: flex; justify-content: space-between; align-items: center; padding: 0 2px 6px; }
.zoom { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--suave); }
.zoom input { width: 120px; }
.tl-corpo { display: grid; grid-template-columns: var(--nome-w) minmax(0, 1fr); }
.nomes .n { height: 32px; display: flex; align-items: center; font-size: 11px; color: var(--suave); border-bottom: 1px solid var(--linha); box-sizing: border-box; padding-right: 6px; }
.nomes .regua-n { height: 22px; }
.rolo { overflow-x: auto; position: relative; }
.pista { position: relative; }
.regua { height: 22px; position: relative; border-bottom: 1px solid var(--linha); cursor: pointer; }
.regua span { position: absolute; top: 4px; font-family: var(--f-num); font-size: 10px; color: var(--suave); transform: translateX(2px); white-space: nowrap; }
.regua span::before { content: ""; position: absolute; left: -2px; top: -4px; height: 6px; border-left: 1px solid var(--suave); }
.trilha { position: relative; height: 32px; border-bottom: 1px solid var(--linha); box-sizing: border-box; }
.seg { position: absolute; top: 5px; bottom: 5px; border-radius: 4px; background: #2f2a3d; }
.emenda { position: absolute; top: 2px; bottom: 2px; width: 2px; margin-left: -1px; background: var(--perigo); }
.bloco { position: absolute; height: 22px; border-radius: 5px; overflow: hidden; display: flex; align-items: center; padding: 0 8px; box-sizing: border-box;
  font-size: 11px; color: #fff; cursor: grab; border: 1px solid transparent; }
.bloco span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; pointer-events: none; }
.bloco .alca { position: absolute; right: 0; top: 0; bottom: 0; width: 7px; cursor: ew-resize; background: rgba(255,255,255,0.18); }
.bloco.sel { border-color: var(--acento); box-shadow: 0 0 0 1px var(--acento); }
.bloco.editado::after { content: ""; position: absolute; left: 3px; top: 3px; width: 5px; height: 5px; border-radius: 50%; background: var(--acento); }
.t-motion { background: var(--c-motion); } .t-broll { background: var(--c-broll); } .t-texto { background: var(--c-texto); } .t-legenda { background: var(--c-legenda); }
.sfx-pino { position: absolute; top: 7px; width: 10px; height: 18px; margin-left: -5px; border-radius: 3px; background: var(--c-sfx); cursor: pointer; }
.sfx-pino.sel { box-shadow: 0 0 0 2px var(--acento); }
.musica { position: absolute; top: 6px; bottom: 6px; border-radius: 4px; background: #2a3b3c; font-size: 11px; display: flex; align-items: center; padding: 0 8px; color: var(--suave); }
.faixa-corte { position: absolute; top: 22px; bottom: 0; background: rgba(255, 122, 122, 0.18); border-left: 1px solid var(--perigo); border-right: 1px solid var(--perigo); pointer-events: none; }
.agulha { position: absolute; top: 0; bottom: 0; width: 2px; margin-left: -1px; background: var(--acento); pointer-events: none; box-shadow: 0 0 6px var(--acento); }
.dicas { font-size: 12px; color: var(--suave); margin: 0; }
@media (max-width: 820px) {
  .topo { grid-template-columns: minmax(0, 1fr); }
  .monitor { max-width: 320px; margin: 0 auto; width: 100%; }
  .painel { max-height: none; }
  :root { --nome-w: 76px; }
  .desl { grid-template-columns: 92px minmax(0, 1fr) 64px; }
}
@media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto !important; } }
"""


def estudio(pj: Path, saida_dir: Path, titulo: str, sub: str, cfg: dict | None = None) -> tuple[Path, dict]:
    """Gera a página-estúdio: HTML com o app (Player + timeline + painéis) embutido e a mídia leve
    (vídeo 720p, faixas de áudio em AAC). Devolve (html, mapa de arquivos para publicar)."""
    import subprocess
    from .utils import ffmpeg
    rdir = Path(__file__).resolve().parent.parent / "remotion"
    subprocess.run(["npx", "esbuild", "src/estudio/main.tsx", "--bundle", "--minify", "--format=iife",
                    "--jsx=automatic", "--define:process.env.NODE_ENV=\"production\"", "--outfile=out/estudio/app.js"],
                   cwd=rdir, check=True, capture_output=True)
    app = (rdir / "out" / "estudio" / "app.js").read_text(encoding="utf-8")
    proj = json.loads(pj.read_text(encoding="utf-8"))
    proj.pop("alteracoes", None)   # o estúdio parte da base; as alterações vêm do banco da página
    saida_dir.mkdir(parents=True, exist_ok=True)
    (saida_dir / "midia").mkdir(exist_ok=True)
    arquivos = {}

    def leve(src: Path, rel: str, audio: bool):
        dst = saida_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg("-i", str(src), "-vf", "scale=720:-2", "-c:v", "libx264", "-crf", "25", "-preset", "veryfast",
               "-pix_fmt", "yuv420p", "-g", "15", *(["-c:a", "aac", "-b:a", "128k"] if audio else ["-an"]),
               "-movflags", "+faststart", str(dst))
        arquivos[rel] = str(dst)

    def som(src: Path, rel: str, kbps: int = 128):
        dst = saida_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg("-i", str(src), "-c:a", "aac", "-b:a", f"{kbps}k", "-ar", "48000", str(dst))
        arquivos[rel] = str(dst)
        return rel

    leve(pj.parent / proj["base"], "base.mp4", not proj.get("audio"))
    for c in proj["camadas"]:
        if c.get("arquivo"):
            leve(pj.parent / c["arquivo"], c["arquivo"], False)
    a = proj.get("audio")
    if a:
        a["voz"] = som(pj.parent / a["voz"], a["voz"].rsplit(".", 1)[0] + ".m4a")
        if a.get("trilha"):
            a["trilha"] = som(pj.parent / a["trilha"], a["trilha"].rsplit(".", 1)[0] + ".m4a")
        for s in a["sfx"]:
            s["arquivo"] = som(pj.parent / s["arquivo"], s["arquivo"].rsplit(".", 1)[0] + ".m4a", 96)
    if cfg:
        proj["looks"] = {k: dict(v) for k, v in (cfg.get("cor") or {}).get("looks", {}).items()}
    proj["raiz"] = ""
    dados = json.dumps(proj, ensure_ascii=False).replace("</", "<\\/")
    html_txt = (f"<title>{html.escape(titulo)}</title>\n"
                '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
                '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Rubik:ital,wght@0,400;0,500;0,700;0,800;0,900;1,700'
                '&family=Noto+Serif:ital,wght@0,400;0,700;0,900;1,400;1,700;1,900'
                '&family=JetBrains+Mono:wght@400;700&family=Permanent+Marker&display=swap">\n'
                f"<style>{ESTUDIO_CSS}</style>\n"
                '<div id="app"></div>\n'
                f"<script>window.PROJETO = {dados};</script>\n"
                f"<script>{app}</script>\n")
    out = saida_dir / "estudio.html"
    out.write_text(html_txt, encoding="utf-8")
    return out, arquivos
