import React, { useEffect, useState } from "react";
import {
  AbsoluteFill, CalculateMetadataFunction, continueRender, delayRender, interpolate, spring,
  staticFile, useCurrentFrame, useVideoConfig, Easing,
} from "remotion";

// Elementos de motion graphics do editor, renderizados com fundo TRANSPARENTE (ProRes 4444)
// e sobrepostos pelo FFmpeg no tempo exato da fala. Regra do cliente: tudo em BRANCO —
// destaque só com fonte, peso, tamanho e itálico (nunca cores).

export type Tema = {
  fonte: string;          // família principal (Inter, JetBrains Mono...)
  fonte_titulo: string;   // callout / título de conceito
  animacao: "pop" | "suave" | "deslize" | "digitacao";
  espacamento: number;    // letter-spacing em em
  caixa_alta_destaque: boolean;
};

type Palavra = { w: string; s: number; kw?: number };

export type Props = {
  tipo: "card" | "contador" | "callout" | "gancho";
  W: number; H: number; fps: number; dur: number;
  tema: Tema;
  // card / gancho
  palavras?: Palavra[];
  y?: number;             // centro vertical (fração da altura)
  // contador
  valor?: number; unidade?: string; dur_conta?: number;
  // callout
  texto?: string;
};

// Fontes do cliente em todos os modelos: Rubik Bold (texto comum) + Noto Serif (destaque).
const FONTES: [string, string, string, string][] = [
  ["Rubik", "Rubik-Regular.ttf", "400", "normal"],
  ["Rubik", "Rubik-Medium.ttf", "500", "normal"],
  ["Rubik", "Rubik-Bold.ttf", "700", "normal"],
  ["Rubik", "Rubik-ExtraBold.ttf", "800", "normal"],
  ["Rubik", "Rubik-Black.ttf", "900", "normal"],
  ["Rubik", "Rubik-BoldItalic.ttf", "700", "italic"],
  ["Noto Serif", "NotoSerif-Regular.ttf", "400", "normal"],
  ["Noto Serif", "NotoSerif-Bold.ttf", "700", "normal"],
  ["Noto Serif", "NotoSerif-Black.ttf", "900", "normal"],
  ["Noto Serif", "NotoSerif-Italic.ttf", "400", "italic"],
  ["Noto Serif", "NotoSerif-BoldItalic.ttf", "700", "italic"],
  ["Noto Serif", "NotoSerif-BlackItalic.ttf", "900", "italic"],
  // Black Jack (Typadelic) — copiada de assets/fonts pelo editor; a licença não permite ir pro git
  ["Black Jack", "BlackJack.ttf", "400", "normal"],
];

// Fonte manuscrita (Black Jack): sem negrito/itálico falso e um pouco maior, para destacar
// sem deformar as letras.
export const SCRIPT = ["Black Jack", "BlackJack"];
export const estiloDestaque = (familia: string, peso: number, italico: boolean) =>
  SCRIPT.includes(familia)
    ? { fontFamily: familia, fontWeight: 400, fontStyle: "normal" as const, escala: 1.28 }
    : { fontFamily: familia, fontWeight: peso, fontStyle: (italico ? "italic" : "normal") as "italic" | "normal", escala: 1 };

// No Studio/render as fontes vêm de public/fonts; na página de revisão (Player) vêm do Google Fonts
// (window.__FONTES_EXTERNAS) — mesmas famílias.
const externas = () => typeof window !== "undefined" && (window as unknown as { __FONTES_EXTERNAS?: boolean }).__FONTES_EXTERNAS;
export const useFontes = () => {
  const [h] = useState(() => (externas() ? null : delayRender("fontes")));
  useEffect(() => {
    if (h === null) return;
    // cada fonte carrega sozinha: se uma faltar (ex.: Black Jack fora desta máquina) as outras seguem
    Promise.all(FONTES.map(([fam, arq, weight, style]) => {
      const f = new FontFace(fam, `url(${staticFile("fonts/" + arq)})`, { weight, style });
      return f.load().then((ok) => document.fonts.add(ok)).catch(() => undefined);
    })).then(() => continueRender(h));
  }, [h]);
};

const SOMBRA = "0 4px 18px rgba(0,0,0,0.55), 0 2px 4px rgba(0,0,0,0.6)";

// entrada de cada palavra conforme o tema (f = frames desde que a palavra foi falada)
const entrada = (anim: Tema["animacao"], f: number, fps: number) => {
  if (f < 0) return { opacity: 0, transform: "none" };
  if (anim === "digitacao") return { opacity: 1, transform: "none" };
  if (anim === "suave") {
    const p = interpolate(f, [0, 0.35 * fps], [0, 1], { extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
    return { opacity: p, transform: `translateY(${(1 - p) * 18}px)`, filter: `blur(${(1 - p) * 6}px)` };
  }
  if (anim === "deslize") {
    const p = spring({ frame: f, fps, config: { damping: 16, mass: 0.6 } });
    return { opacity: p, transform: `translateX(${(1 - p) * -40}px)` };
  }
  const p = spring({ frame: f, fps, config: { damping: 11, stiffness: 180, mass: 0.6 } });
  return { opacity: Math.min(1, p * 1.4), transform: `scale(${0.55 + 0.45 * p})` };
};

const saida = (frame: number, total: number, fps: number) =>
  interpolate(frame, [total - 0.15 * fps, total], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

// ----------------------------------------------------------------------------- card / gancho
const Frase: React.FC<{ p: Props; grande: boolean }> = ({ p, grande }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const ws = p.palavras ?? [];
  const k = Math.min(p.W, p.H) / 1080;
  const kwi = ws.reduce((b, w, i) => ((w.kw ?? 0) > (ws[b]?.kw ?? -1) ? i : b), 0);
  // nome próprio inteiro fica junto no destaque (ex.: "Y Combinator", "Steve Jobs")
  const maiusc = (i: number) => i >= 0 && i < ws.length && /^[A-ZÀ-Ý]/.test(ws[i].w) && i > 0;
  let k0 = kwi, k1 = kwi;
  if (maiusc(kwi)) {
    while (maiusc(k0 - 1) || (k0 - 1 === 0 && /^[A-ZÀ-Ý]/.test(ws[0].w) && ws[0].w.length <= 2)) k0--;
    while (maiusc(k1 + 1)) k1++;
  }
  // linhas: até 3 palavras; a palavra-chave (ou o nome) ganha a própria linha gigante
  const linhas: number[][] = [];
  let cur: number[] = [];
  ws.forEach((_, i) => {
    if (i === k0 && cur.length) { linhas.push(cur); cur = []; }
    cur.push(i);
    if (i === k1 || (cur.length === 3 && (i < k0 || i > k1))) { linhas.push(cur); cur = []; }
  });
  if (cur.length) linhas.push(cur);
  const base = (grande ? 66 : 58) * k;
  const out = saida(frame, durationInFrames, fps);
  const t = p.tema;
  return (
    <AbsoluteFill style={{ opacity: out }}>
      <div style={{
        position: "absolute", left: "6%", width: "88%", top: `${(p.y ?? 0.47) * 100}%`,
        transform: "translateY(-50%)", display: "flex", flexDirection: "column", alignItems: "center",
        gap: 6 * k, textAlign: "center",
      }}>
        {linhas.map((ln, li) => {
          const big = ln.includes(kwi);  // linha do destaque (inclui o nome inteiro)
          const ital = !big && li === linhas.length - 1 && linhas.length > 1;
          return (
            <div key={li} style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", columnGap: 0.28 * base }}>
              {ln.map((i) => {
                const w = ws[i];
                const f = frame - Math.round(w.s * fps);
                const txt = big && t.caixa_alta_destaque && !SCRIPT.includes(t.fonte_titulo) ? w.w.toUpperCase() : w.w;
                const vis = t.animacao === "digitacao"
                  ? txt.slice(0, Math.max(0, Math.floor(f / Math.max(1, fps * 0.035))))
                  : txt;
                return (
                  <span key={i} style={{
                    ...(big || ital ? estiloDestaque(t.fonte_titulo, big ? 900 : 700, ital) : { fontFamily: t.fonte, fontWeight: 700, fontStyle: "normal" as const }),
                    color: "#FFFFFF", textShadow: SOMBRA,
                    fontSize: (big ? base * 1.9 : base) * (big || ital ? estiloDestaque(t.fonte_titulo, 900, ital).escala : 1), lineHeight: 1.05, letterSpacing: `${t.espacamento}em`,
                    display: "inline-block", ...entrada(t.animacao, f, fps),
                  }}>{vis}</span>
                );
              })}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// ----------------------------------------------------------------------------- contador
const fmt = (v: number) => {
  if (v >= 1e6) return (v / 1e6).toFixed(v % 1e6 === 0 ? 0 : 1).replace(".", ",") + " mi";
  return Math.round(v).toLocaleString("pt-BR");
};

const Contador: React.FC<{ p: Props }> = ({ p }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const k = Math.min(p.W, p.H) / 1080;
  const n = (p.dur_conta ?? 1.6) * fps;
  const prog = interpolate(frame, [0, n], [0, 1], { extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  const pop = spring({ frame, fps, config: { damping: 10, stiffness: 200, mass: 0.5 } });
  const fim = spring({ frame: frame - n, fps, config: { damping: 8, stiffness: 260, mass: 0.4 } });
  const pct = p.unidade === "%";
  return (
    <AbsoluteFill style={{ opacity: saida(frame, durationInFrames, fps) }}>
      <div style={{
        position: "absolute", top: `${(p.y ?? 0.3) * 100}%`, width: "100%", textAlign: "center",
        transform: `translateY(-50%) scale(${(0.6 + 0.4 * pop) * (1 + 0.06 * fim * (1 - Math.min(1, fim)))})`,
        fontFamily: p.tema.fonte, color: "#FFFFFF", textShadow: SOMBRA,
      }}>
        <div style={{ fontWeight: 900, fontSize: 132 * k, lineHeight: 1, fontVariantNumeric: "tabular-nums" }}>
          {fmt((p.valor ?? 0) * prog)}{pct ? "%" : ""}
        </div>
        {p.unidade && !pct ? (
          <div style={{ fontWeight: 600, fontStyle: "italic", fontSize: 50 * k, marginTop: 8 * k }}>{p.unidade}</div>
        ) : null}
        <div style={{
          margin: `${14 * k}px auto 0`, height: 6 * k, borderRadius: 3 * k, background: "#FFFFFF",
          width: `${prog * 38}%`, boxShadow: SOMBRA,
        }} />
      </div>
    </AbsoluteFill>
  );
};

// ----------------------------------------------------------------------------- callout
const Callout: React.FC<{ p: Props }> = ({ p }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const k = Math.min(p.W, p.H) / 1080;
  // "escrita à mão": revela da esquerda para a direita + leve rotação e respiro
  const rev = interpolate(frame, [0, 0.45 * fps], [0, 100], { extrapolateRight: "clamp", easing: Easing.out(Easing.quad) });
  const pop = spring({ frame, fps, config: { damping: 12, stiffness: 160 } });
  const resp = 1 + 0.04 * interpolate(frame, [0.45 * fps, durationInFrames], [0, 1], { extrapolateLeft: "clamp" });
  const sub = interpolate(frame, [0.35 * fps, 0.7 * fps], [0, 100], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ opacity: saida(frame, durationInFrames, fps) }}>
      <div style={{
        position: "absolute", top: `${(p.y ?? 0.45) * 100}%`, width: "100%", textAlign: "center",
        transform: `translateY(-50%) rotate(-3deg) scale(${(0.7 + 0.3 * pop) * resp})`,
      }}>
        <div style={{
          display: "inline-block", ...estiloDestaque(p.tema.fonte_titulo, 700, false), color: "#FFFFFF",
          fontSize: 104 * k * estiloDestaque(p.tema.fonte_titulo, 700, false).escala,
          textShadow: SOMBRA, clipPath: `inset(-20% ${100 - rev}% -20% -5%)`, letterSpacing: "0.02em",
        }}>{SCRIPT.includes(p.tema.fonte_titulo) ? p.texto ?? "" : (p.texto ?? "").toUpperCase()}</div>
        <div style={{
          margin: `${4 * k}px auto 0`, height: 7 * k, width: "46%", background: "#FFFFFF", borderRadius: 4 * k,
          clipPath: `inset(0 ${100 - sub}% 0 0)`, boxShadow: SOMBRA,
        }} />
      </div>
    </AbsoluteFill>
  );
};

export const Elemento: React.FC<Props> = (p) => {
  useFontes();
  if (p.tipo === "contador") return <Contador p={p} />;
  if (p.tipo === "callout") return <Callout p={p} />;
  return <Frase p={p} grande={p.tipo === "gancho"} />;
};

export const metadados: CalculateMetadataFunction<Props> = ({ props }) => ({
  width: props.W, height: props.H, fps: props.fps,
  durationInFrames: Math.max(2, Math.round(props.dur * props.fps)),
});

export const padrao: Props = {
  tipo: "card", W: 1080, H: 1920, fps: 30, dur: 2.4,
  tema: { fonte: "Rubik", fonte_titulo: "Noto Serif", animacao: "pop", espacamento: 0, caixa_alta_destaque: true },
  palavras: [{ w: "não", s: 0 }, { w: "existe", s: 0.25 }, { w: "perfil", s: 0.55, kw: 0.6 }, { w: "perfeito", s: 0.9, kw: 0.9 }],
};
