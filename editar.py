#!/usr/bin/env python3
"""CLI do pipeline de edição automatizada.

Exemplos:
  python editar.py bruto.mp4 --estilo referencia2 --plataforma reels
  python editar.py bruto.mp4 --estilo viral_reels --plataforma tiktok --preview
  python editar.py bruto.mp4 --modo sugestao            # lista onde aplicaria cada técnica e para
  python editar.py bruto.mp4 --usar-revisao             # aplica revisao/*.yaml editados
  python editar.py bruto.mp4 --revisar                  # para após o corte de silêncio p/ revisão
  python editar.py a.mp4 b.mp4 --estilo documentario    # várias tomadas → um vídeo
  python editar.py bruto.mp4 --set cortes.j_cut.ativo=false --set musica.humor=dramatico
"""
import argparse
import sys
from pathlib import Path

from editor.config import estilos_disponiveis


def main(argv=None):
    ap = argparse.ArgumentParser(description="Editor de vídeo automatizado", formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__)
    ap.add_argument("entradas", nargs="+", type=Path, help="vídeo(s) bruto(s)")
    ap.add_argument("--estilo", default="viral_reels", help=f"preset: {', '.join(estilos_disponiveis())} ou caminho .yaml")
    ap.add_argument("--plataforma", default="reels", help="reels | tiktok | shorts | youtube | youtube_vertical")
    ap.add_argument("--config", type=Path, help="YAML extra com ajustes finos")
    ap.add_argument("--set", action="append", default=[], metavar="CHAVE=VALOR", help="sobrescreve uma chave (ex.: silencio.limiar_db=-40)")
    ap.add_argument("--preview", action="store_true", help="versão rápida em baixa resolução")
    ap.add_argument("--modo", choices=["automatico", "sugestao"], help="modo das técnicas de corte")
    ap.add_argument("--revisar", action="store_true", help="para após o corte de silêncios para revisão manual")
    ap.add_argument("--usar-revisao", action="store_true", help="usa os arquivos editados em work/.../revisao/")
    ap.add_argument("--saida", type=Path, help="arquivo de saída (padrão: output/<nome>_<estilo>_<plataforma>.mp4)")
    a = ap.parse_args(argv)
    for p in a.entradas:
        if not p.exists():
            ap.error(f"arquivo não encontrado: {p}")
    from editor.pipeline import Parada, run
    try:
        rep = run([p.resolve() for p in a.entradas], a.estilo, a.plataforma, a.config, a.set, a.preview,
                  a.usar_revisao, a.revisar, a.modo, a.saida)
    except Parada as e:
        print(f"\n⏸  {e}")
        return 2
    print(f"\n✅ {rep['saida']['arquivo']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
