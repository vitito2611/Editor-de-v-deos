"""ETAPA 11 — Orquestração do pipeline completo.

  entrada (cópia de trabalho; o original nunca é tocado)
  → análise inicial → transcrição → NLP
  → limpeza da voz (Etapa 7) → corte de silêncios (Etapa 3, revisão opcional)
  → técnicas de corte (Etapa 4, modo automático ou sugestão)
  → trilha: escolha + beats (Etapa 9) → beat cuts
  → correção de cor (Etapa 6) → render dos segmentos e montagem
  → legendas (Etapa 5) + motion graphics (Etapa 10)
  → SFX (Etapa 8) → mix com ducking → master (-14 LUFS)
  → composição final e exportação por plataforma → relatório

A voz é limpa ANTES da detecção de silêncio porque a redução de ruído melhora o VAD;
o resultado final é o mesmo da ordem descrita no briefing.
"""
from __future__ import annotations

import hashlib
from fractions import Fraction
import shutil
from pathlib import Path

import numpy as np
import yaml

from . import analysis, audio, cinematic, color, motion, music, nlp, render, sfx, silence, subtitles, transcribe
from .config import load_config
from .timeline import layout_times, map_words, snap_clips
from .utils import ROOT, Timer, ffmpeg, load_audio, log, probe, read_json, setup_logging, write_json


class Parada(Exception):
    """Interrupção intencional (revisão manual / modo sugestão)."""


def _rot90(src: Path) -> bool:
    from .utils import run as _run
    p = _run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
              "stream_side_data=rotation", "-of", "csv=p=0", str(src)])
    try:
        vals = [v for v in (p.stdout or "").replace(",", " ").split() if v.lstrip("-").isdigit()]
        return any(abs(int(v)) in (90, 270) for v in vals)
    except (ValueError, IndexError):
        return False


def _normalize_source(src: Path, g: dict) -> Path:
    """Fonte intermediária ("mezanino") quando necessário:
    • HDR (HLG / PQ, ex.: iPhone Dolby Vision) → SDR Rec.709 com tone mapping (hable)
    • resolução acima de fonte_max_altura → reduz (mantém margem para zoom) e
    • FPS acima de fps_max → reduz (renders muito mais rápidos)
    Sem isso, vídeo HDR fica lavado/estourado e 4K60 deixa o render lento."""
    from .utils import run as _run
    p = _run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
              "stream=color_transfer,width,height,r_frame_rate", "-of", "json", str(src)])
    import json as _json
    st = _json.loads(p.stdout)["streams"][0]
    trc = st.get("color_transfer", "")
    hdr = g.get("hdr_para_sdr", True) and trc in ("arib-std-b67", "smpte2084")
    w, h = int(st["width"]), int(st["height"])
    if _rot90(src):
        w, h = h, w          # iPhone grava deitado + flag de rotação; o FFmpeg gira antes dos filtros
    num, den = map(int, st["r_frame_rate"].split("/"))
    fps = num / den
    maxh = g.get("fonte_max_lado", 2560)
    fmax = g.get("fps_max", 30)
    scale = max(w, h) > maxh
    slow = fmax and fps > fmax + 0.5
    if not (hdr or scale or slow):
        return src
    # cache compartilhado entre estilos/plataformas (mesmo bruto = mesmo mezanino)
    cache = ROOT / "work" / "_fontes"
    cache.mkdir(parents=True, exist_ok=True)
    dst = cache / f"{_cache_key(src, 'mez2')}_mezanino.mp4"
    if dst.exists():
        log.info("  (cache) mezanino %s", dst.name)
        return dst
    vf = []
    if slow:
        vf.append(f"fps={fmax}")
    sw, sh = (w, h)
    if scale:
        k = maxh / max(w, h)
        sw, sh = int(round(w * k / 2) * 2), int(round(h * k / 2) * 2)
    if hdr:
        npl = 203 if trc == "arib-std-b67" else 100
        vf.append(f"zscale=w={sw}:h={sh}:tin={trc}:min=bt2020nc:pin=bt2020:rin=tv:t=linear:npl={npl},"
                  "format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,"
                  "zscale=t=bt709:m=bt709:r=tv,format=yuv420p")
    else:
        vf.append(f"scale={sw}:{sh}:flags=lanczos,format=yuv420p")
    log.info("  fonte normalizada: %s%s%s → %dx%d", "HDR→SDR " if hdr else "", f"{w}x{h} " if scale else "",
             f"{fps:.0f}→{fmax} fps" if slow else "", sw, sh)
    # intermediário: superfast + CRF 12 (≈ sem perda visível, 2x mais rápido que fast) e GOP curto
    # (os segmentos fazem seek no mezanino — com GOP 250 cada seek decodificava até 8 s)
    tmp = dst.with_suffix(".tmp.mp4")
    # Mac: o chip decodifica o HEVC 10-bit do iPhone por hardware (VideoToolbox) — a etapa mais lenta na nuvem
    import sys as _sys
    hw = ["-hwaccel", "videotoolbox"] if _sys.platform == "darwin" else []
    ffmpeg(*hw, "-i", str(src), "-vf", ",".join(vf), "-c:v", "libx264", "-crf", "12", "-preset", "superfast", "-g", "15",
           "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
           "-c:a", "aac", "-b:a", "256k", "-map_metadata", "-1", str(tmp))
    tmp.replace(dst)
    return dst


def _remove_bars(src: Path, enabled: bool) -> Path:
    """Detecta tarjas pretas embutidas (ex.: 16:9 dentro de 9:16) e gera uma cópia só com a
    área ativa. Sem isso o reframe/zoom trataria as tarjas como imagem."""
    if not enabled:
        return src
    import re as _re
    from .utils import run as _run
    m = probe(src)
    found = []
    for k in range(1, 7):   # 6 amostras de 3 frames ao longo do vídeo (antes: decodificava tudo)
        t = m["duracao"] * k / 7
        p = _run(["ffmpeg", "-hide_banner", "-nostdin", "-ss", f"{t:.2f}", "-i", str(src), "-an", "-frames:v", "3",
                  "-vf", "cropdetect=limit=24:round=2:reset=0", "-f", "null", "-"])
        found += _re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", p.stderr)[-1:]
    if found:   # a maior área ativa vista (uma cena escura não pode "inventar" tarja)
        found = [max(found, key=lambda c: int(c[0]) * int(c[1]))]
    if not found:
        return src
    w, h, x, y = map(int, found[-1])
    if w * h > 0.93 * m["largura"] * m["altura"] or w < 64 or h < 64:
        return src
    dst = src.with_name(src.stem + "_ativa.mp4")
    if not dst.exists():
        log.info("  tarjas pretas detectadas → área ativa %dx%d+%d+%d", w, h, x, y)
        ffmpeg("-i", str(src), "-vf", f"crop={w}:{h}:{x}:{y}", "-c:v", "libx264", "-crf", "12", "-preset", "superfast", "-g", "15",
               "-c:a", "copy", str(dst))
    return dst


def _prepare_sources(inputs: list[Path], work: Path, remove_bars: bool = True) -> tuple[Path, list[float]]:
    """Copia a(s) entrada(s) para a pasta de trabalho. Várias entradas são unidas em uma
    fonte normalizada; as junções viram trocas de plano."""
    if len(inputs) == 1:
        dst = work / f"fonte{inputs[0].suffix.lower()}"
        if dst.is_symlink() or dst.exists():
            dst.unlink()
        try:
            dst.symlink_to(inputs[0].resolve())
        except OSError:
            shutil.copy2(inputs[0], dst)
        return _remove_bars(dst, remove_bars), []
    m0 = probe(inputs[0])
    dst = work / "fonte.mp4"
    args, fc, bounds, t = [], [], [], 0.0
    for i, p in enumerate(inputs):
        args += ["-i", str(p)]
        fc.append(f"[{i}:v]scale={m0['largura']}:{m0['altura']}:force_original_aspect_ratio=decrease,"
                  f"pad={m0['largura']}:{m0['altura']}:(ow-iw)/2:(oh-ih)/2,fps={m0['fps_float']},setsar=1[v{i}];"
                  f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo[a{i}]")
        t += probe(p)["duracao"]
        bounds.append(t)
    fc.append("".join(f"[v{i}][a{i}]" for i in range(len(inputs))) + f"concat=n={len(inputs)}:v=1:a=1[v][a]")
    if not dst.exists():
        ffmpeg(*args, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]", "-c:v", "libx264",
               "-crf", "14", "-preset", "fast", "-c:a", "pcm_s16le", str(dst.with_suffix(".mkv")))
        dst.with_suffix(".mkv").rename(dst)
    return _remove_bars(dst, remove_bars), bounds[:-1]


def _cache_key(p: Path, extra: str) -> str:
    st = p.stat()
    return hashlib.md5(f"{st.st_size}-{st.st_mtime_ns}-{extra}".encode()).hexdigest()[:10]


def run(inputs: list[Path], estilo: str | None, plataforma: str, config: Path | None = None,
        overrides: list[str] | None = None, preview: bool = False, usar_revisao: bool = False,
        revisar: bool = False, modo: str | None = None, saida: Path | None = None) -> dict:
    cfg = load_config(estilo, config, overrides)
    if modo:
        cfg["cortes"]["modo"] = modo
    if revisar:
        cfg["silencio"]["revisao_manual"] = True
    if plataforma not in cfg["plataformas"]:
        raise ValueError(f"Plataforma '{plataforma}' inválida. Opções: {list(k for k in cfg['plataformas'] if isinstance(cfg['plataformas'][k], dict))}")
    plat = cfg["plataformas"][plataforma]
    nome = inputs[0].stem
    tag = f"{nome}_{cfg.get('_estilo', 'padrao')}_{plataforma}"
    work = ROOT / cfg["geral"]["pasta_trabalho"] / tag
    outdir = ROOT / cfg["geral"]["pasta_saida"]
    for d in (work, work / "segmentos", work / "revisao", outdir):
        d.mkdir(parents=True, exist_ok=True)
    setup_logging("INFO", work / "pipeline.log")
    timer = Timer()
    rep: dict = {"entrada": [str(p) for p in inputs], "estilo": cfg.get("_estilo"), "plataforma": plataforma,
                 "preview": preview}
    threads = cfg["geral"]["threads"]

    # ------------------------------------------------------------------ análise
    with timer.etapa("Análise inicial"):
        src, joins = _prepare_sources(inputs, work, False)
        # saída 4K precisa do bruto em resolução cheia (o mezanino normal é 1440p)
        geral = dict(cfg["geral"], fonte_max_lado=max(cfg["geral"].get("fonte_max_lado", 2560), plat["largura"], plat["altura"]))
        src = _remove_bars(_normalize_source(src, geral), cfg["geral"].get("remover_tarjas", True))
        akey = _cache_key(src, "analise1")
        afile = work / "analise.json"
        if afile.exists() and read_json(afile).get("chave") == akey:
            an = read_json(afile)["an"]
            an["meta"]["fps"] = Fraction(an["meta"]["fps"])
            log.info("  (cache) análise da fonte")
        else:
            an = analysis.analyze(src)
            write_json(afile, {"chave": akey, "an": dict(an, meta=dict(an["meta"], fps=str(an["meta"]["fps"])))})
        an["planos"] = sorted(set(an["planos"] + joins))
        meta = an["meta"]
        dur = meta["duracao"]
        fps = meta["fps"]
        rep["analise"] = an
    # ------------------------------------------------------------------ transcrição
    with timer.etapa("Transcrição"):
        key = _cache_key(src, cfg["transcricao"]["motor"])
        tfile = work / "transcricao.json"
        if tfile.exists() and read_json(tfile).get("chave") == key:
            words = read_json(tfile)["palavras"]
            log.info("  (cache) %d palavras", len(words))
        else:
            words = transcribe.transcribe(load_audio(src, 16000), cfg["transcricao"], threads)
            write_json(tfile, {"chave": key, "palavras": words})
        words = transcribe.apply_corrections(words, cfg["transcricao"].get("correcoes"))
        transcribe.to_srt(words, work / "transcricao.srt")
    with timer.etapa("Análise de linguagem (NLP)"):
        nres = nlp.annotate(words, cfg)
        frases = nres["frases"]
        write_json(work / "nlp.json", {k: v for k, v in nres.items() if k != "palavras"})
    # ------------------------------------------------------------------ áudio: limpeza
    with timer.etapa("Correção de áudio (limpeza da voz)"):
        sr = cfg["audio"]["taxa_amostragem"]
        vwav = work / "voz_limpa.wav"
        rep["audio_limpeza"] = audio.clean_voice(src, an, cfg, vwav)
        voice = load_audio(vwav, sr)
    # ------------------------------------------------------------------ silêncios
    from .vision import FrameReader
    frames = FrameReader(src)
    with timer.etapa("Corte inteligente de silêncios"):
        from scipy.signal import resample_poly
        v16 = resample_poly(voice, 160, sr // 100).astype(np.float32)
        if cfg["silencio"]["ativo"]:
            sres = silence.detect(v16, words, frases, dur, cfg, frames)
        else:
            sres = {"pausas": [], "manter": [[0.0, dur]], "limiar_db": 0, "rms_db": [], "hop": 0.02}
        rev = work / "revisao" / "cortes_silencio.yaml"
        if usar_revisao and rev.exists():
            sres = silence.load_review(rev, sres, dur, cfg["silencio"])
        else:
            silence.write_review(sres, rev)
        # erros de gravação (recomeços, gaguejadas, muletas) — revisão em revisao/erros_gravacao.yaml
        from . import erros
        erev = work / "revisao" / "erros_gravacao.yaml"
        if usar_revisao and erev.exists():
            ecortes = yaml.safe_load(erev.read_text(encoding="utf-8")).get("erros") or []
        else:
            ecortes = erros.detectar(words, cfg)
            erev.write_text("# Erros de gravação detectados. 'aplicar: false' mantém o trecho; rode com --usar-revisao.\n"
                            + yaml.safe_dump({"erros": ecortes}, allow_unicode=True, sort_keys=False), encoding="utf-8")
        if ecortes:
            db = np.array(sres["rms_db"]) if sres.get("rms_db") else None
            antes = sum(b - a for a, b in sres["manter"])
            sres["manter"] = erros.aplicar(sres["manter"], ecortes, db, sres.get("hop", 0.02))
            log.info("  erros de gravação removidos: %.1fs", antes - sum(b - a for a, b in sres["manter"]))
        sres["erros"] = ecortes
        if sres["rms_db"]:
            silence.plot(sres, words, work / "silencio.png", dur)
        rep["silencio"] = {k: v for k, v in sres.items() if k not in ("rms_db",)}
        if cfg["silencio"]["revisao_manual"] and not usar_revisao:
            silence.preview(src, sres["manter"], work / "revisao" / "preview_cortes.mp4")
            raise Parada(f"Revisão manual: edite {rev} (preview em revisao/preview_cortes.mp4) e rode com --usar-revisao")
    # ------------------------------------------------------------------ técnicas de corte
    with timer.etapa("Técnicas de corte cinematográfico"):
        clips = cinematic.build_clips(sres["manter"], words, frases, an["planos"], dur, cfg)
        snap_clips(clips, fps)
        clips = [c for c in clips if c.dur > 1.5 / float(fps)]
        cinematic.attach_faces(clips, frames)
        brolls = motion.find_broll(words, cfg)
        decisions = cinematic.decide(clips, words, frases, cfg, frames,
                                     broll_spans=[(b["s_src"], b["e_src"]) for b in brolls])
        trev = work / "revisao" / "tecnicas.yaml"
        if usar_revisao and trev.exists():
            decisions = cinematic.load_review(trev, decisions)
        else:
            cinematic.write_review(decisions, trev)
            if cfg["cortes"]["modo"] == "sugestao":
                raise Parada(f"Modo sugestão: revise {trev} e rode com --usar-revisao")
        cinematic.apply(clips, decisions, fps)
        total = layout_times(clips, fps)
    # ------------------------------------------------------------------ trilha + beat cut
    with timer.etapa("Trilha sonora (escolha e beats)"):
        words_out = map_words(clips, words)
        frases_out = _map_frases(frases, words_out)
        mplan = None
        if cfg["musica"]["ativo"]:
            mplan = music.plan(total, nres["tom"], [f for f in frases_out if f["s"] is not None], cfg, sr)
            bdec = cinematic.decide_beats(clips, mplan["beats"], cfg, decisions)
            cinematic.apply_beats(clips, bdec, fps)
            decisions += bdec
            total = layout_times(clips, fps)
            words_out = map_words(clips, words)
            frases_out = _map_frases(frases, words_out)
        # limite de duração da plataforma
        lim = plat.get("duracao_max_s")
        if lim and total > lim:
            if cfg["plataformas"]["ao_exceder_duracao"] == "cortar":
                ends = [f["e"] for f in frases_out if f["e"] and f["e"] <= lim]
                cut = max(ends) + 0.3 if ends else lim
                clips = [c for c in clips if c.out_start < cut]
                clips[-1].a_out = clips[-1].a_in + (cut - clips[-1].out_start)
                clips[-1].v_out = clips[-1].v_in + clips[-1].dur
                snap_clips(clips, fps)
                total = layout_times(clips, fps)
                words_out = [w for w in words_out if w["s"] < total]
                log.warning("  duração cortada para %.1fs (limite %ss)", total, lim)
            else:
                log.warning("  ⚠ duração %.1fs excede o limite de %ss da plataforma %s", total, lim, plataforma)
        rep["tecnicas"] = {"decisoes": decisions, "resumo": cinematic.summarize(decisions)}
        write_json(work / "decisoes_tecnicas.json", decisions)
        log.info("  técnicas: %s", rep["tecnicas"]["resumo"])
        log.info("  duração: %.1fs → %.1fs", dur, total)
    # ------------------------------------------------------------------ cor + render
    scale = (cfg["preview"]["altura"] / max(plat["largura"], plat["altura"])) if preview else 1.0
    g = render.compute_geometry(meta, plat, cfg, scale)
    with timer.etapa("Correção de cor"):
        shot_stats = color.analyze_shots(clips, frames, cfg)
        primary = color.primary_filters(shot_stats, cfg)
        lut = color.lut_filter(cfg)
        rep["cor"] = {"layout": g.mode, "conteudo": [g.content_x, g.content_y, g.content_w, g.content_h, g.canvas_w, g.canvas_h], "look": cfg["cor"]["look"], "primaria": {str(k): v for k, v in primary.items()}}
    with timer.etapa("Render dos segmentos e montagem"):
        segdir = work / "segmentos"
        segdir.mkdir(parents=True, exist_ok=True)
        jobs = render.build_jobs(clips, [src], g, primary, segdir)
        # com o projeto Remotion (layout cheio), cor/grão/vinheta vão direto nos segmentos: o vídeo
        # base do Remotion vira só "montado + áudio" (sem um encode inteiro a mais)
        from . import remotion_fx as _rfx
        cor_nos_segmentos = (not preview and bool(_rfx.elementos(cfg)) and _rfx.cfg_of(cfg).get("edicao", True)
                             and g.mode not in ("letterbox", "blur_fill"))
        if cor_nos_segmentos:
            post = [x for x in (lut, f"noise=alls={int(cfg['motion']['grao'])}:allf=t" if cfg["motion"].get("grao") else "",
                                "vignette=PI/5" if cfg["motion"].get("vinheta") else "") if x]
            if post:
                for j in jobs:
                    j["filtro"] = j["filtro"] + "," + ",".join(post)
        # remove só segmentos que não fazem mais parte da edição (os iguais são reaproveitados)
        vivos = {Path(j["out"]).name for j in jobs} | {Path(j["out"]).with_suffix(".sig").name for j in jobs}
        for f in segdir.glob("*"):
            if f.name not in vivos:
                f.unlink()
        render.render_segments(jobs, g.fps, threads, preview)
        montado = render.assemble(jobs, g.fps, segdir / "montado.mp4", preview)
        vdur = probe(montado)["duracao"]
        log.info("  %d segmentos, vídeo montado %.2fs (timeline %.2fs)", len(jobs), vdur, total)
    # ------------------------------------------------------------------ dinamismo (B-roll, fotos, cards)
    dyn_events, creditos = [], []
    if (cfg.get("dinamismo") or {}).get("ativo"):
        with timer.etapa("Dinamismo: B-roll, fotos e cards de motion"):
            from . import dinamismo
            plano = dinamismo.plan(words_out, frases_out, cfg, total)
            dyn_events, creditos = dinamismo.fetch_and_render(plano, cfg, g, montado, work)
            rep["dinamismo"] = [{k: (str(v) if isinstance(v, Path) else v) for k, v in e.items()} for e in dyn_events]
            rep["creditos"] = creditos
    # ------------------------------------------------------------------ ângulos de câmera por IA (Seedance)
    if (cfg.get("angulos") or {}).get("ativo"):
        with timer.etapa("Ângulos de IA (plano / inserção)"):
            from . import angulos
            pp = angulos.preparar(clips, src, work, cfg)
            ang = angulos.eventos(clips, work, cfg, g)
            # não sobrepõe B-roll/fotos/cards já planejados
            ang = [e for e in ang if not any(e["t"] < o["t"] + o["dur"] and o["t"] < e["t"] + e["dur"] for o in dyn_events)]
            dyn_events = dyn_events + ang
            rep["angulos"] = {"plano": str(pp) if pp else None, "inseridos": [{k: (str(v) if isinstance(v, Path) else v) for k, v in e.items()} for e in ang]}
    faces = [(c.out_start, c.out_start + c.dur, render.face_in_canvas(c, c._win, g)) for c in clips]
    faces = [f for f in faces if f[2]]
    # ------------------------------------------------------------------ áudio: mix
    with timer.etapa("Efeitos sonoros, trilha (ducking) e masterização"):
        vtrack = audio.assemble(clips, voice, sr, fps, cfg["audio"]["crossfade_corte_ms"])
        n = int(round(total * sr))
        vtrack = np.pad(vtrack, (0, max(0, n - len(vtrack))))[:n]
        vdb, vact = audio.voice_envelope(vtrack, sr)
        mtrack = None
        if mplan:
            smash_t = [c.out_start for c in clips if "smash_cut" in c.tags and cfg["cortes"]["smash_cut"]["corte_musica_s"] > 0]
            mtrack = music.render(mplan, total, vdb, vact, 0.02, smash_t, cfg, sr)
            rep["musica"] = {"humor": mplan["humor"], "trechos": [{k: v for k, v in s.items() if k != "entry"} for s in mplan["trechos"]],
                             "beats": len(mplan["beats"])}
        extras = []
        for e in dyn_events:   # whoosh na entrada de cada sobreposição; impacto nos cards
            if e.get("tipo") == "angulo_ia":
                continue           # troca de ângulo é corte seco, como numa multicâmera real
            extras.append((e["t"], "transicao", f"entrada {e['tipo']}", 2.5))
            if e["tipo"] == "card":
                extras.append((e["t"] + 0.12, "impacto", "card de impacto", 2.2))
        zc = [c for c in clips if "jump_zoom" in c.tags]
        if cfg["sfx"].get("punchin", True):
            extras += [(c.out_start, "transicao", "punch-in", 0.6) for c in zc[::2]]
        events = sfx.plan(clips, decisions, words_out, frases_out, total, cfg, sr, extras)
        rep["sfx"] = [{k: v for k, v in e.items() if k != "audio"} for e in events]
        amaster, minfo = audio.mix_and_master(vtrack, mtrack, events, sr, cfg, plat, work)
        rep["audio_master"] = minfo
    # ------------------------------------------------------------------ legendas + motion
    with timer.etapa("Legendas dinâmicas e motion graphics"):
        for c in nres["callouts"]:
            c["t_out"] = next((w["s"] for w in words_out if w["i"] >= frases[c["sent"]]["w0"]), None)
        for nn in nres["numeros"]:
            nn["t_out"] = next((w["s"] for w in words_out if w["i"] == nn["i"]), None)
        from . import remotion_fx
        externos = remotion_fx.elementos(cfg)   # elementos desenhados pelo Remotion (React)

        def montar_ass(externos):
            doc = subtitles.AssDoc(g.canvas_w, g.canvas_h)
            jobs, card_spans = [], []
            if dyn_events:
                from . import dinamismo
                card_spans = dinamismo.ass_cards(doc, dyn_events, words_out, g, cfg,
                                                 jobs=jobs if "card" in externos else None)
                # durante o motion o texto já está na tela: a legenda falada não se repete por cima
                card_spans = card_spans + [(e["t"], e["t"] + e["dur"]) for e in dyn_events if e["tipo"] == "motion"]
            rep["legendas"] = subtitles.build(words_out, frases_out, g, faces, cfg, doc, pular=card_spans)
            rep["motion"] = motion.build(doc, g, nres, words_out, frases_out, faces, cfg, total, externos, jobs)
            return doc, jobs, card_spans

        doc, rjobs, card_spans = montar_ass(externos)
        # modo projeto: a edição vira uma composição Remotion (Studio/Player) e o final sai dela
        modo_projeto = bool(externos) and remotion_fx.cfg_of(cfg).get("edicao", True) and not preview
        motion_clips = []
        if externos and not modo_projeto:
            motion_clips = remotion_fx.render(rjobs, g, cfg, work)
            if motion_clips is None:   # falhou → mesmos elementos em ASS
                doc, rjobs, card_spans = montar_ass(set())
                motion_clips = []
            rep["remotion"] = [{"tipo": c["tipo"], "t": c["t"], "dur": c["dur"]} for c in motion_clips]
        ass = work / "legendas.ass"
        doc.write(ass)
        overlays = []
        if cfg["motion"]["borda_filme"]:
            overlays.append({"arquivo": motion.film_border(g, work / "moldura.png")})
        broll_out = []
        for b in brolls:
            from .timeline import src_to_out
            t = src_to_out(clips, 0, b["s_src"])
            if t is not None:
                broll_out.append({"t": t, "dur": min(cfg["motion"]["broll"]["duracao_s"], total - t), "arquivo": b["arquivo"]})
        broll_out += [{"t": e["t"], "dur": e["dur"], "arquivo": e["arquivo"], "corte_seco": e.get("corte_seco", False)}
                      for e in dyn_events]
        rep["broll"] = [{"t": round(b["t"], 2), "arquivo": str(b["arquivo"])} for b in broll_out]
    # ------------------------------------------------------------------ composição final
    with timer.etapa("Composição final e exportação"):
        suffix = "_preview" if preview else ""
        out = Path(saida) if saida else outdir / f"{tag}{suffix}.mp4"
        feito = False
        if modo_projeto:
            from . import projeto
            base = work / "base.mp4"   # cortes + zoom + cor + áudio, sem camadas (intermediário de alta qualidade)
            if cor_nos_segmentos and not overlays:
                # a cor já está nos segmentos: só junta vídeo + áudio, sem recodificar o vídeo
                ffmpeg("-i", str(montado), "-i", str(amaster), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                       "-c:a", "aac", "-b:a", "256k", "-t", f"{total:.3f}", str(base))
            else:
                render.compose(montado, amaster, None, g, cfg, dict(plat, crf=14, preset="veryfast"), base,
                               "" if cor_nos_segmentos else lut, [], overlays, preview, total)
            pj = projeto.exportar(Path(out).stem.replace("_com_trilha", ""), g, total, base, lut, cfg, words_out,
                                  faces, dyn_events, rjobs, card_spans, lut_fundo_card=not cor_nos_segmentos,
                                  estilos_log=rep.get("legendas"))
            rep["projeto_remotion"] = str(pj)
            feito = projeto.renderizar(pj, out, plat["crf"])
            if not feito:   # sem Remotion funcional: mesmos elementos em ASS pelo FFmpeg
                doc, rjobs, card_spans = montar_ass(set())
                doc.write(ass)
        if not feito:
            cfg_c = cfg
            if modo_projeto and cor_nos_segmentos:   # cor/grão já aplicados nos segmentos
                cfg_c = dict(cfg, motion=dict(cfg["motion"], grao=0, vinheta=False))
            render.compose(montado, amaster, ass if cfg["legendas"]["ativo"] or rep["motion"] else None, g, cfg_c, plat,
                           out, "" if (modo_projeto and cor_nos_segmentos) else lut, broll_out, overlays, preview, total,
                           motion_clips)
        fin = probe(out)
        loud = analysis.loudness_stats(out)
        rep["saida"] = {"arquivo": str(out), "duracao": fin["duracao"], "resolucao": f"{fin['largura']}x{fin['altura']}",
                        "lufs": loud["lufs"], "true_peak": loud["true_peak"], "lra": loud["lra"]}
        log.info("  ✅ %s  (%.1fs, %s, %.1f LUFS, TP %.1f)", out, fin["duracao"], rep["saida"]["resolucao"],
                 loud["lufs"] or 0, loud["true_peak"] or 0)
        # versão sem trilha (cliente põe a música em alta no app): mesmo vídeo, só troca o áudio
        if cfg["geral"].get("versao_sem_trilha", True) and mtrack is not None and not preview:
            asem, _ = audio.mix_and_master(vtrack, None, events, sr, cfg, plat, work, nome="audio_master_sem_trilha")
            out_sem = out.with_name(out.stem.replace("_com_trilha", "") + "_sem_trilha.mp4")
            ffmpeg("-i", str(out), "-i", str(asem), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
                   "-b:a", f"{plat['audio_kbps']}k", "-ar", "48000", "-movflags", "+faststart", "-shortest", str(out_sem))
            rep["saida"]["sem_trilha"] = str(out_sem)
            log.info("  ✅ %s  (mesmo vídeo, sem música)", out_sem)
    # ------------------------------------------------------------------ relatório
    rep["tempos"] = timer.etapas
    from .report import write_report
    write_report(rep, src, clips, out, work, cfg, frames)
    if not cfg["geral"]["manter_intermediarios"]:
        shutil.rmtree(work / "segmentos", ignore_errors=True)
    return rep


def _map_frases(frases: list[dict], words_out: list[dict]) -> list[dict]:
    by_sent: dict[int, list[dict]] = {}
    for w in words_out:
        by_sent.setdefault(w["sent"], []).append(w)
    out = []
    for f in frases:
        ws = by_sent.get(f["id"])
        nf = dict(f)
        nf["s"], nf["e"] = (ws[0]["s"], ws[-1]["e"]) if ws else (None, None)
        out.append(nf)
    return out
