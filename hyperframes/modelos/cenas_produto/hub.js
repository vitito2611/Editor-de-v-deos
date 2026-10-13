// "Dominar três coisas: marketing, gestão e inteligência artificial": hub com o dentista no centro e três nós que
// acendem no tempo de cada palavra, ligados por linhas tracejadas que correm; chips de função em cada nó.
function cena() {
  varredura(T(-0.25));
  rotulo(C.rotulo || "O DENTISTA DOS PRÓXIMOS 10 ANOS", 60, 455, T(0.05));
  titulo(C.titulo || "Domine *três* coisas.", { x: 60, y: 495, tam: 90, t: T(0.1), passo: 0.08 });
  const cx = 470, cy = 1040;
  const centro = mk("div", "abs"); pos(centro, cx - 90, cy - 90);
  Object.assign(centro.style, { width: px(180), height: px(180), borderRadius: px(44), background: "#111214", padding: px(42),
    boxShadow: `0 ${px(26)} ${px(60)} rgba(17,18,20,0.25)` });
  centro.innerHTML = icone("dente", "#ffffff", 1.6);
  tl.fromTo(centro, { opacity: 0, scale: 0.6, rotation: -8 }, { opacity: 1, scale: 1, rotation: 0, duration: 0.6, ease: MOLA }, T(0.3));
  const anel = mk("div", "abs"); pos(anel, cx - 170, cy - 170);
  Object.assign(anel.style, { width: px(340), height: px(340), borderRadius: "50%", border: `2px dashed #c9cac6` });
  tl.fromTo(anel, { opacity: 0, scale: 0.7, rotation: 0 }, { opacity: 1, scale: 1, duration: 0.6, ease: EXPO }, T(0.35));
  tl.to(anel, { rotation: 40, duration: D.dur, ease: "none" }, T(0.35));
  const itens = C.itens || [{ nome: "Marketing", sub: "atrair pacientes", ic: "mega", t: 2.1, x: 470, y: 720 }, { nome: "Gestão", sub: "clínica sem depender de você", ic: "grafico", t: 2.9, x: 150, y: 1320 }, { nome: "IA", sub: "automatizar processos", ic: "chip", t: 3.6, x: 760, y: 1300 }];
  itens.forEach((it) => {
    const no = mk("div", "card"); no.style.width = px(250); no.style.height = px(112); pos(no, it.x - 125, it.y - 56);
    no.innerHTML = `<div class="ativo"></div><div style="position:relative;display:flex;align-items:center;gap:${px(14)};padding:${px(18)} ${px(20)}">` +
      `<div style="width:${px(44)};height:${px(44)};color:#111214">${icone(it.ic)}</div><div style="font-weight:900;font-size:${px(34)};text-transform:uppercase">${esc(it.nome)}</div></div>`;
    seta(cx + (it.x - cx) * 0.33, cy + (it.y - cy) * 0.33, cx + (it.x - cx) * 0.8, cy + (it.y - cy) * 0.8, T(it.t - 0.15), "#24d0dc", true);
    tl.fromTo(no, { opacity: 0, scale: 0.7, x: (cx - it.x) * 0.3 * U, y: (cy - it.y) * 0.3 * U }, { opacity: 1, scale: 1, x: 0, y: 0, duration: 0.55, ease: MOLA }, T(it.t));
    tl.fromTo(no.querySelector(".ativo"), { opacity: 0 }, { opacity: 1, duration: 0.3 }, T(it.t + 0.1));
    tl.to(no.querySelector(".ativo"), { opacity: 0, duration: 0.5 }, T(it.t + 0.8));
    const ch = mk("div", "chip", null, esc(it.sub)); pos(ch, it.x - 125, it.y + 68);
    if (it.x > 600) { ch.style.left = "auto"; ch.style.right = px(W / U - X0 - (it.x + 125)); }
    tl.fromTo(ch, { opacity: 0, y: 12 * U }, { opacity: 1, y: 0, duration: 0.4, ease: Q }, T(it.t + 0.25));
  });
  camera(1.035, -10);
}
