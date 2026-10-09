"""Pipeline de edição de vídeo automatizada.

Módulos (um por etapa):
    analysis      — análise inicial (metadados, loudness, planos)
    transcribe    — transcrição com timestamp por palavra
    nlp           — frases, palavras-chave, tom, tópicos, gatilhos
    silence       — corte inteligente de silêncios com contexto
    cinematic     — J/L/match/smash/jump-zoom/beat/reaction cut
    color         — correção primária + LUTs
    audio         — limpeza, dinâmica, mix e master
    sfx           — efeitos sonoros estratégicos
    music         — trilha variada com ducking e beats
    subtitles     — legendas dinâmicas (ASS)
    motion        — motion graphics e efeitos visuais
    render        — renderização de segmentos e composição final
    pipeline      — orquestração
"""

__version__ = "1.0.0"

# Mac: o "ffmpeg" do Homebrew vem sem libass; o completo ("ffmpeg-full") é keg-only → entra na frente do PATH
import os as _os

for _d in ("/opt/homebrew/opt/ffmpeg-full/bin", "/usr/local/opt/ffmpeg-full/bin"):
    if _os.path.isfile(_os.path.join(_d, "ffmpeg")) and _d not in _os.environ.get("PATH", ""):
        _os.environ["PATH"] = _d + _os.pathsep + _os.environ.get("PATH", "")
        break
