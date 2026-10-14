// "Menos do que 10% fatura acima de 100 mil": grade 10×10; 90 apagam, 10 acendem e sobem; barra 10% × 90%.
function cena() {
  varredura(T(-0.25));
  rotulo(C.rotulo || "SEGUNDO UMA ESTIMATIVA", 0, 455, T(0.05), true);
  titulo(C.titulo || "Menos de *10%* passa de R$100 mil.", { y: 495, tam: 78, centro: true, larg: 940, t: T(0.1), passo: 0.06 });
  const n = 10, tam = 54, gap = 12, x0 = 540 - (10 * 66 - 12) / 2, y0 = 720, sel = new Set();
  while (sel.size < 10) sel.add(Math.floor(rnd() * 100));
  const qs = [];
  for (let i = 0; i < 100; i++) {
    const r = Math.floor(i / n), c = i % n, q = mk("div", "abs");
    pos(q, x0 + c * (tam + gap), y0 + r * (tam + gap));
    Object.assign(q.style, { width: px(tam), height: px(tam), borderRadius: px(14), background: "#ffffff", border: "1px solid #dcdcd8" });
    tl.fromTo(q, { opacity: 0, scale: 0.5 }, { opacity: 1, scale: 1, duration: 0.3, ease: MOLA }, T(0.2 + (r + c) * 0.02));
    qs.push({ q, on: sel.has(i) });
  }
  qs.forEach(({ q, on }) => {
    if (on) {
      tl.to(q, { backgroundColor: "#24d0dc", borderColor: "#24d0dc", scale: 1.12, duration: 0.35, ease: MOLA }, T(1.1));
      q.innerHTML = `<div style="width:60%;height:60%;margin:20%">${icone("check", "#06363a", 2.4)}</div>`;
      tl.fromTo(q.firstChild, { opacity: 0 }, { opacity: 1, duration: 0.2 }, T(1.25));
    } else tl.to(q, { opacity: 0.28, duration: 0.4 }, T(1.1));
  });
  // barra empilhada
  const b = mk("div", "abs"); pos(b, x0, 1430); Object.assign(b.style, { width: px(648), height: px(18), borderRadius: px(9), background: "#e4e4e0", overflow: "hidden" });
  const f = mk("div", "abs", b); Object.assign(f.style, { left: 0, top: 0, bottom: 0, width: "10%", background: "#24d0dc", transformOrigin: "0 50%" });
  tl.fromTo(b, { opacity: 0 }, { opacity: 1, duration: 0.3 }, T(1.2)); tl.fromTo(f, { scaleX: 0 }, { scaleX: 1, duration: 0.5, ease: Q }, T(1.4));
  const lb = mk("div", "abs rot", null, "<i></i>10% FATURA &gt; R$100 MIL"); pos(lb, x0, 1390);
  tl.fromTo(lb, { opacity: 0, y: 10 * U }, { opacity: 1, y: 0, duration: 0.4, ease: Q }, T(1.5));
  camera(1.04, -10);
}
