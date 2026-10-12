// Cena "relogio": um mostrador de 24 h em perspectiva. Um arco de luz dá a volta inteira (o dia todo) com
// o sol correndo na borda; depois tudo se apaga e só 1 hora (1/24) acende, salta para frente e explode em luz.
// Fala: "gerar em uma hora o que ele fazia o dia todinho".
function montarCena(ctx) {
  const { THREE, scene, camera, rnd, fase, E, brilho, poeira, bokeh, ACENTO, D } = ctx;
  const c = D.cena || {};
  scene.fog = new THREE.FogExp2(0x070512, 0.045);
  scene.add(new THREE.AmbientLight(0xbfb0ff, 0.5));
  const key = new THREE.DirectionalLight(0xffffff, 1.8); key.position.set(2, 4, 6); scene.add(key);
  const R = 0.98, yc = -0.45;
  const mostrador = new THREE.Group(); mostrador.position.y = yc; scene.add(mostrador);
  // 24 marcas (cada hora é um bloco de vidro); a de "1 hora" é a 0
  const blocos = [];
  for (let h = 0; h < 24; h++) {
    const a = Math.PI / 2 - (h / 24) * Math.PI * 2;
    const m = new THREE.Mesh(new THREE.BoxGeometry(0.075, h % 6 === 0 ? 0.3 : 0.18, 0.06),
      new THREE.MeshPhysicalMaterial({ color: 0x2a1f48, roughness: 0.25, metalness: 0.3, clearcoat: 1, emissive: 0x000000 }));
    m.position.set(Math.cos(a) * R, Math.sin(a) * R, 0);
    m.rotation.z = a - Math.PI / 2;
    mostrador.add(m); blocos.push(m);
  }
  // trilho do dia (anel apagado) + arco aceso que varre
  mostrador.add(new THREE.Mesh(new THREE.TorusGeometry(R * 0.86, 0.012, 8, 200),
    new THREE.MeshBasicMaterial({ color: 0x5b4a8a, transparent: true, opacity: 0.5 })));
  const arco = new THREE.Mesh(new THREE.TorusGeometry(R * 0.86, 0.035, 10, 8, 0.001),
    new THREE.MeshBasicMaterial({ color: 0xffc46b, transparent: true, opacity: 0.95, blending: THREE.AdditiveBlending }));
  arco.rotation.z = -Math.PI / 2; arco.scale.x = -1;   // começa no topo, sentido horário
  mostrador.add(arco);
  let arcoAtual = -1;
  const arcoAte = (fr) => {   // refaz o arco só quando muda (barato: 1 anel)
    const q = Math.round(fr * 480) / 480;
    if (q === arcoAtual) return;
    arcoAtual = q;
    arco.geometry.dispose();
    arco.geometry = new THREE.TorusGeometry(R * 0.86, 0.035, 10, Math.max(2, Math.round(240 * q)), Math.max(0.001, q * Math.PI * 2));
  };
  const sol = brilho(new THREE.Color(0xffc46b), 0.9, 1); mostrador.add(sol);
  const solN = brilho(new THREE.Color(0xffffff), 0.32, 1); mostrador.add(solN);
  // fatia de 1 hora (o destaque)
  const fatia = new THREE.Mesh(new THREE.RingGeometry(R * 0.32, R * 1.02, 48, 1, Math.PI / 2 - (Math.PI * 2) / 24, (Math.PI * 2) / 24),
    new THREE.MeshBasicMaterial({ color: ACENTO, transparent: true, opacity: 0, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false }));
  mostrador.add(fatia);
  const estouro = brilho(ACENTO, 3, 0); mostrador.add(estouro);
  // centro: pino
  const pino = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.08, 32), new THREE.MeshStandardMaterial({ color: 0xffffff, metalness: 0.8, roughness: 0.2 }));
  pino.rotation.x = Math.PI / 2; mostrador.add(pino);
  const ponteiro = new THREE.Mesh(new THREE.BoxGeometry(0.035, R * 0.8, 0.02), new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0x444444 }));
  ponteiro.geometry.translate(0, R * 0.4, 0); mostrador.add(ponteiro);
  const fundo = poeira(500, [10, 14, 10], 0x9f8bff, 0.026); fundo.position.z = -3; scene.add(fundo);
  const bk = bokeh(6, 1.3, 4.5, 6.8, [ACENTO, new THREE.Color(0xffc46b)]); scene.add(bk);
  const tDia0 = 0.15, tDia1 = c.dia_fim ?? 1.45, tHora = tDia1 + 0.25;

  return (t) => {
    const k = fase(t, 0, D.dur + (D.pre_roll || 0), E.sine);
    camera.position.set(0.7 - 1.0 * k, 0.6 - 0.3 * k, 9.4 - 1.0 * k);
    camera.lookAt(0, yc + 0.5, 0);
    mostrador.rotation.set(-0.42 + 0.18 * k, 0.32 - 0.4 * k, 0);
    // o dia inteiro passando (rápido, com aceleração)
    const dia = fase(t, tDia0, tDia1, E.inOut);
    const apaga = fase(t, tDia1 + 0.05, tDia1 + 0.35, E.out3);
    arcoAte(dia);
    arco.material.opacity = 0.95 * (1 - apaga);
    const a = Math.PI / 2 - dia * Math.PI * 2;
    sol.position.set(Math.cos(a) * R * 0.86, Math.sin(a) * R * 0.86, 0.05);
    solN.position.copy(sol.position);
    sol.material.opacity = solN.material.opacity = (dia > 0.001 ? 1 : 0) * (1 - apaga);
    ponteiro.rotation.z = -dia * Math.PI * 2 * (1 - apaga) - apaga * (Math.PI * 2) / 48;
    blocos.forEach((b, h) => {
      const aceso = dia >= h / 24 ? 1 : 0;
      b.material.emissive.setHex(0xffb24a); b.material.emissiveIntensity = aceso * 0.6 * (1 - apaga);
    });
    // só 1 hora acende, salta para frente e solta um clarão
    const hora = fase(t, tHora, tHora + 0.55, E.back);
    fatia.material.opacity = hora * 0.75;
    fatia.position.z = hora * 0.35; fatia.scale.setScalar(1 + hora * 0.08);
    blocos[0].material.emissive = ACENTO; blocos[0].material.emissiveIntensity = Math.max(blocos[0].material.emissiveIntensity, hora * 1.2);
    const ex = fase(t, tHora, tHora + 0.7, E.out3);
    estouro.position.set(Math.cos(Math.PI / 2 - Math.PI / 24) * R * 0.7, Math.sin(Math.PI / 2 - Math.PI / 24) * R * 0.7, 0.4);
    estouro.material.opacity = (ex > 0 ? 1 : 0) * (1 - ex) * 0.9; estouro.scale.setScalar(0.5 + ex * 3);
    fundo.rotation.y = t * 0.03;
    bk.userData.mover(t);
  };
}
