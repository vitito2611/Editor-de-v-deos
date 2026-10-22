import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { estiloDestaque } from "./Elemento";

// Layout "filme" (referência referencias/motion5/ref.mp4, pedido do vídeo 1022): fundo preto, uma cena de filme
// motivacional num card arredondado em cima, o orador num card embaixo, e a legenda como TIPOGRAFIA grande em
// cima da cena — palavras empilhadas em caixa alta (Rubik Black) com a palavra-chave na fonte manuscrita do
// cliente (Black Jack), cada bloco num lugar diferente da cena, palavras entrando no tempo da fala.

export type Caixa = [number, number, number, number];   // x, y, w, h em unidades de 1080 de largura
export type LayoutFilme = {
  tipo: "filme";
  topo: Caixa;               // card da cena de filme
  baixo: Caixa;              // card do orador
  raio?: number;             // arredondamento dos cards
  foco_y?: number;           // 0..1: que altura do vídeo do orador fica no centro do card de baixo
};

export const LAYOUT_FILME_PADRAO: LayoutFilme = {
  tipo: "filme", topo: [40, 150, 1000, 860], baixo: [40, 1040, 1000, 470], raio: 34, foco_y: 0.38,
};

export const Card: React.FC<{ c: Caixa; k: number; raio: number; children: React.ReactNode }> = ({ c, k, raio, children }) => (
  <div style={{
    position: "absolute", left: c[0] * k, top: c[1] * k, width: c[2] * k, height: c[3] * k,
    borderRadius: raio * k, overflow: "hidden", background: "#0b0b0b",
  }}>{children}</div>
);

// posições dos blocos dentro do card de cima (âncora x/y relativa ao card, alinhamento e largura do bloco).
// O topo do card fica atrás da zona do Reels (420 px): o texto só usa a parte de baixo do card.
const POSICOES: { x: number; y: number; al: "left" | "right" | "center"; larg: number }[] = [
  { x: 0.06, y: 0.52, al: "left", larg: 0.62 },
  { x: 0.94, y: 0.62, al: "right", larg: 0.6 },
  { x: 0.5, y: 0.66, al: "center", larg: 0.8 },
  { x: 0.06, y: 0.74, al: "left", larg: 0.56 },
  { x: 0.94, y: 0.5, al: "right", larg: 0.58 },
  { x: 0.5, y: 0.56, al: "center", larg: 0.72 },
];

export type BlocoFilme = {
  t: number; palavras: { w: string; s: number; kw?: number }[];
  pos?: number;                        // índice em POSICOES (o editor varia de bloco em bloco)
  tamanho?: number;                    // escala (1 = padrão), ajustável no estúdio pelo tamanho da legenda
  sem_destaque?: boolean;
};

const CAR = 0.64;   // largura média de um caractere em em (Rubik Black caixa alta)

export const LegendaFilme: React.FC<{
  b: BlocoFilme; W: number; layout: LayoutFilme; fonteTitulo: string; escala: number; dy: number; caixaAlta: boolean;
}> = ({ b, W, layout, fonteTitulo, escala, dy }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const k = W / 1080;
  const [cx, cy, cw, ch] = layout.topo;
  const P = POSICOES[(b.pos ?? 0) % POSICOES.length];
  const ws = b.palavras;
  const kwi = ws.reduce((m, w, i) => ((w.kw ?? 0) > (ws[m]?.kw ?? -1) ? i : m), 0);
  const temKw = !b.sem_destaque && ws.length > 1 && (ws[kwi]?.kw ?? 0) >= 0.4;
  // quebra: palavras curtas se juntam (até ~9 letras por linha); a palavra-chave fica sozinha
  const linhas: number[][] = [];
  ws.forEach((w, i) => {
    const ult = linhas[linhas.length - 1];
    const so = temKw && i === kwi;
    const lenUlt = ult ? ult.reduce((n, j) => n + ws[j].w.length + 1, 0) : 99;
    if (!ult || so || (temKw && ult.includes(kwi)) || lenUlt + w.w.length > 9) linhas.push([i]);
    else ult.push(i);
  });
  const largBloco = P.larg * cw * k;
  const esc = (b.tamanho ?? 1) * escala;
  const destaque = estiloDestaque(fonteTitulo, 900, true);
  const tamLinha = (ln: number[]) => {
    const txt = ln.map((i) => ws[i].w).join(" ");
    const ehKw = temKw && ln.length === 1 && ln[0] === kwi;
    const car = ehKw ? 0.5 * destaque.escala : CAR;
    // a linha tenta ocupar a largura do bloco (efeito "justificado" da referência), com limites
    return Math.max(54 * k, Math.min((ehKw ? 190 : 150) * k, largBloco / Math.max(3, txt.length * car))) * esc;
  };
  const alturas = linhas.map((ln) => tamLinha(ln) * 0.98);
  const altura = alturas.reduce((a, b2) => a + b2, 0);
  // âncora dentro do card; o bloco nunca sai do card nem sobe para a zona de cima do Reels (420 px)
  const topoMin = Math.max(cy * k + 30 * k, 430 * k);
  const fundoMax = (cy + ch) * k - 30 * k;
  const y0 = Math.min(fundoMax - altura, Math.max(topoMin, (cy + ch * P.y) * k - altura / 2 + dy * k));
  const xA = (cx + cw * P.x) * k;
  const left = P.al === "left" ? xA : P.al === "right" ? xA - largBloco : xA - largBloco / 2;
  const sai = interpolate(frame, [durationInFrames - 0.15 * fps, durationInFrames], [1, 0], { extrapolateLeft: "clamp" });
  let y = y0;
  return (
    <div style={{ position: "absolute", inset: 0, opacity: sai, pointerEvents: "none" }}>
      {linhas.map((ln, li) => {
        const fs = tamLinha(ln);
        const top = y;
        y += alturas[li];
        return (
          <div key={li} style={{
            position: "absolute", left, top, width: largBloco, textAlign: P.al, whiteSpace: "nowrap", lineHeight: 0.98,
          }}>
            {ln.map((i, wi) => {
              const w = ws[i];
              const f = frame - Math.round((w.s - b.t) * fps);
              const pop = f < 0 ? 0 : spring({ frame: f, fps, config: { damping: 15, stiffness: 240, mass: 0.45 } });
              const ehKw = temKw && i === kwi;
              const st = ehKw ? { fontFamily: destaque.fontFamily, fontWeight: destaque.fontWeight, fontStyle: destaque.fontStyle }
                : { fontFamily: "Rubik", fontWeight: 900, fontStyle: "normal" as const };
              return (
                <span key={i} style={{
                  ...st, fontSize: fs * (ehKw ? destaque.escala : 1), color: "#fff",
                  textTransform: ehKw ? "none" : "uppercase", letterSpacing: ehKw ? 0 : "-0.01em",
                  textShadow: "0 4px 24px rgba(0,0,0,0.55), 0 1px 3px rgba(0,0,0,0.6)",
                  display: "inline-block", marginLeft: wi ? 0.22 * fs : 0,
                  opacity: f < 0 ? 0 : Math.min(1, 0.25 + pop), filter: f < 0 ? undefined : `blur(${(1 - pop) * 6 * k}px)`,
                  transform: `translateY(${(1 - pop) * 18 * k}px) scale(${0.9 + 0.1 * pop})`,
                }}>{w.w}</span>
              );
            })}
          </div>
        );
      })}
    </div>
  );
};
