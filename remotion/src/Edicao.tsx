import React from "react";
import {
  AbsoluteFill, CalculateMetadataFunction, Img, interpolate, OffthreadVideo, Sequence, spring, staticFile,
  useCurrentFrame, useVideoConfig,
} from "remotion";
import { Elemento, Tema, useFontes, estiloDestaque, SCRIPT } from "./Elemento";

// A edição inteira como composição Remotion — o que você vê no Studio (ou no Player da página de
// revisão) é exatamente o que é renderizado. O editor Python (editor/projeto.py) gera o projeto:
//   base     vídeo com cortes, zooms, transições, cor e áudio masterizado (FFmpeg)
//   camadas  legendas, cards, contadores, títulos, B-roll e fotos — cada uma é um <Sequence>
//            com nome, editável (texto, tempo, duração, ocultar) sem re-renderizar a base.
// Regra do cliente: tudo em branco; destaque só por fonte, peso, tamanho e itálico.

export type Palavra = { w: string; s: number; kw?: number };
export type Legenda = { id: string; t: number; dur: number; palavras: Palavra[]; y: number; oculto?: boolean };
export type Camada = {
  id: string; tipo: "broll" | "foto" | "card" | "contador" | "callout" | "gancho";
  t: number; dur: number; oculto?: boolean; nome?: string;
  arquivo?: string; corte_seco?: boolean;            // broll/foto/fundo do card
  palavras?: Palavra[]; y?: number;                  // card/gancho
  valor?: number; unidade?: string; dur_conta?: number; // contador
  texto?: string;                                    // callout
  motivo?: string;                                   // por que o editor pôs a camada (mostrado no estúdio)
};
export type Projeto = {
  nome: string; W: number; H: number; fps: number; dur: number;
  raiz: string;            // prefixo da mídia: "projetos/<slug>/" no Studio; "" na página (URLs relativas)
  base: string;
  tema: Tema & { fonte_legenda: string; tamanho_legenda: number };
  legendas: Legenda[];
  camadas: Camada[];
};

const SOMBRA = "0 3px 14px rgba(0,0,0,0.55), 0 1px 3px rgba(0,0,0,0.7)";

const midia = (p: Projeto, f: string) =>
  /^(https?:|blob:|data:|\.\/|\/)/.test(f) || p.raiz === "" ? f : staticFile(p.raiz + f);

// ----------------------------------------------------------------------------- legenda dinâmica branca
const BlocoLegenda: React.FC<{ b: Legenda; p: Projeto }> = ({ b, p }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const k = Math.min(p.W, p.H) / 1080;
  const base = p.tema.tamanho_legenda * k;
  const ws = b.palavras;
  const kwi = ws.reduce((m, w, i) => ((w.kw ?? 0) > (ws[m]?.kw ?? -1) ? i : m), 0);
  const destaque = (ws[kwi]?.kw ?? 0) >= 0.6 && ws.length > 1;
  const linhas: number[][] = destaque
    ? [ws.map((_, i) => i).filter((i) => i < kwi), [kwi], ws.map((_, i) => i).filter((i) => i > kwi)].filter((l) => l.length)
    : [ws.map((_, i) => i)];
  return (
    <AbsoluteFill>
      <div style={{
        position: "absolute", left: "7%", width: "86%", top: `${b.y * 100}%`, transform: "translateY(-50%)",
        display: "flex", flexDirection: "column", alignItems: "center", gap: 2 * k, textAlign: "center",
      }}>
        {linhas.map((ln, li) => (
          <div key={li} style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", columnGap: 0.3 * base }}>
            {ln.map((i) => {
              const w = ws[i];
              const f = frame - Math.round((w.s - b.t) * fps);
              const pop = f < 0 ? 0 : spring({ frame: f, fps, config: { damping: 14, stiffness: 220, mass: 0.5 } });
              const big = destaque && i === kwi;
              return (
                <span key={i} style={{
                  // Rubik Bold no texto comum; a troca de fonte do destaque é sempre a do cliente (Black Jack)
                  ...(big || li === 2 ? estiloDestaque(p.tema.fonte_titulo, big ? 900 : 700, !big)
                    : { fontFamily: p.tema.fonte_legenda, fontWeight: 700, fontStyle: "normal" as const }),
                  color: "#FFFFFF", textShadow: SOMBRA,
                  WebkitTextStroke: `${Math.max(1, 1.5 * k)}px rgba(0,0,0,0.35)`, paintOrder: "stroke fill",
                  fontSize: (big ? base * 1.7 : base) * (big || li === 2 ? estiloDestaque(p.tema.fonte_titulo, 900, false).escala : 1),
                  lineHeight: 1.08,
                  opacity: f < 0 ? 0 : 1, transform: `scale(${0.82 + 0.18 * pop})`, display: "inline-block",
                }}>{big && p.tema.caixa_alta_destaque && !SCRIPT.includes(p.tema.fonte_titulo) ? w.w.toUpperCase() : w.w}</span>
              );
            })}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

// ----------------------------------------------------------------------------- B-roll / foto
const Insercao: React.FC<{ c: Camada; p: Projeto }> = ({ c, p }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const fade = c.corte_seco ? 1 : Math.min(
    interpolate(frame, [0, 0.12 * fps], [0, 1], { extrapolateRight: "clamp" }),
    interpolate(frame, [durationInFrames - 0.12 * fps, durationInFrames], [1, 0], { extrapolateLeft: "clamp" }));
  const src = midia(p, c.arquivo ?? "");
  const img = /\.(jpe?g|png|webp)$/i.test(src);
  const zoom = 1 + 0.12 * (frame / Math.max(1, durationInFrames));   // Ken Burns nas fotos
  return (
    <AbsoluteFill style={{ opacity: fade }}>
      {img
        ? <Img src={src} style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${zoom})` }} />
        : <OffthreadVideo src={src} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />}
    </AbsoluteFill>
  );
};

const nomeCamada = (c: Camada) => c.nome ?? ({
  broll: "B-roll", foto: "Foto", card: "Card", contador: "Contador", callout: "Título", gancho: "Gancho",
}[c.tipo] + (c.texto ? `: ${c.texto}` : c.palavras ? `: ${c.palavras.map((w) => w.w).join(" ")}` :
  c.valor ? `: ${c.valor} ${c.unidade ?? ""}` : ""));

export const Edicao: React.FC<Projeto> = (p) => {
  useFontes();
  const { fps } = p;
  const ordem = ["broll", "foto", "card", "gancho", "callout", "contador"];
  const camadas = [...p.camadas].filter((c) => !c.oculto).sort((a, b) => ordem.indexOf(a.tipo) - ordem.indexOf(b.tipo));
  const el = (c: Camada) => ({
    W: p.W, H: p.H, fps: p.fps, dur: c.dur, tema: p.tema,
    palavras: c.palavras, y: c.y, valor: c.valor, unidade: c.unidade,
    dur_conta: c.dur_conta, texto: c.texto,
  });
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <OffthreadVideo src={midia(p, p.base)} />
      {camadas.map((c) => (
        <Sequence key={c.id} name={nomeCamada(c)} from={Math.round(c.t * fps)}
          durationInFrames={Math.max(1, Math.round(c.dur * fps))} layout="none">
          {(c.tipo === "broll" || c.tipo === "foto" || (c.tipo === "card" && c.arquivo)) && <Insercao c={c} p={p} />}
          {c.tipo !== "broll" && c.tipo !== "foto" && <AbsoluteFill><Elemento tipo={c.tipo} {...el(c)} /></AbsoluteFill>}
        </Sequence>
      ))}
      {p.legendas.filter((b) => !b.oculto).map((b) => (
        <Sequence key={b.id} name={`Legenda: ${b.palavras.map((w) => w.w).join(" ")}`} from={Math.round(b.t * fps)}
          durationInFrames={Math.max(1, Math.round(b.dur * fps))} layout="none">
          <BlocoLegenda b={b} p={p} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

export const metadadosEdicao: CalculateMetadataFunction<Projeto> = ({ props }) => ({
  width: props.W, height: props.H, fps: props.fps, durationInFrames: Math.max(1, Math.round(props.dur * props.fps)),
});
