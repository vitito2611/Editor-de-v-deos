// "Clínicas de alto padrão dependem de uma equipe grande: recepcionista, CRC, gerente... e eu não dou 5 anos para
// alguns desses processos serem automatizados": lista de funções que entra no tempo da fala; no "5 anos" o título
// troca e cada linha enche a barra e ganha o selo AUTOMATIZADO.
function cena() {
  varredura(T(-0.25));
  rotulo(C.rotulo || "CLÍNICA DE ALTO PADRÃO", 0, 455, T(0.05), true);
  const t1 = titulo(C.titulo || "Uma equipe *grande*.", { y: 495, tam: 84, centro: true, larg: 940, t: T(0.1), passo: 0.08 });
  const tv = C.virada ?? 5.3;
  const t2 = titulo(C.titulo2 || "Em menos de *5 anos*: automatizado.", { y: 495, tam: 76, centro: true, larg: 940, t: T(tv + 0.1), passo: 0.06 });
  tl.to(t1, { opacity: 0, y: -40 * U, duration: 0.3, ease: "power2.in" }, T(tv - 0.1));
  const itens = C.itens || [{ nome: "Recepção", t: 1.9 }, { nome: "CRC", t: 2.6 }, { nome: "Gerência", t: 3.6 }, { nome: "Confirmações", t: 4.1 }, { nome: "Follow-up", t: 4.5 }];
  const y0 = 720, hh = 128;
  itens.forEach((it, i) => {
    const row = mk("div", "card"); pos(row, 180, y0 + i * (hh + 18)); row.style.width = px(720); row.style.height = px(hh);
    row.innerHTML = `<div class="ativo"></div><div class="fila" style="left:${px(28)};right:${px(28)};top:${px(38)}">` +
      `<span class="ponto"></span><span style="font-weight:700;font-size:${px(34)}">${esc(it.nome)}</span>` +
      `<span class="trilho"><i></i></span></div>`;
    tl.fromTo(row, { opacity: 0, x: 80 * U }, { opacity: 1, x: 0, duration: 0.5, ease: EXPO }, T(it.t));
    const ta = T(tv + 0.25 + i * 0.13);
    tl.fromTo(row.querySelector(".trilho i"), { scaleX: 0 }, { scaleX: 1, duration: 0.55, ease: QIO }, ta);
    tl.to(row.querySelector(".ponto"), { backgroundColor: "#24d0dc", duration: 0.2 }, ta + 0.5);
    tl.fromTo(row.querySelector(".ativo"), { opacity: 0 }, { opacity: 1, duration: 0.3 }, ta + 0.5);
    const ok = mk("div", "abs ok", row, "✓ automatizado"); Object.assign(ok.style, { right: px(28), top: px(84) });
    tl.fromTo(ok, { opacity: 0, scale: 0.7 }, { opacity: 1, scale: 1, duration: 0.35, ease: MOLA }, ta + 0.55);
  });
  camera(1.03, -10);
}
