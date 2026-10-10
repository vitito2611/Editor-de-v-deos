// Estúdio de edição em conjunto (página no claude.ai) — editor completo.
// Player do Remotion com a MESMA composição do render final + linha do tempo com arrastar/redimensionar
// + painéis de Cor, Legendas, Áudio, Camadas e Cortes. Tudo salva sozinho no banco da página
// (db: doc "edicao/atual") e sincroniza entre abas/aparelhos; "Renderizar vídeo final" chama o Claude
// (comments.sendToClaude), que aplica e renderiza com e sem trilha.
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { Player, PlayerRef } from "@remotion/player";
import { Edicao, efetivo, Projeto, Camada, Legenda } from "../Edicao";
import { Alteracoes, COR_NEUTRA, Cor, ESTILO_LEGENDAS_PADRAO, EstiloLegendas, mapaCortes, normalizar, SEM_ALTERACOES } from "../ajustes";

type Look = Partial<Cor>;
declare global {
  interface Window {
    PROJETO: Projeto & { looks?: Record<string, Look>; fonte_destaque_local?: boolean };
    claude?: { use: (n: string) => Promise<any> }; __FONTES_EXTERNAS?: boolean;
  }
}

type Sel = { kind: "camada" | "legenda" | "sfx"; id: string } | null;
type Aba = "cor" | "legendas" | "audio" | "camadas" | "cortes";

const fmt = (t: number) => {
  const s = Math.max(0, t);
  return `${Math.floor(s / 60)}:${(s % 60).toFixed(1).padStart(4, "0")}`;
};
const ROT: Record<string, string> = { broll: "B-roll", foto: "Foto", card: "Card", contador: "Contador", callout: "Título", gancho: "Gancho" };
const nomeCam = (c: Camada) => c.nome ?? (ROT[c.tipo] + (c.texto ? `: ${c.texto}` : c.palavras ? `: ${c.palavras.map((w) => w.w).join(" ")}` : ""));
const txtLeg = (l: Legenda) => l.palavras.map((w) => w.w).join(" ");
const igual = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));

// troca o texto mantendo o tempo de cada palavra (palavras novas dividem o intervalo)
function reescrever(ws: { w: string; s: number; kw?: number }[], novo: string, t0: number, dur: number, relativo: boolean) {
  const toks = novo.trim().split(/\s+/).filter(Boolean);
  const ini = relativo ? 0 : t0;
  return toks.map((w, i) => {
    const velho = ws[i];
    const s = velho ? velho.s : ini + (dur * 0.8 * i) / Math.max(1, toks.length);
    return { w, s, kw: velho?.kw ?? 0 };
  });
}

// ===================================================================================== App
const App: React.FC = () => {
  const base = window.PROJETO;
  const player = useRef<PlayerRef>(null);
  const [alt, setAltRaw] = useState<Alteracoes>(SEM_ALTERACOES);
  const hist = useRef<{ antes: Alteracoes[]; depois: Alteracoes[]; ultimo: string; quando: number }>({ antes: [], depois: [], ultimo: "", quando: 0 });
  const [sel, setSel] = useState<Sel>(null);
  const [aba, setAba] = useState<Aba>("cor");
  const [t, setT] = useState(0);
  const [tocando, setTocando] = useState(false);
  const [antesDepois, setAntesDepois] = useState(false);
  const [db, setDb] = useState<any>(null);
  const [salvo, setSalvo] = useState<string>(JSON.stringify(SEM_ALTERACOES));
  const [estado, setEstado] = useState("Conectando ao banco da página…");
  const [statusRender, setStatusRender] = useState<any>(null);

  // ---------------------------------------------------------------- alterações (com desfazer/refazer)
  const mudar = useCallback((fn: (a: Alteracoes) => Alteracoes, grupo = "") => {
    setAltRaw((a) => {
      const n = fn(a);
      if (igual(n, a)) return a;
      const h = hist.current, agora = Date.now();
      if (!(grupo && grupo === h.ultimo && agora - h.quando < 900)) { h.antes.push(a); if (h.antes.length > 200) h.antes.shift(); }
      h.depois = []; h.ultimo = grupo; h.quando = agora;
      return n;
    });
  }, []);
  const desfazer = () => setAltRaw((a) => { const h = hist.current; const p = h.antes.pop(); if (!p) return a; h.depois.push(a); h.ultimo = ""; return p; });
  const refazer = () => setAltRaw((a) => { const h = hist.current; const p = h.depois.pop(); if (!p) return a; h.antes.push(a); h.ultimo = ""; return p; });

  // ---------------------------------------------------------------- banco: carrega, acompanha e salva sozinho
  const salvoRef = useRef(salvo);
  salvoRef.current = salvo;
  const altRef = useRef(alt);
  altRef.current = alt;
  useEffect(() => {
    let offs: (() => void)[] = [];
    let vivo = true;
    (async () => {
      const d = window.claude ? await window.claude.use("db") : null;
      if (!vivo) return;
      if (!d) { setEstado("Sem banco nesta visualização: dá para testar, mas não salva."); return; }
      setDb(d);
      setEstado("");
      offs.push(d.doc("edicao/atual").onSnapshot((snap: any) => {
        if (!snap.exists || snap.metadata.hasPendingWrites) return;
        const v = snap.data() as any;
        const a = normalizar(v);
        const js = JSON.stringify(a);
        if (js === salvoRef.current) return;
        // mudança vinda de outra aba/aparelho: entra se não há edição local pendente
        if (JSON.stringify(altRef.current) === salvoRef.current || salvoRef.current === JSON.stringify(SEM_ALTERACOES)) {
          setAltRaw(a);
        }
        setSalvo(js);
      }, () => setEstado("Conexão com o banco perdida; recarregue a página.")));
      offs.push(d.doc("edicao/status").onSnapshot((snap: any) => { if (snap.exists) setStatusRender(snap.data()); }, () => undefined));
    })();
    return () => { vivo = false; offs.forEach((f) => f()); };
  }, []);
  const pendente = JSON.stringify(alt) !== salvo;
  useEffect(() => {
    if (!db || !pendente) return;
    const h = setTimeout(async () => {
      const js = JSON.stringify(alt);
      try {
        setEstado("Salvando…");
        await db.doc("edicao/atual").set({ ...alt, salvo_em: new Date().toISOString() });
        setSalvo(js);
        setEstado("");
      } catch (e: any) {
        setEstado(e?.code === "invalid_argument" || e?.code === "permission_denied" ? "Você não tem permissão para salvar nesta página." : "Não salvou; tentando de novo na próxima mudança.");
      }
    }, 700);
    return () => clearTimeout(h);
  }, [alt, db, pendente]);

  // ---------------------------------------------------------------- player
  const projPlayer = useMemo(() => ({
    ...base, alteracoes: antesDepois ? { ...alt, cor: { ...alt.cor, intensidade: 0, vinheta: 0, grao: 0 } } : alt,
  }), [base, alt, antesDepois]);
  const ef = useMemo(() => efetivo({ ...base, alteracoes: alt }), [base, alt]);
  const mapa = useMemo(() => mapaCortes(base.dur, alt.cortes), [base.dur, alt.cortes]);
  const fps = base.fps;
  useEffect(() => {
    const p = player.current;
    if (!p) return;
    const f = (e: { detail: { frame: number } }) => setT(e.detail.frame / fps);
    const play = () => setTocando(true), pause = () => setTocando(false);
    p.addEventListener("frameupdate", f); p.addEventListener("play", play); p.addEventListener("pause", pause);
    return () => { p.removeEventListener("frameupdate", f); p.removeEventListener("play", play); p.removeEventListener("pause", pause); };
  }, [fps]);
  const ir = useCallback((s: number) => { player.current?.seekTo(Math.round(clamp(s, 0, ef.dur) * fps)); setT(clamp(s, 0, ef.dur)); }, [ef.dur, fps]);

  // ---------------------------------------------------------------- edição de itens (tempo de saída → base)
  const mudarCamada = (id: string, patch: Record<string, unknown>, grupo = "") => mudar((a) => {
    if (id.startsWith("N")) return { ...a, novas: { ...a.novas, [id]: { ...(a.novas[id] ?? {}), ...patch } } };
    return { ...a, camadas: { ...a.camadas, [id]: { ...(a.camadas[id] ?? {}), ...patch } } };
  }, grupo);
  const mudarLegenda = (id: string, patch: Record<string, unknown>, grupo = "") =>
    mudar((a) => ({ ...a, legendas: { ...a.legendas, [id]: { ...(a.legendas[id] ?? {}), ...patch } } }), grupo);
  const moverItem = (kind: "camada" | "legenda", id: string, novoT: number, novaDur?: number) => {
    if (kind === "camada") {
      const c = ef.camadas.find((x) => x.id === id);
      if (!c) return;
      const patch: Record<string, unknown> = { t: id.startsWith("N") ? Math.max(0, novoT) : mapa.o2b(Math.max(0, novoT)) };
      if (novaDur !== undefined) patch.dur = Math.max(0.2, novaDur);
      mudarCamada(id, patch, "mover" + id);
    } else {
      const orig = base.legendas.find((x) => x.id === id);
      const atual = { ...orig, ...(alt.legendas[id] ?? {}) } as Legenda;
      if (!orig) return;
      const tb = mapa.o2b(Math.max(0, novoT));
      const d = tb - atual.t;
      const patch: Record<string, unknown> = { t: tb, palavras: atual.palavras.map((w) => ({ ...w, s: w.s + d })) };
      if (novaDur !== undefined) patch.dur = Math.max(0.2, novaDur);
      mudarLegenda(id, patch, "mover" + id);
    }
  };

  // ---------------------------------------------------------------- render final (chama o Claude)
  const [comentarios, setComentarios] = useState<any>(null);
  const [podeEnviar, setPodeEnviar] = useState<string>("");
  useEffect(() => {
    (async () => {
      const c = window.claude ? await window.claude.use("comments") : null;
      setComentarios(c);
      if (c) { try { setPodeEnviar(await c.canSendToClaude()); } catch { setPodeEnviar("off"); } }
    })();
  }, []);
  const botaoRender = useRef<HTMLButtonElement>(null);
  const [envio, setEnvio] = useState("");
  const enviar = async (texto: string) => {
    if (!comentarios || !botaoRender.current) return;
    try {
      if (db && pendente) { await db.doc("edicao/atual").set({ ...alt, salvo_em: new Date().toISOString() }); setSalvo(JSON.stringify(alt)); }
      const anchor = await comentarios.anchorFor(botaoRender.current);
      await comentarios.sendToClaude({ anchor, text: texto.slice(0, 3900) });
      setEnvio("Pedido enviado. O Claude responde nos comentários desta página quando terminar.");
    } catch (e: any) {
      setEnvio(e?.code === "claude_unavailable" ? "Nenhuma sessão do Claude está acompanhando agora. Peça no chat: “renderiza a edição do estúdio”."
        : e?.code === "rate_limited" ? "Aguarde um pouco antes de enviar de novo." : "Não deu para enviar. Peça no chat: “renderiza a edição do estúdio”.");
    }
  };
  const renderizar = () => enviar(
    "Renderizar o vídeo final com a edição salva no estúdio (doc edicao/atual): aplicar, renderizar com e sem trilha e entregar." +
    (alt.pedido.trim() ? `\n\nPedido junto: ${alt.pedido.trim()}` : ""));

  // ---------------------------------------------------------------- atalhos
  const marca = useRef<{ i: number | null; o: number | null }>({ i: null, o: null });
  const [marcas, setMarcas] = useState<{ i: number | null; o: number | null }>({ i: null, o: null });
  const setMarca = (k: "i" | "o", v: number | null) => { marca.current = { ...marca.current, [k]: v }; setMarcas({ ...marca.current }); };
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      const alvo = e.target as HTMLElement;
      if (alvo && (alvo.tagName === "INPUT" || alvo.tagName === "TEXTAREA" || alvo.isContentEditable)) return;
      if (e.code === "Space") { e.preventDefault(); player.current?.toggle(); }
      else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "z") { e.preventDefault(); e.shiftKey ? refazer() : desfazer(); }
      else if (e.key === "i" || e.key === "I") setMarca("i", t);
      else if (e.key === "o" || e.key === "O") setMarca("o", t);
      else if (e.key === "ArrowLeft") ir(t - (e.shiftKey ? 1 : 1 / fps));
      else if (e.key === "ArrowRight") ir(t + (e.shiftKey ? 1 : 1 / fps));
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [t, fps, ir]);

  const nAlt = Object.keys(alt.camadas).length + Object.keys(alt.legendas).length + Object.keys(alt.sfx).length +
    Object.keys(alt.novas).length + Object.keys(alt.cor).length + Object.keys(alt.estilo_legendas).length + alt.cortes.length +
    (alt.audio.vol ? Object.keys(alt.audio.vol).length : 0) + (alt.audio.trilha_ativa === undefined ? 0 : 1);

  return (
    <div className="estudio">
      <header className="barra">
        <div className="titulo">
          <span className="selo">Estúdio</span>
          <h1>{base.nome}</h1>
        </div>
        <div className="acoes-topo">
          <span className={"salvo" + (pendente ? " pend" : "")} role="status">
            {estado || (pendente ? "Salvando…" : nAlt ? `Salvo · ${nAlt} ajuste${nAlt > 1 ? "s" : ""}` : "Sem alterações")}
          </span>
          <button type="button" className="fantasma" onClick={desfazer} disabled={!hist.current.antes.length} title="Desfazer (Ctrl+Z)">Desfazer</button>
          <button type="button" className="fantasma" onClick={refazer} disabled={!hist.current.depois.length} title="Refazer (Ctrl+Shift+Z)">Refazer</button>
          <button type="button" className="primario" ref={botaoRender} onClick={renderizar}
            disabled={!comentarios || podeEnviar !== "available"}
            title={podeEnviar === "available" ? "Chama o Claude para renderizar com e sem trilha" : "Disponível para quem edita a página, com uma sessão do Claude acompanhando"}>
            Renderizar vídeo final
          </button>
        </div>
      </header>
      {(envio || statusRender) && (
        <div className="aviso" role="status">
          {envio && <span>{envio}</span>}
          {statusRender?.mensagem && <span className={"st st-" + (statusRender.estado ?? "")}>{statusRender.mensagem}</span>}
        </div>
      )}

      <div className="topo">
        <div className="monitor">
          <Player ref={player} component={Edicao} inputProps={projPlayer} durationInFrames={Math.max(1, Math.round(ef.dur * fps))}
            fps={fps} compositionWidth={base.W} compositionHeight={base.H} controls
            style={{ width: "100%", aspectRatio: `${base.W} / ${base.H}`, borderRadius: 10, overflow: "hidden" }} acknowledgeRemotionLicense />
          <div className="sob-monitor">
            <span className="tc">{fmt(t)} / {fmt(ef.dur)}</span>
            <button type="button" className={"fantasma pequeno" + (antesDepois ? " ativo" : "")}
              onPointerDown={() => setAntesDepois(true)} onPointerUp={() => setAntesDepois(false)} onPointerLeave={() => setAntesDepois(false)}
              onKeyDown={(e) => { if (e.key === "Enter") setAntesDepois((v) => !v); }}>
              Segure: sem cor
            </button>
          </div>
        </div>

        <aside className="painel">
          <nav className="abas" role="tablist">
            {([["cor", "Cor"], ["legendas", "Legendas"], ["audio", "Áudio"], ["camadas", "Camadas"], ["cortes", "Cortes"]] as [Aba, string][]).map(([k, n]) => (
              <button key={k} type="button" role="tab" aria-selected={aba === k} className={aba === k ? "on" : ""} onClick={() => setAba(k)}>{n}</button>
            ))}
          </nav>
          <div className="conteudo">
            {aba === "cor" && <PainelCor base={base} alt={alt} mudar={mudar} />}
            {aba === "legendas" && <PainelLegendas base={base} ef={ef} alt={alt} mudar={mudar} sel={sel} setSel={setSel} ir={ir}
              mudarLegenda={mudarLegenda} moverItem={moverItem} t={t} />}
            {aba === "audio" && <PainelAudio base={base} ef={ef} alt={alt} mudar={mudar} ir={ir} />}
            {aba === "camadas" && <PainelCamadas ef={ef} alt={alt} mudar={mudar} sel={sel} setSel={setSel} ir={ir}
              mudarCamada={mudarCamada} moverItem={moverItem} t={t} />}
            {aba === "cortes" && <PainelCortes base={base} alt={alt} mudar={mudar} mapa={mapa} t={t} ir={ir} marcas={marcas} setMarca={setMarca} />}
          </div>
          <div className="pedido">
            <label htmlFor="pedido">Pedido para o Claude <em>(trocar motion, música, foto…)</em></label>
            <textarea id="pedido" rows={2} value={alt.pedido} placeholder="Ex.: no 0:17 troca o motion do celular por um gráfico"
              onChange={(e) => { const v = e.target.value; mudar((a) => ({ ...a, pedido: v }), "pedido"); }} />
            <button type="button" className="fantasma" disabled={!alt.pedido.trim() || podeEnviar !== "available"}
              onClick={() => enviar(`Pedido do estúdio (doc edicao/atual): ${alt.pedido.trim()}`)}>Enviar pedido</button>
          </div>
        </aside>
      </div>

      <Timeline ef={ef} alt={alt} base={base} t={t} tocando={tocando} ir={ir} sel={sel}
        selecionar={(s) => { setSel(s); if (s) setAba(s.kind === "legenda" ? "legendas" : s.kind === "sfx" ? "audio" : "camadas"); }}
        moverItem={moverItem} marcas={marcas} />
      <p className="dicas">Espaço: tocar/pausar · ←/→: quadro a quadro (Shift: 1 s) · I/O: marcar trecho para cortar · Ctrl+Z: desfazer.
        Tudo salva sozinho e aparece para quem estiver com a página aberta.</p>
    </div>
  );
};

// ===================================================================================== controles
const Deslizante: React.FC<{ id: string; rotulo: string; v: number; min: number; max: number; passo: number; fmt: (v: number) => string;
  padrao?: number; aoMudar: (v: number) => void }> = ({ id, rotulo, v, min, max, passo, fmt: f, padrao, aoMudar }) => (
  <div className="desl">
    <label htmlFor={id}>{rotulo}</label>
    <input id={id} type="range" min={min} max={max} step={passo} value={v} onChange={(e) => aoMudar(Number(e.target.value))}
      onDoubleClick={() => padrao !== undefined && aoMudar(padrao)} />
    <output htmlFor={id}>{f(v)}</output>
  </div>
);
const pct = (v: number) => `${Math.round(v * 100)}%`;
const sinal = (v: number, d = 2) => (v > 0 ? "+" : "") + v.toFixed(d);
const db = (v: number) => (v <= -40 ? "mudo" : `${v > 0 ? "+" : ""}${v.toFixed(1)} dB`);

type PProps = { base: Window["PROJETO"]; alt: Alteracoes; mudar: (fn: (a: Alteracoes) => Alteracoes, g?: string) => void };

const PainelCor: React.FC<PProps> = ({ base, alt, mudar }) => {
  const c: Cor = { ...COR_NEUTRA, ...(base.cor ?? {}), ...alt.cor } as Cor;
  const orig: Cor = { ...COR_NEUTRA, ...(base.cor ?? {}) } as Cor;
  const set = (k: keyof Cor) => (v: number) => mudar((a) => ({ ...a, cor: { ...a.cor, [k]: v } }), "cor-" + k);
  const looks = base.looks ?? {};
  const aplicarLook = (nome: string) => mudar((a) => ({ ...a, cor: nome === "nenhum"
    ? { look: "nenhum", intensidade: 0 } : { ...looks[nome], look: nome, intensidade: 1, exposicao: c.exposicao, vinheta: c.vinheta, grao: c.grao } }));
  const S = (k: keyof Cor, r: string, min: number, max: number, passo: number, f: (v: number) => string) =>
    <Deslizante key={k} id={"cor-" + k} rotulo={r} v={c[k] as number} min={min} max={max} passo={passo} fmt={f} padrao={orig[k] as number} aoMudar={set(k)} />;
  return (
    <div className="grupo">
      <h2>Look</h2>
      <div className="chips">
        {["nenhum", ...Object.keys(looks)].map((n) => (
          <button key={n} type="button" className={"chip" + ((c.look ?? orig.look) === n ? " on" : "")} onClick={() => aplicarLook(n)}>
            {n === "nenhum" ? "Sem look" : n.replace(/_/g, " ")}
          </button>
        ))}
      </div>
      {S("intensidade", "Intensidade do look", 0, 1, 0.01, pct)}
      <h2>Ajustes</h2>
      {S("exposicao", "Exposição", -1, 1, 0.01, (v) => sinal(v) + " EV")}
      {S("contraste", "Contraste", -0.1, 0.45, 0.005, (v) => sinal(v * 100, 0))}
      {S("saturacao", "Saturação", 0, 1.6, 0.01, pct)}
      {S("vibrance", "Vibrância", -0.3, 0.4, 0.01, (v) => sinal(v * 100, 0))}
      {S("temperatura", "Temperatura", -0.2, 0.2, 0.005, (v) => (v < 0 ? "azul " : v > 0 ? "quente " : "") + Math.abs(v * 100).toFixed(0))}
      {S("tint", "Tint", -0.1, 0.1, 0.005, (v) => (v < 0 ? "magenta " : v > 0 ? "verde " : "") + Math.abs(v * 100).toFixed(0))}
      {S("pretos", "Pretos", -0.1, 0.15, 0.005, (v) => sinal(v * 100, 0))}
      {S("vinheta", "Vinheta", 0, 1, 0.01, pct)}
      {S("grao", "Grão de filme", 0, 1, 0.01, pct)}
      <div className="linha-botoes">
        <button type="button" className="fantasma" onClick={() => mudar((a) => ({ ...a, cor: {} }))} disabled={!Object.keys(alt.cor).length}>Voltar à cor do Claude</button>
      </div>
      <p className="nota">Duplo clique num controle volta ao valor original. A prévia usa a mesma conta do vídeo final.</p>
    </div>
  );
};

type EfP = ReturnType<typeof efetivo>;

const PainelLegendas: React.FC<PProps & { ef: EfP; sel: Sel; setSel: (s: Sel) => void; ir: (s: number) => void; t: number;
  mudarLegenda: (id: string, p: Record<string, unknown>, g?: string) => void; moverItem: (k: "camada" | "legenda", id: string, t: number, d?: number) => void }> =
  ({ base, ef, alt, mudar, sel, setSel, ir, mudarLegenda, moverItem, t }) => {
    const e: EstiloLegendas = { ...ESTILO_LEGENDAS_PADRAO, ...(base.estilo_legendas ?? {}), ...alt.estilo_legendas };
    const set = (k: keyof EstiloLegendas) => (v: unknown) => mudar((a) => ({ ...a, estilo_legendas: { ...a.estilo_legendas, [k]: v } }), "leg-" + k);
    const atual = sel?.kind === "legenda" ? ef.legendas.find((l) => l.id === sel.id) : null;
    const listaRef = useRef<HTMLDivElement>(null);
    const ativa = ef.legendas.find((l) => t >= l.t && t < l.t + l.dur);
    return (
      <div className="grupo">
        <h2>Todas as legendas</h2>
        <Deslizante id="leg-escala" rotulo="Tamanho" v={e.escala} min={0.6} max={1.6} passo={0.01} fmt={pct} padrao={1} aoMudar={set("escala")} />
        <Deslizante id="leg-y" rotulo="Altura" v={e.deslocY} min={-0.25} max={0.25} passo={0.005} fmt={(v) => (v < 0 ? "↑ " : v > 0 ? "↓ " : "") + Math.abs(v * 100).toFixed(1) + "%"} padrao={0} aoMudar={set("deslocY")} />
        <Deslizante id="leg-contorno" rotulo="Contorno" v={e.contorno} min={0} max={1} passo={0.01} fmt={pct} padrao={ESTILO_LEGENDAS_PADRAO.contorno} aoMudar={set("contorno")} />
        <Deslizante id="leg-sombra" rotulo="Sombra" v={e.sombra} min={0} max={1} passo={0.01} fmt={pct} padrao={ESTILO_LEGENDAS_PADRAO.sombra} aoMudar={set("sombra")} />
        <div className="campo-linha">
          <label htmlFor="leg-estilo">Animação</label>
          <select id="leg-estilo" value={e.estilo} onChange={(ev) => set("estilo")(ev.target.value)}>
            <option value="auto">Do modelo</option><option value="dinamico">Dinâmica (palavra a palavra)</option>
            <option value="simples">Simples (frase inteira)</option><option value="cinetico">Cinética (destaque grande)</option>
          </select>
        </div>
        <label className="check"><input id="leg-caixa" type="checkbox" checked={e.caixaAlta} onChange={(ev) => set("caixaAlta")(ev.target.checked)} /> Caixa alta</label>
        <label className="check"><input id="leg-ocultas" type="checkbox" checked={e.ocultas} onChange={(ev) => set("ocultas")(ev.target.checked)} /> Esconder todas</label>

        {atual ? (
          <FichaLegenda key={atual.id} l={atual} base={base} alt={alt} mudarLegenda={mudarLegenda} moverItem={moverItem} ir={ir} fechar={() => setSel(null)} />
        ) : (
          <>
            <h2>Cada legenda <em className="dim">({ef.legendas.length})</em></h2>
            <div className="lista" ref={listaRef}>
              {ef.legendas.map((l) => (
                <button key={l.id} type="button" className={"item" + (ativa?.id === l.id ? " agora" : "") + (l.oculto ? " oculto" : "") + (alt.legendas[l.id] ? " editado" : "")}
                  onClick={() => { setSel({ kind: "legenda", id: l.id }); ir(l.t + 0.01); }}>
                  <span className="tc">{fmt(l.t)}</span><span className="tx">{txtLeg(l)}</span>
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    );
  };

const FichaLegenda: React.FC<{ l: Legenda; base: Window["PROJETO"]; alt: Alteracoes; mudarLegenda: (id: string, p: Record<string, unknown>, g?: string) => void;
  moverItem: (k: "camada" | "legenda", id: string, t: number, d?: number) => void; ir: (s: number) => void; fechar: () => void }> =
  ({ l, base, alt, mudarLegenda, moverItem, ir, fechar }) => {
    const orig = base.legendas.find((x) => x.id === l.id)!;
    const cur = { ...orig, ...(alt.legendas[l.id] ?? {}) } as Legenda;   // tempo da base (para editar palavras)
    const [rasc, setRasc] = useState(txtLeg(l));
    useEffect(() => setRasc(txtLeg(l)), [l.id]);   // eslint-disable-line react-hooks/exhaustive-deps
    const aplicarTexto = () => { if (rasc.trim() && rasc !== txtLeg(cur)) mudarLegenda(l.id, { palavras: reescrever(cur.palavras, rasc, cur.t, cur.dur, false) }); };
    const kwi = cur.palavras.reduce((m, w, i) => ((w.kw ?? 0) > (cur.palavras[m]?.kw ?? -1) ? i : m), 0);
    const temDest = !cur.sem_destaque && (cur.palavras[kwi]?.kw ?? 0) >= 0.6;
    return (
      <div className="ficha">
        <div className="ficha-topo">
          <span className="tag">Legenda</span>
          <button type="button" className="link" onClick={() => ir(l.t + 0.01)}>{fmt(l.t)}</button>
          {alt.legendas[l.id] && <button type="button" className="link" onClick={() => mudarLegenda(l.id, Object.fromEntries(Object.keys(alt.legendas[l.id]).map((k) => [k, (orig as any)[k]])))}>restaurar</button>}
          <button type="button" className="link fechar" onClick={fechar} aria-label="Fechar">Lista</button>
        </div>
        <label htmlFor={"txt-" + l.id}>Texto</label>
        <textarea id={"txt-" + l.id} rows={2} value={rasc} onChange={(e) => setRasc(e.target.value)} onBlur={aplicarTexto} />
        <div className="rot-mini">Palavra em destaque (toque para escolher)</div>
        <div className="palavras">
          {cur.palavras.map((w, i) => (
            <button key={i} type="button" className={"pal" + (temDest && i === kwi ? " on" : "")}
              onClick={() => mudarLegenda(l.id, { sem_destaque: false, palavras: cur.palavras.map((x, j) => ({ ...x, kw: j === i ? 1 : Math.min(0.5, x.kw ?? 0) })) })}>{w.w}</button>
          ))}
          <button type="button" className={"pal" + (!temDest ? " on" : "")} onClick={() => mudarLegenda(l.id, { sem_destaque: true })}>sem destaque</button>
        </div>
        <div className="campo-linha">
          <label htmlFor={"est-" + l.id}>Animação</label>
          <select id={"est-" + l.id} value={cur.estilo_fixo ?? ""} onChange={(e) => mudarLegenda(l.id, { estilo_fixo: e.target.value || undefined })}>
            <option value="">Igual às outras</option><option value="dinamico">Dinâmica</option><option value="simples">Simples</option><option value="cinetico">Cinética</option>
          </select>
        </div>
        <Deslizante id={"dy-" + l.id} rotulo="Altura desta" v={cur.dy ?? 0} min={-0.3} max={0.3} passo={0.005} fmt={(v) => (v * 100).toFixed(1) + "%"} padrao={0}
          aoMudar={(v) => mudarLegenda(l.id, { dy: v }, "dy" + l.id)} />
        <div className="linha">
          <label className="num"><span>Início (s)</span>
            <input id={"ini-" + l.id} type="number" step={0.05} value={Number(l.t.toFixed(2))} onChange={(e) => moverItem("legenda", l.id, Number(e.target.value))} /></label>
          <label className="num"><span>Duração (s)</span>
            <input id={"dur-" + l.id} type="number" step={0.05} min={0.2} value={Number(cur.dur.toFixed(2))} onChange={(e) => mudarLegenda(l.id, { dur: Math.max(0.2, Number(e.target.value)) }, "dur" + l.id)} /></label>
        </div>
        <label className="check"><input id={"oc-" + l.id} type="checkbox" checked={!!cur.oculto} onChange={(e) => mudarLegenda(l.id, { oculto: e.target.checked })} /> Esconder esta legenda</label>
      </div>
    );
  };

const PainelAudio: React.FC<PProps & { ef: EfP; ir: (s: number) => void }> = ({ base, ef, alt, mudar, ir }) => {
  const a = base.audio;
  if (!a) return <div className="grupo"><p className="nota">Este vídeo foi editado antes das faixas separadas: o áudio vem junto do vídeo. Peça no chat para refazer com áudio editável.</p></div>;
  const vol = { ...a.vol, ...(alt.audio.vol ?? {}) };
  const trilhaAtiva = alt.audio.trilha_ativa ?? a.trilha_ativa ?? true;
  const setVol = (k: "voz" | "trilha" | "sfx") => (v: number) => mudar((x) => ({ ...x, audio: { ...x.audio, vol: { ...vol, ...(x.audio.vol ?? {}), [k]: v } } }), "vol-" + k);
  return (
    <div className="grupo">
      <h2>Volumes</h2>
      <Deslizante id="vol-voz" rotulo="Voz" v={vol.voz} min={-12} max={12} passo={0.5} fmt={db} padrao={0} aoMudar={setVol("voz")} />
      {a.trilha && <Deslizante id="vol-trilha" rotulo="Trilha" v={vol.trilha} min={-40} max={12} passo={0.5} fmt={db} padrao={0} aoMudar={setVol("trilha")} />}
      <Deslizante id="vol-sfx" rotulo="Efeitos (todos)" v={vol.sfx} min={-40} max={12} passo={0.5} fmt={db} padrao={0} aoMudar={setVol("sfx")} />
      {a.trilha && <label className="check"><input id="trilha-on" type="checkbox" checked={trilhaAtiva}
        onChange={(e) => { const v = e.target.checked; mudar((x) => ({ ...x, audio: { ...x.audio, trilha_ativa: v } })); }} /> Trilha ligada</label>}
      <p className="nota">O vídeo final sai sempre em duas versões: com e sem trilha. O volume geral é ajustado no final para o padrão do Instagram.</p>
      <h2>Efeitos sonoros <em className="dim">({a.sfx.length})</em></h2>
      <div className="lista sfx">
        {a.sfx.map((s) => {
          const cur = { ...s, ...(alt.sfx[s.id] ?? {}) };
          const tOut = ef.sfxs.find((x) => x.id === s.id)?.t;
          return (
            <div key={s.id} className={"sfx-item" + (cur.oculto ? " oculto" : "") + (tOut === undefined ? " cortado" : "")}>
              <input id={"sfx-on-" + s.id} type="checkbox" checked={!cur.oculto} aria-label={"Ligar " + s.nome}
                onChange={(e) => { const v = !e.target.checked; mudar((x) => ({ ...x, sfx: { ...x.sfx, [s.id]: { ...(x.sfx[s.id] ?? {}), oculto: v } } })); }} />
              <button type="button" className="link tc" onClick={() => tOut !== undefined && ir(Math.max(0, tOut - 0.6))} disabled={tOut === undefined}>
                {tOut === undefined ? "cortado" : fmt(tOut)}</button>
              <span className="tx" title={s.nome}>{s.nome}</span>
              <input id={"sfx-g-" + s.id} type="range" min={-30} max={10} step={0.5} value={cur.ganho_db} aria-label={"Volume de " + s.nome}
                onChange={(e) => { const v = Number(e.target.value); mudar((x) => ({ ...x, sfx: { ...x.sfx, [s.id]: { ...(x.sfx[s.id] ?? {}), ganho_db: v } } }), "sfxg" + s.id); }} />
              <output htmlFor={"sfx-g-" + s.id}>{cur.ganho_db.toFixed(0)}</output>
            </div>
          );
        })}
      </div>
    </div>
  );
};

let contNovas = 0;
const PainelCamadas: React.FC<{ ef: EfP; alt: Alteracoes; mudar: PProps["mudar"]; sel: Sel; setSel: (s: Sel) => void; ir: (s: number) => void; t: number;
  mudarCamada: (id: string, p: Record<string, unknown>, g?: string) => void; moverItem: (k: "camada" | "legenda", id: string, t: number, d?: number) => void }> =
  ({ ef, alt, mudar, sel, setSel, ir, t, mudarCamada, moverItem }) => {
    const atual = sel?.kind === "camada" ? ef.camadas.find((c) => c.id === sel.id) : null;
    const nova = (tipo: "callout" | "gancho") => {
      const id = `N${Date.now().toString(36)}${(contNovas++).toString(36)}`;
      const txt = tipo === "callout" ? "Novo título" : "Seu gancho aqui";
      const extra = tipo === "callout" ? { texto: txt } : { palavras: txt.split(" ").map((w, i) => ({ w, s: i * 0.12, kw: i === 2 ? 1 : 0 })), y: 0.42 };
      mudar((a) => ({ ...a, novas: { ...a.novas, [id]: { tipo, t: Number(t.toFixed(2)), dur: 2.4, nome: tipo === "callout" ? "Título (novo)" : "Gancho (novo)", ...extra } } }));
      setSel({ kind: "camada", id });
    };
    return (
      <div className="grupo">
        <div className="linha-botoes">
          <button type="button" className="fantasma" onClick={() => nova("callout")}>+ Título em {fmt(t)}</button>
          <button type="button" className="fantasma" onClick={() => nova("gancho")}>+ Gancho em {fmt(t)}</button>
        </div>
        {atual ? <FichaCamada key={atual.id} c={atual} alt={alt} mudar={mudar} mudarCamada={mudarCamada} moverItem={moverItem} ir={ir} fechar={() => setSel(null)} /> : (
          <>
            <h2>Camadas <em className="dim">({ef.camadas.length})</em></h2>
            <div className="lista">
              {ef.camadas.map((c) => (
                <div key={c.id} className={"item" + (c.oculto ? " oculto" : "") + (alt.camadas[c.id] || alt.novas[c.id] ? " editado" : "")}>
                  <input id={"vis-" + c.id} type="checkbox" checked={!c.oculto} aria-label={"Mostrar " + nomeCam(c)} onChange={(e) => mudarCamada(c.id, { oculto: !e.target.checked })} />
                  <button type="button" className="link tc" onClick={() => ir(c.t + 0.01)}>{fmt(c.t)}</button>
                  <button type="button" className="tx botao-tx" onClick={() => { setSel({ kind: "camada", id: c.id }); ir(c.t + 0.01); }}>
                    <span className={"pino p-" + (c.nome?.startsWith("Motion") ? "motion" : c.tipo)} />{nomeCam(c)}</button>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    );
  };

const FichaCamada: React.FC<{ c: Camada; alt: Alteracoes; mudar: PProps["mudar"]; mudarCamada: (id: string, p: Record<string, unknown>, g?: string) => void;
  moverItem: (k: "camada" | "legenda", id: string, t: number, d?: number) => void; ir: (s: number) => void; fechar: () => void }> =
  ({ c, alt, mudar, mudarCamada, moverItem, ir, fechar }) => {
    const temTexto = ["card", "gancho", "callout"].includes(c.tipo);
    const txt = c.palavras ? c.palavras.map((w) => w.w).join(" ") : c.texto ?? "";
    const [rasc, setRasc] = useState(txt);
    useEffect(() => setRasc(txt), [c.id]);   // eslint-disable-line react-hooks/exhaustive-deps
    const aplicarTexto = () => {
      if (rasc === txt || !rasc.trim()) return;
      if (c.tipo === "callout") mudarCamada(c.id, { texto: rasc });
      else mudarCamada(c.id, { palavras: reescrever(c.palavras ?? [], rasc, c.t, c.dur, true).map((w) => ({ ...w, kw: /^[A-ZÀ-Ý0-9]{2,}$/.test(w.w) ? 1 : w.kw })) });
    };
    const novaCam = c.id.startsWith("N");
    return (
      <div className="ficha">
        <div className="ficha-topo">
          <span className="tag">{c.nome?.startsWith("Motion") ? "Motion" : ROT[c.tipo]}</span>
          <button type="button" className="link" onClick={() => ir(c.t + 0.01)}>{fmt(c.t)}</button>
          {!novaCam && alt.camadas[c.id] && <button type="button" className="link" onClick={() => mudar((a) => { const { [c.id]: _x, ...r } = a.camadas; return { ...a, camadas: r }; })}>restaurar</button>}
          {novaCam && <button type="button" className="link perigo" onClick={() => { mudar((a) => { const { [c.id]: _x, ...r } = a.novas; return { ...a, novas: r }; }); fechar(); }}>apagar</button>}
          <button type="button" className="link fechar" onClick={fechar}>Lista</button>
        </div>
        {c.motivo && <p className="nota">{c.motivo}</p>}
        {temTexto && (<>
          <label htmlFor={"ctx-" + c.id}>Texto {c.tipo !== "callout" && <em className="dim">(palavra em CAIXA ALTA vira destaque)</em>}</label>
          <textarea id={"ctx-" + c.id} rows={2} value={rasc} onChange={(e) => setRasc(e.target.value)} onBlur={aplicarTexto} />
        </>)}
        {(c.tipo === "gancho" || c.tipo === "card") && (
          <Deslizante id={"cy-" + c.id} rotulo="Altura" v={c.y ?? 0.47} min={0.1} max={0.9} passo={0.005} fmt={pct} padrao={0.47} aoMudar={(v) => mudarCamada(c.id, { y: v }, "cy" + c.id)} />
        )}
        <div className="linha">
          <label className="num"><span>Início (s)</span>
            <input id={"cini-" + c.id} type="number" step={0.05} value={Number(c.t.toFixed(2))} onChange={(e) => moverItem("camada", c.id, Number(e.target.value))} /></label>
          <label className="num"><span>Duração (s)</span>
            <input id={"cdur-" + c.id} type="number" step={0.05} min={0.2} value={Number(c.dur.toFixed(2))} onChange={(e) => mudarCamada(c.id, { dur: Math.max(0.2, Number(e.target.value)) }, "cdur" + c.id)} /></label>
        </div>
        <label className="check"><input id={"coc-" + c.id} type="checkbox" checked={!!c.oculto} onChange={(e) => mudarCamada(c.id, { oculto: e.target.checked })} /> Esconder no vídeo</label>
        {c.nome?.startsWith("Motion") && <p className="nota">Para mudar o conteúdo do motion, escreva no pedido para o Claude (ex.: “troca por um gráfico subindo”).</p>}
      </div>
    );
  };

const PainelCortes: React.FC<PProps & { mapa: ReturnType<typeof mapaCortes>; t: number; ir: (s: number) => void;
  marcas: { i: number | null; o: number | null }; setMarca: (k: "i" | "o", v: number | null) => void }> =
  ({ alt, mudar, mapa, t, ir, marcas, setMarca }) => {
    const ok = marcas.i !== null && marcas.o !== null && Math.abs(marcas.o - marcas.i) > 0.05;
    const cortar = () => {
      if (!ok) return;
      const a = Math.min(marcas.i!, marcas.o!), b = Math.max(marcas.i!, marcas.o!);
      const novo: [number, number] = [Number(mapa.o2b(a).toFixed(3)), Number(mapa.o2b(b).toFixed(3))];
      mudar((x) => ({ ...x, cortes: [...x.cortes, novo] }));
      setMarca("i", null); setMarca("o", null);
      ir(a);
    };
    return (
      <div className="grupo">
        <h2>Cortar um trecho</h2>
        <p className="nota">Pare no começo do trecho e marque a entrada (tecla I), depois no fim e marque a saída (tecla O).</p>
        <div className="marcas">
          <button type="button" className="fantasma" onClick={() => setMarca("i", t)}>Entrada {marcas.i !== null ? fmt(marcas.i) : "—"}</button>
          <button type="button" className="fantasma" onClick={() => setMarca("o", t)}>Saída {marcas.o !== null ? fmt(marcas.o) : "—"}</button>
        </div>
        <div className="linha-botoes">
          <button type="button" className="primario" disabled={!ok} onClick={cortar}>
            Cortar {ok ? `${Math.abs(marcas.o! - marcas.i!).toFixed(2)} s` : "trecho"}</button>
          {ok && <button type="button" className="fantasma" onClick={() => ir(Math.min(marcas.i!, marcas.o!))}>Ver trecho</button>}
        </div>
        <h2>Cortes feitos <em className="dim">({alt.cortes.length})</em></h2>
        {!alt.cortes.length && <p className="nota">Nenhum corte. Pausas e erros de gravação já foram tirados pelo Claude.</p>}
        <div className="lista">
          {alt.cortes.map(([a, b], i) => {
            const pos = mapa.b2o(Math.max(0, a - 0.001)) ?? mapa.b2o(b + 0.001) ?? 0;
            return (
              <div key={i} className="item">
                <button type="button" className="link tc" onClick={() => ir(pos)}>{fmt(pos)}</button>
                <span className="tx">−{(b - a).toFixed(2)} s</span>
                <button type="button" className="link" onClick={() => mudar((x) => ({ ...x, cortes: x.cortes.filter((_, j) => j !== i) }))}>restaurar</button>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

// ===================================================================================== linha do tempo
const Timeline: React.FC<{ ef: EfP; alt: Alteracoes; base: Window["PROJETO"]; t: number; tocando: boolean; ir: (s: number) => void; sel: Sel;
  selecionar: (s: Sel) => void; moverItem: (k: "camada" | "legenda", id: string, t: number, d?: number) => void;
  marcas: { i: number | null; o: number | null } }> = ({ ef, alt, t, tocando, ir, sel, selecionar, moverItem, marcas }) => {
  const [zoom, setZoom] = useState(28);   // px por segundo
  const rolo = useRef<HTMLDivElement>(null);
  const W = Math.max(1, ef.dur * zoom);
  const arr = useRef<{ kind: "camada" | "legenda"; id: string; x0: number; t0: number; d0: number; modo: "mover" | "fim"; moveu: boolean } | null>(null);
  useEffect(() => {   // acompanha a agulha tocando
    const r = rolo.current;
    if (!r || !tocando) return;
    const x = t * zoom;
    if (x < r.scrollLeft + 40 || x > r.scrollLeft + r.clientWidth - 80) r.scrollLeft = x - 80;
  }, [t, zoom, tocando]);
  const down = (e: React.PointerEvent, kind: "camada" | "legenda", id: string, t0: number, d0: number, modo: "mover" | "fim") => {
    e.stopPropagation();
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    arr.current = { kind, id, x0: e.clientX, t0, d0, modo, moveu: false };
  };
  const move = (e: React.PointerEvent) => {
    const a = arr.current;
    if (!a) return;
    const dt = (e.clientX - a.x0) / zoom;
    if (Math.abs(e.clientX - a.x0) > 3) a.moveu = true;
    if (!a.moveu) return;
    if (a.modo === "mover") moverItem(a.kind, a.id, Math.max(0, a.t0 + dt));
    else moverItem(a.kind, a.id, a.t0, Math.max(0.2, a.d0 + dt));
  };
  const up = (e: React.PointerEvent, kind: "camada" | "legenda" | "sfx", id: string, ti: number) => {
    const a = arr.current;
    arr.current = null;
    if (!a || !a.moveu) { selecionar({ kind, id }); ir(ti + 0.01); }
    e.stopPropagation();
  };
  const seek = (e: React.PointerEvent<HTMLDivElement>) => {
    const r = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
    ir((e.clientX - r.left) / zoom);
  };
  const faixas = (itens: { id: string; t: number; dur: number }[]) => {
    const fins: number[] = [];
    const lane = new Map<string, number>();
    [...itens].sort((a, b) => a.t - b.t).forEach((it) => {
      let l = fins.findIndex((f) => f <= it.t + 0.01);
      if (l < 0) { l = fins.length; fins.push(0); }
      fins[l] = it.t + it.dur;
      lane.set(it.id, l);
    });
    return { lane, n: Math.max(1, fins.length) };
  };
  const motion = ef.camadas.filter((c) => c.tipo === "broll" || c.tipo === "foto");
  const textos = ef.camadas.filter((c) => !(c.tipo === "broll" || c.tipo === "foto"));
  const bloco = (kind: "camada" | "legenda", c: { id: string; t: number; dur: number; oculto?: boolean }, cls: string, rot: string, lane: number, editado: boolean) => (
    <div key={c.id} role="button" tabIndex={0} title={`${fmt(c.t)} · ${rot}`}
      className={`bloco ${cls}${sel?.id === c.id ? " sel" : ""}${c.oculto ? " oculto" : ""}${editado ? " editado" : ""}`}
      style={{ left: c.t * zoom, width: Math.max(6, c.dur * zoom), top: 3 + 26 * lane }}
      onPointerDown={(e) => down(e, kind, c.id, c.t, c.dur, "mover")} onPointerMove={move} onPointerUp={(e) => up(e, kind, c.id, c.t)}
      onKeyDown={(e) => { if (e.key === "Enter") { selecionar({ kind, id: c.id }); ir(c.t + 0.01); } }}>
      <span>{rot}</span>
      <i className="alca" onPointerDown={(e) => down(e, kind, c.id, c.t, c.dur, "fim")} onPointerMove={move} onPointerUp={(e) => up(e, kind, c.id, c.t)} />
    </div>
  );
  const fm = faixas(motion), ft = faixas(textos), fl = faixas(ef.legendas);
  const passoRegua = zoom > 60 ? 1 : zoom > 20 ? 2 : 5;
  return (
    <section className="timeline" aria-label="Linha do tempo">
      <div className="tl-topo">
        <span className="tc">{fmt(t)}</span>
        <label className="zoom" htmlFor="tl-zoom">Zoom <input id="tl-zoom" type="range" min={8} max={140} value={zoom} onChange={(e) => setZoom(Number(e.target.value))} /></label>
      </div>
      <div className="tl-corpo">
        <div className="nomes">
          <div className="n regua-n" />
          <div className="n">Vídeo</div>
          <div className="n" style={{ height: 26 * fm.n + 6 }}>Motion e B-roll</div>
          <div className="n" style={{ height: 26 * ft.n + 6 }}>Títulos e cards</div>
          <div className="n" style={{ height: 26 * fl.n + 6 }}>Legendas</div>
          <div className="n">Efeitos</div>
          <div className="n">Trilha</div>
        </div>
        <div className="rolo" ref={rolo}>
          <div className="pista" style={{ width: W }}>
            <div className="regua" onPointerDown={seek}>
              {Array.from({ length: Math.floor(ef.dur / passoRegua) + 1 }, (_, i) => (
                <span key={i} style={{ left: i * passoRegua * zoom }}>{fmt(i * passoRegua).replace(/\.0$/, "")}</span>
              ))}
            </div>
            <div className="trilha" onPointerDown={seek}>
              {ef.segs.map((s, i) => <div key={i} className="seg" style={{ left: s.o * zoom, width: (s.b - s.a) * zoom }} />)}
              {ef.segs.slice(1).map((s, i) => <div key={"c" + i} className="emenda" style={{ left: s.o * zoom }} title="Corte feito no estúdio" />)}
            </div>
            <div className="trilha" style={{ height: 26 * fm.n + 6 }}>
              {motion.map((c) => bloco("camada", c, c.nome?.startsWith("Motion") ? "t-motion" : "t-broll", nomeCam(c), fm.lane.get(c.id) ?? 0, !!alt.camadas[c.id]))}
            </div>
            <div className="trilha" style={{ height: 26 * ft.n + 6 }}>
              {textos.map((c) => bloco("camada", c, "t-texto", nomeCam(c), ft.lane.get(c.id) ?? 0, !!(alt.camadas[c.id] || alt.novas[c.id])))}
            </div>
            <div className="trilha" style={{ height: 26 * fl.n + 6 }}>
              {ef.legendas.map((l) => bloco("legenda", l, "t-legenda", txtLeg(l), fl.lane.get(l.id) ?? 0, !!alt.legendas[l.id]))}
            </div>
            <div className="trilha">
              {ef.sfxs.map((s) => (
                <div key={s.id} role="button" tabIndex={0} title={`${fmt(s.t)} · ${s.nome}`}
                  className={"sfx-pino" + (s.oculto ? " oculto" : "") + (sel?.id === s.id ? " sel" : "")} style={{ left: Math.max(0, s.t) * zoom }}
                  onPointerDown={(e) => e.stopPropagation()} onPointerUp={(e) => up(e, "sfx", s.id, Math.max(0, s.t))} />
              ))}
            </div>
            <div className="trilha">
              {ef.audio?.trilha && <div className={"musica" + (ef.audio.trilha_ativa ? "" : " oculto")} style={{ left: 0, width: W }}>
                {ef.audio.trilha_ativa ? `Trilha ${(ef.audio.vol.trilha > 0 ? "+" : "") + ef.audio.vol.trilha} dB` : "Trilha desligada"}</div>}
            </div>
            {marcas.i !== null && marcas.o !== null && (
              <div className="faixa-corte" style={{ left: Math.min(marcas.i, marcas.o) * zoom, width: Math.abs(marcas.o - marcas.i) * zoom }} />
            )}
            <div className="agulha" style={{ left: t * zoom }} />
          </div>
        </div>
      </div>
    </section>
  );
};

window.__FONTES_EXTERNAS = true;
createRoot(document.getElementById("app")!).render(<App />);
