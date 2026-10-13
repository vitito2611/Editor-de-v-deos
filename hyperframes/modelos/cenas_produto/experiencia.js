// "Recém-formados ... estão tendo resultados melhores que dentistas com 20, 30 anos de mercado": dois cards
// comparando técnica × resultado; as barras crescem e a do recém-formado passa na frente.
function cena() {
  varredura(T(-0.25));
  rotulo(C.rotulo || "COMO ISSO É POSSÍVEL?", 60, 455, T(0.05));
  titulo(C.titulo || "Resultados *melhores*.", { x: 60, y: 495, tam: 90, t: T(0.1), passo: 0.08 });
  const lin = (cd, y, nome, alvo, cor, t) => {
    const r = mk("div", "abs", cd); Object.assign(r.style, { left: px(30), right: px(30), top: px(y) });
    r.innerHTML = `<div style="display:flex;justify-content:space-between;font-family:Mono;font-size:${px(16)};letter-spacing:.16em;color:#8c8d89">` +
      `<span>${nome}</span><span class="v">0%</span></div><div style="position:relative;height:${px(14)};border-radius:${px(7)};background:#ecece8;margin-top:${px(10)};overflow:hidden">` +
      `<i style="position:absolute;inset:0;background:${cor};transform-origin:0 50%;transform:scaleX(0)"></i></div>`;
    tl.fromTo(r.querySelector("i"), { scaleX: 0 }, { scaleX: alvo, duration: 0.9, ease: "power3.out" }, t);
    const o = { v: 0 }, v = r.querySelector(".v");
    tl.fromTo(o, { v: 0 }, { v: alvo * 100, duration: 0.9, ease: "power3.out", onUpdate: () => { v.textContent = Math.round(o.v) + "%"; } }, t);
  };
  const mkCard = (y, num, nome, sub, tec, res, t, cor) => {
    const cd = card(60, y, 780, 300, { num, nome, sub, ic: "user", t });
    cd.querySelector(".barra").style.display = "none";
    lin(cd, 150, "TÉCNICA", tec, "#111214", t + 0.35); lin(cd, 220, "RESULTADO", res, cor, t + 0.55);
    return cd;
  };
  mkCard(650, "01", C.a || "30 anos de mercado", "experiência", 0.92, 0.38, T(0.25), "#9a9b97");
  const b = mkCard(990, "02", C.b || "Recém-formado", "posicionamento", 0.55, 0.88, T(0.5), "#24d0dc");
  b.ativa(T(1.5), 0.6);
  explosao(60 + 780 - 40, 990 + 40, T(1.55), 90);
  camera(1.035, -8);
}
