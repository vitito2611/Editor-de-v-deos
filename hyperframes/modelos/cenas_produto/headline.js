// Abertura: rótulo + título que escurece palavra a palavra com marca-texto em "10 anos", régua tracejada 2026 → 2036
// que corre, e o orador numa janela (formato janela do Remotion) que no fim abre para a tela cheia.
function cena() {
  rotulo(C.rotulo || "ODONTOLOGIA · O FUTURO", 60, 455, T(0.0));
  titulo(C.titulo || "Como vão ser os próximos *10 anos* na odontologia?", { x: 60, y: 500, tam: C.tam || 80, larg: 960, t: T(0.08), passo: 0.06 });
  // régua de anos: tracejado que corre + marcadores
  const y = 812, ns = "http://www.w3.org/2000/svg";
  const s = document.createElementNS(ns, "svg");
  s.setAttribute("width", px(1080)); s.setAttribute("height", px(40)); s.setAttribute("viewBox", "0 -20 1080 40");
  Object.assign(s.style, { position: "absolute", left: px(X0), top: px(y - 20) }); palco.appendChild(s);
  const l = document.createElementNS(ns, "line"); l.setAttribute("x1", 60); l.setAttribute("x2", 1020); l.setAttribute("y1", 0); l.setAttribute("y2", 0);
  l.setAttribute("stroke", "#111214"); l.setAttribute("stroke-width", 4); l.setAttribute("stroke-dasharray", "14 12"); s.appendChild(l);
  tl.fromTo(l, { attr: { x2: 60 } }, { attr: { x2: 1020 }, duration: 0.9, ease: "power3.inOut" }, T(0.5));
  tl.fromTo(l, { attr: { "stroke-dashoffset": 0 } }, { attr: { "stroke-dashoffset": -260 }, duration: D.dur + 0.5, ease: "none" }, T(0.0));
  const ano0 = mk("div", "abs rot", null, "2026"); pos(ano0, 60, y + 18); const ano1 = mk("div", "abs rot", null, "2036"); pos(ano1, 930, y + 18);
  tl.fromTo([ano0, ano1], { opacity: 0, y: 10 * U }, { opacity: 1, y: 0, duration: 0.4, stagger: 0.25, ease: Q }, T(0.7));
  const marca = mk("div", "abs"); Object.assign(marca.style, { width: px(16), height: px(16), borderRadius: "50%", background: "#24d0dc", boxShadow: `0 0 0 ${px(6)} rgba(36,208,220,0.25)` });
  pos(marca, 52, y - 8); tl.fromTo(marca, { x: 0 }, { x: 960 * U, duration: 1.6, ease: "power2.inOut" }, T(0.6));
  // sombra/moldura atrás da janela do orador (o vídeo entra por cima, pelo Remotion)
  const j = C.janela_px || [108, 866, 864, 600];
  const sombra = mk("div", "card"); pos(sombra, j[0], j[1]); sombra.style.width = px(j[2]); sombra.style.height = px(j[3]);
  tl.fromTo(sombra, { opacity: 0, scale: 0.96 }, { opacity: 1, scale: 1, duration: 0.5, ease: EXPO }, T(0.0));
  // saída: tudo sobe e some enquanto a janela abre
  const sai = C.sai ?? (D.dur - 0.6);
  tl.to(palco, { y: -90 * U, opacity: 0, duration: 0.45, ease: "power2.in" }, T(sai));
  camera(1.03, -8);
}
