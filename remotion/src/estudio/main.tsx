// Estúdio de edição em conjunto (página de revisão no claude.ai).
// Player do Remotion com a MESMA composição do render final + timeline de camadas + inspetor.
// As alterações ficam no banco da página (db: doc "edicao/atual"); o Claude lê, aplica no
// projeto.json e renderiza o final só das camadas (sem refazer cortes/cor).
import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { Player, PlayerRef } from "@remotion/player";
import { Edicao, Projeto, Camada, Legenda } from "../Edicao";

declare global {
  interface Window { PROJETO: Projeto; claude?: { use: (n: string) => Promise<any> }; __FONTES_EXTERNAS?: boolean }
}

type Item = { kind: "camada"; c: Camada } | { kind: "legenda"; c: Legenda };
type Alteracoes = { camadas: Record<string, Partial<Camada>>; legendas: Record<string, Partial<Legenda>>; pedido: string };

const VAZIO: Alteracoes = { camadas: {}, legendas: {}, pedido: "" };
const fmt = (t: number) => `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, "0")}`;
const texto = (it: Item) => it.kind === "legenda" ? it.c.palavras.map((w) => w.w).join(" ")
  : it.c.texto ?? (it.c.palavras ? it.c.palavras.map((w) => w.w).join(" ") : it.c.nome ?? (it.c.valor ? `${it.c.valor.toLocaleString("pt-BR")} ${it.c.unidade ?? ""}` : it.c.tipo));
const ROT: Record<string, string> = { broll: "B-roll", foto: "Foto", card: "Card", contador: "Contador", callout: "Título", gancho: "Gancho" };

function aplicar(base: Projeto, a: Alteracoes): Projeto {
  return {
    ...base,
    camadas: base.camadas.map((c) => ({ ...c, ...(a.camadas[c.id] ?? {}) })),
    legendas: base.legendas.map((l) => ({ ...l, ...(a.legendas[l.id] ?? {}) })),
  };
}

// troca o texto de uma legenda/card mantendo o tempo de cada palavra (palavras novas dividem o intervalo)
function reescrever(ws: { w: string; s: number; kw?: number }[], novo: string, t0: number, dur: number, relativo: boolean) {
  const toks = novo.trim().split(/\s+/).filter(Boolean);
  const ini = relativo ? 0 : t0;
  return toks.map((w, i) => {
    const velho = ws[i];
    const s = velho ? velho.s : ini + (dur * 0.8 * i) / Math.max(1, toks.length);
    const kw = /^[A-ZÀ-Ý0-9]{2,}$/.test(w) ? 1 : velho?.kw ?? 0;
    return { w, s, kw };
  });
}

const App: React.FC = () => {
  const base = window.PROJETO;
  const player = useRef<PlayerRef>(null);
  const [alt, setAlt] = useState<Alteracoes>(VAZIO);
  const [salvo, setSalvo] = useState<string>("");
  const [sel, setSel] = useState<string | null>(null);
  const [t, setT] = useState(0);
  const [db, setDb] = useState<any>(null);
  const [estado, setEstado] = useState("Carregando o banco da página…");
  const proj = useMemo(() => aplicar(base, alt), [base, alt]);

  // banco da página: carrega e acompanha as alterações salvas (inclusive de outra aba/dispositivo)
  useEffect(() => {
    let off: (() => void) | undefined;
    let vivo = true;
    (async () => {
      const d = window.claude ? await window.claude.use("db") : null;
      if (!vivo) return;
      if (!d) { setEstado("Sem banco nesta visualização: dá para testar, mas não salvar."); return; }
      setDb(d);
      setEstado("");
      off = d.doc("edicao/atual").onSnapshot((snap: any) => {
        if (!snap.exists || snap.metadata.hasPendingWrites) return;
        const v = snap.data() as any;
        const a = { camadas: v.camadas ?? {}, legendas: v.legendas ?? {}, pedido: v.pedido ?? "" };
        setAlt(a);
        setSalvo(JSON.stringify(a));
      }, () => setEstado("Conexão com o banco perdida; recarregue a página."));
    })();
    return () => { vivo = false; off?.(); };
  }, []);

  useEffect(() => {
    const p = player.current;
    if (!p) return;
    const f = (e: { detail: { frame: number } }) => setT(e.detail.frame / base.fps);
    p.addEventListener("frameupdate", f);
    return () => p.removeEventListener("frameupdate", f);
  }, [base.fps]);

  const itens: Item[] = useMemo(() => [
    ...proj.camadas.map((c) => ({ kind: "camada" as const, c })),
    ...proj.legendas.map((c) => ({ kind: "legenda" as const, c })),
  ], [proj]);
  const atual = itens.find((i) => i.c.id === sel) ?? null;
  const pendente = JSON.stringify(alt) !== (salvo || JSON.stringify(VAZIO));

  const mudar = (it: Item, patch: Record<string, unknown>) => {
    setAlt((a) => {
      const k = it.kind === "camada" ? "camadas" : "legendas";
      return { ...a, [k]: { ...a[k], [it.c.id]: { ...(a[k][it.c.id] ?? {}), ...patch } } };
    });
  };
  const desfazer = (it: Item) => setAlt((a) => {
    const k = it.kind === "camada" ? "camadas" : "legendas";
    const { [it.c.id]: _x, ...resto } = a[k];
    return { ...a, [k]: resto };
  });
  const salvar = async () => {
    if (!db) return;
    setEstado("Salvando…");
    try {
      await db.doc("edicao/atual").set({ ...alt, salvo_em: new Date().toISOString() });
      setSalvo(JSON.stringify(alt));
      setEstado("Salvo. Peça no chat: “aplica as edições da página”.");
    } catch (e: any) {
      setEstado(e?.code === "invalid_argument" ? "Você não tem permissão de salvar nesta página." : "Não salvou; tente de novo.");
    }
  };
  const ir = (s: number) => { player.current?.seekTo(Math.round(s * base.fps)); };

  const pxs = 100 / proj.dur;
  const trilhas: { nome: string; itens: Item[] }[] = [
    { nome: "B-roll e fotos", itens: itens.filter((i) => i.kind === "camada" && (i.c.tipo === "broll" || i.c.tipo === "foto")) },
    { nome: "Motion (Remotion)", itens: itens.filter((i) => i.kind === "camada" && !["broll", "foto"].includes(i.c.tipo)) },
    { nome: "Legendas", itens: itens.filter((i) => i.kind === "legenda") },
  ];
  const editado = (it: Item) => !!(it.kind === "camada" ? alt.camadas[it.c.id] : alt.legendas[it.c.id]);

  return (
    <div className="estudio">
      <div className="topo">
        <div className="monitor">
          <Player ref={player} component={Edicao} inputProps={proj} durationInFrames={Math.round(proj.dur * proj.fps)}
            fps={proj.fps} compositionWidth={proj.W} compositionHeight={proj.H} controls
            style={{ width: "100%", aspectRatio: `${proj.W} / ${proj.H}` }} acknowledgeRemotionLicense />
        </div>
        <aside className="inspetor">
          {atual ? (
            <Inspetor it={atual} editado={editado(atual)} mudar={(p) => mudar(atual, p)} desfazer={() => desfazer(atual)} ir={ir} />
          ) : (
            <div className="vazio">
              <h2>Como editar junto</h2>
              <p>Toque num bloco da linha do tempo para mudar texto, início, duração ou esconder. O vídeo ao lado já mostra a mudança.</p>
              <p>Quando terminar, salve e me diga no chat. Eu aplico e renderizo o final sem refazer os cortes.</p>
            </div>
          )}
          <label className="campo">
            <span>Pedido para o Claude (troca de foto, B-roll, música…)</span>
            <textarea id="pedido" rows={3} value={alt.pedido} placeholder="Ex.: 0:17 troca o B-roll da torcida por foto do Arruda"
              onChange={(e) => setAlt((a) => ({ ...a, pedido: e.target.value }))} />
          </label>
          <div className="acoes">
            <button type="button" className="primario" disabled={!db || !pendente} onClick={salvar}>
              {pendente ? "Salvar alterações" : "Tudo salvo"}
            </button>
            {estado && <span className="estado">{estado}</span>}
          </div>
        </aside>
      </div>
      <section className="timeline" aria-label="Linha do tempo">
        <div className="regua">
          {Array.from({ length: Math.floor(proj.dur / 5) + 1 }, (_, i) => (
            <span key={i} style={{ left: `${i * 5 * pxs}%` }}>{fmt(i * 5)}</span>
          ))}
        </div>
        {trilhas.map((tr) => {
          // blocos que se sobrepõem na mesma trilha vão para uma sub-linha
          const fins: number[] = [];
          const lane = new Map<string, number>();
          [...tr.itens].sort((a, b) => a.c.t - b.c.t).forEach((it) => {
            let l = fins.findIndex((f) => f <= it.c.t + 0.01);
            if (l < 0) { l = fins.length; fins.push(0); }
            fins[l] = it.c.t + it.c.dur;
            lane.set(it.c.id, l);
          });
          const n = Math.max(1, fins.length);
          return (
          <div className="trilha" key={tr.nome}>
            <div className="nome-trilha">{tr.nome}</div>
            <div className="faixa" style={{ height: 28 * n }}>
              {tr.itens.map((it) => (
                <button type="button" key={it.c.id} title={`${fmt(it.c.t)} · ${texto(it)}`}
                  className={`bloco t-${it.kind === "legenda" ? "legenda" : it.c.tipo}${sel === it.c.id ? " sel" : ""}${it.c.oculto ? " oculto" : ""}${editado(it) ? " editado" : ""}`}
                  style={{ left: `${it.c.t * pxs}%`, width: `${Math.max(0.6, it.c.dur * pxs)}%`, top: 3 + 28 * (lane.get(it.c.id) ?? 0) }}
                  onClick={() => { setSel(it.c.id); ir(it.c.t); }}>
                  <span>{texto(it)}</span>
                </button>
              ))}
            </div>
          </div>
          );
        })}
        <div className="cabeca" style={{ left: `calc(var(--nome-w) + (100% - var(--nome-w)) * ${t / proj.dur})` }} />
      </section>
    </div>
  );
};

const Inspetor: React.FC<{ it: Item; editado: boolean; mudar: (p: Record<string, unknown>) => void; desfazer: () => void; ir: (s: number) => void }> =
  ({ it, editado, mudar, desfazer, ir }) => {
    const c: any = it.c;
    const tipo = it.kind === "legenda" ? "Legenda" : ROT[c.tipo] ?? c.tipo;
    const temTexto = it.kind === "legenda" || ["card", "gancho"].includes(c.tipo) || c.tipo === "callout";
    const txt = it.kind === "legenda" || c.palavras ? (c.palavras ?? []).map((w: any) => w.w).join(" ") : c.texto ?? "";
    const [rascunho, setRascunho] = useState(txt);
    useEffect(() => setRascunho(txt), [c.id, txt]);
    const aplicarTexto = () => {
      if (rascunho === txt) return;
      if (c.tipo === "callout") mudar({ texto: rascunho });
      else mudar({ palavras: reescrever(c.palavras ?? [], rascunho, c.t, c.dur, it.kind !== "legenda") });
    };
    return (
      <div className="ficha">
        <div className="ficha-topo">
          <span className="tag">{tipo}</span>
          <button type="button" className="link" onClick={() => ir(c.t)}>{fmt(c.t)}</button>
          {editado && <button type="button" className="link" onClick={desfazer}>desfazer</button>}
        </div>
        {c.motivo && <p className="motivo">{c.motivo}</p>}
        {temTexto && (
          <label className="campo">
            <span>Texto {it.kind !== "legenda" && <em>(palavra em CAIXA ALTA vira destaque)</em>}</span>
            <textarea id={`txt-${c.id}`} rows={2} value={rascunho} onChange={(e) => setRascunho(e.target.value)} onBlur={aplicarTexto} />
          </label>
        )}
        {c.tipo === "contador" && (
          <div className="linha">
            <label className="campo"><span>Valor</span>
              <input id={`val-${c.id}`} type="number" value={c.valor} onChange={(e) => mudar({ valor: Number(e.target.value) })} /></label>
            <label className="campo"><span>Unidade</span>
              <input id={`un-${c.id}`} value={c.unidade ?? ""} onChange={(e) => mudar({ unidade: e.target.value })} /></label>
          </div>
        )}
        <div className="linha">
          <label className="campo"><span>Início (s)</span>
            <input id={`ini-${c.id}`} type="number" step={0.1} value={c.t} onChange={(e) => {
              const nt = Math.max(0, Number(e.target.value));
              const d = nt - c.t;
              const patch: any = { t: nt };
              if (it.kind === "legenda") patch.palavras = c.palavras.map((w: any) => ({ ...w, s: w.s + d }));
              mudar(patch);
            }} /></label>
          <label className="campo"><span>Duração (s)</span>
            <input id={`dur-${c.id}`} type="number" step={0.1} min={0.2} value={c.dur} onChange={(e) => mudar({ dur: Math.max(0.2, Number(e.target.value)) })} /></label>
        </div>
        <label className="check">
          <input id={`oc-${c.id}`} type="checkbox" checked={!!c.oculto} onChange={(e) => mudar({ oculto: e.target.checked })} />
          Esconder no vídeo
        </label>
      </div>
    );
  };

window.__FONTES_EXTERNAS = true;
createRoot(document.getElementById("app")!).render(<App />);
