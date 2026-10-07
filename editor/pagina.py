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
ESTUDIO_CSS = """
/* Layout: mesa de edição — monitor 9:16 + inspetor no topo, timeline de trilhas embaixo (como o Remotion Studio) */
:root {
  --bg: #121416; --painel: #1a1d20; --linha: #2b3035; --fg: #eceeee; --suave: #9aa3a8; --acento: #e8e2d6;
  --broll: #3a4a5c; --motion: #5c4a3a; --legenda: #3d4a3f; --sel: #e8e2d6;
  --f-titulo: "Archivo", "Helvetica Neue", Arial, sans-serif; --f-mono: "JetBrains Mono", ui-monospace, Menlo, monospace;
  --nome-w: 120px; color-scheme: dark;
}
body { background: var(--bg); color: var(--fg); font-family: var(--f-titulo); }
.wrap { max-width: 1180px; margin: 0 auto; padding-inline: 16px; padding-block: 20px 40px; display: grid; gap: 18px; }
header h1 { margin: 0; font-weight: 800; font-size: clamp(1.4rem, 3.5vw, 2.1rem); text-wrap: balance; }
header p { margin: 6px 0 0; color: var(--suave); max-width: 70ch; line-height: 1.5; }
.estudio { display: grid; gap: 16px; }
.topo { display: grid; grid-template-columns: minmax(0, 340px) minmax(0, 1fr); gap: 20px; align-items: start; }
.monitor { background: #000; border: 1px solid var(--linha); border-radius: 6px; overflow: hidden; max-width: 100%; }
.inspetor { display: grid; gap: 14px; background: var(--painel); border: 1px solid var(--linha); border-radius: 6px; padding: 16px; min-width: 0; }
.vazio h2 { margin: 0 0 6px; font-size: 1rem; }
.vazio p, .motivo { color: var(--suave); margin: 0 0 6px; line-height: 1.5; font-size: 0.9rem; }
.ficha { display: grid; gap: 12px; }
.ficha-topo { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.tag { font-family: var(--f-mono); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em; padding: 3px 8px; border: 1px solid var(--linha); border-radius: 3px; }
.link { all: unset; cursor: pointer; font-family: var(--f-mono); font-size: 0.82rem; color: var(--acento); text-decoration: underline; }
.campo { display: grid; gap: 5px; font-size: 0.82rem; color: var(--suave); min-width: 0; }
.campo em { font-style: normal; opacity: 0.8; }
.campo input, .campo textarea { font: 0.95rem var(--f-titulo); color: var(--fg); background: var(--bg); border: 1px solid var(--linha); border-radius: 4px; padding: 8px 10px; width: 100%; box-sizing: border-box; resize: vertical; }
.campo input:focus, .campo textarea:focus, .bloco:focus-visible, button:focus-visible { outline: 2px solid var(--acento); outline-offset: 1px; }
.linha { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.check { display: flex; gap: 8px; align-items: center; font-size: 0.9rem; }
.acoes { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.primario { font: 700 0.9rem var(--f-titulo); background: var(--acento); color: #121416; border: 0; border-radius: 4px; padding: 10px 16px; cursor: pointer; }
.primario:disabled { opacity: 0.45; cursor: default; }
.estado { color: var(--suave); font-size: 0.85rem; }
.timeline { position: relative; background: var(--painel); border: 1px solid var(--linha); border-radius: 6px; padding: 10px 12px 12px; overflow-x: auto; }
.regua { position: relative; height: 18px; margin-left: var(--nome-w); font-family: var(--f-mono); font-size: 0.7rem; color: var(--suave); min-width: 640px; }
.regua span { position: absolute; transform: translateX(-2px); font-variant-numeric: tabular-nums; }
.trilha { display: grid; grid-template-columns: var(--nome-w) minmax(640px, 1fr); align-items: center; min-height: 34px; border-top: 1px solid var(--linha); }
.nome-trilha { font-family: var(--f-mono); font-size: 0.72rem; color: var(--suave); text-transform: uppercase; letter-spacing: 0.05em; padding-right: 8px; }
.faixa { position: relative; height: 28px; }
.bloco { position: absolute; top: 3px; height: 22px; border: 1px solid transparent; border-radius: 3px; cursor: pointer; padding: 0 5px; overflow: hidden; color: var(--fg); font: 0.7rem var(--f-titulo); text-align: left; white-space: nowrap; box-sizing: border-box; }
.bloco span { overflow: hidden; text-overflow: ellipsis; display: block; line-height: 20px; }
.t-broll, .t-foto { background: var(--broll); }
.t-card, .t-contador, .t-callout, .t-gancho { background: var(--motion); }
.t-legenda { background: var(--legenda); }
.bloco.sel { border-color: var(--sel); }
.bloco.editado::after { content: ""; position: absolute; right: 3px; top: 3px; width: 6px; height: 6px; border-radius: 50%; background: var(--acento); }
.bloco.oculto { opacity: 0.35; text-decoration: line-through; }
.cabeca { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--acento); pointer-events: none; margin-left: 12px; }
@media (max-width: 760px) { .topo { grid-template-columns: minmax(0, 1fr); } .monitor { max-width: 300px; margin: 0 auto; width: 100%; } :root { --nome-w: 84px; } }
"""


def estudio(pj: Path, saida_dir: Path, titulo: str, sub: str) -> tuple[Path, dict]:
    """Gera a página-estúdio: HTML com o app (Player + timeline) embutido e a mídia em 720p.
    Devolve (html, mapa de arquivos para publicar)."""
    import subprocess
    from .utils import ffmpeg
    rdir = Path(__file__).resolve().parent.parent / "remotion"
    subprocess.run(["npx", "esbuild", "src/estudio/main.tsx", "--bundle", "--minify", "--format=iife",
                    "--jsx=automatic", "--define:process.env.NODE_ENV=\"production\"", "--outfile=out/estudio/app.js"],
                   cwd=rdir, check=True, capture_output=True)
    app = (rdir / "out" / "estudio" / "app.js").read_text(encoding="utf-8")
    proj = json.loads(pj.read_text(encoding="utf-8"))
    saida_dir.mkdir(parents=True, exist_ok=True)
    (saida_dir / "midia").mkdir(exist_ok=True)
    arquivos = {}

    def leve(src: Path, rel: str, audio: bool):
        dst = saida_dir / rel
        ffmpeg("-i", str(src), "-vf", "scale=720:-2", "-c:v", "libx264", "-crf", "25", "-preset", "veryfast",
               "-pix_fmt", "yuv420p", *(["-c:a", "aac", "-b:a", "128k"] if audio else ["-an"]),
               "-movflags", "+faststart", str(dst))
        arquivos[rel] = str(dst)

    leve(pj.parent / proj["base"], "base.mp4", True)
    for c in proj["camadas"]:
        if c.get("arquivo"):
            leve(pj.parent / c["arquivo"], c["arquivo"], False)
    proj["raiz"] = ""
    dados = json.dumps(proj, ensure_ascii=False).replace("</", "<\\/")
    html_txt = (f"<meta charset=\"utf-8\"><title>{html.escape(titulo)}</title>\n"
                '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
                '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;800'
                '&family=Inter:ital,wght@0,400;0,500;0,600;0,700;0,900;1,400;1,600;1,700'
                '&family=JetBrains+Mono:wght@400;700&family=Permanent+Marker&display=swap">\n'
                f"<style>{ESTUDIO_CSS}</style>\n"
                f'<div class="wrap"><header><h1>{html.escape(titulo)}</h1><p>{html.escape(sub)}</p></header>'
                '<div id="app"></div></div>\n'
                f"<script>window.PROJETO = {dados};</script>\n"
                f"<script>{app}</script>\n")
    out = saida_dir / "estudio.html"
    out.write_text(html_txt, encoding="utf-8")
    return out, arquivos
