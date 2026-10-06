"""Testes rápidos das partes determinísticas do pipeline (rode: python -m pytest tests -q)."""
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from editor import cinematic, color, silence, subtitles  # noqa: E402
from editor.config import load_config  # noqa: E402
from editor.timeline import Clip, layout_times, map_words, snap_clips, src_to_out  # noqa: E402

FPS = Fraction(30)


def test_config_merge_and_override():
    cfg = load_config("referencia2", overrides=["silencio.limiar_db=-40", "cortes.j_cut.ativo=false"])
    assert cfg["legendas"]["estilo_base"] == "lateral_misto"
    assert cfg["silencio"]["limiar_db"] == -40
    assert cfg["cortes"]["j_cut"]["ativo"] is False
    assert cfg["cortes"]["l_cut"]["ativo"] is True  # não declarado no estilo → mantém default


def test_keeps_from_gaps_actions():
    sc = load_config()["silencio"]
    gaps = [{"s": 2.0, "e": 3.0, "dur": 1.0, "acao": "cortar"},
            {"s": 5.0, "e": 6.5, "dur": 1.5, "acao": "encurtar"},
            {"s": 8.0, "e": 8.4, "dur": 0.4, "acao": "preservar"}]
    keeps = silence.keeps_from_gaps(gaps, 10.0, sc)
    removed = 10.0 - sum(b - a for a, b in keeps)
    expect = (1.0 - sc["folga_depois_s"] - sc["folga_antes_s"]) + (1.5 - sc["folga_depois_s"] - sc["pausa_preservada_s"] - sc["folga_antes_s"])
    assert abs(removed - expect) < 1e-6


def test_timeline_mapping_and_freeze():
    clips = [Clip(0, 0.0, 2.0), Clip(0, 3.0, 5.0)]
    clips[1].freeze_frames = 6
    snap_clips(clips, FPS)
    total = layout_times(clips, FPS)
    assert abs(total - (4.0 + 0.2)) < 1e-9
    assert abs(src_to_out(clips, 0, 3.5) - 2.7) < 1e-9
    assert src_to_out(clips, 0, 2.5) is None
    words = [{"w": "a", "s": 1.0, "e": 1.2}, {"w": "b", "s": 2.4, "e": 2.6}, {"w": "c", "s": 4.0, "e": 4.3}]
    out = map_words(clips, words)
    assert [w["w"] for w in out] == ["a", "c"]


def test_jl_cut_preserves_duration():
    clips = [Clip(0, 0.0, 3.0), Clip(0, 4.0, 7.0)]
    dec = [{"id": 0, "tecnica": "j_cut", "limite": 0, "params": {"overlap": 0.5}, "aplicar": True}]
    cinematic.apply(clips, dec, FPS)
    vdur = sum(c.v_out - c.v_in for c in clips)
    adur = sum(c.a_out - c.a_in for c in clips)
    assert abs(vdur - adur) < 1e-9
    assert abs(clips[0].v_out - 3.5) < 1e-9 and abs(clips[1].v_in - 4.5) < 1e-9


def test_group_words_respects_limits():
    lc = load_config()["legendas"]
    words = [{"w": w, "s": i * 0.3, "e": i * 0.3 + 0.25, "sent": 0 if i < 6 else 1}
             for i, w in enumerate("um dois três quatro cinco seis. sete oito".split())]
    groups = subtitles.group_words(words, lc, lc["estilos"]["karaoke"])
    assert all(len(g) <= lc["palavras_max"] for g in groups)
    assert all(len({w["sent"] for w in g}) == 1 for g in groups)


def test_lut_identity_when_neutral():
    x = np.random.default_rng(0).random((50, 3))
    y = color._apply_look(x, {"contraste": 0, "saturacao": 1.0, "temperatura": 0, "tint": 0,
                               "sombras": [0, 0, 0], "luzes": [0, 0, 0], "pretos": 0, "vibrance": 0})
    assert np.allclose(x, y, atol=1e-6)


def test_ass_color_and_time():
    assert subtitles.ass_color("#FF8000") == "&H000080FF&"
    assert subtitles.ass_time(3725.456) == "1:02:05.46"


def test_glossary_corrections():
    from editor.transcribe import apply_corrections
    ws = apply_corrections([{"w": "Paranoia."}, {"w": "paranoia,"}, {"w": "outra"}], {"Paranoia": "pronoia"})
    assert [w["w"] for w in ws] == ["Pronoia.", "pronoia,", "outra"]
