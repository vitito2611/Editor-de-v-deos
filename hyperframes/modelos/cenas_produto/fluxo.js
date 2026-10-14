// "Ele recompensa quem sabe se posicionar, quem constrói presença, quem gera percepção de valor": fluxo de cards
// ligados por setas (vertical, cabe no Reels); o estado ativo caminha de card em card no tempo da fala.
function cena() {
  varredura(T(-0.25));
  rotulo(C.rotulo || "O QUE O MERCADO RECOMPENSA", 0, 455, T(0.05), true);
  titulo(C.titulo || "Não só quem é bom *na cadeira.*", { y: 495, tam: 72, centro: true, larg: 940, t: T(0.1), passo: 0.06 });
  const itens = C.itens || [{ nome: "Posicionar", sub: "quem você é", ic: "user", t: 1.7 }, { nome: "Presença", sub: "ser lembrado", ic: "mega", t: 3.3 }, { nome: "Valor", sub: "percepção", ic: "grafico", t: 4.8 }];
  const y0 = 720, h = 190, gap = 74, w = 720, x0 = 540 - w / 2;   // centralizado
  const cards = itens.map((it, i) => card(x0, y0 + i * (h + gap), w, h, { num: `0${i + 1}`, nome: it.nome, sub: it.sub, ic: it.ic, t: T(0.35 + i * 0.18), de: "direita" }));
  itens.forEach((it, i) => { if (i) seta(540, y0 + i * (h + gap) - gap + 8, 540, y0 + i * (h + gap) - 10, T(0.55 + i * 0.18)); });
  itens.forEach((it, i) => { cards[i].ativa(T(it.t), 0.6); if (i) cards[i - 1].desativa(T(it.t)); });
  const fim = itens[itens.length - 1].t;
  explosao(x0 + w - 46, y0 + (itens.length - 1) * (h + gap) + 46, T(fim + 0.1), 80);
  camera(1.03, -10);
}
