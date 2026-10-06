"""Carregamento de configuração: default.yaml ← estilo ← --config ← --set chave=valor.

Merge profundo: cada camada só sobrescreve as chaves que declara.
Acesso: cfg["silencio"]["limiar_db"] (dict normal).
"""
from __future__ import annotations

import copy
from pathlib import Path

import yaml

from .utils import ROOT


def deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _parse_value(v: str):
    return yaml.safe_load(v)


def set_path(cfg: dict, dotted: str, value) -> None:
    node = cfg
    keys = dotted.split(".")
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    node[keys[-1]] = value


def estilos_disponiveis() -> list[str]:
    return sorted(p.stem for p in (ROOT / "config" / "estilos").glob("*.yaml"))


def load_config(estilo: str | None = None, extra: Path | None = None,
                overrides: list[str] | None = None) -> dict:
    cfg = yaml.safe_load((ROOT / "config" / "default.yaml").read_text(encoding="utf-8"))
    if estilo:
        p = Path(estilo)
        if not p.exists():
            p = ROOT / "config" / "estilos" / f"{estilo}.yaml"
        if not p.exists():
            raise FileNotFoundError(
                f"Estilo '{estilo}' não encontrado. Disponíveis: {estilos_disponiveis()}")
        cfg = deep_merge(cfg, yaml.safe_load(p.read_text(encoding="utf-8")) or {})
        cfg["_estilo"] = Path(p).stem
    if extra:
        cfg = deep_merge(cfg, yaml.safe_load(Path(extra).read_text(encoding="utf-8")) or {})
    for ov in overrides or []:
        k, _, v = ov.partition("=")
        set_path(cfg, k.strip(), _parse_value(v))
    return cfg
