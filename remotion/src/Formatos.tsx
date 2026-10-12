import React from "react";
import { AbsoluteFill, Easing, interpolate, OffthreadVideo, spring, useCurrentFrame, useVideoConfig } from "remotion";

// Formatos que misturam a FILMAGEM do cliente com a animação (pedido: "pense em formatos bons", nível cinema).
// O vídeo vem da própria base (mesmo instante da fala, então fica sincronizado e editável no estúdio):
//   janela     o motion ocupa a tela e o cliente aparece numa janela animada (círculo/retângulo com borda de luz)
//   multiplica o cliente vira uma grade de clones (×N) — "ele multiplica"
//   monitor    o cliente encolhe para dentro da tela de um editor de vídeo que se monta sozinho — "editado por IA"
// Tudo dentro da zona segura do Reels (sem nada importante nos 420 px de cima/baixo nem na coluna da direita).

export type Quadro = { t: number; x: number; y: number; w: number; h: number; r?: number; o?: number };
export type Janela = { quadros: Quadro[]; foco?: [number, number]; borda?: boolean };
type Base = { src: string; inicio: number; filtro?: string; fps: number };

const ACENTO = "#24d0dc", MARCA = "#5d2e8c";
const EASE = Easing.bezier(0.65, 0, 0.35, 1);

// vídeo da base a partir do instante em que a camada começa
const Filmagem: React.FC<{ b: Base; foco?: [number, number]; style?: React.CSSProperties }> = ({ b, foco, style }) => (
  <OffthreadVideo src={b.src} muted trimBefore={Math.round(b.inicio * b.fps)}
    style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: `${(foco?.[0] ?? 0.5) * 100}% ${(foco?.[1] ?? 0.38) * 100}%`,
      filter: b.filtro ? `url(#${b.filtro})` : undefined, ...style }} />
);

function quadroEm(qs: Quadro[], t: number): Required<Quadro> {
  const lista = [...qs].sort((a, b) => a.t - b.t);
  const cheio = (q: Quadro): Required<Quadro> => ({ r: 0.06, o: 1, ...q } as Required<Quadro>);
  if (t <= lista[0].t) return cheio(lista[0]);
  for (let i = 0; i < lista.length - 1; i++) {
    const a = cheio(lista[i]), b = cheio(lista[i + 1]);
    if (t <= b.t) {
      const k = EASE((t - a.t) / Math.max(1e-6, b.t - a.t));
      const m = (x: number, y: number) => x + (y - x) * k;
      return { t, x: m(a.x, b.x), y: m(a.y, b.y), w: m(a.w, b.w), h: m(a.h, b.h), r: m(a.r, b.r), o: m(a.o, b.o) };
    }
  }
  return cheio(lista[lista.length - 1]);
}

const Moldura: React.FC<{ q: Required<Quadro>; W: number; H: number; borda?: boolean; children: React.ReactNode }> = ({ q, W, H, borda = true, children }) => {
  const k = Math.min(W, H) / 1080;
  const w = q.w * W, h = q.h * H, raio = q.r * Math.min(w, h) * 2;
  return (
    <div style={{
      position: "absolute", left: q.x * W - w / 2, top: q.y * H - h / 2, width: w, height: h, borderRadius: raio, overflow: "hidden",
      opacity: q.o, boxShadow: borda ? `0 0 0 ${3 * k}px rgba(36,208,220,0.9), 0 0 ${40 * k}px rgba(36,208,220,0.55), 0 ${30 * k}px ${80 * k}px rgba(0,0,0,0.6)` : undefined,
    }}>{children}</div>
  );
};

// --------------------------------------------------------------------------------------------- janela
export const FormatoJanela: React.FC<{ motion: string; janela: Janela; b: Base; W: number; H: number }> = ({ motion, janela, b, W, H }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const q = quadroEm(janela.quadros, frame / fps);
  return (
    <AbsoluteFill>
      <OffthreadVideo src={motion} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      {q.o > 0.01 && <Moldura q={q} W={W} H={H} borda={janela.borda !== false}><Filmagem b={b} foco={janela.foco} /></Moldura>}
    </AbsoluteFill>
  );
};

// --------------------------------------------------------------------------------------------- multiplica
export const FormatoMultiplica: React.FC<{ b: Base; W: number; H: number; texto?: string; fonteTitulo: string }> = ({ b, W, H, texto, fonteTitulo }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const k = Math.min(W, H) / 1080;
  const t = frame / fps;
  // grade 3x3 dentro da zona segura (um pouco à esquerda: a coluna de botões fica à direita)
  const gx0 = 0.1, gx1 = 0.785, gy0 = 0.255, gy1 = 0.745, gap = 0.012;
  const cw = (gx1 - gx0 - 2 * gap) / 3, ch = (gy1 - gy0 - 2 * gap) / 3;
  const ordem = [4, 1, 7, 3, 5, 0, 2, 6, 8];   // centro primeiro, depois em cruz, depois cantos
  const cel = (i: number) => ({ x: gx0 + (i % 3) * (cw + gap) + cw / 2, y: gy0 + Math.floor(i / 3) * (ch + gap) + ch / 2 });
  const enc = interpolate(t, [0, 0.42], [0, 1], { extrapolateRight: "clamp", easing: EASE });   // tela cheia → célula central
  const c0 = cel(4);
  const q0: Required<Quadro> = { t, x: 0.5 + (c0.x - 0.5) * enc, y: 0.5 + (c0.y - 0.5) * enc, w: 1 + (cw - 1) * enc, h: 1 + (ch - 1) * enc, r: 0.06 * enc, o: 1 };
  const valorFinal = Number((texto ?? "×10").replace(/[^\d]/g, "")) || 10;
  const nT = interpolate(t, [0.9, 1.7], [1, valorFinal], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  const tx = spring({ frame: frame - Math.round(0.85 * fps), fps, config: { damping: 12, stiffness: 160 } });
  return (
    <AbsoluteFill style={{ background: `radial-gradient(ellipse 90% 60% at 45% 50%, #2a1450 0%, #120a24 55%, #06040c 100%)` }}>
      {ordem.slice(1).map((i, n) => {
        const s = spring({ frame: frame - Math.round((0.42 + n * 0.07) * fps), fps, config: { damping: 14, stiffness: 180, mass: 0.6 } });
        if (s <= 0.001) return null;
        const c = cel(i);
        // cada clone "sai" do central e vai para a sua célula
        const q: Required<Quadro> = { t, x: c0.x + (c.x - c0.x) * s, y: c0.y + (c.y - c0.y) * s, w: cw * (0.6 + 0.4 * s), h: ch * (0.6 + 0.4 * s), r: 0.06, o: Math.min(1, s * 1.4) };
        return <Moldura key={i} q={q} W={W} H={H}><Filmagem b={b} /></Moldura>;
      })}
      <Moldura q={q0} W={W} H={H} borda={enc > 0.2}><Filmagem b={b} /></Moldura>
      {tx > 0.001 && (
        <div style={{ position: "absolute", left: 0, right: 0, top: `${0.5 * 100}%`, transform: `translate(-3%, -50%) scale(${0.6 + 0.4 * tx})`,
          textAlign: "center", fontFamily: "Rubik", fontWeight: 900, fontSize: 300 * k, color: "#fff", opacity: Math.min(1, tx * 1.5),
          letterSpacing: "-0.04em", textShadow: `0 0 ${60 * k}px rgba(36,208,220,0.85), 0 ${10 * k}px ${50 * k}px rgba(0,0,0,0.7)` }}>
          <span style={{ fontFamily: fonteTitulo, fontWeight: 400, color: ACENTO, fontSize: "0.8em" }}>×</span>{Math.round(nT)}
        </div>
      )}
    </AbsoluteFill>
  );
};

// --------------------------------------------------------------------------------------------- monitor
export const FormatoMonitor: React.FC<{ b: Base; W: number; H: number; texto?: string; dur: number }> = ({ b, W, H, texto, dur }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const k = Math.min(W, H) / 1080;
  const t = frame / fps;
  // janela do app (zona segura) e a área de preview dentro dela
  const app = { x0: 0.07, x1: 0.785, y0: 0.24, y1: 0.765 };
  const aw = (app.x1 - app.x0) * W, ah = (app.y1 - app.y0) * H;
  const prevH = ah * 0.56, prevW = prevH * 9 / 16;
  const prev = { x: (app.x0 * W + aw / 2) / W, y: (app.y0 * H + 70 * k + prevH / 2) / H, w: prevW / W, h: prevH / H };
  const enc = interpolate(t, [0, 0.5], [0, 1], { extrapolateRight: "clamp", easing: EASE });
  const qv: Required<Quadro> = { t, x: 0.5 + (prev.x - 0.5) * enc, y: 0.5 + (prev.y - 0.5) * enc, w: 1 + (prev.w - 1) * enc, h: 1 + (prev.h - 1) * enc, r: 0.035 * enc, o: 1 };
  const appIn = interpolate(t, [0.15, 0.6], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  const tlY = app.y0 * H + 70 * k + prevH + 40 * k, tlH = ah - (70 * k + prevH + 70 * k);
  const cores = [MARCA, ACENTO, "#7c5cc4", "#3f8f86"];
  // clipes determinísticos
  const trilhas = [0, 1, 2, 3].map((i) => {
    const r: { x: number; w: number }[] = [];
    let x = 0, n = 0;
    while (x < 0.98) { const w = Math.min(0.98 - x, 0.08 + ((i * 7 + n * 13) % 9) / 40); r.push({ x, w }); x += w + 0.008; n++; }
    return r;
  });
  const agulha = interpolate(t, [0.5, dur], [0.02, 0.95], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ background: `radial-gradient(ellipse 90% 60% at 45% 50%, #24124a 0%, #10091f 55%, #05030a 100%)` }}>
      <div style={{ position: "absolute", left: app.x0 * W, top: app.y0 * H, width: aw, height: ah, borderRadius: 30 * k, background: "#120c1e",
        border: `${2 * k}px solid rgba(236,232,255,0.12)`, opacity: appIn, transform: `scale(${1.06 - 0.06 * appIn})`,
        boxShadow: `0 ${40 * k}px ${90 * k}px rgba(0,0,0,0.6), 0 0 ${80 * k}px rgba(93,46,140,0.45)` }}>
        <div style={{ height: 56 * k, display: "flex", alignItems: "center", gap: 12 * k, padding: `0 ${24 * k}px`, borderBottom: "1px solid rgba(236,232,255,0.08)" }}>
          {[0, 1, 2].map((i) => <i key={i} style={{ width: 16 * k, height: 16 * k, borderRadius: "50%", background: "rgba(236,232,255,0.2)", display: "block" }} />)}
          <span style={{ marginLeft: 14 * k, fontFamily: "Rubik", fontWeight: 700, fontSize: 24 * k, color: "rgba(236,232,255,0.7)" }}>Zeal · editor</span>
          <span style={{ marginLeft: "auto", fontFamily: "Rubik", fontWeight: 700, fontSize: 22 * k, color: "#061318", background: ACENTO,
            padding: `${6 * k}px ${14 * k}px`, borderRadius: 20 * k, opacity: interpolate(t, [0.9, 1.2], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>
            {texto ?? "100% IA"}</span>
        </div>
        {/* linha do tempo se montando */}
        <div style={{ position: "absolute", left: 24 * k, right: 24 * k, top: tlY - app.y0 * H, height: tlH }}>
          {trilhas.map((tr, i) => tr.map((c, n) => {
            const s = spring({ frame: frame - Math.round((0.45 + i * 0.08 + n * 0.06) * fps), fps, config: { damping: 15, stiffness: 170 } });
            return <div key={`${i}-${n}`} style={{ position: "absolute", left: `${c.x * 100}%`, width: `${c.w * 100}%`, top: `${i * 25}%`, height: "20%",
              borderRadius: 10 * k, background: cores[(i + n) % 4], opacity: 0.88 * Math.min(1, s * 1.3), transform: `translateX(${(1 - s) * 260 * k}px)` }} />;
          }))}
          <div style={{ position: "absolute", top: -10 * k, bottom: 0, left: `${agulha * 100}%`, width: 4 * k, background: "#fff", boxShadow: `0 0 ${16 * k}px #fff` }} />
          {/* cursor da IA cortando */}
          <div style={{ position: "absolute", top: `${(Math.floor(t * 2.5) % 4) * 25 - 6}%`, left: `${agulha * 100 + 1.5}%`, width: 40 * k, height: 40 * k,
            borderRadius: "50%", background: `radial-gradient(circle, #e8fdff 0%, ${ACENTO} 45%, transparent 70%)`, opacity: interpolate(t, [0.8, 1], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }} />
        </div>
      </div>
      <Moldura q={qv} W={W} H={H} borda={enc > 0.3}><Filmagem b={b} /></Moldura>
    </AbsoluteFill>
  );
};
