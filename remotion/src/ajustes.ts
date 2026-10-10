// Núcleo do editor em conjunto: o que pode ser ajustado na edição sem refazer a base no FFmpeg.
// Usado pela composição (Edicao.tsx — Studio, Player da página e render final) e pelo estúdio.
//
// Todos os tempos do projeto ficam no tempo da BASE (o vídeo montado pelo FFmpeg). Os cortes feitos
// no estúdio removem trechos da base; `linearizar` converte tudo para o tempo de SAÍDA.

export type Palavra = { w: string; s: number; kw?: number };

export type Cor = {
  intensidade: number;     // 0–1 mistura do look (0 = sem look)
  exposicao: number;       // em stops (−1…+1)
  contraste: number;       // curva S (0 = linear)
  saturacao: number;       // 1 = original
  vibrance: number;
  temperatura: number;     // <0 azul, >0 quente
  tint: number;            // <0 magenta, >0 verde
  pretos: number;          // >0 levanta (lavado), <0 esmaga
  sombras: [number, number, number];
  luzes: [number, number, number];
  vinheta: number;         // 0–1
  grao: number;            // 0–1
  look?: string;           // nome do look de origem (só informativo)
};

export const COR_NEUTRA: Cor = {
  intensidade: 1, exposicao: 0, contraste: 0, saturacao: 1, vibrance: 0, temperatura: 0, tint: 0, pretos: 0,
  sombras: [0, 0, 0], luzes: [0, 0, 0], vinheta: 0, grao: 0,
};

export type Sfx = { id: string; t: number; arquivo: string; ganho_db: number; nome: string; oculto?: boolean };
export type AudioProj = {
  voz: string;                     // faixa de voz (montada, limpa)
  trilha?: string | null;          // trilha com ducking
  sfx: Sfx[];
  vol: { voz: number; trilha: number; sfx: number };   // dB
  ganho_master_db: number;         // ganho do master (prévia ≈ final; o final é remasterizado)
  trilha_ativa: boolean;
};

export type EstiloLegendas = {
  escala: number;          // 1 = tamanho do modelo
  deslocY: number;         // fração da altura (+ desce)
  estilo: "auto" | "dinamico" | "simples" | "cinetico";
  caixaAlta: boolean;
  contorno: number;        // 0–1
  sombra: number;          // 0–1
  ocultas: boolean;
};
export const ESTILO_LEGENDAS_PADRAO: EstiloLegendas = {
  escala: 1, deslocY: 0, estilo: "auto", caixaAlta: false, contorno: 0.35, sombra: 0.55, ocultas: false,
};

export type Alteracoes = {
  camadas: Record<string, Record<string, unknown>>;
  legendas: Record<string, Record<string, unknown>>;
  sfx: Record<string, Partial<Sfx>>;
  novas: Record<string, Record<string, unknown>>;   // camadas criadas no estúdio (texto, gancho…)
  cor: Partial<Cor>;
  audio: Partial<Pick<AudioProj, "vol" | "trilha_ativa">>;
  estilo_legendas: Partial<EstiloLegendas>;
  cortes: [number, number][];                       // trechos removidos (tempo da base)
  pedido: string;
};
export const SEM_ALTERACOES: Alteracoes = {
  camadas: {}, legendas: {}, sfx: {}, novas: {}, cor: {}, audio: {}, estilo_legendas: {}, cortes: [], pedido: "",
};
export const normalizar = (v: Partial<Alteracoes> | null | undefined): Alteracoes => ({
  ...SEM_ALTERACOES, ...(v ?? {}),
  camadas: v?.camadas ?? {}, legendas: v?.legendas ?? {}, sfx: v?.sfx ?? {}, novas: v?.novas ?? {},
  cor: v?.cor ?? {}, audio: v?.audio ?? {}, estilo_legendas: v?.estilo_legendas ?? {}, cortes: v?.cortes ?? [],
  pedido: v?.pedido ?? "",
});

// ------------------------------------------------------------------------------------- cortes
export type Seg = { a: number; b: number; o: number };   // base [a, b) tocando a partir de o (saída)
export type Mapa = { segs: Seg[]; dur: number; b2o: (t: number) => number | null; o2b: (t: number) => number };

export function mapaCortes(durBase: number, cortes: [number, number][]): Mapa {
  const cs = [...cortes].map(([a, b]) => [Math.max(0, Math.min(a, b)), Math.min(durBase, Math.max(a, b))] as [number, number])
    .filter(([a, b]) => b - a > 0.04).sort((x, y) => x[0] - y[0]);
  const juntos: [number, number][] = [];
  for (const c of cs) {
    const u = juntos[juntos.length - 1];
    if (u && c[0] <= u[1]) u[1] = Math.max(u[1], c[1]); else juntos.push([...c] as [number, number]);
  }
  const segs: Seg[] = [];
  let t = 0, o = 0;
  for (const [a, b] of juntos) {
    if (a > t) { segs.push({ a: t, b: a, o }); o += a - t; }
    t = b;
  }
  if (durBase > t) { segs.push({ a: t, b: durBase, o }); o += durBase - t; }
  const b2o = (x: number) => {
    for (const s of segs) if (x >= s.a - 1e-6 && x < s.b + 1e-6) return s.o + (x - s.a);
    return null;   // dentro de um corte
  };
  const o2b = (x: number) => {
    for (const s of segs) if (x < s.o + (s.b - s.a) + 1e-6) return s.a + Math.max(0, x - s.o);
    const u = segs[segs.length - 1];
    return u ? u.b : x;
  };
  return { segs, dur: o, b2o, o2b };
}

// próximo tempo de saída válido para um item que começa em t (se começa dentro de um corte, vai para o fim dele)
function entrada(m: Mapa, t: number): number | null {
  const d = m.b2o(t);
  if (d !== null) return d;
  const prox = m.segs.find((s) => s.a >= t);
  return prox ? prox.o : null;
}

// Aplica um item com {t, dur} (tempo da base) ao mapa de cortes: devolve {t, dur} na saída, ou null
export function remapear(m: Mapa, t: number, dur: number): { t: number; dur: number } | null {
  const ini = entrada(m, t);
  if (ini === null) return null;
  // fim: o quanto do intervalo [t, t+dur] sobrevive
  let vivo = 0;
  for (const s of m.segs) vivo += Math.max(0, Math.min(s.b, t + dur) - Math.max(s.a, t));
  if (vivo < 0.08) return null;
  return { t: ini, dur: vivo };
}

export const dbLin = (db: number) => Math.pow(10, db / 20);

// ------------------------------------------------------------------------------------- filtro de cor (SVG)
// Mesma conta de editor/color.py::_apply_look (temperatura/tint → curva S → pretos → split-toning →
// saturação/vibrance), em espaço sRGB, como filtro SVG — o Chrome aplica igual na prévia e no render.
const N = 33;
const amostra = (f: (x: number) => number) =>
  Array.from({ length: N }, (_, i) => Math.min(1, Math.max(0, f(i / (N - 1))))).map((v) => v.toFixed(4)).join(" ");

export function filtroCor(c: Cor) {
  const ex = Math.pow(2, c.exposicao);
  const wb = [ex * (1 + c.temperatura), ex * (1 + c.tint), ex * (1 - c.temperatura)];
  const k = c.contraste * 2.2;
  const curva = (x: number) => {
    let y = k >= 0 ? (1 - k) * x + k * (x * x * (3 - 2 * x)) : x;
    y = c.pretos >= 0 ? c.pretos + y * (1 - c.pretos) : Math.min(1, Math.max(0, (y + c.pretos) / (1 + c.pretos)));
    return y;
  };
  const split = (i: number) => (L: number) => 0.5 + c.sombras[i] * (1 - L) ** 2 + c.luzes[i] * L * L;
  const sat = Math.max(0, c.saturacao * (1 + c.vibrance * 0.5));
  return {
    wb: `${wb[0]} 0 0 0 0  0 ${wb[1]} 0 0 0  0 0 ${wb[2]} 0 0  0 0 0 1 0`,
    curva: amostra(curva),
    split: [0, 1, 2].map((i) => amostra(split(i))),
    sat: sat.toFixed(4),
    mix: Math.min(1, Math.max(0, c.intensidade)),
  };
}
