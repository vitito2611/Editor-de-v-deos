"""Gera o banco local de efeitos sonoros e trilhas (síntese procedural, livre de direitos).

Uso:  python -m editor.assets_gen            (gera assets/sfx e assets/music)

Por que sintetizar? Bancos online (Freesound, Pixabay) exigem rede/chave. Este banco
garante que o pipeline funcione 100% offline. Para qualidade de produção, basta
colocar arquivos reais em assets/music/<humor>/ e assets/sfx/<categoria>/ — o pipeline
usa tudo que estiver nas pastas (os sintetizados podem ser apagados).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml
from scipy import signal

from .utils import ROOT, save_wav

SR = 48000
rng = np.random.default_rng(1234)


# ----------------------------------------------------------------------------- utilidades DSP
def t_axis(dur):
    return np.arange(int(dur * SR)) / SR


def env_adsr(n, a=0.01, d=0.1, s=0.7, r=0.2):
    a_n, d_n, r_n = int(a * SR), int(d * SR), int(r * SR)
    s_n = max(0, n - a_n - d_n - r_n)
    e = np.concatenate([np.linspace(0, 1, a_n, endpoint=False),
                        np.linspace(1, s, d_n, endpoint=False),
                        np.full(s_n, s), np.linspace(s, 0, r_n)])
    return np.pad(e, (0, max(0, n - len(e))))[:n]


def exp_decay(n, tau):
    return np.exp(-np.arange(n) / (tau * SR))


def bandpass(x, lo, hi, order=2):
    b, a = signal.butter(order, [lo / (SR / 2), min(hi / (SR / 2), 0.99)], "band")
    return signal.lfilter(b, a, x)


def lowpass(x, fc, order=2):
    b, a = signal.butter(order, min(fc / (SR / 2), 0.99), "low")
    return signal.lfilter(b, a, x)


def highpass(x, fc, order=2):
    b, a = signal.butter(order, fc / (SR / 2), "high")
    return signal.lfilter(b, a, x)


def reverb(x, tail=1.2, mix=0.25):
    n = int(tail * SR)
    ir = rng.standard_normal(n) * exp_decay(n, tail / 5)
    ir = lowpass(ir, 6000)
    ir /= np.abs(ir).sum() ** 0.5 * 8
    wet = np.pad(signal.fftconvolve(x, ir), (0, 1))[: len(x) + n]
    out = np.pad(x, (0, n)) * (1 - mix) + wet * mix
    return out


def norm(x, peak=0.89):
    m = np.max(np.abs(x)) or 1
    return (x / m * peak).astype(np.float32)


def sweep_noise(dur, f0, f1, q=3.0):
    """Ruído filtrado com banda que varre de f0 a f1 (base de whoosh/riser)."""
    n = int(dur * SR)
    noise = rng.standard_normal(n)
    out = np.zeros(n)
    blk = 512
    for i in range(0, n, blk):
        f = f0 * (f1 / f0) ** (i / n)
        bw = f / q
        seg = noise[max(0, i - 2048): i + blk]
        y = bandpass(seg, max(30, f - bw), min(SR / 2 - 100, f + bw))
        out[i: i + blk] = y[-len(out[i: i + blk]):]
    return out


def stereo(x, width=0.0):
    if width <= 0:
        return np.stack([x, x], 1)
    d = int(0.012 * SR * width)
    return np.stack([x, np.pad(x, (d, 0))[: len(x)]], 1)


# ----------------------------------------------------------------------------- SFX
def sfx_bank() -> dict[str, dict[str, np.ndarray]]:
    b: dict[str, dict[str, np.ndarray]] = {k: {} for k in
                                            ("transicao", "impacto", "atencao", "humor", "ambiente")}
    # Transição -------------------------------------------------------------
    for i, (dur, f0, f1) in enumerate([(0.55, 300, 4000), (0.4, 600, 6000), (0.7, 200, 2500)]):
        n = int(dur * SR)
        e = np.sin(np.linspace(0, np.pi, n)) ** 2
        b["transicao"][f"whoosh_{i+1}"] = norm(reverb(sweep_noise(dur, f0, f1) * e, 0.6, 0.2), 0.8)
    n = int(0.22 * SR)
    b["transicao"]["swipe_1"] = norm(sweep_noise(0.22, 2500, 9000, 2) * np.sin(np.linspace(0, np.pi, n)), 0.7)
    t = t_axis(0.08)
    b["transicao"]["pop_1"] = norm(np.sin(2 * np.pi * (900 - 5000 * t) * t) * exp_decay(len(t), 0.015))
    t = t_axis(1.6)
    riser = sweep_noise(1.6, 200, 8000, 4) * (t / t[-1]) ** 2
    riser += 0.3 * np.sin(2 * np.pi * (100 + 600 * t ** 2) * t) * (t / t[-1]) ** 2
    b["transicao"]["riser_1"] = norm(riser, 0.7)
    # Impacto ---------------------------------------------------------------
    t = t_axis(0.5)
    kick = np.sin(2 * np.pi * (45 + 140 * np.exp(-t * 30)) * t) * exp_decay(len(t), 0.12)
    click = highpass(rng.standard_normal(len(t)), 2000) * exp_decay(len(t), 0.004)
    b["impacto"]["punch_1"] = norm(kick + 0.4 * click)
    t = t_axis(2.2)
    boom = np.sin(2 * np.pi * (30 + 60 * np.exp(-t * 4)) * t) * exp_decay(len(t), 0.6)
    boom += 0.25 * lowpass(rng.standard_normal(len(t)), 300) * exp_decay(len(t), 0.3)
    b["impacto"]["boom_1"] = norm(boom)
    t = t_axis(0.4)
    hit = np.sin(2 * np.pi * (60 + 100 * np.exp(-t * 20)) * t) * exp_decay(len(t), 0.1)
    hit += 0.6 * bandpass(rng.standard_normal(len(t)), 800, 6000) * exp_decay(len(t), 0.03)
    b["impacto"]["hit_1"] = norm(reverb(hit, 1.8, 0.35))
    # Atenção ---------------------------------------------------------------
    def bell(f, dur=1.2):
        t = t_axis(dur)
        x = sum(a * np.sin(2 * np.pi * f * m * t) * exp_decay(len(t), dur / (2 + 3 * k))
                for k, (m, a) in enumerate([(1, 1), (2.76, 0.4), (5.4, 0.2), (8.9, 0.08)]))
        return x
    b["atencao"]["ding_1"] = norm(reverb(bell(1568), 0.8, 0.15), 0.7)
    n1, n2 = bell(1318, 0.35), bell(1760, 0.6)
    b["atencao"]["notificacao_1"] = norm(np.concatenate([n1[: int(0.11 * SR)], n2]), 0.7)
    beep = np.sin(2 * np.pi * 2000 * t_axis(0.07)) * env_adsr(int(0.07 * SR), 0.003, 0.01, 0.8, 0.02)
    gap = np.zeros(int(0.06 * SR))
    b["atencao"]["alerta_1"] = norm(np.concatenate([beep, gap, beep, gap, beep]), 0.5)
    # Humor -----------------------------------------------------------------
    t = t_axis(0.7)
    f = 180 + 120 * np.sin(2 * np.pi * 9 * t) * np.exp(-t * 3) + 200 * np.exp(-t * 6)
    b["humor"]["boing_1"] = norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * exp_decay(len(t), 0.25), 0.7)
    t = t_axis(0.9)
    f = 700 * np.exp(-t * 2.2)
    b["humor"]["queda_1"] = norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * env_adsr(len(t), 0.01, 0.1, 0.8, 0.3), 0.6)
    # Ambiente --------------------------------------------------------------
    n = 20 * SR
    white = rng.standard_normal(n)
    pink = signal.lfilter([0.049922035, -0.095993537, 0.050612699, -0.004408786],
                          [1, -2.494956002, 2.017265875, -0.522189400], white)
    b["ambiente"]["room_tone_1"] = norm(lowpass(pink, 1200), 0.3)
    return b


# ----------------------------------------------------------------------------- MÚSICA
NOTE = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}
MAJOR = [0, 2, 4, 5, 7, 9, 11]
MINOR = [0, 2, 3, 5, 7, 8, 10]


def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def chord(root_midi, scale, degree, n=3):
    """Tríade (ou tétrade) diatônica em graus da escala, retorna notas MIDI."""
    out = []
    for k in range(n):
        idx = degree + 2 * k
        out.append(root_midi + scale[idx % 7] + 12 * (idx // 7))
    return out


def saw(f, t, detune=0.0):
    ph = (f * (1 + detune)) * t
    return 2 * (ph - np.floor(ph + 0.5))


def synth_kick(n):
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * (48 + 110 * np.exp(-t * 35)) * t) * exp_decay(n, 0.16)


def synth_snare(n):
    t = np.arange(n) / SR
    return (0.6 * bandpass(rng.standard_normal(n), 1200, 7000) * exp_decay(n, 0.06)
            + 0.4 * np.sin(2 * np.pi * 190 * t) * exp_decay(n, 0.04))


def synth_hat(n, open_=False):
    return highpass(rng.standard_normal(n), 7000) * exp_decay(n, 0.12 if open_ else 0.025)


def synth_pluck(f, n, bright=3000):
    t = np.arange(n) / SR
    x = saw(f, t) * 0.6 + np.sin(2 * np.pi * f * t) * 0.4
    return lowpass(x, bright) * exp_decay(n, 0.22)


def synth_piano(f, n):
    t = np.arange(n) / SR
    x = sum(a * np.sin(2 * np.pi * f * m * t) for m, a in [(1, 1), (2, 0.35), (3, 0.15), (4, 0.06)])
    return x * exp_decay(n, 0.9) * env_adsr(n, 0.004, 0.05, 1, 0.05)


def synth_pad(freqs, n, cutoff=1800):
    t = np.arange(n) / SR
    x = sum(saw(f, t, d) for f in freqs for d in (-0.004, 0.0, 0.005)) / (3 * len(freqs))
    return lowpass(x, cutoff) * env_adsr(n, 0.6, 0.2, 0.85, 0.6)


MOODS = {
    #            bpm  tonica escala   progressão(graus)   kit
    "energetico": [(124, "A", MINOR, [0, 5, 2, 6], "four"), (128, "E", MINOR, [0, 3, 5, 4], "four")],
    "informativo": [(100, "C", MAJOR, [0, 4, 5, 3], "light"), (96, "G", MAJOR, [0, 5, 3, 4], "light")],
    "emocional": [(78, "D", MAJOR, [5, 3, 0, 4], "piano"), (84, "F", MAJOR, [0, 2, 5, 3], "piano")],
    "dramatico": [(90, "D", MINOR, [0, 3, 5, 4], "epic"), (86, "C", MINOR, [0, 5, 3, 6], "epic")],
    "sombrio": [(95, "F#", MINOR, [0, 1, 0, 5], "dark"), (102, "B", MINOR, [0, 5, 1, 0], "dark")],
}


def compose(bpm, tonic, scale, prog, kit, dur=96.0, seed=0):
    """Compõe uma faixa com seções (intro, A, breakdown, B, outro) e energia variando."""
    r = np.random.default_rng(seed)
    beat = 60 / bpm
    bar = 4 * beat
    nbars = int(dur / bar)
    n_total = int(nbars * bar * SR) + SR * 2
    L = np.zeros(n_total)
    R = np.zeros(n_total)
    root = 48 + NOTE[tonic]
    # Mapa de energia por compasso: intro 4, A 8, break 4, B 8, ... outro 4
    sections = []
    pattern = [("intro", 4), ("A", 8), ("break", 4), ("B", 8)]
    while sum(s[1] for s in sections) < nbars - 4:
        for s in pattern[1:] if sections else pattern:
            sections.append(s)
    sections.append(("outro", 4))
    energy_map = []
    for name, nb in sections:
        e = {"intro": 0.3, "A": 0.7, "break": 0.4, "B": 1.0, "outro": 0.35}[name]
        energy_map += [(name, e)] * nb
    energy_map = energy_map[:nbars]

    def add(x, start_s, gain=1.0, pan=0.0):
        i = int(start_s * SR)
        j = min(n_total, i + len(x))
        if j <= i:
            return
        L[i:j] += x[: j - i] * gain * (1 - max(0, pan))
        R[i:j] += x[: j - i] * gain * (1 + min(0, pan))

    for b_i, (sec, en) in enumerate(energy_map):
        t0 = b_i * bar
        deg = prog[b_i % len(prog)]
        notes = chord(root, scale, deg, 4 if kit in ("piano", "epic") else 3)
        # Pad
        pad = synth_pad([midi_hz(m + 12) for m in notes[:3]], int(bar * SR) + int(0.6 * SR),
                        900 + 1600 * en)
        add(pad, t0, 0.22 if kit != "dark" else 0.3)
        # Baixo
        bn = int(beat * SR)
        if sec != "intro" or kit == "dark":
            for k in range(4 if kit != "piano" else 2):
                st = t0 + k * (beat if kit != "piano" else 2 * beat)
                f = midi_hz(notes[0] - 12)
                tt = np.arange(bn) / SR
                bass = lowpass(saw(f, tt) * 0.5 + np.sin(2 * np.pi * f * tt), 400) * env_adsr(bn, 0.005, 0.1, 0.6, 0.1)
                add(bass, st, 0.32 * en + 0.1)
        # Melodia / arpejo
        if kit in ("four", "light", "dark"):
            step = beat / (4 if kit == "four" else 2)
            for k in range(int(bar / step)):
                if sec == "intro" and k % 2:
                    continue
                m = notes[(k * 2 + b_i) % len(notes)] + 24 - (12 if kit == "dark" else 0)
                p = synth_pluck(midi_hz(m), int(step * SR * 1.6), 2500 + 3000 * en)
                add(p, t0 + k * step, 0.10 * (0.6 + en), pan=0.3 * np.sin(k))
        else:  # piano / epic: arpejo em colcheias com notas da tétrade
            step = beat / 2
            for k in range(8):
                if r.random() < 0.15:
                    continue
                m = notes[[0, 1, 2, 3, 2, 1, 2, 3][k]] + 12
                add(synth_piano(midi_hz(m), int(2.5 * SR)), t0 + k * step, 0.16, pan=0.2 * np.cos(k))
        # Bateria
        if en >= 0.55 or (kit == "dark" and en >= 0.4):
            kn = int(0.4 * SR)
            for k in range(4):
                st = t0 + k * beat
                if kit in ("four", "dark") or (kit == "light" and k in (0, 2)) or (kit in ("piano", "epic") and k == 0):
                    add(synth_kick(kn), st, 0.75 if kit != "piano" else 0.45)
                if k in (1, 3) and kit in ("four", "light"):
                    add(synth_snare(int(0.3 * SR)), st, 0.35)
                if kit == "epic" and k == 2:
                    add(synth_snare(int(0.3 * SR)), st, 0.45)
            hats = 8 if kit in ("four", "dark") else 4
            if kit != "piano":
                for k in range(hats):
                    add(synth_hat(int(0.15 * SR), open_=(k % 4 == 2 and kit == "four")),
                        t0 + k * bar / hats, 0.07 * en, pan=0.4)
        if kit == "epic" and b_i % 4 == 0 and en >= 0.7:
            t = np.arange(int(2 * SR)) / SR
            add(np.sin(2 * np.pi * (40 + 40 * np.exp(-t * 5)) * t) * exp_decay(len(t), 0.5), t0, 0.6)

    mix = np.stack([L, R], 1)
    # leve "cola": compressão suave por tanh + reverb curto no lado
    mix = np.tanh(mix * 1.4) / 1.4
    fade = int(1.5 * SR)
    mix[:fade] *= np.linspace(0, 1, fade)[:, None]
    end = int(nbars * bar * SR)
    mix = mix[: end + SR]
    mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
    beats = [round(i * beat, 4) for i in range(int(len(mix) / SR / beat))]
    return norm(mix, 0.8), beats, [e for _, e in energy_map], bar


def main():
    out_sfx = ROOT / "assets" / "sfx"
    out_mus = ROOT / "assets" / "music"
    print("Gerando efeitos sonoros...")
    for cat, items in sfx_bank().items():
        (out_sfx / cat).mkdir(parents=True, exist_ok=True)
        for name, x in items.items():
            save_wav(out_sfx / cat / f"{name}.wav", stereo(x, 0.3), SR)
    print("Gerando trilhas...")
    library = {}
    for mood, variants in MOODS.items():
        (out_mus / mood).mkdir(parents=True, exist_ok=True)
        for i, (bpm, tonic, scale, prog, kit) in enumerate(variants):
            x, beats, energy, bar = compose(bpm, tonic, scale, prog, kit, seed=i)
            fn = f"{mood}_{i+1}.wav"
            save_wav(out_mus / mood / fn, x, SR)
            library[f"{mood}/{fn}"] = {"humor": mood, "bpm": bpm, "tom": tonic,
                                       "energia_por_compasso": [round(e, 2) for e in energy],
                                       "compasso_s": round(bar, 4), "licenca": "gerado (domínio público)"}
            print(f"  {mood}/{fn}  {bpm} BPM  {len(x)/SR:.0f}s")
    (out_mus / "library.yaml").write_text(yaml.safe_dump(library, allow_unicode=True, sort_keys=False))
    print("OK")


if __name__ == "__main__":
    main()
