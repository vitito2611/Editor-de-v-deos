// Cena "headline" (abertura): HUD de documentário + "Como vão ser os próximos | 10 anos | na odontologia." com o
// contador 00 → 10 e a régua 2026 → 2036, um globo de pontos girando atrás e o orador numa janela embaixo
// (formato janela, Remotion). No fim tudo sai para cima e a janela abre para a tela cheia.
function montarCena(ctx) {
  const { THREE, scene, camera, D, PRE, ACENTO, rnd, clamp, lerp, E, fase, el, palavras, sobe, digita, cantos, contador, barra,
    brilho, pontos, estrelas, noPlano, px } = ctx;
  const c = D.cena || {};
  const T = (x) => x + PRE;                       // tempos da cena (s) → tempo absoluto
  const dur = D.dur, SAI = T(c.sai ?? dur - 0.62);

  // ---------------------------------------------------------------- 3D: estrelas + globo de pontos
  const est = estrelas(1100); scene.add(est);
  const R = c.globo_r ?? 0.78, N = 6400;
  const pos = new Float32Array(N * 3), cor = new Float32Array(N * 3);
  const ga = Math.PI * (3 - Math.sqrt(5));
  let n = 0;
  for (let i = 0; i < N; i++) {
    const y = 1 - (i / (N - 1)) * 2, r = Math.sqrt(1 - y * y), th = ga * i;
    const x = Math.cos(th) * r, z = Math.sin(th) * r;
    // "continentes" procedurais: só os pontos onde a soma de ondas passa do limiar
    const lat = Math.asin(y), lon = Math.atan2(z, x);
    const f = Math.sin(lon * 2.0 + 0.6) * Math.cos(lat * 2.6) + 0.55 * Math.sin(lon * 4.7 - lat * 3.1) + 0.3 * Math.cos(lon * 9.0 + lat * 7.0);
    const terra = f > 0.32;
    if (!terra && (i % 5)) continue;              // oceano: só 1 em 5 pontos (bem fraco)
    pos[n * 3] = x * R; pos[n * 3 + 1] = y * R; pos[n * 3 + 2] = z * R;
    const b = terra ? 1.1 + 0.5 * rnd() : 0.22;
    cor[n * 3] = b * 0.92; cor[n * 3 + 1] = b * 0.97; cor[n * 3 + 2] = b; n++;
  }
  const globo = new THREE.Group(); scene.add(globo);
  const pts = pontos(pos.slice(0, n * 3), cor.slice(0, n * 3), 0.08, 1); globo.add(pts);
  // luz: lado iluminado (frente-esquerda) brilhante, terminador escuro e borda acesa (atmosfera)
  const base = cor.slice(0, n * 3), nrm = pos.slice(0, n * 3).map((v) => v / R);
  const luz = new THREE.Vector3(-0.55, 0.45, 0.7).normalize(), m3 = new THREE.Matrix3(), v = new THREE.Vector3();
  const ilumina = () => {
    m3.setFromMatrix4(globo.matrixWorld);
    const ca = pts.geometry.attributes.color.array;
    for (let i = 0; i < n; i++) {
      v.set(nrm[i * 3], nrm[i * 3 + 1], nrm[i * 3 + 2]).applyMatrix3(m3).normalize();
      const d = v.dot(luz), borda = Math.pow(1 - Math.abs(v.z), 3);
      const k = 0.18 + 2.2 * Math.max(0, d) + 1.6 * borda;
      ca[i * 3] = base[i * 3] * k * (0.85 + 0.15 * borda); ca[i * 3 + 1] = base[i * 3 + 1] * k; ca[i * 3 + 2] = base[i * 3 + 2] * k * (1 + 0.4 * borda);
    }
    pts.geometry.attributes.color.needsUpdate = true;
  };
  // atmosfera: halo + anel fino de luz (como o planeta da referência)
  const halo = brilho(new THREE.Color(0x8fdcff), R * 3.0, 0.32); globo.add(halo);
  const aro = new THREE.Mesh(new THREE.RingGeometry(R * 1.01, R * 1.025, 160),
    new THREE.MeshBasicMaterial({ color: 0xbfeeff, transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
  scene.add(aro);
  const orbita = new THREE.Mesh(new THREE.TorusGeometry(R * 1.32, 0.006, 8, 220),
    new THREE.MeshBasicMaterial({ color: ACENTO, transparent: true, opacity: 0.7, blending: THREE.AdditiveBlending, depthWrite: false }));
  scene.add(orbita);
  const satel = brilho(new THREE.Color(0xffffff), 0.32, 1); scene.add(satel);
  const centro = noPlano(c.globo_x ?? 900, c.globo_y ?? 735, 0);

  // ---------------------------------------------------------------- HUD
  const topo = el("mono", "", 60, 440, { fontSize: px(17) });
  const rec = el("mono qt", "", 640, 440, { fontSize: px(17), width: px(380), textAlign: "right" });
  const rot = el("mono ac", "", 60, 506, { fontSize: px(22) });
  const lin = el("tit", "", 60, 548, { fontSize: px(c.tam_linha ?? 58) });
  const sLin = palavras(lin, c.linha || "Como vão ser os próximos");
  const num = el("num", "", 52, 622, { fontSize: px(c.tam_numero ?? 250) });
  const setNum = contador(num, String(c.numero ?? 10).length, c.unidade ?? "anos");
  const scr = el("script", "", 66, 838, { fontSize: px(c.tam_script ?? 86) });
  scr.textContent = c.script || "na odontologia.";
  const ano0 = el("mono", String(c.ano_ini ?? 2026), 60, 958, { fontSize: px(16) });
  const ano1 = el("mono", String(c.ano_fim ?? 2036), 900, 958, { fontSize: px(16), width: px(120), textAlign: "right" });
  const anoV = el("mono ac", "", 60, 958, { fontSize: px(16) });
  const bar = barra(60, 990, 960);
  // cantos de enquadramento da janela do orador (mesmo retângulo dos quadros da janela no plano)
  const jw = c.janela_px || [108, 1010, 864, 640];
  const cnt = cantos(jw[0] - 14, jw[1] - 14, jw[2] + 28, jw[3] + 28, 30);

  const ini = c.ano_ini ?? 2026, fim = c.ano_fim ?? 2036, alvo = c.numero ?? 10;
  return (t) => {
    const s = fase(t, SAI, SAI + 0.4, E.in3);          // saída
    // 3D
    est.userData.mover(t);
    const eg = fase(t, T(-0.3), T(0.9), E.expo);
    globo.position.copy(centro).add(new THREE.Vector3((1 - eg) * 1.4, 0.15 * Math.sin(t * 0.6) + s * 2.4, 0));
    globo.scale.setScalar(lerp(0.7, 1, eg));
    globo.rotation.set(0.32, t * 0.38 + 0.8, 0.12);
    globo.updateMatrixWorld(); ilumina();
    pts.material.opacity = eg * (1 - s);
    halo.material.opacity = 0.3 * eg * (1 - s);
    aro.position.copy(globo.position); aro.scale.setScalar(globo.scale.x); aro.material.opacity = 0.28 * eg * (1 - s);
    orbita.position.copy(globo.position); orbita.scale.setScalar(globo.scale.x);
    orbita.rotation.set(1.18, 0.0, -0.42 + t * 0.05); orbita.material.opacity = 0.6 * fase(t, T(0.4), T(1.2)) * (1 - s);
    const a = t * 1.25 + 0.4, rr = R * 1.32 * globo.scale.x;
    const p = new THREE.Vector3(Math.cos(a) * rr, Math.sin(a) * rr, 0).applyEuler(orbita.rotation).add(orbita.position);
    satel.position.copy(p); satel.material.opacity = orbita.material.opacity;
    camera.position.set(Math.sin(t * 0.3) * 0.12, Math.cos(t * 0.25) * 0.08, 12 - fase(t, 0, dur + PRE, E.sine) * 0.6);
    camera.lookAt(0, 0, 0);
    // HUD
    digita(topo, c.hud || "ZEAL  /  GUIA DE CAMPO", t, T(0.0), 60);
    const f = Math.max(0, Math.floor((t - PRE) * 30));
    rec.textContent = `● REC   TC 00:00:${String(Math.floor(f / 30)).padStart(2, "0")}:${String(f % 30).padStart(2, "0")}`;
    rec.style.opacity = fase(t, T(0.05), T(0.3)) * (1 - s);
    topo.style.opacity = 1 - s;
    digita(rot, c.rotulo || "01 — O FUTURO", t, T(0.12), 40);
    rot.style.opacity = 1 - s;
    sobe(sLin, t, T(0.22), 0.06, 0.75, SAI);
    // contador 00 → 10 (desacelera no fim) com leve escala
    const k = fase(t, T(0.45), T(1.65), E.out5);
    setNum(alvo * k);
    const ent = fase(t, T(0.38), T(0.95), E.expo);
    num.style.transform = `translateY(${(1 - ent) * 60 - s * 120}px) scale(${0.985 + 0.015 * k})`;
    num.style.opacity = ent * (1 - s);
    // script revelado da esquerda para a direita
    const ks = fase(t, T(1.0), T(1.75), E.inOut);
    scr.style.clipPath = `inset(-20% ${100 - ks * 100}% -30% -5%)`;
    scr.style.opacity = 1 - s;
    scr.style.transform = `translateY(${-s * 90}px)`;
    // régua de anos
    const kb = fase(t, T(0.45), T(1.65), E.out5);
    bar(kb, fase(t, T(0.3), T(0.6)) * (1 - s));
    anoV.textContent = String(Math.round(lerp(ini, fim, kb)));
    anoV.style.left = px(ctx.X0 + 60 + kb * 960 - 22); anoV.style.top = px(1004);
    anoV.style.opacity = fase(t, T(0.45), T(0.7)) * (1 - s);
    ano0.style.opacity = 0.9 * fase(t, T(0.3), T(0.6)) * (1 - s) * (1 - fase(kb, 0, 0.08, E.lin));
    ano1.style.opacity = 0.9 * fase(t, T(0.3), T(0.6)) * (1 - s) * (1 - fase(kb, 0.86, 0.95, E.lin));
    // cantos da janela: abrem junto com a janela e somem quando ela vira tela cheia
    cnt(t, fase(t, T(0.1), T(0.75), E.expo), 1 - fase(t, SAI - 0.1, SAI + 0.15));
  };
}
