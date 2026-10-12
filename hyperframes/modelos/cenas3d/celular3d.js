// Cena "celular3d": celular 3D de verdade (corpo de metal com reflexo, tela viva desenhada a cada quadro:
// orbe ouvindo a consulta, ondas de voz, dica em tempo real) e o briefing saltando para fora da tela.
// Zeal = copiloto de vendas do dentista (NÃO dá diagnóstico nem plano de tratamento). Pensada para o
// formato "janela": o vídeo do cliente fica numa janela no alto à direita e o celular ocupa o lado esquerdo.
function montarCena(ctx) {
  const { THREE, scene, camera, rnd, fase, E, brilho, poeira, bokeh, RoundedBoxGeometry, ACENTO, D, H } = ctx;
  const c = D.cena || {};
  const PRE = D.pre_roll || 0;
  scene.fog = new THREE.FogExp2(0x08051a, 0.035);
  scene.add(new THREE.AmbientLight(0xc7b8ff, 0.5));
  const key = new THREE.DirectionalLight(0xffffff, 2.4); key.position.set(3, 4, 6); scene.add(key);
  const rim = new THREE.PointLight(ACENTO, 50, 10); rim.position.set(-2.5, 1.5, -1); scene.add(rim);
  const rim2 = new THREE.PointLight(0x8a4dff, 40, 10); rim2.position.set(2.5, -2, -0.5); scene.add(rim2);
  camera.position.set(0, 0, 9); camera.lookAt(0, 0, 0);
  const meiaAlt = Math.tan((camera.fov * Math.PI) / 360) * 9, meiaLarg = meiaAlt * camera.aspect;
  // posição do celular: fração da largura/altura do quadro (padrão: lado esquerdo, abaixo da janela do vídeo)
  const px = (c.cel_x ?? 0.3) * 2 - 1, py = 1 - (c.cel_y ?? 0.6) * 2;
  const alvo = new THREE.Vector3(px * meiaLarg, py * meiaAlt, 0);
  const escala = c.cel_escala ?? 1.0;

  // ---- tela (canvas atualizado a cada quadro)
  const TW = 540, TH = 1120;
  const cv = document.createElement("canvas"); cv.width = TW; cv.height = TH;
  const g = cv.getContext("2d");
  const telaTex = new THREE.CanvasTexture(cv); telaTex.colorSpace = THREE.SRGBColorSpace; telaTex.anisotropy = 8;
  const falas = c.falas || [["pac", "Achei caro…"], ["ia", "Objeção: preço. Mostre o parcelamento."]];
  const app = c.app || "Zeal · Copiloto";
  const rr = (x, y, w, h, r) => { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); };
  const quebra = (txt, maxW) => { const ws = txt.split(" "), ls = []; let l = ""; ws.forEach((w) => { const t2 = l ? l + " " + w : w; if (g.measureText(t2).width > maxW) { ls.push(l); l = w; } else l = t2; }); if (l) ls.push(l); return ls; };
  function desenhaTela(t) {
    const tl = t - PRE;
    const gr = g.createLinearGradient(0, 0, 0, TH); gr.addColorStop(0, "#1b1032"); gr.addColorStop(0.6, "#0d0819"); gr.addColorStop(1, "#0b1622");
    g.fillStyle = gr; g.fillRect(0, 0, TW, TH);
    g.fillStyle = "#fff"; g.font = "700 26px Rubik"; g.fillText("9:41", 46, 52);
    g.fillStyle = "#000"; rr(TW / 2 - 70, 22, 140, 40, 20); g.fill();
    // cabeçalho
    g.font = "700 30px Rubik"; g.fillStyle = "#fff"; g.fillText(app, 120, 150);
    const pulso = 1 + 0.08 * Math.sin(tl * 10);
    const og = g.createRadialGradient(72, 138, 2, 72, 138, 34 * pulso); og.addColorStop(0, "#e8fdff"); og.addColorStop(0.45, "#24d0dc"); og.addColorStop(1, "#5d2e8c");
    g.fillStyle = og; g.beginPath(); g.arc(72, 138, 30 * pulso, 0, Math.PI * 2); g.fill();
    g.fillStyle = "rgba(36,208,220,0.15)"; rr(TW - 160, 118, 120, 38, 19); g.fill();
    g.fillStyle = "#24d0dc"; g.font = "700 18px Rubik"; g.fillText("AO VIVO", TW - 140, 144);
    // ondas de voz (barras) — só quando a IA fala
    const fala = tl > 0.9 ? 1 : 0.25;
    for (let i = 0; i < 26; i++) {
      const a = (0.25 + 0.75 * Math.abs(Math.sin(i * 1.7 + tl * 9) * Math.cos(i * 0.6 - tl * 5))) * fala;
      const h = 14 + a * 130, x = 40 + i * 18;
      const bg = g.createLinearGradient(0, 280 - h / 2, 0, 280 + h / 2); bg.addColorStop(0, "#d9fbff"); bg.addColorStop(1, "#24d0dc");
      g.fillStyle = bg; rr(x, 280 - h / 2, 9, h, 4.5); g.fill();
    }
    // conversa
    let y = 400;
    falas.forEach(([q, txt], i) => {
      const ent = fase(tl, 0.35 + i * 0.75, 0.75 + i * 0.75, E.out3);
      if (ent <= 0) return;
      g.font = "500 27px Rubik";
      const ls = quebra(txt, 360), bh = 30 + ls.length * 36, bw = 400;
      const ia = q === "ia", x = ia ? TW - 40 - bw : 40;
      g.save(); g.globalAlpha = ent; g.translate(0, (1 - ent) * 30);
      g.fillStyle = ia ? "#24d0dc" : "rgba(255,255,255,0.10)"; rr(x, y, bw, bh, 26); g.fill();
      g.fillStyle = ia ? "#061318" : "#ffffff"; ls.forEach((l, k) => g.fillText(l, x + 24, y + 46 + k * 36));
      g.restore();
      y += bh + 22;
    });
    telaTex.needsUpdate = true;
  }

  // ---- corpo do celular
  const cel = new THREE.Group(); scene.add(cel);
  const W3 = 1.18 * escala, H3 = 2.42 * escala;
  const corpo = new THREE.Mesh(new RoundedBoxGeometry(W3, H3, 0.11, 6, 0.16 * escala),
    new THREE.MeshPhysicalMaterial({ color: 0x1b1726, metalness: 0.85, roughness: 0.28, clearcoat: 1, clearcoatRoughness: 0.1, envMapIntensity: 1.4 }));
  cel.add(corpo);
  const tela = new THREE.Mesh(new THREE.PlaneGeometry(W3 * 0.9, H3 * 0.93), new THREE.MeshBasicMaterial({ map: telaTex, toneMapped: false }));
  tela.position.z = 0.058; cel.add(tela);
  const reflexo = new THREE.Mesh(new THREE.PlaneGeometry(W3 * 0.9, H3 * 0.93), new THREE.MeshPhysicalMaterial({ color: 0xffffff, transparent: true, opacity: 0.06,
    roughness: 0.05, metalness: 0, clearcoat: 1, envMapIntensity: 2 })); reflexo.position.z = 0.061; cel.add(reflexo);
  const sombra = brilho(new THREE.Color(0x8a4dff), 4.2, 0.35); sombra.position.z = -0.4; cel.add(sombra);

  // ---- cartão do briefing (sai da tela para a frente)
  const cc = document.createElement("canvas"); cc.width = 640; cc.height = 400;
  const g2 = cc.getContext("2d");
  const cartao = c.cartao || { titulo: "Briefing da consulta", linhas: [["Perfil", "Analítico"], ["Objeção", "Preço"], ["Rapport", "Alto"]] };
  const texC = new THREE.CanvasTexture(cc); texC.colorSpace = THREE.SRGBColorSpace;
  function desenhaCartao(p) {
    g2.fillStyle = "#f3effb"; g2.fillRect(0, 0, 640, 400);   // cantos na cor da borda (sem quadrado preto)
    const rr2 = (x, y, w, h, r) => { g2.beginPath(); g2.moveTo(x + r, y); g2.arcTo(x + w, y, x + w, y + h, r); g2.arcTo(x + w, y + h, x, y + h, r); g2.arcTo(x, y + h, x, y, r); g2.arcTo(x, y, x + w, y, r); g2.closePath(); };
    const bg = g2.createLinearGradient(0, 0, 0, 400); bg.addColorStop(0, "#ffffff"); bg.addColorStop(1, "#efeaf9");
    g2.fillStyle = bg; rr2(0, 0, 640, 400, 44); g2.fill();
    g2.fillStyle = "#24d0dc"; g2.beginPath(); g2.arc(78, 78, 38, 0, Math.PI * 2); g2.fill();
    g2.strokeStyle = "#061318"; g2.lineWidth = 8; g2.lineCap = "round"; g2.beginPath(); g2.moveTo(60, 79); g2.lineTo(73, 92); g2.lineTo(97, 66); g2.stroke();
    g2.fillStyle = "#1b1230"; g2.font = "700 40px Rubik"; g2.fillText(cartao.titulo, 136, 92);
    (cartao.linhas || []).forEach(([a, b], i) => {
      const nl = (cartao.linhas || []).length, y = 172 + i * (nl > 2 ? 58 : 78);
      g2.fillStyle = "#e3dcf0"; g2.fillRect(40, y - 40, 560, 2);
      g2.fillStyle = "#5b4f75"; g2.font = "500 30px Rubik"; g2.fillText(a, 40, y + 4);
      g2.fillStyle = "#1b1230"; g2.font = "700 30px Rubik"; const w = g2.measureText(b).width; g2.fillText(b, 600 - w, y + 4);
    });
    g2.fillStyle = "#e3dcf0"; rr2(40, 345, 560, 16, 8); g2.fill();
    const pg = g2.createLinearGradient(40, 0, 600, 0); pg.addColorStop(0, "#5d2e8c"); pg.addColorStop(1, "#24d0dc");
    g2.fillStyle = pg; rr2(40, 345, 560 * p, 16, 8); g2.fill();
    texC.needsUpdate = true;
  }
  const cartaoM = new THREE.Mesh(new RoundedBoxGeometry(1.5 * escala, 0.94 * escala, 0.03, 4, 0.08), [
    new THREE.MeshBasicMaterial({ color: 0xf3effb }), new THREE.MeshBasicMaterial({ color: 0xf3effb }),
    new THREE.MeshBasicMaterial({ color: 0xf3effb }), new THREE.MeshBasicMaterial({ color: 0xf3effb }),
    new THREE.MeshBasicMaterial({ map: texC, toneMapped: false }), new THREE.MeshBasicMaterial({ color: 0xf3effb })]);
  scene.add(cartaoM);
  const cartaoHalo = brilho(ACENTO, 2.6, 0); scene.add(cartaoHalo);
  const fundo = poeira(450, [12, 16, 10], 0x9f8bff, 0.026); fundo.position.z = -3; scene.add(fundo);
  const bk = bokeh(5, 1.3, 4.5, 6.8, [ACENTO, new THREE.Color(0x8a4dff)]); scene.add(bk);
  const tCartao = (c.cartao_t ?? 2.1) + PRE;

  return (t) => {
    desenhaTela(t);
    const ent = fase(t, PRE - 0.35, PRE + 0.75, E.expo);
    cel.position.set(alvo.x - (1 - ent) * 1.2, alvo.y - (1 - ent) * 3.2 + Math.sin(t * 1.4) * 0.04, (1 - ent) * -2);
    cel.rotation.set(0.12 + (1 - ent) * 0.7 + Math.sin(t * 0.8) * 0.03, 0.42 - 0.18 * fase(t, 0, D.dur + PRE, E.sine) + (1 - ent) * 0.6, -0.05 + (1 - ent) * 0.2);
    const pc = fase(t, tCartao, tCartao + 0.8, E.expo);
    desenhaCartao(fase(t, tCartao + 0.3, tCartao + 1.3, E.inOut));
    cartaoM.visible = pc > 0.001;
    const destino = new THREE.Vector3(alvo.x + 0.75 * escala, alvo.y - 0.35 * escala, 1.3);
    cartaoM.position.lerpVectors(new THREE.Vector3(alvo.x, alvo.y, 0.1), destino, pc);
    cartaoM.rotation.set(0.05, 0.25 * (1 - pc) + 0.12, -0.04);
    cartaoM.scale.setScalar(0.35 + 0.65 * pc);
    cartaoHalo.position.copy(cartaoM.position).add(new THREE.Vector3(0, 0, -0.1)); cartaoHalo.material.opacity = pc * 0.35;
    tela.material.color.setScalar(1 - pc * 0.35);
    camera.position.set(Math.sin(t * 0.35) * 0.2, Math.cos(t * 0.3) * 0.12, 9 - fase(t, 0, D.dur + PRE, E.sine) * 0.6);
    camera.lookAt(0, 0, 0);
    fundo.rotation.y = t * 0.03;
    bk.userData.mover(t);
  };
}
