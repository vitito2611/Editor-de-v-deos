// Cena "orbe": a IA como um orbe de plasma (esfera deformada por ruído, borda fresnel ciano, núcleo roxo,
// partículas em órbita). Usada no formato "janela": o vídeo do cliente entra num círculo à esquerda e, no
// instante `junta` (tempo da inserção), o círculo e o orbe se encontram no centro e viram um orbe maior.
function montarCena(ctx) {
  const { THREE, scene, camera, rnd, fase, E, brilho, poeira, bokeh, ACENTO, D } = ctx;
  const c = D.cena || {};
  const PRE = D.pre_roll || 0;
  const junta = (c.junta ?? 1.2) + PRE;          // tempo da cena em que os dois se fundem
  const lado = c.orbe_x ?? 0.62;                   // posição inicial (fração da largura visível, a partir do centro)
  scene.fog = new THREE.FogExp2(0x08051a, 0.04);
  camera.position.set(0, 0, 9); camera.lookAt(0, 0, 0);
  const meiaAltura = Math.tan((camera.fov * Math.PI) / 360) * 9, meiaLarg = meiaAltura * camera.aspect;
  const yc = (c.orbe_y ?? -0.02) * meiaAltura * 2 * -1;   // fração da altura a partir do centro (+ = abaixo)

  const ruido = `
    vec3 mod289(vec3 x){return x-floor(x*(1./289.))*289.;} vec4 mod289(vec4 x){return x-floor(x*(1./289.))*289.;}
    vec4 permute(vec4 x){return mod289(((x*34.)+1.)*x);} vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-0.85373472095314*r;}
    float snoise(vec3 v){const vec2 C=vec2(1./6.,1./3.);const vec4 D=vec4(0.,.5,1.,2.);vec3 i=floor(v+dot(v,C.yyy));vec3 x0=v-i+dot(i,C.xxx);
    vec3 g=step(x0.yzx,x0.xyz);vec3 l=1.-g;vec3 i1=min(g.xyz,l.zxy);vec3 i2=max(g.xyz,l.zxy);vec3 x1=x0-i1+C.xxx;vec3 x2=x0-i2+C.yyy;vec3 x3=x0-D.yyy;
    i=mod289(i);vec4 p=permute(permute(permute(i.z+vec4(0.,i1.z,i2.z,1.))+i.y+vec4(0.,i1.y,i2.y,1.))+i.x+vec4(0.,i1.x,i2.x,1.));
    float n_=.142857142857;vec3 ns=n_*D.wyz-D.xzx;vec4 j=p-49.*floor(p*ns.z*ns.z);vec4 x_=floor(j*ns.z);vec4 y_=floor(j-7.*x_);
    vec4 x=x_*ns.x+ns.yyyy;vec4 y=y_*ns.x+ns.yyyy;vec4 h=1.-abs(x)-abs(y);vec4 b0=vec4(x.xy,y.xy);vec4 b1=vec4(x.zw,y.zw);
    vec4 s0=floor(b0)*2.+1.;vec4 s1=floor(b1)*2.+1.;vec4 sh=-step(h,vec4(0.));vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy;vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;
    vec3 p0=vec3(a0.xy,h.x);vec3 p1=vec3(a0.zw,h.y);vec3 p2=vec3(a1.xy,h.z);vec3 p3=vec3(a1.zw,h.w);
    vec4 norm=taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));p0*=norm.x;p1*=norm.y;p2*=norm.z;p3*=norm.w;
    vec4 m=max(.6-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.);m=m*m;return 42.*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));}`;
  const uni = { uT: { value: 0 }, uForca: { value: 0.07 }, uC1: { value: ACENTO }, uC2: { value: new THREE.Color(0x6b2fd6) } };
  const orbeMat = new THREE.ShaderMaterial({
    uniforms: uni, transparent: true,
    vertexShader: `${ruido} uniform float uT; uniform float uForca; varying vec3 vN; varying vec3 vV; varying float vR;
      void main(){ float r = snoise(normal*0.9 + vec3(uT*0.35)) * uForca + snoise(normal*1.8 - uT*0.5)*uForca*0.25;
        vec3 p = position + normal * r; vR = r;
        vec4 mv = modelViewMatrix * vec4(p,1.); vN = normalize(normalMatrix*normal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix*mv; }`,
    fragmentShader: `uniform vec3 uC1; uniform vec3 uC2; varying vec3 vN; varying vec3 vV; varying float vR;
      void main(){ float d = max(dot(vN,vV),0.); float f = pow(1.-d, 2.0);
        vec3 nucleo = mix(uC1, vec3(1.0), pow(d, 6.0)*0.85);          // centro claro (luz de dentro)
        vec3 meio = mix(uC2, uC1, 0.55 + vR*2.0);
        vec3 cor = mix(nucleo, meio, smoothstep(0.15, 0.85, 1.-d)) + uC1*f*1.2 + vec3(1.)*pow(f,6.)*0.6;
        gl_FragColor = vec4(cor, 0.9); }`,
  });
  const orbe = new THREE.Group(); scene.add(orbe);
  const esfera = new THREE.Mesh(new THREE.IcosahedronGeometry(1, 48), orbeMat); orbe.add(esfera);
  const halo = brilho(ACENTO, 3.2, 0.45); orbe.add(halo);
  const brilhoN = brilho(new THREE.Color(0xffffff), 1.6, 0.5); brilhoN.position.z = 0.6; orbe.add(brilhoN);
  const haloN = brilho(new THREE.Color(0x8a4dff), 5, 0.25); orbe.add(haloN);
  // partículas em órbita (cinturão inclinado)
  const NP = 600, pg = new THREE.BufferGeometry(), pp = new Float32Array(NP * 3), pd = [];
  for (let i = 0; i < NP; i++) pd.push({ r: 1.25 + rnd() * 0.9, a: rnd() * Math.PI * 2, y: (rnd() - 0.5) * 0.18, v: 0.5 + rnd() * 0.9 });
  pg.setAttribute("position", new THREE.BufferAttribute(pp, 3));
  const cinto = new THREE.Points(pg, new THREE.PointsMaterial({ color: 0xc8f6ff, size: 0.03, transparent: true, opacity: 0.9,
    blending: THREE.AdditiveBlending, depthWrite: false })); cinto.rotation.set(1.2, 0.2, 0.3); orbe.add(cinto);
  // ondas de choque na fusão
  const ondas = [0, 0.12, 0.24].map(() => { const m = new THREE.Mesh(new THREE.RingGeometry(0.98, 1.0, 96),
    new THREE.MeshBasicMaterial({ color: ACENTO, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, depthWrite: false }));
    scene.add(m); return m; });
  const fundo = poeira(500, [12, 16, 10], 0x9f8bff, 0.026); fundo.position.z = -3; scene.add(fundo);
  const bk = bokeh(6, 1.3, 4.5, 6.8, [ACENTO, new THREE.Color(0x8a4dff)]); scene.add(bk);

  return (t) => {
    uni.uT.value = t;
    const ent = fase(t, PRE - 0.3, PRE + 0.5, E.expo);
    const j = fase(t, junta - 0.35, junta + 0.05, E.in3);           // vai para o centro (encontro)
    const cresce = fase(t, junta, junta + 0.6, E.back);               // vira o orbe maior
    const x = (lado * meiaLarg) * (1 - j) + (1 - ent) * 2.5;
    orbe.position.set(x, yc, 0);
    const esc = 0.48 * ent + cresce * 0.3;
    orbe.scale.setScalar(Math.max(0.001, esc) * (1 + 0.03 * Math.sin(t * 6)));
    uni.uForca.value = 0.06 + cresce * 0.1 * (1 - fase(t, junta + 0.5, junta + 1.3));
    halo.material.opacity = 0.35 + cresce * 0.35;
    for (let i = 0; i < NP; i++) {
      const d = pd[i], a = d.a + t * d.v;
      pp[i * 3] = Math.cos(a) * d.r; pp[i * 3 + 1] = d.y; pp[i * 3 + 2] = Math.sin(a) * d.r;
    }
    pg.attributes.position.needsUpdate = true;
    ondas.forEach((o, i) => {
      const k = fase(t, junta + i * 0.12, junta + i * 0.12 + 0.9, E.out3);
      o.position.set(0, yc, 0.2); o.scale.setScalar(0.6 + k * (2.6 + i * 0.6)); o.material.opacity = (k > 0 ? 1 : 0) * (1 - k) * 0.9;
    });
    camera.position.set(Math.sin(t * 0.4) * 0.25, Math.cos(t * 0.3) * 0.15, 9 - fase(t, 0, D.dur + PRE, E.sine) * 0.8);
    camera.lookAt(0, 0, 0);
    fundo.rotation.y = t * 0.03;
    bk.userData.mover(t);
  };
}
