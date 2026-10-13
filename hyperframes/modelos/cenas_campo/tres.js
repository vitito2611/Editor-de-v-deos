// Cena "tres": "dominar três coisas" — índice de guia de campo com 3 linhas. Cada item entra no instante em que é
// falado (itens[i].t), com seu objeto de pontos à esquerda: ondas (sinal que se espalha), estrutura (cubo de
// pontos que se monta) e rede (esfera neural com conexões que acendem). O "3" grande conta junto.
function montarCena(ctx) {
  const { THREE, scene, camera, D, PRE, ACENTO, QUENTE, rnd, clamp, lerp, E, fase, el, palavras, sobe, digita, cantos, contador, barra,
    brilho, pontos, estrelas, noPlano, px } = ctx;
  const c = D.cena || {};
  const T = (x) => x + PRE;
  const dur = D.dur, SAI = T(c.sai ?? dur - 0.45);
  const itens = c.itens || [{ nome: "Marketing", obj: "ondas", t: 1.0 }, { nome: "Gestão", obj: "estrutura", t: 1.8 }, { nome: "Inteligência artificial", obj: "rede", t: 2.5 }];
  const Y = c.linhas_y || [985, 1165, 1345];

  const est = estrelas(800); scene.add(est);
  const objetos = itens.map((it, i) => {
    const g = new THREE.Group(); g.position.copy(noPlano(c.obj_x ?? 165, Y[i], 0)); g.scale.setScalar(1.7); scene.add(g);
    let upd = () => {};
    if (it.obj === "ondas") {
      const aneis = [0, 1, 2, 3].map((j) => {
        const n = 90, pos = new Float32Array(n * 3);
        for (let k = 0; k < n; k++) { const a = (k / n) * Math.PI * 2; pos[k * 3] = Math.cos(a); pos[k * 3 + 1] = Math.sin(a); pos[k * 3 + 2] = 0; }
        const p = pontos(pos, null, 0.05, 1); p.material.color = new THREE.Color(0xffffff); g.add(p); return p;
      });
      const nucleo = brilho(ACENTO, 0.25, 1); g.add(nucleo);
      g.rotation.set(-0.9, 0, 0);
      upd = (t, e, s) => {
        aneis.forEach((p, j) => {
          const ph = ((t * 0.55 + j / 4) % 1);
          p.scale.setScalar(0.06 + ph * 0.42); p.material.opacity = e * (1 - ph) * (1 - s);
          p.material.color.set(j % 2 ? ACENTO : 0xffffff);
        });
        nucleo.material.opacity = e * (1 - s); nucleo.scale.setScalar(0.22 + 0.04 * Math.sin(t * 6));
      };
    } else if (it.obj === "estrutura") {
      const n = 7, pos = [], alvo = [];
      for (let x = 0; x < n; x++) for (let y = 0; y < n; y++) for (let z = 0; z < n; z++) {
        const borda = [x, y, z].filter((v) => v === 0 || v === n - 1).length >= 2;
        if (!borda && !(c.cubo_cheio ?? true)) continue;
        if (![x, y, z].some((v) => v === 0 || v === n - 1)) continue;
        alvo.push([(x / (n - 1) - 0.5) * 0.22, (y / (n - 1) - 0.5) * 0.22, (z / (n - 1) - 0.5) * 0.22]);
        pos.push((rnd() - 0.5) * 1.6, (rnd() - 0.5) * 1.6, (rnd() - 0.5) * 1.6);
      }
      const ini = Float32Array.from(pos), arr = Float32Array.from(pos);
      const p = pontos(arr, null, 0.04, 1); p.material.color = new THREE.Color(0xffffff); g.add(p);
      const arestas = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(0.22, 0.22, 0.22)),
        new THREE.LineBasicMaterial({ color: ACENTO, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
      g.add(arestas);
      const nucC = brilho(ACENTO, 0.5, 0); g.add(nucC);
      upd = (t, e, s) => {
        const k = fase(t, T(it.t - 0.05), T(it.t + 0.6), E.expo);
        arestas.material.opacity = 0.9 * fase(t, T(it.t + 0.35), T(it.t + 0.8)) * (1 - s);
        nucC.material.opacity = 0.35 * k * (1 - s);
        alvo.forEach((a, i) => { for (let d = 0; d < 3; d++) arr[i * 3 + d] = lerp(ini[i * 3 + d], a[d], k); });
        p.geometry.attributes.position.needsUpdate = true;
        p.material.opacity = e * (1 - s); p.material.color.set(new THREE.Color(0xffffff).lerp(ACENTO, k * 0.5));
        g.rotation.set(0.5 + t * 0.4, t * 0.7, 0);
      };
    } else {   // rede neural
      const n = 120, pts = [], ga = Math.PI * (3 - Math.sqrt(5));
      for (let i = 0; i < n; i++) { const y = 1 - (i / (n - 1)) * 2, r = Math.sqrt(1 - y * y), th = ga * i; pts.push(new THREE.Vector3(Math.cos(th) * r * 0.18, y * 0.18, Math.sin(th) * r * 0.18)); }
      const arr = new Float32Array(n * 3); pts.forEach((v, i) => v.toArray(arr, i * 3));
      const p = pontos(arr, null, 0.04, 1); p.material.color = new THREE.Color(0xffffff); g.add(p);
      const seg = [];
      pts.forEach((a, i) => pts.forEach((b, j) => { if (j > i && a.distanceTo(b) < 0.057) seg.push(a.x, a.y, a.z, b.x, b.y, b.z); }));
      const lg = new THREE.BufferGeometry(); lg.setAttribute("position", new THREE.Float32BufferAttribute(seg, 3));
      const linhas = new THREE.LineSegments(lg, new THREE.LineBasicMaterial({ color: ACENTO, transparent: true, opacity: 0.5, blending: THREE.AdditiveBlending, depthWrite: false }));
      g.add(linhas);
      const nuc = brilho(ACENTO, 0.55, 0.5); g.add(nuc);
      upd = (t, e, s) => {
        const k = fase(t, T(it.t), T(it.t + 0.8), E.out3);
        lg.setDrawRange(0, Math.floor((seg.length / 3) * k));
        p.material.opacity = e * (1 - s); linhas.material.opacity = 0.55 * e * (1 - s) * (0.7 + 0.3 * Math.sin(t * 8));
        nuc.material.opacity = 0.45 * e * k * (1 - s);
        g.rotation.set(0.3, t * 0.8, 0.1);
      };
    }
    return { g, upd };
  });

  // ---------------------------------------------------------------- HUD
  const topo = el("mono", "", 60, 440, { fontSize: px(17) });
  const tc = el("mono qt", "", 640, 440, { fontSize: px(17), width: px(380), textAlign: "right" });
  const rot = el("mono ac", "", 60, 520, { fontSize: px(22) });
  const num = el("num", "", 50, 560, { fontSize: px(200) });
  const setNum = contador(num, 1, c.unidade ?? "coisas");
  const scr = el("script", "", 60, 762, { fontSize: px(70) });
  scr.textContent = c.script || "ao mesmo tempo.";
  const linhas = itens.map((it, i) => {
    const idx = el("mono ac", `0${i + 1}`, 300, Y[i] - 52, { fontSize: px(18) });
    const nm = el("tit", "", 300, Y[i] - 26, { fontSize: px(it.tam ?? 60) });
    const sp = palavras(nm, it.nome);
    const fio = el("", "", 300, Y[i] + 56, { height: px(1), width: px(520), background: "rgba(244,241,234,0.16)", transformOrigin: "0 50%" });
    return { idx, nm, sp, fio, t: it.t };
  });
  const cnt = cantos(40, 420, 1000, 1080, 30);

  return (t) => {
    const s = fase(t, SAI, SAI + 0.35, E.in3);
    est.userData.mover(t);
    objetos.forEach((o, i) => o.upd(t, fase(t, T(itens[i].t - 0.15), T(itens[i].t + 0.5), E.expo), s));
    camera.position.set(Math.sin(t * 0.3) * 0.08, Math.cos(t * 0.25) * 0.06, 12 - fase(t, 0, dur + PRE, E.sine) * 0.4);
    camera.lookAt(0, 0, 0);
    digita(topo, c.hud || "ZEAL  /  GUIA DE CAMPO", t, T(-0.3), 80);
    const f = Math.max(0, Math.floor((t - PRE) * 30) + (c.tc0 ?? 0) * 30);
    tc.textContent = `● TC 00:00:${String(Math.floor(f / 30) % 60).padStart(2, "0")}:${String(f % 30).padStart(2, "0")}`;
    digita(rot, c.rotulo || "05 — O DENTISTA DE 2036", t, T(-0.15), 46);
    [topo, tc, rot].forEach((e) => (e.style.opacity = 1 - s));
    const ent = fase(t, T(-0.25), T(0.45), E.expo);
    const quantos = itens.filter((it) => t >= T(it.t)).length;
    setNum(c.numero_fixo ? itens.length : Math.max(quantos, Math.round(itens.length * fase(t, T(0.0), T(0.6), E.out3) * (quantos ? 1 : 1))));
    num.style.transform = `translateY(${(1 - ent) * 70 - s * 120}px)`; num.style.opacity = ent * (1 - s);
    const ks = fase(t, T(0.35), T(1.0), E.inOut);
    scr.style.clipPath = `inset(-20% ${100 - ks * 100}% -30% -5%)`; scr.style.opacity = 1 - s;
    linhas.forEach((l) => {
      const k = fase(t, T(l.t - 0.1), T(l.t + 0.5), E.expo);
      sobe(l.sp, t, T(l.t - 0.05), 0.05, 0.6, SAI);
      l.idx.style.opacity = k * (1 - s);
      l.fio.style.transform = `scaleX(${k})`; l.fio.style.opacity = 1 - s;
    });
    cnt(t, fase(t, T(-0.3), T(0.4), E.expo), 1 - s);
  };
}
