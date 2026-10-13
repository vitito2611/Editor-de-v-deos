// Fechamento: "os próximos 10 anos da odontologia ... é um mar azul": frase central com marca-texto, onda tracejada
// que corre, explosão no destaque e os três pilares em chips que se encaixam.
function cena() {
  varredura(T(-0.25));
  rotulo(C.rotulo || "OS PRÓXIMOS 10 ANOS", 0, 560, T(0.05), true);
  titulo(C.titulo || "Um *mar azul.*", { y: 610, tam: 132, centro: true, larg: 1000, t: T(0.1), passo: 0.1 });
  const ns = "http://www.w3.org/2000/svg", s = document.createElementNS(ns, "svg");
  s.setAttribute("width", px(1080)); s.setAttribute("height", px(200)); s.setAttribute("viewBox", "0 -100 1080 200");
  Object.assign(s.style, { position: "absolute", left: px(X0), top: px(880) }); palco.appendChild(s);
  [0, 1, 2].forEach((k) => {
    let d = "M-40 0"; for (let x = -40; x <= 1120; x += 20) d += ` L${x} ${Math.sin(x / 70 + k * 0.9) * (26 - k * 6)}`;
    const p = document.createElementNS(ns, "path"); p.setAttribute("d", d); p.setAttribute("fill", "none");
    p.setAttribute("stroke", k ? "#9ee9ef" : "#24d0dc"); p.setAttribute("stroke-width", k ? 2 : 4); p.setAttribute("stroke-dasharray", k ? "6 10" : "16 12");
    p.setAttribute("transform", `translate(0 ${k * 34})`); s.appendChild(p);
    tl.fromTo(p, { attr: { "stroke-dashoffset": 0 } }, { attr: { "stroke-dashoffset": -400 - k * 80 }, duration: D.dur + 0.5, ease: "none" }, T(0));
    tl.fromTo(p, { opacity: 0 }, { opacity: 1, duration: 0.5 }, T(0.3 + k * 0.1));
  });
  explosao(540, 700, T(0.95), 150);
  const pil = C.pilares || ["Marketing", "Gestão", "IA"];
  pil.forEach((p, i) => {
    const ch = mk("div", "chip" + (i === 1 ? " on" : ""), null, esc(p)); ch.style.fontSize = px(24);
    pos(ch, 150 + i * 270, 1140);
    tl.fromTo(ch, { opacity: 0, y: 40 * U, rotation: (i - 1) * 6 }, { opacity: 1, y: 0, rotation: 0, duration: 0.55, ease: MOLA }, T(1.3 + i * 0.15));
  });
  camera(1.05, -6);
}
