# Modelo de edição — padrão aprovado (vídeo 3 "IA e emprego", v6)

Receita para editar os próximos vídeos do cliente (Zeal). Tudo aqui foi aprovado por ele; o que muda de vídeo para
vídeo é só o **plano** (`config/planos/<video>.yaml`): motions, headline e glossário.

> Comando: `python editar.py entrada/<video>.mov --estilo referencia1 --plataforma reels --config config/planos/<video>.yaml`
> (no Mac sai em 4K e vai direto para a pasta do Drive — ver `docs/MAC.md`).

## 1. Corte (ritmo)

- Pausas ≥ 0,22 s **saem** (`silencio.pausa_preservada_s: 0.22`); recomeços, gaguejadas, muletas e frases abandonadas
  saem por `editor/erros.py` (revisão em `work/<job>/revisao/erros_gravacao.yaml`).
- Troca de plano a cada **≤ 2,6 s** com jump zoom variado: `cortes.jump_zoom: {modo: variado, zoom_niveis: [1.0, 1.1,
  1.04, 1.16, 1.07], dividir_max_s: 2.6}`.
- Depois de aprovado, **congelar** a edição (`congelado:` no plano → transcrição + trechos mantidos), para o render
  em outra máquina/resolução sair idêntico.

## 2. Legendas (aprovadas: "as legendas e as ênfases estão legais")

- Sempre **brancas**, sem cor. Base **Rubik Bold**, pequena, no peito (`estilo_base: minimal_peito`, até 3 palavras).
- **Ênfase** = frase de impacto em estilo `cinetico` (palavra-chave em **Black Jack** maior, entra com animação),
  posição `peito` para não cobrir a boca. `impacto_score_min: 0.8` → só as frases fortes viram ênfase (≈2–3 por minuto).
- Glossário do ASR por vídeo em `transcricao.correcoes` (Zeal costuma sair "I", "Nasil", "Iar"…).
- Zona segura do Reels: 420 px em cima/embaixo + coluna de botões à direita (já automático).

## 3. Som (aprovado)

- SFX no nível da v2: `sfx: {intervalo_min_s: 0.9, max_por_minuto: 30, volume_rel_voz_db: -9}`; transições (whoosh)
  em cada motion, impactos nas ênfases (−4 dB), 1 riser antes do momento-chave. **Nunca** o "plin"/sparkle.
- Trilha Mixkit emocional com ducking; master −14 LUFS. Sempre **duas versões**: com trilha e sem trilha.

## 4. Cor

- Look `azul_cinema` aplicado ao vivo (estúdio). Ajuste aprovado no vídeo 3: intensidade 0,63, contraste +0,20,
  exposição −0,39 (`config/planos/video3_ia_emprego_estudio.json`) — bom ponto de partida para a mesma sala.

## 5. Motions (o que mudou a cada rodada de feedback)

- 1 motion a cada ~6–8 s de fala, **só nos momentos-chave**, entrando com corte seco já em movimento (`pre_roll`).
- **Pouquíssimo texto**: 1–3 palavras por motion (o cliente reclamou de "muita legenda nos motions").
- Formatos com a filmagem (Remotion): `formato: janela` (o cliente numa janela/círculo sobre o motion),
  `efeito: multiplica` (grade de clones ×N) e `efeito: monitor` (o cliente dentro de um editor de vídeo).
- Reprovado: esteira 3D "muito feia", motions "de amador", paletas rosa/lilás claro, motions só de letras.
- **Padrão atual: modelo `produto`** (referência `referencias/motion4/ref.mp4`; o `campo` foi reprovado) — ver
  `CONTEXTO.md` para as cenas, a sincronização com a fala e o fluxo completo (estúdio + página de entrega).
- **Headline de abertura** nos primeiros ~2,5 s (dentro da zona segura), no mesmo idioma visual do motion.

## 6. Zeal (conteúdo)

A Zeal é o **copiloto de vendas do dentista** (áudio da consulta → perfil comportamental, objeções e como
contorná-las em tempo real, rapport, resumo, briefing pós-consulta). **Nunca** diagnóstico, plano de tratamento,
implante ou agendamento. Tela aprovada: paciente "Achei caro…" → Zeal "Objeção: preço. Mostre o parcelamento." +
cartão "Briefing da consulta" (Perfil · Objeção · Rapport).

## 7. Entrega

- Conferir contact sheet antes de entregar.
- Na nuvem: **página de entrega** (link, ~6,3 Mbps, sem o limite de 30 MB do chat) — ver `CONTEXTO.md`. No Mac: 4K na pasta do Drive.
- Publicar o **estúdio** do vídeo (Artifact) para o cliente ajustar sem digitar.
