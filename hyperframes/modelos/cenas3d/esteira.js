// Cena "esteira": documentos IDÊNTICOS vêm em fila numa trilha curva e são engolidos por um vórtice de IA
// (anéis de luz girando + redemoinho de partículas). Fala: "repetição, tarefa mecânica — a IA vai engolir".
function montarCena(ctx) {
  const { THREE, scene, camera, rnd, fase, E, brilho, texturaIcone, poeira, bokeh, RoundedBoxGeometry, ACENTO, D } = ctx;
  const c = D.cena || {};
  scene.fog = new THREE.FogExp2(0x0a0618, 0.05);
  scene.add(new THREE.AmbientLight(0xc0b0ff, 0.45));
  const key = new THREE.DirectionalLight(0xffffff, 2.0); key.position.set(-2, 3, 5); scene.add(key);
  const luzV = new THREE.PointLight(ACENTO, 60, 9); scene.add(luzV);
  const roxa = new THREE.PointLight(0x8a4dff, 40, 10); roxa.position.set(2.5, -2, 1); scene.add(roxa);

  const centro = new THREE.Vector3(0.15, -0.05, 0);
  luzV.position.copy(centro).add(new THREE.Vector3(0, 0, 0.8));
  // vórtice: anéis concêntricos com inclinações diferentes + núcleo brilhante
  const vortice = new THREE.Group(); vortice.position.copy(centro); scene.add(vortice);
  const aneis = [0.55, 0.85, 1.18, 1.5].map((r, i) => {
    const m = new THREE.Mesh(new THREE.TorusGeometry(r, 0.012 + i * 0.004, 8, 160),
      new THREE.MeshBasicMaterial({ color: i % 2 ? 0x9f6bff : ACENTO, transparent: true, opacity: 0.85 - i * 0.12,
        blending: THREE.AdditiveBlending, depthWrite: false }));
    m.rotation.set(1.15 + i * 0.08, 0.25 * (i % 2 ? -1 : 1), 0);
    vortice.add(m); return m;
  });
  const nucleo = brilho(ACENTO, 1.6, 0.9); vortice.add(nucleo);
  const nucleo2 = brilho(new THREE.Color(0xffffff), 0.55, 0.95); vortice.add(nucleo2);
  // redemoinho de partículas caindo para o centro
  const NP = 900, pg = new THREE.BufferGeometry(), pp = new Float32Array(NP * 3), pdat = [];
  for (let i = 0; i < NP; i++) pdat.push({ r0: 0.35 + rnd() * 1.9, a0: rnd() * Math.PI * 2, y: (rnd() - 0.5) * 0.35, v: 0.35 + rnd() * 0.7 });
  pg.setAttribute("position", new THREE.BufferAttribute(pp, 3));
  const redemoinho = new THREE.Points(pg, new THREE.PointsMaterial({ color: 0xbfe9ff, size: 0.028, transparent: true, opacity: 0.85,
    blending: THREE.AdditiveBlending, depthWrite: false }));
  redemoinho.rotation.x = 1.15; vortice.add(redemoinho);

  // documentos idênticos (a repetição) — mesma folha, mesmo ícone
  const papel = new RoundedBoxGeometry(0.4, 0.53, 0.02, 3, 0.03);
  const matPapel = new THREE.MeshPhysicalMaterial({ color: 0xf2eeff, roughness: 0.35, metalness: 0.0, clearcoat: 0.6, envMapIntensity: 0.9 });
  const tex = texturaIcone("doc", "#5d2e8c", 256);
  const N = 11, docs = [];
  for (let i = 0; i < N; i++) {
    const g = new THREE.Group();
    g.add(new THREE.Mesh(papel, matPapel));
    const face = new THREE.Mesh(new THREE.PlaneGeometry(0.32, 0.32), new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false }));
    face.position.z = 0.016; g.add(face);
    scene.add(g); docs.push(g);
  }
  // trilha: vem de baixo-esquerda (perto da câmera) e faz a curva até o vórtice
  const trilha = new THREE.CatmullRomCurve3([
    new THREE.Vector3(-2.6, -3.4, 3.2), new THREE.Vector3(-1.9, -1.9, 2.0), new THREE.Vector3(-1.3, -0.6, 1.1),
    new THREE.Vector3(-0.7, 0.35, 0.5), centro.clone()]);
  const faixa = new THREE.Mesh(new THREE.TubeGeometry(trilha, 120, 0.012, 6, false),
    new THREE.MeshBasicMaterial({ color: ACENTO, transparent: true, opacity: 0.18, blending: THREE.AdditiveBlending, depthWrite: false }));
  faixa.position.z = -0.35; scene.add(faixa);
  const flashes = docs.map(() => { const f = brilho(new THREE.Color(0xffffff), 0.8, 0); f.position.copy(centro); scene.add(f); return f; });
  const fundo = poeira(450, [10, 14, 10], 0x8c7bff, 0.028); fundo.position.z = -3; scene.add(fundo);
  const bk = bokeh(6, 1.3, 4.5, 6.8, [ACENTO, new THREE.Color(0x8a4dff)]); scene.add(bk);
  const vel = c.velocidade ?? 0.42;

  return (t) => {
    const k = fase(t, 0, D.dur + (D.pre_roll || 0), E.sine);
    camera.position.set(-0.7 + 1.0 * k, 0.45 - 0.3 * k, 9.6 - 1.2 * k);
    camera.lookAt(centro.x - 0.35, centro.y + 0.55, 0);
    camera.rotateZ(0.04 - 0.06 * k);
    aneis.forEach((a, i) => { a.rotation.z = t * (0.9 + i * 0.35) * (i % 2 ? -1 : 1); });
    const pulso = 1 + 0.08 * Math.sin(t * 9);
    nucleo.scale.setScalar(1.6 * pulso); nucleo2.scale.setScalar(0.55 * pulso);
    for (let i = 0; i < NP; i++) {
      const d = pdat[i], fr = ((t * d.v * 0.5 + i / NP) % 1);
      const r = d.r0 * (1 - fr), a = d.a0 + fr * 7;
      pp[i * 3] = Math.cos(a) * r; pp[i * 3 + 1] = d.y * (1 - fr); pp[i * 3 + 2] = Math.sin(a) * r;
    }
    pg.attributes.position.needsUpdate = true;
    docs.forEach((g, i) => {
      // cada folha percorre a trilha; nos últimos 25% gira em espiral e encolhe dentro do vórtice
      const s = ((t * vel + i / N) % 1);
      const p = trilha.getPointAt(Math.min(0.999, s));
      const fim = fase(s, 0.72, 1, E.in3);
      const ang = fim * 9;
      g.position.set(p.x + Math.cos(ang) * 0.35 * fim * (1 - fim) * 4, p.y + Math.sin(ang) * 0.25 * fim * (1 - fim) * 4, p.z);
      const tg = trilha.getTangentAt(Math.min(0.999, s));
      g.rotation.set(-0.35 + tg.y * 0.4, 0.5 - tg.x * 0.3, ang + Math.sin(s * 6) * 0.08);
      g.scale.setScalar((1 - fim) * fase(s, 0, 0.08, E.out3));
      flashes[i].material.opacity = Math.max(0, 1 - Math.abs(s - 0.985) / 0.03) * 0.8;
    });
    fundo.rotation.y = -t * 0.04;
    bk.userData.mover(t);
  };
}
