"""Motion graphics com Remotion (React) — cards de frase, contador, callout e gancho.

Cada elemento que o editor faria em ASS (motion.py / dinamismo.ass_cards) vira um "job":
o Remotion renderiza o elemento com fundo transparente (ProRes 4444, composição `Elemento`
em remotion/src/Elemento.tsx) e o FFmpeg o sobrepõe no tempo exato da fala (render.compose).

Regra do cliente vale aqui também: tudo em branco; destaque só com fonte/peso/tamanho/itálico.
O visual de cada modelo vem de `remotion.tema` no preset (fonte, animação, espaçamento).

Sem Node/Remotion instalado (ou se o render falhar) o pipeline volta para os mesmos elementos
em ASS — o vídeo sai igual, só com animações mais simples.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from .utils import ROOT, log

DIR = ROOT / "remotion"
DEFAULTS = {
    "ativo": False,
    "elementos": ["card", "contador", "callout", "gancho"],
    "tema": {"fonte": "Inter", "fonte_titulo": "Permanent Marker", "animacao": "pop",
             "espacamento": 0, "caixa_alta_destaque": True},
    "concorrencia": None,
}


def cfg_of(cfg: dict) -> dict:
    d = dict(DEFAULTS)
    d.update(cfg.get("remotion") or {})
    d["tema"] = dict(DEFAULTS["tema"], **(d.get("tema") or {}))
    # fonte de destaque do cliente (Black Jack): copia para o Remotion; sem o arquivo, usa a reserva
    if d["tema"].get("fonte_titulo") in ("Black Jack", "BlackJack"):
        from .utils import arquivo_black_jack
        bj = arquivo_black_jack()
        if bj:
            dst = DIR / "public" / "fonts" / "BlackJack.ttf"
            if not dst.exists() or dst.stat().st_size != bj.stat().st_size:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(bj, dst)
        else:
            d["tema"]["fonte_titulo"] = (cfg.get("legendas") or {}).get("fonte_destaque_reserva", "Noto Serif")
    return d


def disponivel() -> bool:
    return bool(shutil.which("node")) and (DIR / "node_modules" / "@remotion" / "renderer").exists()


def elementos(cfg: dict) -> set[str]:
    """Elementos que o Remotion vai desenhar (vazio = tudo em ASS)."""
    rc = cfg_of(cfg)
    if not rc["ativo"]:
        return set()
    if not disponivel():
        log.warning("  Remotion ativo, mas Node/remotion/node_modules ausente → motion em ASS "
                    "(instale: cd remotion && npm install)")
        return set()
    return set(rc["elementos"])


def render(jobs: list[dict], g, cfg: dict, work: Path) -> list[dict] | None:
    """Renderiza os jobs (com cache por conteúdo). Devolve [{t, dur, arquivo}] ou None se falhar."""
    if not jobs:
        return []
    rc = cfg_of(cfg)
    out_dir = work / "remotion"
    out_dir.mkdir(exist_ok=True)
    itens, clips = [], []
    for j in jobs:
        props = {"W": g.canvas_w, "H": g.canvas_h, "fps": round(float(g.fps), 3), "tema": rc["tema"],
                 **{k: v for k, v in j.items() if k != "t"}}
        h = hashlib.sha1(json.dumps(props, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
        dst = out_dir / f"{j['tipo']}_{h}.mov"
        if not dst.exists():
            itens.append({"props": props, "saida": str(dst)})
        clips.append({"t": j["t"], "dur": j["dur"], "arquivo": dst, "tipo": j["tipo"]})
    if itens:
        lote = out_dir / "lote.json"
        lote.write_text(json.dumps({"itens": itens, "concorrencia": rc["concorrencia"]}, ensure_ascii=False))
        log.info("  Remotion: renderizando %d elementos (%s)…", len(itens),
                 ", ".join(sorted({i["props"]["tipo"] for i in itens})))
        r = subprocess.run(["node", str(DIR / "render-lote.mjs"), str(lote)], cwd=DIR, capture_output=True, text=True)
        if r.returncode != 0:
            log.warning("  Remotion falhou → motion em ASS. %s", (r.stderr or r.stdout)[-600:])
            return None
    if not all(c["arquivo"].exists() for c in clips):
        return None
    log.info("  Remotion: %d elementos prontos (%s)", len(clips),
             {k: sum(c["tipo"] == k for c in clips) for k in sorted({c["tipo"] for c in clips})})
    return clips
