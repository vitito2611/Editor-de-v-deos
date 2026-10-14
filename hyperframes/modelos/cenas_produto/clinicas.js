// "Hoje existem mais de 90 mil clínicas": card com o número contando + mosaico de clínicas (quadradinhos) que
// acende em onda diagonal. Varredura de cor na entrada.
function cena() {
  varredura(T(-0.25));
  rotulo(C.rotulo || "O MERCADO HOJE", 0, 455, T(0.05), true);
  titulo(C.titulo || "Mais de *90 mil* clínicas.", { y: 495, tam: 86, centro: true, larg: 940, t: T(0.1), passo: 0.07 });
  const cd = mk("div", "card"); pos(cd, 160, 700); cd.style.width = px(760); cd.style.height = px(190);
  cd.innerHTML = `<div style="padding:${px(26)} ${px(30)}"><div class="num">CLÍNICAS ODONTOLÓGICAS</div>` +
    `<div class="n" style="font-weight:900;font-size:${px(112)};letter-spacing:-0.04em;line-height:1;margin-top:${px(10)}">0</div></div>` +
    `<div class="ic" style="width:${px(40)};height:${px(40)}">${icone("dente")}</div>`;
  tl.fromTo(cd, { opacity: 0, y: 50 * U, scale: 0.95 }, { opacity: 1, y: 0, scale: 1, duration: 0.6, ease: EXPO }, T(0.2));
  conta(cd.querySelector(".n"), 0, C.numero ?? 90000, T(0.3), 1.6);
  // mosaico
  const cols = 11, rows = 10, tam = 44, gap = 12, x0 = 540 - (11 * 56 - 12) / 2, y0 = 930;   // centralizado (238–842)
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
    const q = mk("div", "abs"); pos(q, x0 + c * (tam + gap), y0 + r * (tam + gap));
    const destaque = (r * 7 + c * 3) % 11 === 0;
    Object.assign(q.style, { width: px(tam), height: px(tam), borderRadius: px(10), background: destaque ? "#24d0dc" : "#ffffff",
      border: `1px solid ${destaque ? "#24d0dc" : "#e1e1dd"}`, boxShadow: `0 ${px(4)} ${px(10)} rgba(17,18,20,0.05)` });
    tl.fromTo(q, { opacity: 0, scale: 0.4 }, { opacity: 1, scale: 1, duration: 0.35, ease: MOLA }, T(0.35 + (r + c) * 0.035));
  }
  camera(1.04, -12);
}
