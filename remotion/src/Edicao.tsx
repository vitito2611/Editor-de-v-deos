import React, { useMemo } from "react";
import {
  AbsoluteFill, Audio, CalculateMetadataFunction, Img, interpolate, OffthreadVideo, Sequence, spring, staticFile,
  useCurrentFrame, useVideoConfig, random,
} from "remotion";
import { Elemento, Tema, useFontes, estiloDestaque, SCRIPT } from "./Elemento";
import {
  Alteracoes, AudioProj, COR_NEUTRA, Cor, dbLin, ESTILO_LEGENDAS_PADRAO, EstiloLegendas, filtroCor, mapaCortes,
  normalizar, Palavra, remapear, Seg,
} from "./ajustes";

// A edição inteira como composição Remotion — o que se vê no Studio, no Player do estúdio da página
// e no render final é a MESMA coisa. O editor Python (editor/projeto.py) gera o projeto:
//   base     vídeo com cortes, zooms e transições (FFmpeg) — sem o look de cor, sem áudio
//   cor      o look (azul cinematográfico etc.) aplicado aqui, ao vivo, por filtro SVG (mesma conta do FFmpeg)
//   áudio    voz, trilha e cada efeito sonoro separados (volumes editáveis)
//   camadas  legendas, cards, motions, B-roll e fotos — cada uma é um <Sequence> editável
//   cortes   trechos removidos no estúdio
// Regra do cliente: legendas em branco; destaque só por fonte, peso, tamanho e itálico.

export type { Palavra };
export type Legenda = {
  id: string; t: number; dur: number; palavras: Palavra[]; y: number; oculto?: boolean;
  estilo?: "dinamico" | "cinetico" | "simples";   // segue o modelo (ex.: referencia1 = simples + cinetico)
  estilo_fixo?: "dinamico" | "cinetico" | "simples";   // escolhido no estúdio (vence o estilo geral)
  sem_destaque?: boolean;
  tamanho?: number; dy?: number;
};
export type Camada = {
  id: string; tipo: "broll" | "foto" | "card" | "contador" | "callout" | "gancho";
  t: number; dur: number; oculto?: boolean; nome?: string;
  arquivo?: string; corte_seco?: boolean;            // broll/foto/fundo do card/motion
  cor?: boolean;                                     // recebe o look de cor (motion não recebe)
  desloc?: number;                                   // segundos pulados do início da mídia (após corte)
  palavras?: Palavra[]; y?: number;                  // card/gancho
  valor?: number; unidade?: string; dur_conta?: number; // contador
  texto?: string;                                    // callout
  motivo?: string;                                   // por que o editor pôs a camada (mostrado no estúdio)
  volume_db?: number;
};
export type Projeto = {
  nome: string; W: number; H: number; fps: number; dur: number;
  raiz: string;            // prefixo da mídia: "projetos/<slug>/" no Studio; "" na página (URLs relativas)
  base: string;
  tema: Tema & { fonte_legenda: string; tamanho_legenda: number };
  legendas: Legenda[];
  camadas: Camada[];
  cor?: Partial<Cor>;
  audio?: AudioProj | null;
  estilo_legendas?: Partial<EstiloLegendas>;
  alteracoes?: Partial<Alteracoes> | null;   // o que foi mudado no estúdio (aplicado aqui)
  sem_audio?: boolean;                       // render final: o áudio é mixado à parte (Python) e entra depois
};

type Efetivo = Omit<Projeto, "cor" | "estilo_legendas"> & {
  cor: Cor; estilo_legendas: EstiloLegendas; segs: Seg[]; sfxs: AudioProj["sfx"];
};

// ----------------------------------------------------------------------------- alterações + cortes
export function efetivo(p: Projeto): Efetivo {
  const a = normalizar(p.alteracoes);
  const novas = Object.entries(a.novas).map(([id, v]) => ({ id, tipo: "callout", t: 0, dur: 2, ...v } as Camada));
  const camadas = [...p.camadas.map((c) => ({ ...c, ...(a.camadas[c.id] ?? {}) } as Camada)), ...novas];
  const legendas = p.legendas.map((l) => ({ ...l, ...(a.legendas[l.id] ?? {}) } as Legenda));
  const cor: Cor = { ...COR_NEUTRA, ...(p.cor ?? {}), ...a.cor } as Cor;
  const estilo_legendas: EstiloLegendas = { ...ESTILO_LEGENDAS_PADRAO, ...(p.estilo_legendas ?? {}), ...a.estilo_legendas };
  const audio = p.audio ? {
    ...p.audio, vol: { ...p.audio.vol, ...(a.audio.vol ?? {}) },
    trilha_ativa: a.audio.trilha_ativa ?? p.audio.trilha_ativa ?? true,
    sfx: p.audio.sfx.map((s) => ({ ...s, ...(a.sfx[s.id] ?? {}) })),
  } : null;
  const m = mapaCortes(p.dur, a.cortes);
  const cam2: Camada[] = [];
  for (const c of camadas) {
    if (c.id.startsWith("N")) { cam2.push(c); continue; }   // camadas novas já estão no tempo de saída
    const r = remapear(m, c.t, c.dur);
    if (!r) continue;
    cam2.push({ ...c, t: r.t, dur: r.dur, desloc: Math.max(0, m.o2b(r.t) - c.t) });
  }
  const leg2: Legenda[] = [];
  for (const l of legendas) {
    const r = remapear(m, l.t, l.dur);
    if (!r) continue;
    const ws = l.palavras.map((w) => ({ ...w, s: m.b2o(w.s) })).filter((w) => w.s !== null) as Palavra[];
    if (!ws.length) continue;
    leg2.push({ ...l, t: r.t, dur: r.dur, palavras: ws });
  }
  // riser começa antes do corte (t < 0 no início do vídeo): fica como está
  const sfxs = (audio?.sfx ?? []).map((s) => ({ ...s, t: s.t < 0 ? s.t : m.b2o(s.t) })).filter((s) => s.t !== null) as AudioProj["sfx"];
  return { ...p, dur: m.dur, camadas: cam2, legendas: leg2, cor, estilo_legendas, audio, segs: m.segs, sfxs };
}

const midia = (p: { raiz: string }, f: string) =>
  /^(https?:|blob:|data:|\.\/|\/)/.test(f) || p.raiz === "" ? f : staticFile(p.raiz + f);

const sombraTexto = (e: EstiloLegendas) =>
  e.sombra > 0 ? `0 ${3 * e.sombra / 0.55}px ${14 * e.sombra / 0.55}px rgba(0,0,0,${Math.min(0.9, e.sombra)}), 0 1px 3px rgba(0,0,0,${Math.min(0.9, e.sombra + 0.15)})` : "none";

// ----------------------------------------------------------------------------- legendas
const LegendaSimples: React.FC<{ b: Legenda; p: Efetivo }> = ({ b, p }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const e = p.estilo_legendas;
  const k = Math.min(p.W, p.H) / 1080;
  const ent = interpolate(frame, [0, 0.18 * fps], [0, 1], { extrapolateRight: "clamp" });
  const sai = interpolate(frame, [durationInFrames - 0.12 * fps, durationInFrames], [1, 0], { extrapolateLeft: "clamp" });
  const txt = b.palavras.map((w) => w.w).join(" ");
  return (
    <AbsoluteFill>
      <div style={{
        position: "absolute", left: "8%", width: "84%", top: `${(b.y + e.deslocY + (b.dy ?? 0)) * 100}%`, textAlign: "center",
        transform: `translateY(calc(-50% + ${(1 - ent) * 10 * k}px))`, opacity: Math.min(ent, sai),
        fontFamily: p.tema.fonte_legenda, fontWeight: 700, color: "#FFFFFF", fontSize: (b.tamanho ?? 46) * k * e.escala,
        lineHeight: 1.15, textShadow: sombraTexto(e),
        WebkitTextStroke: e.contorno > 0 ? `${Math.max(1, 3 * e.contorno * k)}px rgba(0,0,0,${0.3 + e.contorno * 0.5})` : undefined,
        paintOrder: "stroke fill",
      }}>{e.caixaAlta ? txt.toUpperCase() : txt}</div>
    </AbsoluteFill>
  );
};

const BlocoLegenda: React.FC<{ b: Legenda; p: Efetivo; estilo: string }> = ({ b, p, estilo }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const e = p.estilo_legendas;
  const k = Math.min(p.W, p.H) / 1080;
  // cinético (frase de impacto): base maior e palavra-chave sempre gigante na fonte de destaque
  const cinetico = estilo === "cinetico";
  const base = (cinetico ? Math.min(b.tamanho ?? 96, 84) : p.tema.tamanho_legenda) * k * e.escala;
  const ws = b.palavras;
  const kwi = ws.reduce((m, w, i) => ((w.kw ?? 0) > (ws[m]?.kw ?? -1) ? i : m), 0);
  const destaque = !b.sem_destaque && ((ws[kwi]?.kw ?? 0) >= 0.6 || cinetico) && ws.length > 1;
  const linhas: number[][] = destaque
    ? [ws.map((_, i) => i).filter((i) => i < kwi), [kwi], ws.map((_, i) => i).filter((i) => i > kwi)].filter((l) => l.length)
    : [ws.map((_, i) => i)];
  return (
    <AbsoluteFill>
      <div style={{
        position: "absolute", left: "7%", width: "86%", top: `${(b.y + e.deslocY + (b.dy ?? 0)) * 100}%`, transform: "translateY(-50%)",
        display: "flex", flexDirection: "column", alignItems: "center", gap: 2 * k, textAlign: "center",
      }}>
        {linhas.map((ln, li) => (
          <div key={li} style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", columnGap: 0.3 * base }}>
            {ln.map((i) => {
              const w = ws[i];
              const f = frame - Math.round((w.s - b.t) * fps);
              const pop = f < 0 ? 0 : spring({ frame: f, fps, config: { damping: 14, stiffness: 220, mass: 0.5 } });
              const big = destaque && i === kwi;
              const dest = big || (destaque && li === 2);
              const txt = big && p.tema.caixa_alta_destaque && !SCRIPT.includes(p.tema.fonte_titulo) || e.caixaAlta && !dest ? w.w.toUpperCase() : w.w;
              return (
                <span key={i} style={{
                  // Rubik Bold no texto comum; a troca de fonte do destaque é sempre a do cliente (Black Jack)
                  ...(dest ? estiloDestaque(p.tema.fonte_titulo, big ? 900 : 700, !big)
                    : { fontFamily: p.tema.fonte_legenda, fontWeight: 700, fontStyle: "normal" as const }),
                  color: "#FFFFFF", textShadow: sombraTexto(e),
                  WebkitTextStroke: e.contorno > 0 ? `${Math.max(1, 4.3 * e.contorno * k)}px rgba(0,0,0,${0.2 + e.contorno * 0.45})` : undefined,
                  paintOrder: "stroke fill",
                  fontSize: (big ? base * 1.7 : base) * (dest ? estiloDestaque(p.tema.fonte_titulo, 900, false).escala : 1),
                  lineHeight: 1.08,
                  opacity: f < 0 ? 0 : 1, transform: `scale(${0.82 + 0.18 * pop})`, display: "inline-block",
                }}>{txt}</span>
              );
            })}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

// ----------------------------------------------------------------------------- B-roll / foto / motion
const Insercao: React.FC<{ c: Camada; p: Efetivo }> = ({ c, p }) => {
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
        : <OffthreadVideo src={src} muted trimBefore={Math.round((c.desloc ?? 0) * fps)}
          style={{ width: "100%", height: "100%", objectFit: "cover" }} />}
    </AbsoluteFill>
  );
};

// ----------------------------------------------------------------------------- cor: filtro + vinheta + grão
const FiltroCor: React.FC<{ id: string; c: Cor }> = ({ id, c }) => {
  const f = useMemo(() => filtroCor(c), [c]);
  return (
    <svg width={0} height={0} style={{ position: "absolute" }} aria-hidden>
      <filter id={id} colorInterpolationFilters="sRGB" x="0" y="0" width="1" height="1">
        <feColorMatrix type="matrix" values={f.wb} result="wb" />
        <feComponentTransfer in="wb" result="curva">
          <feFuncR type="table" tableValues={f.curva} /><feFuncG type="table" tableValues={f.curva} />
          <feFuncB type="table" tableValues={f.curva} />
        </feComponentTransfer>
        <feColorMatrix in="curva" type="matrix" result="lum"
          values="0.2126 0.7152 0.0722 0 0  0.2126 0.7152 0.0722 0 0  0.2126 0.7152 0.0722 0 0  0 0 0 1 0" />
        <feComponentTransfer in="lum" result="split">
          <feFuncR type="table" tableValues={f.split[0]} /><feFuncG type="table" tableValues={f.split[1]} />
          <feFuncB type="table" tableValues={f.split[2]} />
        </feComponentTransfer>
        <feComposite in="curva" in2="split" operator="arithmetic" k1="0" k2="1" k3="1" k4="-0.5" result="tonado" />
        <feColorMatrix in="tonado" type="saturate" values={f.sat} result="look" />
        <feComposite in="look" in2="SourceGraphic" operator="arithmetic" k1="0" k2={f.mix} k3={1 - f.mix} k4="0" />
      </filter>
    </svg>
  );
};

let ruido: string | null = null;
const texturaRuido = () => {   // ladrilho de grão gerado uma vez (determinístico)
  if (ruido || typeof document === "undefined") return ruido;
  const cv = document.createElement("canvas");
  cv.width = cv.height = 256;
  const ctx = cv.getContext("2d");
  if (!ctx) return null;
  const im = ctx.createImageData(256, 256);
  for (let i = 0; i < 256 * 256; i++) {
    const v = Math.round(random(`g${i}`) * 255);
    im.data[i * 4] = im.data[i * 4 + 1] = im.data[i * 4 + 2] = v; im.data[i * 4 + 3] = 255;
  }
  ctx.putImageData(im, 0, 0);
  ruido = cv.toDataURL("image/png");
  return ruido;
};

const Grao: React.FC<{ forca: number }> = ({ forca }) => {
  const frame = useCurrentFrame();
  const src = texturaRuido();
  if (!src || forca <= 0) return null;
  const dx = Math.floor(random(`x${frame}`) * 256), dy = Math.floor(random(`y${frame}`) * 256);
  return <AbsoluteFill style={{
    backgroundImage: `url(${src})`, backgroundPosition: `${dx}px ${dy}px`, mixBlendMode: "overlay",
    opacity: Math.min(0.6, forca * 0.45), pointerEvents: "none",
  }} />;
};

// ----------------------------------------------------------------------------- áudio
const Faixas: React.FC<{ p: Efetivo }> = ({ p }) => {
  const a = p.audio;
  if (!a || p.sem_audio) return null;
  const { fps } = p;
  const mg = a.ganho_master_db ?? 0;
  const trechos = (src: string, db: number, nome: string) => p.segs.map((s, i) => (
    <Sequence key={nome + i} name={`${nome} ${i + 1}`} from={Math.round(s.o * fps)} durationInFrames={Math.max(1, Math.round((s.b - s.a) * fps))} layout="none">
      <Audio src={midia(p, src)} trimBefore={Math.round(s.a * fps)} volume={dbLin(db + mg)} />
    </Sequence>
  ));
  return (
    <>
      {trechos(a.voz, a.vol.voz, "Voz")}
      {a.trilha && a.trilha_ativa && trechos(a.trilha, a.vol.trilha, "Trilha")}
      {p.sfxs.filter((s) => !s.oculto).map((s) => (
        <Sequence key={s.id} name={`SFX: ${s.nome}`} from={Math.max(0, Math.round(s.t * fps))} layout="none">
          <Audio src={midia(p, s.arquivo)} trimBefore={Math.max(0, Math.round(-s.t * fps))} volume={dbLin(s.ganho_db + a.vol.sfx + mg)} />
        </Sequence>
      ))}
    </>
  );
};

const nomeCamada = (c: Camada) => c.nome ?? ({
  broll: "B-roll", foto: "Foto", card: "Card", contador: "Contador", callout: "Título", gancho: "Gancho",
}[c.tipo] + (c.texto ? `: ${c.texto}` : c.palavras ? `: ${c.palavras.map((w) => w.w).join(" ")}` :
  c.valor ? `: ${c.valor} ${c.unidade ?? ""}` : ""));

export const Edicao: React.FC<Projeto> = (bruto) => {
  useFontes();
  const p = useMemo(() => efetivo(bruto), [bruto]);
  const { fps } = p;
  const idFiltro = "cor-" + (p.nome || "x").replace(/[^a-zA-Z0-9]/g, "");
  const ordem = ["broll", "foto", "card", "gancho", "callout", "contador"];
  const camadas = [...p.camadas].filter((c) => !c.oculto).sort((a, b) => ordem.indexOf(a.tipo) - ordem.indexOf(b.tipo));
  const comCor = camadas.filter((c) => (c.tipo === "broll" || c.tipo === "foto" || (c.tipo === "card" && c.arquivo)) && c.cor !== false);
  const semCor = camadas.filter((c) => !comCor.includes(c));
  const el = (c: Camada) => ({
    W: p.W, H: p.H, fps: p.fps, dur: c.dur, tema: p.tema,
    palavras: c.palavras, y: c.y, valor: c.valor, unidade: c.unidade,
    dur_conta: c.dur_conta, texto: c.texto,
  });
  const seq = (c: Camada, filho: React.ReactNode) => (
    <Sequence key={c.id} name={nomeCamada(c)} from={Math.round(c.t * fps)}
      durationInFrames={Math.max(1, Math.round(c.dur * fps))} layout="none">{filho}</Sequence>
  );
  const e = p.estilo_legendas;
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <FiltroCor id={idFiltro} c={p.cor} />
      <AbsoluteFill style={{ filter: `url(#${idFiltro})` }}>
        {p.segs.map((s, i) => (
          <Sequence key={"b" + i} name={`Vídeo ${i + 1}`} from={Math.round(s.o * fps)}
            durationInFrames={Math.max(1, Math.round((s.b - s.a) * fps))} layout="none">
            <AbsoluteFill><OffthreadVideo src={midia(p, p.base)} muted={!!p.audio || !!p.sem_audio} trimBefore={Math.round(s.a * fps)} /></AbsoluteFill>
          </Sequence>
        ))}
        {comCor.map((c) => seq(c, <Insercao c={c} p={p} />))}
      </AbsoluteFill>
      {p.cor.vinheta > 0 && <AbsoluteFill style={{ pointerEvents: "none",
        background: `radial-gradient(ellipse 78% 70% at 50% 48%, transparent 50%, rgba(0,0,0,${0.75 * p.cor.vinheta}) 100%)` }} />}
      <Grao forca={p.cor.grao} />
      {semCor.map((c) => seq(c, <>
        {(c.tipo === "broll" || c.tipo === "foto" || (c.tipo === "card" && c.arquivo)) && <Insercao c={c} p={p} />}
        {c.tipo !== "broll" && c.tipo !== "foto" && <AbsoluteFill><Elemento tipo={c.tipo} {...el(c)} /></AbsoluteFill>}
      </>))}
      {comCor.filter((c) => c.tipo === "card").map((c) => seq({ ...c, id: c.id + "-txt" },
        <AbsoluteFill><Elemento tipo="card" {...el(c)} /></AbsoluteFill>))}
      {!e.ocultas && p.legendas.filter((b) => !b.oculto).map((b) => {
        const estilo = b.estilo_fixo ?? (e.estilo !== "auto" ? e.estilo : b.estilo ?? "dinamico");
        return (
          <Sequence key={b.id} name={`Legenda: ${b.palavras.map((w) => w.w).join(" ")}`} from={Math.round(b.t * fps)}
            durationInFrames={Math.max(1, Math.round(b.dur * fps))} layout="none">
            {estilo === "simples" ? <LegendaSimples b={b} p={p} /> : <BlocoLegenda b={b} p={p} estilo={estilo} />}
          </Sequence>
        );
      })}
      <Faixas p={p} />
    </AbsoluteFill>
  );
};

export const metadadosEdicao: CalculateMetadataFunction<Projeto> = ({ props }) => {
  const d = efetivo(props).dur;
  return { width: props.W, height: props.H, fps: props.fps, durationInFrames: Math.max(1, Math.round(d * props.fps)) };
};
