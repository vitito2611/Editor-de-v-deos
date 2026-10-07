"""Busca e download de mídia de banco (B-roll, fotos, trilhas e SFX) com cache local.

Fontes (todas com licença de uso comercial gratuita):
  • Pexels      vídeos e fotos verticais — exige chave grátis (env PEXELS_API_KEY ou
                dinamismo.pexels_api_key). Aceita busca em português (locale pt-BR).
  • Openverse   fotos CC (inclui Wikimedia Commons) — sem chave. Bom para pessoas/marcas
                famosas (ex.: "Steve Jobs"). Só licenças que permitem uso comercial.
  • Mixkit      trilhas e efeitos sonoros gratuitos (Mixkit License, sem atribuição).

Domínios que o ambiente precisa liberar (Network access → Custom):
  api.pexels.com, images.pexels.com, videos.pexels.com, player.vimeo.com, *.vimeocdn.com,
  api.openverse.org, upload.wikimedia.org, commons.wikimedia.org, live.staticflickr.com,
  mixkit.co, assets.mixkit.co

Tudo é cacheado em assets/cache_stock/ — a mesma busca não baixa de novo.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

from .utils import ROOT, log

CACHE = ROOT / "assets" / "cache_stock"
UA = {"User-Agent": "Mozilla/5.0 (editor-de-videos; +https://github.com/vitito2611/Editor-de-v-deos)"}


def _get(url: str, headers: dict | None = None, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _download(url: str, dst: Path, headers: dict | None = None) -> Path | None:
    if dst.exists() and dst.stat().st_size > 1000:
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = _get(url, headers, timeout=120)
        dst.write_bytes(data)
        return dst
    except Exception as e:  # noqa: BLE001
        log.warning("  download falhou (%s): %s", type(e).__name__, url[:90])
        return None


def _key(*parts) -> str:
    return hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:12]


def available(host: str) -> bool:
    try:
        _get(f"https://{host}", timeout=8)
        return True
    except urllib.error.HTTPError:
        return True          # respondeu (mesmo 4xx) → host liberado
    except Exception:  # noqa: BLE001
        return False


# ----------------------------------------------------------------------------- Pexels
def pexels_key(cfg: dict) -> str | None:
    return os.environ.get("PEXELS_API_KEY") or (cfg.get("dinamismo") or {}).get("pexels_api_key")


def pexels_video(query: str, cfg: dict, min_dur: float = 3.0, skip: int = 0) -> Path | None:
    key = pexels_key(cfg)
    if not key:
        return None
    meta = CACHE / "pexels" / f"v_{_key(query)}.json"
    try:
        if meta.exists():
            data = json.loads(meta.read_text())
        else:
            q = urllib.parse.urlencode({"query": query, "orientation": "portrait", "per_page": 12,
                                        "size": "medium", "locale": "pt-BR"})
            data = json.loads(_get(f"https://api.pexels.com/videos/search?{q}", {"Authorization": key}))
            meta.parent.mkdir(parents=True, exist_ok=True)
            meta.write_text(json.dumps(data))
    except Exception as e:  # noqa: BLE001
        log.warning("  Pexels indisponível (%s)", type(e).__name__)
        return None
    vids = [v for v in data.get("videos", []) if v.get("duration", 0) >= min_dur]
    if not vids:
        return None
    v = vids[skip % len(vids)]
    files = [f for f in v["video_files"] if f.get("width") and f.get("height") and f["height"] >= f["width"]] or v["video_files"]
    f = min(files, key=lambda f: abs((f.get("width") or 0) - 1080))
    return _download(f["link"], CACHE / "pexels" / f"v_{v['id']}_{f.get('width')}.mp4")


def pexels_photo(query: str, cfg: dict, skip: int = 0) -> Path | None:
    key = pexels_key(cfg)
    if not key:
        return None
    try:
        q = urllib.parse.urlencode({"query": query, "orientation": "portrait", "per_page": 10, "locale": "pt-BR"})
        data = json.loads(_get(f"https://api.pexels.com/v1/search?{q}", {"Authorization": key}))
    except Exception as e:  # noqa: BLE001
        log.warning("  Pexels indisponível (%s)", type(e).__name__)
        return None
    ph = data.get("photos", [])
    if not ph:
        return None
    p = ph[skip % len(ph)]
    return _download(p["src"].get("portrait") or p["src"]["large2x"], CACHE / "pexels" / f"p_{p['id']}.jpg")


# ----------------------------------------------------------------------------- Mixkit (vídeos, sem chave)
def mixkit_videos(query: str) -> list[dict]:
    """Resultados da busca de vídeos do Mixkit (em inglês): id, título, vertical?, url 360p."""
    slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
    meta = CACHE / "mixkit" / f"busca_{slug}.json"
    if meta.exists():
        return json.loads(meta.read_text())
    try:
        html = _get(f"https://mixkit.co/free-stock-video/discover/{slug}/").decode("utf-8", "ignore")
    except Exception as e:  # noqa: BLE001
        log.warning("  Mixkit indisponível (%s)", type(e).__name__)
        return []
    out = []
    for blk in re.split(r'class="item-grid-card[ "]', html)[1:]:
        v = re.search(r'<video src="(https://assets\.mixkit\.co/[^"]+?-360\.mp4)"', blk)
        dims = re.search(r'class="item-grid-video-player__thumb"[^>]*width="(\d+)" height="(\d+)"', blk)
        title = re.search(r'item-grid-card__title">\s*<a [^>]+>([^<]+)<', blk)
        if not v:
            continue
        w, h = (int(dims.group(1)), int(dims.group(2))) if dims else (16, 9)
        out.append({"url360": v.group(1), "vertical": h > w, "titulo": title.group(1).strip() if title else ""})
    if out:   # não cacheia busca vazia
        meta.parent.mkdir(parents=True, exist_ok=True)
        meta.write_text(json.dumps(out))
    return out


def mixkit_video(query: str, skip: int = 0, prefer_vertical: bool = True) -> Path | None:
    words = query.split()
    res = []
    # busca composta sem resultado → tira palavras do fim ("shy man thinking" → "shy man" → "shy")
    for n in range(len(words), 0, -1):
        res = mixkit_videos(" ".join(words[:n]))
        if res:
            break
    if not res:
        return None
    if prefer_vertical:   # verticais primeiro, mas só entre os 8 mais relevantes
        top = res[:8]
        res = sorted(top, key=lambda r: not r["vertical"]) + res[8:]
    r = res[skip % len(res)]
    for q in ("1080", "720", "360"):
        url = r["url360"].replace("-360.mp4", f"-{q}.mp4")
        f = _download(url, CACHE / "mixkit" / (Path(urllib.parse.urlparse(url).path).name))
        if f:
            log.info("  B-roll Mixkit '%s' → %s%s", query, r["titulo"][:50], " (vertical)" if r["vertical"] else "")
            return f
    return None


# ----------------------------------------------------------------------------- Openverse (CC / Wikimedia)
def openverse_photo(query: str, skip: int = 0) -> tuple[Path, dict] | None:
    """Foto CC com uso comercial permitido (by, by-sa, cc0, pdm). Retorna (arquivo, créditos)."""
    try:
        q = urllib.parse.urlencode({"q": query, "license_type": "commercial", "page_size": 12, "mature": "false"})
        data = json.loads(_get(f"https://api.openverse.org/v1/images/?{q}"))
    except Exception as e:  # noqa: BLE001
        log.warning("  Openverse indisponível (%s)", type(e).__name__)
        return None
    res = [r for r in data.get("results", []) if (r.get("height") or 0) >= 500]
    if not res:
        return None
    qw = [w.lower() for w in query.split()]
    ruim = ("fake", "render", "art", "drawing", "cartoon", "illustration", "poster", "logo", "mural",
            "painting", "sketch", "caricature", "statue", "graffiti", "memorial", "tribute", "applesoft",
            "tattoo", "figurine", "cosplay", "case", "icon", "doll", "toy")

    def score(r):
        t = (r.get("title") or "").lower()
        tags = " ".join(x.get("name", "") for x in (r.get("tags") or [])).lower()
        sc = 3 * all(w in t for w in qw) + 1 * all(w in t + " " + tags for w in qw)
        sc += 1 if (r.get("height") or 0) >= 800 else 0
        sc -= 4 * any(b in t for b in ruim)
        return sc
    res = sorted(res, key=score, reverse=True)
    r = res[skip % len(res)]
    ext = Path(urllib.parse.urlparse(r["url"]).path).suffix.lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".jpg"
    f = _download(r["url"], CACHE / "openverse" / f"{r['id']}{ext}")
    if not f:
        return None
    cred = {"titulo": r.get("title"), "autor": r.get("creator"), "licenca": f"{r.get('license')} {r.get('license_version') or ''}".strip(),
            "fonte": r.get("foreign_landing_url")}
    return f, cred


# ----------------------------------------------------------------------------- Mixkit (trilhas e SFX)
MIXKIT_SFX = {   # categoria do pipeline → páginas de efeitos do Mixkit (ordem = popularidade)
    "transicao": ["whoosh", "swoosh", "transition"],
    "impacto": ["impact", "hit", "boom"],
    "atencao": ["pop", "click", "notification"],
    "humor": ["cartoon", "funny"],
    "riser": ["riser", "cinematic"],
    "glitch": ["glitch"],
}
# ids de efeitos do Mixkit vetados pelo cliente (nunca baixar de novo)
MIXKIT_PROIBIDOS = {"2350"}   # "Magic sparkle whoosh" — o "plin" de brilho
MIXKIT_MUSIC = {   # humor do pipeline → páginas de trilhas do Mixkit
    "energetico": ["hip-hop", "mood/energetic", "genre/electronica"],
    "informativo": ["mood/inspiring", "corporate", "technology"],
    "emocional": ["mood/inspiring", "mood/emotional", "piano"],
    "dramatico": ["cinematic", "mood/dramatic", "epic"],
    "sombrio": ["mood/dark", "suspense"],
}


def _mixkit_mp3s(page: str) -> list[str]:
    try:
        html = _get(page).decode("utf-8", "ignore")
    except Exception as e:  # noqa: BLE001
        log.warning("  Mixkit: página indisponível (%s): %s", type(e).__name__, page)
        return []
    urls = re.findall(r"https://assets\.mixkit\.co/[^\"'\s<>]+?\.mp3", html)
    return list(dict.fromkeys(urls))


def _mixkit_pull(base: str, mapping: dict, dest: Path, per: int, label: str) -> int:
    n = 0
    seen = set()
    for cat, pages in mapping.items():
        got = len(list((dest / cat).glob("mx_*.mp3"))) if (dest / cat).exists() else 0
        for pg in pages:
            if got >= per:
                break
            for u in _mixkit_mp3s(f"https://mixkit.co/{base}/{pg}/"):
                if got >= per:
                    break
                if u in seen or any(f"/{pid}/" in u for pid in MIXKIT_PROIBIDOS):
                    continue
                seen.add(u)
                ident = re.findall(r"/(\d+)/", u)
                name = f"mx_{pg.split('/')[-1]}_{ident[-1] if ident else len(seen)}.mp3"
                if _download(u, dest / cat / name):
                    got += 1
        n += got
        log.info("  %s Mixkit %-11s %d", label, cat, got)
    return n


def mixkit_sfx(dest: Path, per_cat: int = 8) -> int:
    return _mixkit_pull("free-sound-effects", MIXKIT_SFX, dest, per_cat, "SFX")


def mixkit_music(dest: Path, per_mood: int = 6) -> int:
    return _mixkit_pull("free-stock-music", MIXKIT_MUSIC, dest, per_mood, "trilhas")


def main():
    """python -m editor.stock  → baixa o pacote de SFX e trilhas reais do Mixkit."""
    from .utils import setup_logging
    setup_logging("INFO")
    a = mixkit_sfx(ROOT / "assets" / "sfx")
    b = mixkit_music(ROOT / "assets" / "music")
    print(f"SFX: {a}  trilhas: {b}")


if __name__ == "__main__":
    main()
