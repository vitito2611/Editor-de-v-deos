"""Projeto Remotion da edição — para ver e editar junto (Studio / Player) e renderizar o final.

Divide a edição em:
  base.mp4   cortes, zooms, transições, cor, grão e o áudio masterizado (feito pelo FFmpeg — pesado)
  camadas    legendas, cards, contadores, títulos, B-roll e fotos (React, leves e editáveis)

Saída em remotion/public/projetos/<slug>/ (projeto.json + mídia) e a lista de composições em
remotion/src/projetos.gen.ts. No Studio (`cd remotion && npx remotion studio`) cada vídeo aparece
como uma composição com cada camada nomeada na timeline. O render final usa render-edicao.mjs.
Editar o projeto.json (texto, tempo, duração, `oculto: true`) e renderizar de novo NÃO refaz a base.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from .remotion_fx import DIR, cfg_of
from .subtitles import Placer, group_words
from .utils import ffmpeg, log

PUBLIC = DIR / "public" / "projetos"


def slug(nome: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", nome).strip("-")
    return ("Edicao-" + s)[:60]


VARIANTE = {"dinamico": "dinamico", "cinetico": "cinetico"}   # resto → "simples" (frase inteira, discreta)


def _legendas(words_out, g, faces, cfg, pular, estilos_log=None) -> list[dict]:
    """Blocos de legenda para o Remotion, respeitando o estilo de cada modelo: o estilo de cada bloco
    vem da mesma decisão das legendas ASS (base × impacto)."""
    from .subtitles import aplicar_fontes
    lc = dict(cfg["legendas"])
    estilos = aplicar_fontes(lc)
    st = estilos[lc["estilo_base"]]
    por_t = {round(r["t"], 2): r["estilo"] for r in (estilos_log or [])}
    placer = Placer(g, faces, lc)
    size = st.get("tamanho", 64) * (g.canvas_w / 1080 if g.canvas_h > g.canvas_w else g.canvas_h / 1080)
    ws = [w for w in words_out if not any(a - 0.05 <= w["s"] < b for a, b in pular)]
    grupos = group_words(ws, lc, st)
    out = []
    for k, grp in enumerate(grupos):
        t0 = grp[0]["s"]
        nxt = grupos[k + 1][0]["s"] if k + 1 < len(grupos) else grp[-1]["e"] + 0.4
        t1 = min(nxt, grp[-1]["e"] + 0.6)
        # a legenda termina onde começa um motion/card (não invade o texto da inserção)
        t1 = min([t1] + [a for a, _ in pular if a > t0 + 0.05])
        nchars = sum(len(w["w"]) + 1 for w in grp)
        nome = por_t.get(round(t0, 2), lc["estilo_base"])
        sb = estilos.get(nome, st)
        tam = sb.get("tamanho", 64)
        pos = sb.get("posicao", "peito")
        if pos == "centro":
            pos = "peito"          # preferência do cliente: legenda logo abaixo do rosto, sem cobrir a boca
        _, y = placer.anchor(pos, t0, tam * size / max(1, st.get("tamanho", 64)), nchars, 2)
        out.append({"id": f"L{k:03d}", "t": round(t0, 3), "dur": round(max(0.2, t1 - t0), 3),
                    "palavras": [{"w": w["w"], "s": round(w["s"], 3), "kw": round(w.get("kw", 0), 3)} for w in grp],
                    "y": round(y / g.canvas_h, 4), "estilo": VARIANTE.get(sb.get("animacao"), "simples"),
                    "tamanho": tam})
    return out


def cor_do_cfg(cfg: dict) -> dict:
    """Parâmetros do look (mesma conta de color._apply_look) para o filtro ao vivo do estúdio."""
    cc = cfg.get("cor") or {}
    look = cc.get("look") if cc.get("ativo", True) else None
    prm = dict((cc.get("looks") or {}).get(look) or {}) if look else {}
    mc = cfg.get("motion") or {}
    return {"look": look or "nenhum", "intensidade": float(cc.get("intensidade_look", 1.0)) if look else 0.0,
            "exposicao": 0.0, "contraste": prm.get("contraste", 0.0), "saturacao": prm.get("saturacao", 1.0),
            "vibrance": prm.get("vibrance", 0.0), "temperatura": prm.get("temperatura", 0.0), "tint": prm.get("tint", 0.0),
            "pretos": prm.get("pretos", 0.0), "sombras": list(prm.get("sombras", [0, 0, 0])),
            "luzes": list(prm.get("luzes", [0, 0, 0])), "vinheta": 0.6 if mc.get("vinheta") else 0.0,
            "grao": round(min(1.0, float(mc.get("grao") or 0) / 12), 2)}


def exportar(nome: str, g, total: float, base: Path, lut: str, cfg: dict, words_out, faces,
             dyn_events: list[dict], rjobs: list[dict], card_spans, lut_fundo_card: bool = True,
             estilos_log=None, cor_ao_vivo: bool = False, faixas: dict | None = None, master: dict | None = None) -> Path:
    """Escreve o projeto (mídia + projeto.json) e atualiza a lista de composições.
    cor_ao_vivo: a base vem SEM o look; o estúdio/Remotion aplica (editável). faixas: voz/trilha/SFX separados."""
    rc = cfg_of(cfg)
    sl = slug(nome)
    d = PUBLIC / sl
    if d.exists():
        shutil.rmtree(d)
    (d / "midia").mkdir(parents=True)
    shutil.copy2(base, d / "base.mp4")
    audio_proj = None
    if faixas:
        (d / "audio").mkdir()
        for f in [faixas["voz"], faixas.get("trilha")] + [x["arquivo"] for x in faixas["sfx"]]:
            if f:
                shutil.copy2(Path(faixas["pasta"]) / f, d / "audio" / f)
        audio_proj = {"voz": "audio/" + faixas["voz"], "trilha": "audio/" + faixas["trilha"] if faixas.get("trilha") else None,
                      "sfx": [dict(x, arquivo="audio/" + x["arquivo"]) for x in faixas["sfx"]],
                      "vol": {"voz": 0.0, "trilha": 0.0, "sfx": 0.0}, "trilha_ativa": True,
                      "ganho_master_db": round(float((master or {}).get("ganho_db", 0.0)), 2),
                      "lufs_alvo": (master or {}).get("alvo_lufs")}
    camadas = []
    cards_rem = {round(j["t"], 2): j for j in rjobs if j["tipo"] == "card"}
    for k, e in enumerate(dyn_events):
        arq = Path(e["arquivo"])
        dst = d / "midia" / f"{k:02d}_{e['tipo']}.mp4"
        # B-roll/fotos/fundos de card recebem a mesma cor (LUT) que o vídeo base
        # o fundo do card vem do próprio vídeo: se a cor já foi aplicada nos segmentos, não aplica de novo
        # motion (HyperFrames) tem a paleta própria do exemplo: não recebe o look da filmagem
        filtro = lut if (lut and not cor_ao_vivo and e["tipo"] != "motion" and (e["tipo"] != "card" or lut_fundo_card)) else "null"
        ffmpeg("-i", str(arq), "-an", "-vf", filtro, "-c:v", "libx264", "-crf", "16", "-preset", "veryfast",
               "-pix_fmt", "yuv420p", str(dst))
        c = {"id": f"C{k:02d}", "tipo": "broll" if e["tipo"] in ("video", "angulo_ia", "motion") else e["tipo"],
             "t": round(e["t"], 3), "dur": round(e["dur"], 3), "arquivo": f"midia/{dst.name}",
             "corte_seco": bool(e.get("corte_seco")), "motivo": e.get("motivo", ""), "cor": e["tipo"] != "motion"}
        if e["tipo"] == "foto":
            c["tipo"] = "broll"          # a foto já vem com Ken Burns renderizado em vídeo
            c["nome"] = f"Foto: {e.get('busca', '')}"
        elif e["tipo"] == "video":
            c["nome"] = f"B-roll: {e.get('busca', '')}"
        elif e["tipo"] == "motion":
            c["nome"] = f"Motion: {e.get('busca') or 'HyperFrames'}"
        elif e["tipo"] == "card":
            j = cards_rem.get(round(e["t"], 2))
            c["palavras"] = j["palavras"] if j else [{"w": t, "s": 0.12 * i} for i, t in enumerate((e.get("texto") or "").split())]
            c["y"] = j["y"] if j else 0.47
        camadas.append(c)
    for k, j in enumerate(x for x in rjobs if x["tipo"] != "card"):
        camadas.append(dict({kk: v for kk, v in j.items()}, id=f"M{k:02d}"))
    proj = {
        "nome": nome, "W": g.canvas_w, "H": g.canvas_h, "fps": round(float(g.fps), 3), "dur": round(total, 3),
        "raiz": f"projetos/{sl}/", "base": "base.mp4",
        "tema": dict(rc["tema"], fonte_legenda=_fonte_legenda(cfg),
                     tamanho_legenda=cfg["legendas"]["estilos"][cfg["legendas"]["estilo_base"]].get("tamanho", 64)),
        "legendas": _legendas(words_out, g, faces, cfg, card_spans, estilos_log),
        "camadas": sorted(camadas, key=lambda c: c["t"]),
        "cor": cor_do_cfg(cfg) if cor_ao_vivo else {"intensidade": 0.0},
        "audio": audio_proj,
    }
    pj = d / "projeto.json"
    pj.write_text(json.dumps(proj, ensure_ascii=False, indent=1), encoding="utf-8")
    gerar_lista()
    log.info("  projeto Remotion: %s (%d legendas, %d camadas) → Studio: cd remotion && npx remotion studio",
             sl, len(proj["legendas"]), len(proj["camadas"]))
    return pj


def _fonte_legenda(cfg) -> str:
    st = cfg["legendas"]["estilos"][cfg["legendas"]["estilo_base"]]
    return cfg["legendas"].get("fonte_base") or st.get("fonte", "Rubik")


def gerar_lista() -> None:
    itens = []
    for pj in sorted(PUBLIC.glob("*/projeto.json")):
        props = json.loads(pj.read_text(encoding="utf-8"))
        itens.append(f'  {{ id: {json.dumps(pj.parent.name)}, props: {json.dumps(props, ensure_ascii=False)} }},')
    (DIR / "src" / "projetos.gen.ts").write_text(
        "// Gerado por editor/projeto.py — um item por vídeo editado (não edite à mão).\n"
        'import type { Projeto } from "./Edicao";\n'
        "export const PROJETOS: { id: string; props: Projeto }[] = [\n" + "\n".join(itens) + "\n];\n",
        encoding="utf-8")


def renderizar(pj: Path, saida: Path, crf: int = 18, sem_trilha: Path | None = None, cfg: dict | None = None) -> bool:
    """Render final pelo Remotion (o mesmo do estúdio). Com faixas de áudio, o vídeo sai mudo do Remotion e o
    áudio é mixado aqui (mesmos volumes/cortes/SFX do estúdio) e masterizado; `sem_trilha` gera a 2ª versão."""
    log.info("  render final pelo Remotion (o mesmo do Studio)…")
    pj = Path(pj).resolve()
    proj = json.loads(pj.read_text(encoding="utf-8"))
    com_faixas = bool(proj.get("audio"))
    alvo = Path(saida).resolve()
    video = alvo.with_name(alvo.stem + "_video.mp4") if com_faixas else alvo
    props = pj
    if com_faixas:
        props = pj.with_name("projeto_render.json")
        props.write_text(json.dumps(dict(proj, sem_audio=True), ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(["node", str(DIR / "render-edicao.mjs"), str(props), str(video), str(crf)],
                       cwd=DIR, capture_output=True, text=True)
    if r.returncode != 0 or not video.exists():
        log.warning("  render Remotion falhou → composição FFmpeg. %s", (r.stderr or r.stdout)[-800:])
        return False
    if com_faixas:
        cfg = cfg or _cfg_padrao()
        for com_trilha, destino in ((True, alvo), (False, sem_trilha)):
            if destino is None:
                continue
            wav = mixar(pj, alvo.with_name(alvo.stem + ("_mix.wav" if com_trilha else "_mix_sem.wav")), cfg, com_trilha)
            ffmpeg("-i", str(video), "-i", str(wav), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
                   "-b:a", "256k", "-ar", "48000", "-movflags", "+faststart", "-shortest", str(Path(destino).resolve()))
        video.unlink(missing_ok=True)
    return True


def _cfg_padrao() -> dict:
    import yaml
    from .utils import ROOT
    return yaml.safe_load((ROOT / "config" / "default.yaml").read_text(encoding="utf-8"))


def _mapa(dur: float, cortes: list) -> list[tuple[float, float, float]]:
    """Mesma conta de remotion/src/ajustes.ts::mapaCortes → [(a, b, o)] trechos mantidos da base."""
    cs = sorted((max(0.0, min(a, b)), min(dur, max(a, b))) for a, b in (cortes or []))
    cs = [c for c in cs if c[1] - c[0] > 0.04]
    juntos: list[list[float]] = []
    for a, b in cs:
        if juntos and a <= juntos[-1][1]:
            juntos[-1][1] = max(juntos[-1][1], b)
        else:
            juntos.append([a, b])
    segs, t, o = [], 0.0, 0.0
    for a, b in juntos:
        if a > t:
            segs.append((t, a, o))
            o += a - t
        t = b
    if dur > t:
        segs.append((t, dur, o))
    return segs


def mixar(pj: Path, saida: Path, cfg: dict, com_trilha: bool = True) -> Path:
    """Mixa as faixas do projeto com as alterações do estúdio (volumes, SFX, cortes) e masteriza."""
    import numpy as np
    from .audio import masterizar
    from .utils import load_audio, save_wav
    proj = json.loads(Path(pj).read_text(encoding="utf-8"))
    a = proj["audio"]
    alt = proj.get("alteracoes") or {}
    vol = dict(a["vol"], **((alt.get("audio") or {}).get("vol") or {}))
    trilha_ativa = (alt.get("audio") or {}).get("trilha_ativa", a.get("trilha_ativa", True))
    raiz = Path(pj).parent
    sr = 48000
    segs = _mapa(proj["dur"], alt.get("cortes") or [])
    n = int(round(sum(b - a_ for a_, b, _ in segs) * sr))

    def faixa(arq: str) -> np.ndarray:
        x = load_audio(raiz / arq, sr, mono=False)
        out = np.zeros((n, 2), np.float32)
        fade = int(0.008 * sr)
        for a_, b, o in segs:
            s0, s1, d0 = int(a_ * sr), int(b * sr), int(o * sr)
            pedaco = x[s0:s1].copy()
            if len(pedaco) > 2 * fade:   # micro-fade nas emendas dos cortes (sem clique)
                rampa = np.linspace(0, 1, fade, dtype=np.float32)[:, None]
                pedaco[:fade] *= rampa
                pedaco[-fade:] *= rampa[::-1]
            e = min(n, d0 + len(pedaco))
            out[d0:e] += pedaco[: e - d0]
        return out

    mix = faixa(a["voz"]) * 10 ** (vol["voz"] / 20)
    if com_trilha and trilha_ativa and a.get("trilha"):
        mix += faixa(a["trilha"]) * 10 ** (vol["trilha"] / 20)
    mud = alt.get("sfx") or {}
    for s in a["sfx"]:
        s = dict(s, **mud.get(s["id"], {}))
        if s.get("oculto"):
            continue
        t = s["t"]
        if t >= 0:
            to = next((o + (t - a_) for a_, b, o in segs if a_ - 1e-6 <= t < b + 1e-6), None)
            if to is None:
                continue
        else:
            to = t
        clip = load_audio(raiz / s["arquivo"], sr, mono=False) * 10 ** ((s["ganho_db"] + vol["sfx"]) / 20)
        i0 = int(round(to * sr))
        if i0 < 0:
            clip, i0 = clip[-i0:], 0
        e = min(n, i0 + len(clip))
        if e > i0:
            mix[i0:e] += clip[: e - i0]
    pre = Path(saida).with_name(Path(saida).stem + "_pre.wav")
    save_wav(pre, mix, sr)
    plat = {"lufs": a.get("lufs_alvo")} if a.get("lufs_alvo") is not None else {}
    out, _ = masterizar(pre, Path(saida), sr, cfg, plat)
    return out


def aplicar(pj: Path, alt: dict) -> dict:
    """Guarda as alterações salvas no estúdio (db "edicao/atual") no projeto: a composição Remotion e a
    mixagem aplicam na hora de renderizar (a base original fica intacta, dá para voltar atrás)."""
    proj = json.loads(pj.read_text(encoding="utf-8"))
    alt = {k: v for k, v in alt.items() if k not in ("salvo_em", "por")}
    proj["alteracoes"] = alt
    pj.write_text(json.dumps(proj, ensure_ascii=False, indent=1), encoding="utf-8")
    gerar_lista()
    n = sum(len(alt.get(k) or {}) for k in ("camadas", "legendas", "sfx", "novas", "cor", "estilo_legendas"))
    log.info("  %d ajustes + %d cortes guardados no projeto%s", n, len(alt.get("cortes") or []),
             f"; pedido: {alt['pedido']}" if alt.get("pedido") else "")
    return proj


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Projeto Remotion: aplicar edições da página e renderizar")
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("aplicar")
    a.add_argument("projeto", type=Path)
    a.add_argument("alteracoes", type=Path, help="JSON salvo pela página (doc edicao/atual)")
    r = sp.add_parser("renderizar")
    r.add_argument("projeto", type=Path)
    r.add_argument("saida", type=Path)
    r.add_argument("--audio-sem-trilha", type=Path, help="gera também <saida>_sem_trilha.mp4 trocando o áudio")
    x = ap.parse_args()
    if x.cmd == "aplicar":
        aplicar(x.projeto, json.loads(x.alteracoes.read_text(encoding="utf-8")))
    elif json.loads(x.projeto.read_text(encoding="utf-8")).get("audio"):
        sem = x.saida.with_name(x.saida.stem.replace("_com_trilha", "") + "_sem_trilha.mp4")
        if renderizar(x.projeto, x.saida, sem_trilha=sem):
            print(x.saida)
            print(sem)
    else:
        if renderizar(x.projeto, x.saida) and x.audio_sem_trilha:
            sem = x.saida.with_name(x.saida.stem.replace("_com_trilha", "") + "_sem_trilha.mp4")
            ffmpeg("-i", str(x.saida), "-i", str(x.audio_sem_trilha), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                   "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(sem))
            print(sem)


if __name__ == "__main__":
    from .utils import setup_logging
    setup_logging()
    main()
