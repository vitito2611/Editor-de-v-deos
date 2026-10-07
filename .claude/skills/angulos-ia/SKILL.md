---
name: angulos-ia
description: Gera ângulos de câmera realistas que nunca foram filmados (por cima do ombro, plongée, macro das mãos, perfil, contra-plongée, plano geral de trás) a partir de um vídeo gravado com UMA câmera, usando Seedance 2.0 pelo MCP da Higgsfield, e os encaixa na edição em cortes secos sincronizados com a fala. Use quando o cliente pedir "ângulos diferentes", "multicâmera com IA", "outras perspectivas", "parecer que tem várias câmeras" ou citar o vídeo de referência da Higgsfield/Seedance.
---

# Ângulos de câmera por IA (Seedance 2.0 + Higgsfield MCP)

Referência do cliente: vídeo da Higgsfield "Deixe seu vídeo mais dinâmico" — embaixo o
original (1 câmera fixa), em cima a edição trocando de ângulo a cada 1–2 s: por cima do ombro,
plongée, plano geral de trás, através de plantas em primeiro plano, macro das mãos/objeto,
POV de dentro da xícara, contra-plongée. Todos gerados por IA preservando pessoa, cenário,
gestos e tempo da fala.

## Pré-requisitos (verifique antes de gastar tempo)

1. `mcp__higgsfield__balance` → precisa de créditos. Custo por ângulo (janela de 5 s):
   720p fast ≈ 12,5 · 720p std ≈ 22,5 · 1080p ≈ 45. Um vídeo com 8 ângulos ≈ 100–360.
   Sempre confirme o custo com `generate_video` + `get_cost: true` e informe o cliente.
2. Rede do ambiente liberando: `upload.higgsfield.ai` (envio) e o CDN dos resultados
   (`d2ol7oe51mr4n9.cloudfront.net`, `*.higgsfield.ai`). Teste com curl antes.

## Passo a passo

1. **Rodar o editor com ângulos ativos** (gera o plano, sem gastar créditos):
   `python editar.py bruto.mp4 --estilo viral_reels --set angulos.ativo=true [--config plano.yaml] --preview`
   → `work/<job>/angulos/plano.yaml` + `janela_XX.mp4` (5 s, 720x1280, com áudio) + `frame_XX.jpg`.
   Revise o plano: troque `angulo` de itens se o conteúdo pedir (ex.: fala sobre as mãos → `maos`).
   Ângulos e prompts: `editor/angulos.py` (`ANGULOS`, `PROMPT_BASE`).
2. **Enviar mídia** — `mcp__higgsfield__media_upload` com `files` (janela + frame de cada item),
   depois para cada um: `curl -X PUT -H "Content-Type: <tipo>" -H "If-None-Match: *" --data-binary @arquivo "<upload_url>"`
   (precisa HTTP 200) e `mcp__higgsfield__media_confirm` (video / image).
3. **Gerar** — `mcp__higgsfield__generate_video_batch` (até 12 itens), cada item:
   ```
   model: seedance_2_0, prompt: <prompt do plano>, duration: 5, resolution: 720p,
   aspect_ratio: "9:16", generate_audio: false,
   medias: [{role: video_references, value: <media_id janela>},
            {role: image_references, value: <media_id frame>}]
   ```
   Use `mode: fast` para rascunho barato. Depois `mcp__higgsfield__jobs_wait` até terminal.
4. **Baixar e registrar** — `curl -L -o work/<job>/angulos/gerado_XX.mp4 <url do resultado>` e
   `python -m editor.angulos registrar work/<job>/angulos/plano.yaml XX gerado_XX.mp4 --job <job_id>`.
5. **Controle de qualidade (obrigatório)** — extraia frames de cada gerado e compare com o
   original: identidade (rosto, óculos, roupa), mãos (dedos extras), cenário coerente, sem texto
   e sem logo. Reprovou → `aprovado: false` no plano (ou regenere com outro ângulo/prompt).
   Ângulos com boca visível: confira a sincronia; se falhar, troque por um de `boca: 0`.
6. **Render final** — rode o editor de novo com `angulos.ativo=true` (sem `--preview`). Cada
   item aprovado vira um corte seco para o ângulo de IA no tempo exato, com a voz original por
   baixo (sem whoosh: troca de câmera não leva SFX). Entregue com e sem trilha, como sempre.

## Boas práticas

- Prefira ângulos que escondem a boca (`ombro`, `plongee`, `maos`, `geral_tras`) — a IA erra
  menos onde não precisa de sincronia labial. Alterne: original → ângulo → original.
- Trechos de 1–2,6 s; nunca no gancho (2 s iniciais) nem colados em B-roll/foto/card.
- Mantenha 1 ângulo por ideia; 6–10 por minuto é o ritmo da referência.
- Sempre respeite as preferências do cliente em `CLAUDE.md`.
