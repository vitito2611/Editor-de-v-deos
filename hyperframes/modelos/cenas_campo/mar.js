// Cena "mar": "é um mar azul" — oceano de pontos (ondas somadas, como um campo de dados) visto rasante, a câmera
// desliza para frente, o horizonte brilha em ciano; rótulo mono, palavra grande e script.
function montarCena(ctx) {
  const { THREE, scene, camera, D, PRE, ACENTO, rnd, clamp, lerp, E, fase, el, palavras, sobe, digita, cantos, contador, barra,
    brilho, pontos, estrelas, noPlano, px } = ctx;
  const c = D.cena || {};
  const T = (x) => x + PRE;
  const dur = D.dur, SAI = T(c.sai ?? dur + 1);   // sem fade no fim: corte seco de volta para o orador

  const est = estrelas(900); scene.add(est);
  const NX = 190, NZ = 130, pos = new Float32Array(NX * NZ * 3), cor = new Float32Array(NX * NZ * 3);
  const p = pontos(pos, cor, 0.1, 1); scene.add(p);
  const sol = brilho(ACENTO, 9, 0.35); scene.add(sol);
  const sol2 = brilho(new THREE.Color(0xffffff), 2.2, 0.5); scene.add(sol2);
  const azulFundo = new THREE.Color(0x0b3a8a), azul = new THREE.Color(0x2a8cff);

  const topo = el("mono", "", 60, 440, { fontSize: px(17) });
  const tc = el("mono qt", "", 640, 440, { fontSize: px(17), width: px(380), textAlign: "right" });
  const rot = el("mono ac", "", 60, 520, { fontSize: px(22) });
  const tit = el("num", "", 50, 585, { fontSize: px(c.tam ?? 180) });
  const sTit = palavras(tit, c.titulo || "mar azul.");
  const scr = el("script", "", 60, 760, { fontSize: px(70) });
  scr.textContent = c.script || "para quem dominar os três.";
  const sub = el("mono", "", 60, 860, { fontSize: px(16) });
  const cnt = cantos(40, 420, 1000, 1080, 30);

  return (t) => {
    const s = fase(t, SAI, SAI + 0.35, E.in3);
    est.userData.mover(t);
    const ent = fase(t, T(-0.3), T(1.0), E.expo);
    const avanco = t * 1.6;
    let i = 0;
    for (let z = 0; z < NZ; z++) for (let x = 0; x < NX; x++, i++) {
      const X = (x - NX / 2) * 0.13, Z = -z * 0.2 + 3;
      const zz = Z - avanco;
      const h = 0.18 * Math.sin(X * 1.1 + zz * 0.9 + t * 1.4) + 0.12 * Math.sin(X * 2.3 - zz * 1.7 + t * 2.1) + 0.06 * Math.sin(X * 4.0 + zz * 3.1 - t * 2.7);
      pos[i * 3] = X; pos[i * 3 + 1] = h * ent - 1.6; pos[i * 3 + 2] = Z;
      const prof = clamp(z / NZ), crista = clamp((h + 0.3) / 0.6);
      const col = new THREE.Color().copy(azulFundo).lerp(azul, crista).lerp(ACENTO, crista * crista * 0.8).multiplyScalar((0.6 + 1.3 * (1 - prof * 0.7)) * ent * (1 - s));
      cor[i * 3] = col.r; cor[i * 3 + 1] = col.g; cor[i * 3 + 2] = col.b;
    }
    p.geometry.attributes.position.needsUpdate = true; p.geometry.attributes.color.needsUpdate = true;
    sol.visible = sol2.visible = false;
    camera.position.set(Math.sin(t * 0.3) * 0.2, -0.2 + Math.sin(t * 0.7) * 0.05, 6.5);
    camera.lookAt(0, -1.9, -6);
    digita(topo, c.hud || "ZEAL  /  GUIA DE CAMPO", t, T(-0.3), 80);
    const f = Math.max(0, Math.floor((t - PRE) * 30) + (c.tc0 ?? 0) * 30);
    tc.textContent = `● TC 00:00:${String(Math.floor(f / 30) % 60).padStart(2, "0")}:${String(f % 30).padStart(2, "0")}`;
    digita(rot, c.rotulo || "07 — OS PRÓXIMOS 10 ANOS", t, T(-0.15), 46);
    [topo, tc, rot].forEach((e) => (e.style.opacity = 1 - s));
    sobe(sTit, t, T(c.titulo_t ?? 0.15), 0.08, 0.8, SAI);
    const ks = fase(t, T((c.titulo_t ?? 0.15) + 0.5), T((c.titulo_t ?? 0.15) + 1.2), E.inOut);
    scr.style.clipPath = `inset(-20% ${100 - ks * 100}% -30% -5%)`; scr.style.opacity = 1 - s;
    digita(sub, c.sub || "", t, T((c.titulo_t ?? 0.15) + 1.0), 60); sub.style.opacity = 1 - s;
    cnt(t, fase(t, T(-0.3), T(0.4), E.expo), 1 - s);
  };
}
