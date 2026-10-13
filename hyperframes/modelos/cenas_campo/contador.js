// Cena "contador": o número gigante conta (zero-fantasma, unidade pequena), legenda em script, rótulo mono e um
// objeto 3D de pontos que cresce junto com o número:
//   objeto: galaxia  — redemoinho de partículas (mais pontos aparecem conforme conta)   ex.: 90.000 clínicas
//           grade    — matriz 10×10 de pontos; só `acesos` ficam acesos (fração)        ex.: < 10%
//           anel     — anel de `marcas` traços (anos) que enche, ou esvazia (contagem regressiva)
function montarCena(ctx) {
  const { THREE, scene, camera, D, PRE, ACENTO, QUENTE, rnd, clamp, lerp, E, fase, el, palavras, sobe, digita, cantos, contador, barra,
    brilho, pontos, estrelas, noPlano, px, PONTO } = ctx;
  const c = D.cena || {};
  const T = (x) => x + PRE;
  const dur = D.dur, SAI = T(c.sai ?? dur + 1);   // sem fade no fim: corte seco de volta para o orador
  const de = c.de ?? 0, ate = c.numero ?? 100, desce = ate < de;
  const tC0 = T(c.conta_t ?? 0.25), tC1 = T(c.conta_ate ?? Math.min(dur - 0.8, 1.7));
  const objeto = c.objeto || "galaxia";

  // ---------------------------------------------------------------- 3D
  const est = estrelas(900); scene.add(est);
  const grupo = new THREE.Group(); scene.add(grupo);
  const centro = noPlano(540, c.obj_y ?? ({ galaxia: 1180, grade: 1215, anel: 1260 }[objeto] ?? 1200), 0);
  grupo.position.copy(centro);
  let atualiza = () => {};

  if (objeto === "galaxia") {
    // redemoinho em 2 braços: núcleo quente (laranja/branco) e braços frios (ciano/branco), como a referência
    const N = 16000, pos = new Float32Array(N * 3), cor = new Float32Array(N * 3), raio = new Float32Array(N), ang = new Float32Array(N), alt = new Float32Array(N);
    for (let i = 0; i < N; i++) {
      const r = Math.pow(rnd(), 0.62) * 2.3, braco = i % 2, a = braco * Math.PI + r * 2.4 + (rnd() - 0.5) * (0.9 - r * 0.18);
      raio[i] = r; ang[i] = a; alt[i] = (rnd() - 0.5) * 0.22 * (1.2 - r * 0.3);
      const q = clamp(1 - r / 1.1), w = 0.55 + rnd() * 0.45;
      const ci = rnd() < 0.5 ? ACENTO : new THREE.Color(0xffffff);
      const col = new THREE.Color().copy(ci).lerp(QUENTE, q * 0.85).multiplyScalar(w * (0.6 + q * 0.9));
      cor[i * 3] = col.r; cor[i * 3 + 1] = col.g; cor[i * 3 + 2] = col.b;
    }
    const p = pontos(pos, cor, 0.035, 1); grupo.add(p);
    const nucleo = brilho(new THREE.Color(0xffd2b0), 1.6, 0.55); grupo.add(nucleo);
    grupo.rotation.set(-1.05, 0, 0.25);
    atualiza = (t, k, s) => {
      const a0 = t * 0.32;
      for (let i = 0; i < N; i++) {
        const a = ang[i] + a0 * (1.6 - raio[i] * 0.4) + (1 - fase(t, T(-0.3), T(1.2), E.expo)) * 2.5 / (0.3 + raio[i]);
        pos[i * 3] = Math.cos(a) * raio[i]; pos[i * 3 + 1] = Math.sin(a) * raio[i]; pos[i * 3 + 2] = alt[i];
      }
      p.geometry.attributes.position.needsUpdate = true;
      p.geometry.setDrawRange(0, Math.max(1, Math.floor(N * (0.04 + 0.96 * k))));
      p.material.opacity = 1 - s; nucleo.material.opacity = (0.35 + 0.3 * k) * (1 - s);
      grupo.scale.setScalar(lerp(0.75, 1, fase(t, T(-0.3), T(1.0), E.expo)) * (1 + s * 0.4));
    };
  } else if (objeto === "grade") {
    // matriz 10×10 inclinada; os `acesos` primeiros (ordem embaralhada) ficam acesos e sobem
    const n = 10, acesos = c.acesos ?? 10, esp = 0.25, sprites = [], ordem = [...Array(n * n).keys()];
    for (let i = ordem.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [ordem[i], ordem[j]] = [ordem[j], ordem[i]]; }
    const sel = new Set(ordem.slice(0, acesos));
    for (let i = 0; i < n * n; i++) {
      const s = brilho(new THREE.Color(0xffffff), 0.26, 1);
      s.position.set(((i % n) - (n - 1) / 2) * esp, (Math.floor(i / n) - (n - 1) / 2) * esp, 0);
      s.userData = { on: sel.has(i), d: rnd() * 0.5, idx: ordem.indexOf(i) };
      grupo.add(s); sprites.push(s);
    }
    const halo = brilho(ACENTO, 3.6, 0); grupo.add(halo);
    grupo.rotation.set(-0.85, 0, 0.6);
    atualiza = (t, k, s) => {
      const ent = fase(t, T(-0.2), T(0.8), E.expo), sel0 = fase(t, T(0.9), T(1.6), E.out3);
      sprites.forEach((sp) => {
        const e = fase(t, T(-0.2) + sp.userData.d * 0.6, T(0.5) + sp.userData.d * 0.6, E.expo);
        const on = sp.userData.on;
        sp.material.color.set(on ? new THREE.Color(0xffffff).lerp(ACENTO, sel0) : 0xffffff);
        sp.material.opacity = e * (on ? 1 : lerp(0.85, 0.22, sel0)) * (1 - s);
        sp.scale.setScalar((on ? lerp(0.26, 0.5, sel0) : 0.26) * (0.6 + 0.4 * e));
        sp.position.z = on ? sel0 * 0.1 + 0.02 * Math.sin(t * 3 + sp.userData.idx) : 0;
      });
      halo.material.opacity = 0.18 * sel0 * (1 - s);
      grupo.rotation.z = 0.5 + t * 0.06; grupo.scale.setScalar(lerp(0.85, 1, ent));
    };
  } else if (objeto === "anel") {
    // anel de marcas (um traço por ano); cheio → esvazia na contagem regressiva, ou enche contando
    const m = c.marcas ?? 60, R = c.raio ?? 0.82, traços = [];
    for (let i = 0; i < m; i++) {
      const a = Math.PI / 2 - (i / m) * Math.PI * 2;
      const geo = new THREE.PlaneGeometry(0.035, i % 5 ? 0.16 : 0.3);
      const mat = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.2, blending: THREE.AdditiveBlending, depthWrite: false });
      const me = new THREE.Mesh(geo, mat); me.position.set(Math.cos(a) * R, Math.sin(a) * R, 0); me.rotation.z = a - Math.PI / 2;
      grupo.add(me); traços.push(me);
    }
    const cabeca = brilho(new THREE.Color(0xffffff), 0.6, 1); grupo.add(cabeca);
    const halo = brilho(ACENTO, 4.5, 0.12); grupo.add(halo);
    const arco = new THREE.Mesh(new THREE.TorusGeometry(R * 0.86, 0.012, 8, 200, Math.PI * 2),
      new THREE.MeshBasicMaterial({ color: ACENTO, transparent: true, opacity: 0.8, blending: THREE.AdditiveBlending, depthWrite: false }));
    arco.rotation.z = Math.PI / 2; arco.scale.x = -1; grupo.add(arco);
    atualiza = (t, k, s) => {
      const ent = fase(t, T(-0.25), T(0.7), E.expo);
      const esvazia = desce || c.anel === "esvazia";
      const cheio = esvazia ? 1 - fase(t, tC0, T(dur - 0.2), E.lin) : k;   // fração acesa (esvazia = o tempo acabando)
      traços.forEach((me, i) => {
        const on = i / m < cheio;
        me.material.opacity = ent * (on ? 0.95 : 0.14) * (1 - s);
        me.material.color.set(on ? (esvazia ? 0xffffff : ACENTO) : 0xffffff);
      });
      const a = Math.PI / 2 - cheio * Math.PI * 2;
      cabeca.position.set(Math.cos(a) * R, Math.sin(a) * R, 0.02); cabeca.material.opacity = ent * (1 - s) * (cheio > 0.002 ? 1 : 0);
      arco.geometry.dispose(); arco.geometry = new THREE.TorusGeometry(R * 0.86, 0.012, 8, 200, Math.max(0.0001, cheio * Math.PI * 2));
      arco.material.opacity = 0.8 * ent * (1 - s);
      halo.material.opacity = 0.12 * ent * (1 - s);
      grupo.rotation.set(-0.25 + Math.sin(t * 0.5) * 0.05, 0.2 * Math.sin(t * 0.4), 0);
      grupo.scale.setScalar(lerp(0.8, 1, ent));
    };
  }

  // ---------------------------------------------------------------- HUD
  const topo = el("mono", "", 60, 440, { fontSize: px(17) });
  const tc = el("mono qt", "", 640, 440, { fontSize: px(17), width: px(380), textAlign: "right" });
  const rot = el("mono ac", "", 60, 520, { fontSize: px(22) });
  const num = el("num", "", 50, 560, { fontSize: px(c.tam_numero ?? 210) });
  const setNum = contador(num, c.casas ?? String(Math.max(de, ate)).length, c.unidade || "", c.decimais || 0);
  const pre = c.prefixo ? el("num", c.prefixo, 50, 560, { fontSize: px((c.tam_numero ?? 210) * 0.55), color: "var(--acento)" }) : null;
  if (pre) num.style.left = px(ctx.X0 + 50 + (c.tam_numero ?? 210) * 0.42);
  const scr = el("script", "", 58, 760, { fontSize: px(c.tam_script ?? 78) });
  scr.textContent = c.script || "";
  const sub = el("mono", c.sub || "", 60, 878, { fontSize: px(16) });
  const bar = barra(60, 1470, 760);
  const lbl = el("mono", "", 60, 1440, { fontSize: px(15) });
  const lbr = el("mono", c.fim_barra || "", 620, 1440, { fontSize: px(15), width: px(200), textAlign: "right" });
  const cnt = cantos(40, 420, 1000, 1140, 30);

  return (t) => {
    const s = fase(t, SAI, SAI + 0.35, E.in3);
    const k = fase(t, tC0, tC1, E.out5);
    est.userData.mover(t);
    atualiza(t, k, s);
    camera.position.set(Math.sin(t * 0.35) * 0.15, Math.cos(t * 0.3) * 0.1, 12 - fase(t, 0, dur + PRE, E.sine) * 0.9);
    camera.lookAt(0, -0.2, 0);
    digita(topo, c.hud || "ZEAL  /  GUIA DE CAMPO", t, T(-0.3), 80);
    const f = Math.max(0, Math.floor((t - PRE) * 30) + (c.tc0 ?? 0) * 30);
    tc.textContent = `● TC 00:00:${String(Math.floor(f / 30) % 60).padStart(2, "0")}:${String(f % 30).padStart(2, "0")}`;
    digita(rot, c.rotulo || "", t, T(-0.15), 46);
    [topo, tc, rot].forEach((e) => (e.style.opacity = 1 - s));
    const ent = fase(t, T(-0.25), T(0.45), E.expo);
    setNum(lerp(de, ate, k));
    num.style.transform = `translateY(${(1 - ent) * 70 - s * 120}px)`;
    num.style.opacity = ent * (1 - s);
    if (pre) { pre.style.transform = num.style.transform; pre.style.opacity = num.style.opacity; }
    const ks = fase(t, T(c.script_t ?? 0.55), T((c.script_t ?? 0.55) + 0.7), E.inOut);
    scr.style.clipPath = `inset(-20% ${100 - ks * 100}% -30% -5%)`;
    scr.style.opacity = 1 - s; scr.style.transform = `translateY(${-s * 90}px)`;
    digita(sub, c.sub || "", t, T((c.script_t ?? 0.55) + 0.5), 60); sub.style.opacity = 1 - s;
    bar(k, fase(t, T(-0.1), T(0.3)) * (1 - s));
    lbl.textContent = (c.barra || "decorrido").toUpperCase() + "   " + ((t - PRE) >= 0 ? (t - PRE).toFixed(3) : "0.000") + " s";
    lbl.style.opacity = lbr.style.opacity = 0.9 * (1 - s);
    cnt(t, fase(t, T(-0.3), T(0.4), E.expo), 1 - s);
  };
}
