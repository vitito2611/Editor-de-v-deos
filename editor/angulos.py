"""Ângulos de câmera gerados por IA (Seedance 2.0 via MCP da Higgsfield).

Ideia (vídeo de referência da Higgsfield): o vídeo foi gravado com UMA câmera fixa; a edição
alterna o plano original com ângulos que nunca foram filmados — por cima do ombro, plongée,
macro das mãos, contra-plongée, plano geral de trás — gerados por IA a partir do próprio
trecho, mantendo a mesma pessoa, cenário, gestos e tempo da fala.

Fluxo em 3 fases (as gerações são feitas pelo agente com as ferramentas MCP da Higgsfield,
porque as credenciais vivem no MCP — ver .claude/skills/angulos-ia/SKILL.md):

  1. planejar  (automático, no pipeline com angulos.ativo: true)
     escolhe trechos de 1–2,6 s, recorta janelas de 5 s da fonte (mínimo do Seedance),
     extrai um frame de identidade e escreve work/<job>/angulos/plano.yaml com o prompt de
     câmera de cada item.
  2. gerar     (agente, MCP): media_upload → PUT → media_confirm → generate_video_batch
     (seedance_2_0; medias: video_references = janela, image_references = frame) →
     jobs_wait → baixa o resultado → python -m editor.angulos registrar <plano> <id> <arquivo>
  3. compor    (automático, no pipeline): cada item com resultado vira um corte seco para o
     ângulo de IA no tempo exato (a voz original continua por baixo).

Tudo em tempo da FONTE, então o plano continua válido se os cortes de silêncio mudarem.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from .utils import ffmpeg, log, probe

# Biblioteca de ângulos (vistos no vídeo de referência). "boca" = quanto a boca aparece:
# ângulos com boca pouco visível escondem pequenas falhas de sincronia labial da IA.
ANGULOS = {
    "ombro":       {"boca": 0, "prompt": "over-the-shoulder shot from behind him, camera placed behind his left shoulder at head height, we see the back of his head and shoulder in soft focus in the foreground and the room in front of him"},
    "plongee":     {"boca": 0, "prompt": "top-down overhead shot (bird's-eye view) looking straight down at him from the ceiling, we see the top of his head, shoulders, hands and the space around him"},
    "geral_tras":  {"boca": 0, "prompt": "wide establishing shot from the back corner of the room, showing him from behind three-quarters, his chair, the wall and the whole set, slow subtle dolly-in"},
    "maos":        {"boca": 0, "prompt": "extreme close-up macro shot of his hands gesturing while he talks, shallow depth of field, face out of frame"},
    "perfil":      {"boca": 1, "prompt": "side profile medium close-up, camera 90 degrees to his right at eye level, soft background bokeh"},
    "contra":      {"boca": 1, "prompt": "low-angle shot (worm's-eye) from below his chest looking up at him, slightly wide lens, ceiling visible behind him"},
    "tres_quartos": {"boca": 2, "prompt": "45-degree three-quarter angle medium shot from his left side, slow handheld push-in, cinematic"},
    "primeiro_plano": {"boca": 1, "prompt": "shot through out-of-focus foreground objects close to the lens, camera low and to the side, revealing him talking in the background"},
}
ORDEM_PADRAO = ["ombro", "plongee", "maos", "perfil", "geral_tras", "contra", "tres_quartos", "primeiro_plano"]

PROMPT_BASE = (
    "Re-shoot the exact same moment of the reference video from a completely different camera position: {angulo}. "
    "Keep the same person (identical face, hair, glasses, clothes), the same room, props and lighting as the reference image, "
    "and the same gestures, head movements and timing as the reference video; when the mouth is visible it moves in sync with his speech. "
    "Photorealistic real-camera footage, natural skin texture, cinematic shallow depth of field, no text, no subtitles, no logos, vertical 9:16."
)

DEFAULTS = {
    "ativo": False,
    "quantidade": 8,            # ângulos por vídeo
    "dur_min_s": 1.0,
    "dur_max_s": 2.6,
    "inicio_livre_s": 2.0,      # gancho no plano original
    "janela_s": 5,              # duração enviada ao Seedance (mínimo 4)
    "modelo": "seedance_2_0",
    "resolucao": "720p",        # 720p ≈ 22,5 créditos / 5 s; 1080p ≈ 45; mode fast 720p ≈ 12,5
    "modo": "std",
    "angulos": ORDEM_PADRAO,
    "max_boca": 2,              # 0 = só ângulos sem boca visível (mais seguro)
}


def _cfg(cfg):
    d = dict(DEFAULTS)
    d.update(cfg.get("angulos") or {})
    return d


def plan_path(work: Path) -> Path:
    return work / "angulos" / "plano.yaml"


def preparar(clips, src: Path, work: Path, cfg: dict, evitar_src: list[tuple[float, float]] | None = None) -> Path | None:
    """Escolhe os trechos e prepara janelas + frames. Não sobrescreve um plano existente."""
    ac = _cfg(cfg)
    if not ac["ativo"]:
        return None
    pp = plan_path(work)
    if pp.exists():
        return pp
    d = pp.parent
    d.mkdir(parents=True, exist_ok=True)
    dur_src = probe(src)["duracao"]
    cands = [c for c in clips if ac["dur_min_s"] <= c.dur <= ac["dur_max_s"] + 0.4 and c.out_start >= ac["inicio_livre_s"]]
    cands = [c for c in cands if not any(a - 0.3 < c.a_out and c.a_in < b + 0.3 for a, b in (evitar_src or []))]
    n = min(ac["quantidade"], len(cands))
    if n == 0:
        log.info("  ângulos IA: nenhum trecho elegível")
        return None
    # distribui ao longo do vídeo
    step = len(cands) / n
    escolhidos = [cands[int(i * step + step / 2)] for i in range(n)]
    tipos = [a for a in ac["angulos"] if ANGULOS[a]["boca"] <= ac["max_boca"]]
    itens = []
    for k, c in enumerate(escolhidos):
        a_ini = max(0.0, c.a_in - 0.4)
        a_ini = min(a_ini, max(0.0, dur_src - ac["janela_s"]))
        tipo = tipos[k % len(tipos)]
        seg = d / f"janela_{k:02d}.mp4"
        frame = d / f"frame_{k:02d}.jpg"
        ffmpeg("-ss", f"{a_ini:.3f}", "-i", str(src), "-t", str(ac["janela_s"]), "-vf", "scale=-2:1280",
               "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-c:a", "aac", "-b:a", "128k", str(seg))
        ffmpeg("-ss", f"{(c.a_in + c.a_out) / 2:.3f}", "-i", str(src), "-frames:v", "1", "-vf", "scale=-2:1280", str(frame))
        itens.append({
            "id": k, "angulo": tipo, "s_src": round(c.a_in, 3), "e_src": round(c.a_out, 3),
            "janela_ini_src": round(a_ini, 3), "janela": seg.name, "frame": frame.name,
            "prompt": PROMPT_BASE.format(angulo=ANGULOS[tipo]["prompt"]),
            "modelo": ac["modelo"], "resolucao": ac["resolucao"], "modo": ac["modo"], "duracao": ac["janela_s"],
            "status": "pendente", "job_id": None, "resultado": None, "aprovado": True,
        })
    head = ("# Plano de ângulos de IA. Gere cada item com o MCP da Higgsfield (ver .claude/skills/angulos-ia).\n"
            "# Depois: python -m editor.angulos registrar <este arquivo> <id> <video_gerado.mp4>\n"
            "# 'aprovado: false' descarta um ângulo ruim sem apagar o arquivo.\n")
    pp.write_text(head + yaml.safe_dump({"fonte": str(src), "itens": itens}, allow_unicode=True, sort_keys=False),
                  encoding="utf-8")
    log.info("  ângulos IA: plano com %d trechos → %s", len(itens), pp)
    return pp


def eventos(clips, work: Path, cfg: dict, g) -> list[dict]:
    """Itens já gerados → eventos de sobreposição (corte seco) em tempo de saída."""
    from .timeline import src_to_out
    pp = plan_path(work)
    if not _cfg(cfg)["ativo"] or not pp.exists():
        return []
    plano = yaml.safe_load(pp.read_text(encoding="utf-8"))
    out = []
    for it in plano["itens"]:
        res = it.get("resultado")
        if not res or not it.get("aprovado", True):
            continue
        res = Path(res) if Path(res).is_absolute() else pp.parent / res
        if not res.exists():
            continue
        t = src_to_out(clips, 0, it["s_src"] + 0.01)
        if t is None:
            continue
        dur = it["e_src"] - it["s_src"]
        # o vídeo gerado segue o tempo da janela: o trecho começa em (s_src - janela_ini)
        off = max(0.0, it["s_src"] - it["janela_ini_src"])
        gdur = probe(res)["duracao"]
        k = gdur / it["duracao"] if it.get("duracao") else 1.0   # se o modelo devolver outra duração
        dst = pp.parent / f"pronto_{it['id']:02d}.mp4"
        ffmpeg("-ss", f"{off * k:.3f}", "-i", str(res), "-t", f"{dur * k:.3f}", "-an", "-vf",
               f"setpts=PTS/{k:.5f},scale={g.content_w}:{g.content_h}:force_original_aspect_ratio=increase,"
               f"crop={g.content_w}:{g.content_h},fps={float(g.fps):.6f},setsar=1",
               "-c:v", "libx264", "-crf", "16", "-preset", "fast", "-pix_fmt", "yuv420p", str(dst))
        out.append({"t": round(t, 3), "dur": round(dur, 3), "arquivo": dst, "tipo": "angulo_ia",
                    "angulo": it["angulo"], "corte_seco": True})
    log.info("  ângulos IA: %d inseridos na timeline", len(out))
    return out


def registrar(plano: Path, item_id: int, arquivo: str, job_id: str | None = None) -> None:
    data = yaml.safe_load(plano.read_text(encoding="utf-8"))
    for it in data["itens"]:
        if it["id"] == item_id:
            it["resultado"] = arquivo
            it["status"] = "gerado"
            if job_id:
                it["job_id"] = job_id
    head = "".join(line + "\n" for line in plano.read_text(encoding="utf-8").splitlines() if line.startswith("#"))
    plano.write_text(head + yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Ângulos de IA: registrar resultados / ver status")
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("registrar")
    r.add_argument("plano", type=Path)
    r.add_argument("id", type=int)
    r.add_argument("arquivo")
    r.add_argument("--job")
    s = sp.add_parser("status")
    s.add_argument("plano", type=Path)
    a = ap.parse_args()
    if a.cmd == "registrar":
        registrar(a.plano, a.id, a.arquivo, a.job)
        print("ok")
    else:
        data = yaml.safe_load(a.plano.read_text(encoding="utf-8"))
        for it in data["itens"]:
            print(f"{it['id']:2d} {it['angulo']:15s} {it['s_src']:7.2f}-{it['e_src']:7.2f} {it['status']:9s} {it.get('resultado') or ''}")


if __name__ == "__main__":
    main()
