// Cena "vidros": grade de cartões de vidro (profissões/tarefas) que voa para a câmera; a maioria se
// desintegra em partículas e só os que "ficam" acendem em ciano e avançam. Fala: "alguns empregos vão sumir".
function montarCena(ctx) {
  const { THREE, scene, camera, rnd, fase, E, brilho, texturaIcone, bokeh, poeira, RoundedBoxGeometry, ACENTO, MARCA, D } = ctx;
  const c = D.cena || {};
  const icones = c.icones || ["chat", "grafico", "user", "check", "agenda", "relogio", "doc", "tel", "zap"];
  const ficam = new Set(c.ficam || [1, 3, 7]);
  scene.fog = new THREE.FogExp2(0x0b0716, 0.055);
  scene.add(new THREE.AmbientLight(0xb8a8ff, 0.35));
  const key = new THREE.DirectionalLight(0xffffff, 2.2); key.position.set(1.5, 3, 5); scene.add(key);
  const rimC = new THREE.PointLight(ACENTO, 40, 14); rimC.position.set(-3.2, 1.6, -1.8); scene.add(rimC);
  const rimM = new THREE.PointLight(0x8a4dff, 46, 14); rimM.position.set(3.4, -1.4, -1.2); scene.add(rimM);

  const cw = 0.8, ch = 0.58, gap = 0.11, yc = -0.62;
  const geo = new RoundedBoxGeometry(cw, ch, 0.07, 4, 0.06);
  const lin = new THREE.PlaneGeometry(1, 1);
  const tiles = icones.slice(0, 9).map((ic, i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const g = new THREE.Group();
    const mat = new THREE.MeshPhysicalMaterial({ color: 0x241a3e, metalness: 0.15, roughness: 0.22, clearcoat: 1, clearcoatRoughness: 0.08,
      envMapIntensity: 1.3, transparent: true, opacity: 0.94 });
    const box = new THREE.Mesh(geo, mat); g.add(box);
    const icMat = new THREE.MeshBasicMaterial({ map: texturaIcone(ic, "#ffffff"), transparent: true, depthWrite: false, opacity: 0.9 });
    const icone = new THREE.Mesh(new THREE.PlaneGeometry(0.22, 0.22), icMat);
    icone.position.set(-cw / 2 + 0.2, ch / 2 - 0.19, 0.04); g.add(icone);
    const barras = [0.46, 0.3].map((w, k) => {
      const m = new THREE.Mesh(lin, new THREE.MeshBasicMaterial({ color: 0xcfc6ff, transparent: true, opacity: 0.22, depthWrite: false }));
      m.scale.set(w, 0.045, 1); m.position.set(-cw / 2 + 0.1 + w / 2, -0.06 - k * 0.1, 0.04); g.add(m); return m;
    });
    const halo = brilho(ACENTO, 1.05, 0); halo.position.z = -0.12; g.add(halo);
    const borda = new THREE.Mesh(new RoundedBoxGeometry(cw + 0.03, ch + 0.03, 0.02, 4, 0.07),
      new THREE.MeshBasicMaterial({ color: ACENTO, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending }));
    borda.position.z = -0.03; g.add(borda);
    g.userData = { col, row, mat, icMat, barras, halo, borda, alvo: new THREE.Vector3((col - 1) * (cw + gap), yc + (1 - row) * (ch + gap), 0),
      fica: ficam.has(i), atraso: (col + row) * 0.045 + rnd() * 0.05 };
    scene.add(g);
    return g;
  });
  // partículas de desintegração (uma InstancedMesh para todos os cartões que somem)
  const somem = tiles.filter((g) => !g.userData.fica);
  const porTile = 80, N = somem.length * porTile;
  const pGeo = new THREE.BoxGeometry(1, 1, 1);
  const pMat = new THREE.MeshStandardMaterial({ color: 0xb9a6ff, emissive: 0x6a3df0, emissiveIntensity: 1.2, roughness: 0.4, metalness: 0.2 });
  const parts = new THREE.InstancedMesh(pGeo, pMat, N);
  const pd = [];
  somem.forEach((g, k) => {
    for (let j = 0; j < porTile; j++) {
      const a = g.userData.alvo;
      pd.push({ k, p0: new THREE.Vector3(a.x + (rnd() - 0.5) * cw, a.y + (rnd() - 0.5) * ch, (rnd() - 0.5) * 0.06),
        v: new THREE.Vector3((rnd() - 0.5) * 1.6 + Math.sign(a.x || rnd() - 0.5) * 0.5, 0.5 + rnd() * 1.4, 0.4 + rnd() * 1.8),
        r: new THREE.Vector3(rnd() * 6, rnd() * 6, rnd() * 6), s: 0.018 + rnd() * 0.03, cor: rnd() < 0.35 });
    }
  });
  const cor1 = new THREE.Color(0xd8ccff), cor2 = ACENTO.clone();
  pd.forEach((d, i) => parts.setColorAt(i, d.cor ? cor2 : cor1));
  scene.add(parts);
  const fundo = poeira(500, [9, 14, 10], 0x9f8bff, 0.03); fundo.position.z = -3; scene.add(fundo);
  const bk = bokeh(7, 1.4, 4.2, 6.6, [ACENTO, new THREE.Color(0x8a4dff), new THREE.Color(0xffffff)]); scene.add(bk);
  const varre = new THREE.PointLight(0xffffff, 0, 6); scene.add(varre);
  const flare = brilho(ACENTO, 1, 0); flare.scale.set(7.5, 0.16, 1); scene.add(flare);
  const flareN = brilho(new THREE.Color(0xffffff), 0.9, 0); scene.add(flareN);
  const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), eul = new THREE.Euler(), sc = new THREE.Vector3(), ps = new THREE.Vector3();
  const tQuebra = c.quebra ?? 1.25;

  return (t) => {
    // câmera: dolly lento para dentro + leve órbita (sempre viva)
    const k = fase(t, 0, D.dur + (D.pre_roll || 0), E.sine);
    camera.position.set(0.55 - 0.9 * k, 0.1 - 0.35 * k, 9.8 - 1.3 * k);
    camera.lookAt(0, yc + 0.5, 0);   // grade abaixo do texto (zona segura: texto em cima, cartões no meio)
    camera.rotateZ(-0.03 + 0.05 * k);
    tiles.forEach((g, i) => {
      const u = g.userData;
      const e = fase(t, u.atraso, u.atraso + 0.85, E.expo);
      g.position.set(u.alvo.x * (0.6 + 0.4 * e), u.alvo.y, -7 * (1 - e) + Math.sin(t * 1.3 + i) * 0.04);
      g.rotation.set((1 - e) * 0.9 + Math.sin(t * 0.9 + i) * 0.03, (1 - e) * (u.col - 1) * 0.8 + Math.cos(t * 0.8 + i) * 0.04, 0);
      const op = e;
      if (u.fica) {
        const f = fase(t, tQuebra + 0.15, tQuebra + 0.75, E.back);
        g.position.z += f * 0.45; g.scale.setScalar(1 + f * 0.06);
        u.halo.material.opacity = f * 0.32;
        u.mat.emissive = ACENTO; u.mat.emissiveIntensity = f * 0.10;
        u.borda.material.opacity = f * 0.95;
        u.mat.opacity = 0.94 * op; u.icMat.opacity = 0.9 * op;
        u.icMat.color.copy(new THREE.Color(0xffffff).lerp(ACENTO, f));
      } else {
        const tq = tQuebra + u.atraso * 0.8;
        const treme = t > tq - 0.18 && t < tq ? Math.sin(t * 90) * 0.012 : 0;
        g.position.x += treme;
        const some = fase(t, tq, tq + 0.22, E.in3);
        u.mat.opacity = 0.94 * op * (1 - some); u.icMat.opacity = 0.9 * op * (1 - some);
        u.barras.forEach((b) => (b.material.opacity = 0.22 * op * (1 - some)));
        g.visible = some < 1;
      }
    });
    pd.forEach((d, i) => {
      const g = somem[d.k], tq = tQuebra + g.userData.atraso * 0.8, dt = t - tq;
      if (dt <= 0) { m4.makeScale(0, 0, 0); parts.setMatrixAt(i, m4); return; }
      const vida = clampV(1 - dt / 1.5);
      ps.copy(d.p0).addScaledVector(d.v, dt * (1 - 0.25 * dt)).add(new THREE.Vector3(g.position.x - g.userData.alvo.x, 0, g.position.z));
      eul.set(d.r.x * dt, d.r.y * dt, d.r.z * dt); q.setFromEuler(eul);
      sc.setScalar(d.s * vida * (dt < 0.08 ? dt / 0.08 : 1));
      m4.compose(ps, q, sc); parts.setMatrixAt(i, m4);
    });
    parts.instanceMatrix.needsUpdate = true;
    // reflexo de luz atravessando a grade (o vidro "acende" de lado a lado)
    const v = fase(t, 0.2, 1.3, E.inOut);
    varre.position.set(-2.4 + 4.8 * v, yc + 0.9 - 1.2 * v, 1.2); varre.intensity = 18 * Math.sin(Math.PI * v);
    // flare anamórfico no instante em que os que ficam acendem
    const fl = fase(t, tQuebra + 0.2, tQuebra + 0.45, E.out3) * (1 - fase(t, tQuebra + 0.5, tQuebra + 1.3, E.inOut));
    const alvo = tiles.find((g) => g.userData.fica);
    flare.position.set(0, alvo.position.y + 0.05, alvo.position.z + 0.3); flare.material.opacity = fl * 0.55;
    flareN.position.copy(flare.position); flareN.material.opacity = fl * 0.6;
    fundo.rotation.y = t * 0.03; fundo.position.y = t * 0.08;
    bk.userData.mover(t);
  };
  function clampV(x) { return Math.min(1, Math.max(0, x)); }
}
