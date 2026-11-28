// 《稳定的形状》 — every frame is a pure function of absolute time t (seconds).
import * as THREE from 'three';
import { RoundedBoxGeometry } from '../vendor/RoundedBoxGeometry.js';

const LW = 1920, LH = 1080;
const params = new URLSearchParams(location.search);
const PW = Number(params.get('w') || 1920), PH = Number(params.get('h') || 1080);
const W = LW, H = LH;
const [D, SB, MM] = await Promise.all([
  fetch('../data/data.json').then(r => r.json()),
  fetch('./storyboard.json').then(r => r.json()),
  fetch('../music/music_map.json').then(r => r.json()),
]);
const BEAT = MM.beat_period, ANCHOR = MM.downbeat_anchor;   // measured, not guessed
const beatAt = k => ANCHOR + k * BEAT;
const C = { bg: '#07060a', ivory: '#EDE6D6', gold: '#D9B46A', bright: '#F2D38C', dim: 'rgba(237,230,214,0.45)', faint: 'rgba(237,230,214,0.16)', red: '#B8432F' };
const SERIF = '"Songti SC","STSong",serif', SANS = '"PingFang SC","Heiti SC",sans-serif';
await Promise.all([document.fonts.load(`600 44px ${SANS}`), document.fonts.load(`700 120px ${SERIF}`), document.fonts.load(`400 30px ${SERIF}`)]);

// ---------- utils ----------
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, u) => a + (b - a) * u;
const ss = (a, b, t) => { const u = clamp((t - a) / (b - a)); return u * u * (3 - 2 * u); };
const eio = u => (u = clamp(u), u < .5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2);
const eout = u => 1 - Math.pow(1 - clamp(u), 3);
const win = (t, a, b, fi = .5, fo = .5) => Math.min(ss(a, a + fi, t), 1 - ss(b - fo, b, t));
function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let x = Math.imul(seed ^ seed >>> 15, 1 | seed); x = x + Math.imul(x ^ x >>> 7, 61 | x) ^ x; return ((x ^ x >>> 14) >>> 0) / 4294967296; }; }
const fmt = (x, d = 0) => (x * 100).toFixed(d) + '%';
const fill = s => s.replace(/\{(\w+)\}/g, (_, k) => { if (!(k in D.facts)) throw new Error('missing fact ' + k); return D.facts[k]; });

// ---------- canvases ----------
const bgEl = document.getElementById('bg'), uiEl = document.getElementById('ui');
bgEl.width = uiEl.width = PW; bgEl.height = uiEl.height = PH;
const bg = bgEl.getContext('2d'); const ui = uiEl.getContext('2d');
bg.setTransform(PW / LW, 0, 0, PH / LH, 0, 0); ui.setTransform(PW / LW, 0, 0, PH / LH, 0, 0);
const R0 = rng(7);
const dust = Array.from({ length: 70 }, () => ({ x: R0() * W, y: R0() * H, r: .6 + R0() * 1.6, v: 4 + R0() * 10, p: R0() * 6.28 }));
const grain = Array.from({ length: 4 }, (_, i) => { const c = new OffscreenCanvas(256, 256), g = c.getContext('2d'), r = rng(100 + i), im = g.createImageData(256, 256); for (let j = 0; j < im.data.length; j += 4) { const v = r() * 255; im.data[j] = im.data[j + 1] = im.data[j + 2] = v; im.data[j + 3] = 255; } g.putImageData(im, 0, 0); return c; });

function drawBackground(t, warm = 1) {
  bg.fillStyle = C.bg; bg.fillRect(0, 0, W, H);
  const g = bg.createRadialGradient(W / 2, H * .45, 50, W / 2, H * .45, W * .62);
  g.addColorStop(0, `rgba(92,68,32,${.34 * warm})`); g.addColorStop(.55, `rgba(40,29,15,${.16 * warm})`); g.addColorStop(1, 'rgba(0,0,0,0)');
  bg.fillStyle = g; bg.fillRect(0, 0, W, H);
  for (const d of dust) { const y = (d.y - t * d.v) % H; bg.fillStyle = `rgba(242,211,140,${.08 + .07 * Math.sin(t * .7 + d.p)})`; bg.beginPath(); bg.arc((d.x + 12 * Math.sin(t * .2 + d.p)) % W, y < 0 ? y + H : y, d.r, 0, 6.283); bg.fill(); }
}
function drawGrain(t) {
  const f = Math.round(t * 30); ui.save(); ui.globalAlpha = .035; ui.globalCompositeOperation = 'source-over';
  ui.fillStyle = ui.createPattern(grain[f % 4], 'repeat'); ui.translate((f * 37) % 256, (f * 91) % 256); ui.fillRect(-256, -256, W + 512, H + 512); ui.restore();
  const v = ui.createRadialGradient(W / 2, H / 2, H * .42, W / 2, H / 2, H * 1.05); v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,0.55)');
  ui.fillStyle = v; ui.fillRect(0, 0, W, H);
}

// ---------- text ----------
function text(s, x, y, { size = 30, font = SANS, weight = 400, color = C.ivory, align = 'left', alpha = 1, spacing = 0, base = 'alphabetic' } = {}) {
  if (alpha <= 0) return; ui.save(); ui.globalAlpha *= alpha; ui.font = `${weight} ${size}px ${font}`; ui.fillStyle = color; ui.textAlign = align; ui.textBaseline = base;
  if (spacing) ui.letterSpacing = spacing + 'px';
  if (arguments[3] && arguments[3].halo) { ui.lineJoin = 'round'; ui.strokeStyle = 'rgba(7,6,10,0.92)'; ui.lineWidth = Math.max(6, size * .32); ui.strokeText(s, x, y); }
  ui.fillText(s, x, y); ui.restore();
}
const CAPS = SB.captions.map(c => ({ ...c, segs: fill(c.text).split(/\[\[|\]\]/).map((s, i) => ({ s, hi: i % 2 === 1 })) }));
function captionWidth(c, size = 44) { ui.font = `600 ${size}px ${SANS}`; return c.segs.reduce((w, s) => w + ui.measureText(s.s).width, 0); }
function drawCaptions(t) {
  for (const c of CAPS) {
    const a = win(t, c.t0, c.t1, .28, .28); if (a <= 0) continue;
    let size = 44; while (captionWidth(c, size) > 1560) size -= 2;
    const w = captionWidth(c, size); let x = W / 2 - w / 2; const y = 990 + (1 - a) * 6;
    ui.save(); ui.globalAlpha = a; ui.font = `600 ${size}px ${SANS}`; ui.textBaseline = 'alphabetic';
    ui.shadowColor = 'rgba(0,0,0,0.9)'; ui.shadowBlur = 14;
    for (const s of c.segs) { ui.fillStyle = s.hi ? C.bright : C.ivory; ui.fillText(s.s, x, y); x += ui.measureText(s.s).width; }
    ui.restore();
  }
}
function drawMeta(t) {
  for (const m of SB.meta) {
    const a = win(t, m.t0, m.t1, .6, .5); if (a <= 0) continue;
    ui.save(); ui.globalAlpha = a;
    ui.fillStyle = C.gold; ui.fillRect(96, 74, 3, m.tl2 ? 64 : 34);
    text(m.tl, 116, 100, { size: 30, font: SERIF, weight: 700, color: C.bright });
    if (m.tl2) text(m.tl2, 116, 134, { size: 22, color: C.dim });
    text(m.tr, 1824, 100, { size: 24, font: SERIF, color: C.gold, align: 'right' });
    if (m.tr2) text(m.tr2, 1824, 132, { size: 24, font: SERIF, color: C.gold, align: 'right' });
    ui.restore();
  }
}
function drawTitle(t, a, y = 470, scale = 1) {
  if (a <= 0) return;
  ui.save(); ui.globalAlpha = a; ui.translate(W / 2, y); ui.scale(scale, scale);
  text(SB.title_latin, 0, -128, { size: 24, font: SERIF, color: C.gold, align: 'center', spacing: 10, alpha: .85 });
  ui.shadowColor = 'rgba(242,211,140,0.35)'; ui.shadowBlur = 30;
  const g = ui.createLinearGradient(0, -90, 0, 30); g.addColorStop(0, '#FBE7B0'); g.addColorStop(.55, '#D9B46A'); g.addColorStop(1, '#A87E3A');
  ui.font = `900 132px ${SERIF}`; ui.textAlign = 'center'; ui.fillStyle = g; ui.letterSpacing = '18px'; ui.fillText(SB.title, 9, 0); ui.shadowBlur = 0; ui.letterSpacing = '0px';
  const lg = ui.createLinearGradient(-330, 0, 330, 0); lg.addColorStop(0, 'rgba(217,180,106,0)'); lg.addColorStop(.5, 'rgba(217,180,106,0.9)'); lg.addColorStop(1, 'rgba(217,180,106,0)');
  ui.fillStyle = lg; ui.fillRect(-330, 48, 660, 1.5);
  text(SB.subtitle, 0, 102, { size: 34, color: C.ivory, align: 'center', spacing: 4, alpha: .9 });
  ui.restore();
}

// ---------- chart helper ----------
// xmode 0 = linear, 1 = log10; mixed for morphs.
function makeAxis(o) { return o; }
function mapper(ax) {
  const lx = x => (x - ax.xmin) / (ax.xmax - ax.xmin);
  const gx = x => (Math.log10(Math.max(x, 1e-9)) - Math.log10(ax.lxmin)) / (Math.log10(ax.lxmax) - Math.log10(ax.lxmin));
  return { x: v => ax.x0 + ax.w * lerp(lx(v), gx(v), ax.log), y: v => ax.y0 + ax.h * (1 - (v - ax.ymin) / (ax.ymax - ax.ymin)) };
}
function mixAxis(a, b, u) { const o = {}; for (const k in a) o[k] = typeof a[k] === 'number' ? lerp(a[k], b[k], u) : a[k]; return o; }
function drawAxes(ax, m, a, { yticks = [], xticks = [], ylab = v => v, xlab = v => v, ytitle = '', xtitle = '' } = {}) {
  if (a <= 0) return; ui.save(); ui.globalAlpha = a; ui.strokeStyle = 'rgba(237,230,214,0.35)'; ui.lineWidth = 1.5;
  ui.beginPath(); ui.moveTo(ax.x0, ax.y0); ui.lineTo(ax.x0, ax.y0 + ax.h); ui.lineTo(ax.x0 + ax.w, ax.y0 + ax.h); ui.stroke();
  ui.font = `400 22px ${SANS}`; ui.fillStyle = C.dim;
  for (const v of yticks) { const y = m.y(v); if (y < ax.y0 - 2 || y > ax.y0 + ax.h + 2) continue; ui.textAlign = 'right'; ui.fillText(ylab(v), ax.x0 - 14, y + 7); ui.fillStyle = 'rgba(237,230,214,0.07)'; ui.fillRect(ax.x0, y, ax.w, 1); ui.fillStyle = C.dim; }
  for (const v of xticks) { const x = m.x(v); if (x < ax.x0 - 2 || x > ax.x0 + ax.w + 2) continue; ui.textAlign = 'center'; ui.fillText(xlab(v), x, ax.y0 + ax.h + 34); ui.fillRect(x, ax.y0 + ax.h, 1, 8); }
  if (ytitle) text(ytitle, ax.x0, ax.y0 - 22, { size: 22, color: C.dim });
  if (xtitle) text(xtitle, ax.x0 + ax.w, ax.y0 + ax.h + 70, { size: 22, color: C.dim, align: 'right' });
  ui.restore();
}
function hline(m, ax, v, color, dash = [8, 8], a = 1, label = '') {
  if (a <= 0) return; ui.save(); ui.globalAlpha = a; ui.strokeStyle = color; ui.setLineDash(dash); ui.lineWidth = 1.5; const y = m.y(v);
  ui.beginPath(); ui.moveTo(ax.x0, y); ui.lineTo(ax.x0 + ax.w, y); ui.stroke(); ui.setLineDash([]);
  if (label) text(label, ax.x0 + ax.w + 12, y + 8, { size: 22, color }); ui.restore();
}
function polyline(pts, color, width, a = 1, clip = null) {
  if (a <= 0 || pts.length < 2) return; ui.save(); if (clip) { ui.beginPath(); ui.rect(clip.x0, clip.y0 - 2, clip.w + 2, clip.h + 4); ui.clip(); }
  ui.globalAlpha = a; ui.strokeStyle = color; ui.lineWidth = width; ui.lineJoin = 'round'; if (width >= 2) { ui.shadowColor = color; ui.shadowBlur = 12; }
  ui.beginPath(); ui.moveTo(pts[0][0], pts[0][1]); for (const p of pts) ui.lineTo(p[0], p[1]); ui.stroke(); ui.restore();
}
function dot(x, y, r, color, a = 1, glow = 0) { if (a <= 0) return; ui.save(); ui.globalAlpha = a; ui.fillStyle = color; if (glow) { ui.shadowColor = color; ui.shadowBlur = glow; } ui.beginPath(); ui.arc(x, y, r, 0, 6.283); ui.fill(); ui.restore(); }
function miniCoin(x, y, r, heads, a = 1) {
  if (a <= 0) return; ui.save(); ui.globalAlpha = a;
  if (heads) { const g = ui.createRadialGradient(x - r * .3, y - r * .3, r * .1, x, y, r); g.addColorStop(0, '#F7DE9E'); g.addColorStop(1, '#A9803A'); ui.fillStyle = g; ui.beginPath(); ui.arc(x, y, r, 0, 6.283); ui.fill(); text('正', x, y + r * .36, { size: r * 1.05, font: SERIF, weight: 900, color: '#6B4E1C', align: 'center' }); }
  else { ui.strokeStyle = 'rgba(237,230,214,0.6)'; ui.lineWidth = Math.max(1.2, r * .09); ui.fillStyle = 'rgba(40,34,26,0.9)'; ui.beginPath(); ui.arc(x, y, r, 0, 6.283); ui.fill(); ui.stroke(); text('反', x, y + r * .36, { size: r * 1.05, font: SERIF, weight: 700, color: 'rgba(237,230,214,0.75)', align: 'center' }); }
  ui.restore();
}

// ---------- 3D ----------
const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('gl'), antialias: true, alpha: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1); renderer.setSize(PW, PH, false); renderer.setClearColor(0, 0);
renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.3; renderer.outputColorSpace = THREE.SRGBColorSpace;
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(28, W / H, .1, 200);
{ // warm studio environment (procedural, deterministic)
  const c = document.createElement('canvas'); c.width = 1024; c.height = 512; const g = c.getContext('2d');
  const sky = g.createLinearGradient(0, 0, 0, 512); sky.addColorStop(0, '#5a4630'); sky.addColorStop(.45, '#1c140c'); sky.addColorStop(.55, '#2a1d10'); sky.addColorStop(1, '#4a3520');
  g.fillStyle = sky; g.fillRect(0, 0, 1024, 512); g.filter = 'blur(24px)';
  g.fillStyle = '#fff4e0'; g.fillRect(330, 10, 360, 110); g.fillStyle = '#ffdca8'; g.fillRect(40, 140, 220, 200); g.fillStyle = '#ffe6bf'; g.fillRect(560, 150, 160, 170); g.fillStyle = '#b08a55'; g.fillRect(780, 170, 220, 150);
  const tex = new THREE.CanvasTexture(c); tex.mapping = THREE.EquirectangularReflectionMapping; tex.colorSpace = THREE.SRGBColorSpace;
  scene.environment = new THREE.PMREMGenerator(renderer).fromEquirectangular(tex).texture;
}
scene.add(new THREE.AmbientLight(0xfff0dd, .25));
const fillL = new THREE.PointLight(0xffe6c0, 30, 0, 2); fillL.position.set(0, 5, 8); scene.add(fillL);
const key = new THREE.DirectionalLight(0xffe2b0, 2.6); key.position.set(-3, 6, 4); scene.add(key);
const rim = new THREE.DirectionalLight(0xffc880, 1.4); rim.position.set(4, 3, -5); scene.add(rim);

function faceCanvas(ch, bump) {
  const c = document.createElement('canvas'); c.width = c.height = 1024; const g = c.getContext('2d');
  const base = bump ? '#808080' : '#D8B064';
  g.fillStyle = base; g.fillRect(0, 0, 1024, 1024);
  if (!bump) { const rg = g.createRadialGradient(400, 380, 60, 512, 512, 560); rg.addColorStop(0, '#F3D693'); rg.addColorStop(1, '#B28640'); g.fillStyle = rg; g.fillRect(0, 0, 1024, 1024); }
  g.lineWidth = 46; g.strokeStyle = bump ? '#e8e8e8' : '#E9C982'; g.beginPath(); g.arc(512, 512, 470, 0, 6.283); g.stroke();
  g.lineWidth = 8; g.strokeStyle = bump ? '#c8c8c8' : '#9C7432'; g.beginPath(); g.arc(512, 512, 400, 0, 6.283); g.stroke();
  for (let i = 0; i < 72; i++) { const a = i / 72 * 6.283; g.fillStyle = bump ? '#d0d0d0' : '#A67C36'; g.beginPath(); g.arc(512 + 432 * Math.cos(a), 512 + 432 * Math.sin(a), 7, 0, 6.283); g.fill(); }
  g.font = `900 520px ${SERIF}`; g.textAlign = 'center'; g.textBaseline = 'middle';
  g.fillStyle = bump ? '#f4f4f4' : '#8E6A2C'; g.fillText(ch, 512, 540);
  if (!bump) { g.globalAlpha = .45; g.fillStyle = '#F8E2A8'; g.fillText(ch, 504, 532); }
  const tex = new THREE.CanvasTexture(c); if (!bump) tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8; return tex;
}
function edgeCanvas() { const c = document.createElement('canvas'); c.width = 2048; c.height = 32; const g = c.getContext('2d'); for (let i = 0; i < 2048; i += 8) { g.fillStyle = '#ddd'; g.fillRect(i, 0, 4, 32); g.fillStyle = '#555'; g.fillRect(i + 4, 0, 4, 32); } return new THREE.CanvasTexture(c); }
const metal = { metalness: 1, roughness: .3, envMapIntensity: 1.6 };
const coinMats = [
  new THREE.MeshStandardMaterial({ color: 0xC9A257, bumpMap: edgeCanvas(), bumpScale: 1.2, ...metal }),
  new THREE.MeshStandardMaterial({ map: faceCanvas('正'), bumpMap: faceCanvas('正', true), bumpScale: 2.2, ...metal, color: 0xffffff }),
  new THREE.MeshStandardMaterial({ map: faceCanvas('反'), bumpMap: faceCanvas('反', true), bumpScale: 2.2, ...metal, color: 0xffffff }),
];
const coinGeo = new THREE.CylinderGeometry(1, 1, .12, 128, 1);
const coinPivot = new THREE.Group(), coinTilt = new THREE.Group(), coin = new THREE.Mesh(coinGeo, coinMats);
coinPivot.add(coinTilt); coinTilt.add(coin); scene.add(coinPivot);
// soft contact shadow
const shTex = (() => { const c = document.createElement('canvas'); c.width = c.height = 256; const g = c.getContext('2d'); const rg = g.createRadialGradient(128, 128, 10, 128, 128, 128); rg.addColorStop(0, 'rgba(0,0,0,0.85)'); rg.addColorStop(1, 'rgba(0,0,0,0)'); g.fillStyle = rg; g.fillRect(0, 0, 256, 256); return new THREE.CanvasTexture(c); })();
const shadow = new THREE.Mesh(new THREE.PlaneGeometry(3, 3), new THREE.MeshBasicMaterial({ map: shTex, transparent: true, depthWrite: false })); shadow.rotation.x = -Math.PI / 2; scene.add(shadow);
// coin field (S2)
const FX = 17, FZ = 11, fieldMats = coinMats.map(m => { const c = m.clone(); c.transparent = true; return c; });
const field = new THREE.InstancedMesh(coinGeo, fieldMats, FX * FZ); scene.add(field);
const RF = rng(2026); const fieldInfo = [];
for (let i = 0; i < FX; i++) for (let j = 0; j < FZ; j++) { const x = (i - 8) * 1.15, z = (j - 5) * 1.15; fieldInfo.push({ x, z, hero: i === 8 && j === 5, d: Math.hypot(x, z), r: RF(), res: RF() < .5 ? 1 : 0, yaw: RF() * 6.28 }); }
// die (S8)
function dieFace(n) {
  const c = document.createElement('canvas'); c.width = c.height = 512; const g = c.getContext('2d');
  const rg = g.createRadialGradient(200, 180, 40, 256, 256, 380); rg.addColorStop(0, '#FBF6EA'); rg.addColorStop(1, '#D9CFBA'); g.fillStyle = rg; g.fillRect(0, 0, 512, 512);
  const P = { 1: [[0, 0]], 2: [[-1, -1], [1, 1]], 3: [[-1, -1], [0, 0], [1, 1]], 4: [[-1, -1], [1, -1], [-1, 1], [1, 1]], 5: [[-1, -1], [1, -1], [0, 0], [-1, 1], [1, 1]], 6: [[-1, -1], [1, -1], [-1, 0], [1, 0], [-1, 1], [1, 1]] }[n];
  for (const [a, b] of P) { g.fillStyle = (n === 1 || n === 4) ? '#8E2A1F' : '#1D1A16'; g.beginPath(); g.arc(256 + a * 128, 256 + b * 128, n === 1 ? 70 : 44, 0, 6.283); g.fill(); }
  const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace; return new THREE.MeshPhysicalMaterial({ map: tex, roughness: .32, clearcoat: .6, clearcoatRoughness: .25, metalness: 0 });
}
// BoxGeometry material order: +x,-x,+y,-y,+z,-z  -> faces 3,4,1,6,2,5
const die = new THREE.Mesh(new RoundedBoxGeometry(1, 1, 1, 5, .12), [3, 4, 1, 6, 2, 5].map(dieFace)); scene.add(die);
const FACE_UP = { 1: [0, 0, 0], 6: [Math.PI, 0, 0], 3: [0, 0, Math.PI / 2], 4: [0, 0, -Math.PI / 2], 2: [-Math.PI / 2, 0, 0], 5: [Math.PI / 2, 0, 0] };

function setCamera(pos, look, offsetX = 0) { camera.position.set(...pos); camera.lookAt(...look); if (offsetX) camera.setViewOffset(W, H, offsetX, 0, W, H); else camera.clearViewOffset(); camera.updateProjectionMatrix(); }
// toss: lands at t1 with result (1 正 / 0 反); returns {y, rx, settle}
function toss(t, t0, t1, h, spins, result, prevResult = 1) {
  const T = .06;
  if (t < t0) return { y: T, rx: prevResult ? 0 : Math.PI, air: false };
  const u = (t - t0) / (t1 - t0);
  if (u <= 1) return { y: T + 4 * h * u * (1 - u), rx: (prevResult ? 0 : Math.PI) + u * (spins * 2 * Math.PI + (result === prevResult ? 0 : Math.PI)), air: true };
  const s = t - t1;
  return { y: T + .12 * h * Math.exp(-9 * s) * Math.abs(Math.sin(16 * s)), rx: result ? 0 : Math.PI, wob: .10 * Math.exp(-5 * s) * Math.sin(22 * s), air: false };
}

// ---------- scene state per time ----------
const S = Object.fromEntries(SB.scenes.map(s => [s.id, s]));
const PTS = D.pts, HL = D.highlight;
function render3D(t) {
  coin.visible = false; field.visible = false; die.visible = false; shadow.visible = false;
  let need = false; coinPivot.rotation.set(0, 0, 0); coinTilt.rotation.set(0, 0, 0); coinPivot.position.set(0, 0, 0); coin.position.set(0, 0, 0);
  // S1–S2: hero coin + field
  if (t < 18.4) {
    need = true; coin.visible = true; shadow.visible = true;
    const p = toss(t, 1.15, 4.319, 1.5, 4, 1);
    coinTilt.rotation.x = p.rx; coinTilt.rotation.z = p.wob || 0; coinPivot.position.y = p.y;
    shadow.position.set(0, .001, 0); shadow.scale.setScalar(1 + p.y * .25); shadow.material.opacity = .9 / (1 + p.y);
    coinPivot.rotation.y = .35 + t * .03;
    const pull = eio((t - 5.6) / 4.2);
    const cpos = [0, lerp(2.6, 12.5, pull), lerp(5.6, 14.5, pull)];
    const fieldA = clamp(ss(6.0, 6.6, t) * (1 - .78 * ss(10.4, 12.2, t)) * (1 - ss(15.4, 16.6, t)));
    let off = 0;
    if (t > 16.4) { // descend toward S3 placement (left of frame) on the drum hit
      const u = eio((t - 16.4) / 1.6); off = 520 * u; cpos[1] = lerp(cpos[1], 3.0, u); cpos[2] = lerp(cpos[2], 8.2, u);
    }
    setCamera(cpos, [0, t > 16.4 ? lerp(.4, .55, eio((t - 16.4) / 1.6)) : lerp(.35 + p.y * .55, .4, pull), 0], off);
    const heroA = 1 - ss(10.4, 11.8, t) + ss(15.6, 16.8, t);
    coin.visible = heroA > .02; shadow.visible = coin.visible;
    coinMats.forEach(m => { m.transparent = heroA < 1; m.opacity = clamp(heroA); });
    shadow.material.opacity *= clamp(heroA);
    if (fieldA > 0) {
      field.visible = true; fieldMats.forEach(m => m.opacity = fieldA); const M = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
      fieldInfo.forEach((f, i) => {
        const t0 = 6.75 + f.d * .07 + f.r * .25, p2 = f.hero ? { y: -50, rx: 0 } : toss(t, t0, t0 + 1.05, 1.1, 2, f.res);
        e.set(p2.rx, f.yaw, p2.wob || 0, 'YXZ'); q.setFromEuler(e); const sc = ss(5.9 + f.d * .05, 6.5 + f.d * .05, t) * .82;
        M.compose(new THREE.Vector3(f.x, p2.y - (1 - sc) * .3, f.z), q, new THREE.Vector3(sc + 1e-4, sc + 1e-4, sc + 1e-4)); field.setMatrixAt(i, M);
      });
      field.instanceMatrix.needsUpdate = true;
    }
  }
  // S3: ten tosses on the beat, coin on the left
  else if (t < 31.6) {
    need = true; coin.visible = true; shadow.visible = true; coinMats.forEach(m => { m.transparent = true; m.opacity = 1 - ss(29.9, 31.2, t); });
    let k = 0; while (k < 9 && t >= beatAt(k + 1) + .0) k++;
    const prev = k === 0 ? 1 : D.seq10[k - 1];
    const p = toss(t, beatAt(k) + .02, beatAt(k + 1) - .03, .95, 2, D.seq10[k], prev);
    coinTilt.rotation.x = p.rx; coinTilt.rotation.z = p.wob || 0; coinPivot.position.y = p.y; coinPivot.rotation.y = .35;
    shadow.position.set(0, .001, 0); shadow.scale.setScalar(1 + p.y * .3); shadow.material.opacity = .9 / (1 + p.y);
    const ex = eio((t - 29.9) / 1.4);
    setCamera([0, 3.0 + ex * .8, 8.2 + ex * 3], [0, .55, 0], 520 + ex * 200);
  }
  // S5 intro: Kerrich's coin turning slowly on the left
  else if (t > 46.6 && t < 52.2) {
    need = true; coin.visible = true; const a = win(t, 46.8, 51.9, .8, .9); coinMats.forEach(m => { m.transparent = true; m.opacity = a; });
    coinTilt.rotation.x = Math.PI / 2 - .25; coinPivot.rotation.y = (t - 46.8) * 1.9; coinPivot.position.y = 1.1 + .08 * Math.sin(t * 2);
    setCamera([0, 2.2, 10], [0, 1.0, 0], 520);
  }
  // S8: die rolls six times, two beats per roll
  else if (t > 101.0 && t < 111.4) {
    need = true; die.visible = true; shadow.visible = true; const a = win(t, 101.2, 111.0, .5, .8);
    die.material.forEach(m => { m.transparent = true; m.opacity = a; }); shadow.material.opacity = .7 * a;
    const r0 = beatAt(Math.ceil((101.6 - ANCHOR) / BEAT));
    let k = Math.floor((t - r0) / (2 * BEAT)); k = clamp(k, 0, 5);
    const t0 = r0 + k * 2 * BEAT, t1 = t0 + 2 * BEAT * .62, v = D.dice_first[k];
    const R = rng(500 + k), ax = new THREE.Vector3(R() - .5, R() - .5, R() - .5).normalize();
    const qf = new THREE.Quaternion().setFromEuler(new THREE.Euler(...FACE_UP[v])), qy = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), R() * 1.2 - .6);
    const u = clamp((t - t0) / (t1 - t0)), spin = (1 - eout(u)) * (6 + 4 * R());
    const qs = new THREE.Quaternion().setFromAxisAngle(ax, spin);
    die.quaternion.copy(qy).multiply(qs).multiply(qf);
    const hop = t < t0 ? 0 : (u < 1 ? 1.6 * Math.sin(Math.PI * Math.min(1, u * 1.25)) * (1 - u) + .05 * Math.abs(Math.sin(u * 9)) : 0);
    die.position.set(lerp(-1.4, 0, eout(u)) * (t < t0 ? 0 : 1), .5 + Math.max(0, hop), 0);
    shadow.position.set(die.position.x, .001, 0); shadow.scale.setScalar(.75 + hop * .2);
    setCamera([0, 4.2, 8.6], [0, .4, 0], 560);
  }
  // S10: coin returns, tossed, then spins on its edge until the end
  else if (t > 119.0) {
    need = true; coin.visible = true; shadow.visible = true; const a = ss(119.2, 119.9, t); coinMats.forEach(m => { m.transparent = a < 1; m.opacity = a; });
    if (t < 121.7) { const p = toss(t, 119.75, 121.62, 2.0, 3, 1); coinTilt.rotation.x = p.rx; coinPivot.position.y = p.y; coinPivot.rotation.y = .35; }
    else { // edge spin: upright, slow precession, no result shown
      const s = t - 121.62; coinTilt.rotation.x = Math.PI / 2 - .10 * Math.sin(s * 1.3); coinTilt.rotation.z = .06 * Math.sin(s * 2.1);
      coinPivot.rotation.y = .35 + s * 7.5; coinPivot.position.y = .98 + .03 * Math.sin(s * 3); }
    shadow.position.set(0, .001, 0); shadow.scale.setScalar(1.1); shadow.material.opacity = .7 * a;
    const push = eio((t - 121.6) / 4), back = eio((t - 125.0) / 1.8);
    setCamera([0, lerp(lerp(3.2, 2.4, push), 2.6, back), lerp(lerp(8.6, 7.4, push), 11.5, back)], [0, lerp(.6, 1.0, push), 0], 0);
    if (back > 0) { camera.setViewOffset(W, H, 0, -120 * back, W, H); camera.updateProjectionMatrix(); }
  }
  if (need) renderer.render(scene, camera); else renderer.clear();
}

// ---------- 2D scenes ----------
function S3chart(t) { // ten tosses -> axes morph into the log funnel
  const a = ss(17.7, 18.5, t) * (1 - ss(46.9, 47.6, t) * 0);
  if (t < 17.6 || t > 61) return;
  const A3 = { x0: 820, y0: 230, w: 940, h: 470, xmin: 0, xmax: 10.5, lxmin: 1, lxmax: 10000, log: 0, ymin: 0, ymax: 1 };
  const A4 = { x0: 300, y0: 200, w: 1420, h: 580, xmin: 0, xmax: 10.5, lxmin: 1, lxmax: 10000, log: 1, ymin: 0, ymax: 1 };
  const A4z = { ...A4, ymin: .4, ymax: .6 };
  const A5 = { ...A4z, x0: 1000, w: 720, y0: 230, h: 520 };
  let ax = mixAxis(A3, A4, eio((t - 29.9) / 1.6));
  if (t > 42.4 && params.get('draft') !== '1') ax = mixAxis(A4, A4z, eio((t - 42.5) / 1.3));
  if (t > 46.8) ax = mixAxis(A4z, A5, eio((t - 46.9) / 1.4));
  const fade = 1 - ss(59.6, 60.4, t);
  const m = mapper(ax);
  const isLog = ax.log > .5, ylab = v => fmt(v);
  const yt = ax.ymax - ax.ymin > .5 ? [0, .25, .5, .75, 1] : [.4, .45, .5, .55, .6];
  drawAxes(ax, m, a * fade, { yticks: yt, ylab, xticks: isLog ? [1, 10, 100, 1000, 10000] : [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], xlab: v => v.toLocaleString('en-US'), ytitle: '正面所占比例', xtitle: isLog ? '抛掷次数（对数刻度）' : '抛掷次数' });
  hline(m, ax, .5, C.gold, [6, 8], a * fade * .8, '50%');
  const clip = ax;
  // revealed n for the funnel
  const knots = [[30.6, 0], [34.0, 1], [38.4, 3], [42.4, 4]];
  let ln = 0; for (let i = 0; i < knots.length - 1; i++) if (t >= knots[i][0]) ln = lerp(knots[i][1], knots[i + 1][1], clamp((t - knots[i][0]) / (knots[i + 1][0] - knots[i][0])));
  const nmax = Math.pow(10, ln);
  // 95% band
  const bandA = ss(36.0, 37.6, t) * fade * (1 - ss(46.9, 47.8, t) * .6);
  if (bandA > 0) { for (const sgn of [-1, 1]) { const pts = []; for (let n = 1; n <= 10000; n *= 1.06) pts.push([m.x(n), m.y(.5 + sgn * 1.96 * .5 / Math.sqrt(n))]); ui.save(); ui.setLineDash([5, 7]); polyline(pts, C.bright, 1.4, bandA * .8, clip); ui.restore(); }
    text('虚线：≈95% 区间（正态近似）', ax.x0 + ax.w, ax.y0 - 22, { size: 22, color: C.bright, align: 'right', alpha: bandA * (1 - ss(46.6, 47.2, t)), halo: 1 }); }
  // 60 paths
  const pathsA = ss(30.4, 31.2, t) * fade;
  if (pathsA > 0) {
    D.paths.forEach((p, i) => { if (i === HL) return; const pts = []; for (let j = 0; j < PTS.length && PTS[j] <= nmax; j++) pts.push([m.x(PTS[j]), m.y(p[j])]); ui.save(); ui.globalCompositeOperation = 'lighter'; polyline(pts, '#C79A4E', 1.4, pathsA * (t > 46.9 ? .2 : .34), clip); ui.restore(); });
  }
  // highlighted path (the coin we just tossed)
  const hp = D.paths[HL]; const hpts = [];
  if (t < 30.4) { for (let k = 0; k < 10; k++) { if (t < beatAt(k + 1) - .03) break; hpts.push([m.x(k + 1), m.y(D.p10[k])]); } }
  else for (let j = 0; j < PTS.length && PTS[j] <= Math.max(10, nmax); j++) hpts.push([m.x(PTS[j]), m.y(hp[j])]);
  polyline(hpts, C.ivory, 2.6, a * fade, clip);
  if (t < 31) hpts.forEach(p => dot(p[0], p[1], 6, C.ivory, a * (1 - ss(30.2, 30.9, t)), 10));
  if (hpts.length && t < 46.9) { const p = hpts[hpts.length - 1]; if (p[1] >= ax.y0 - 1 && p[1] <= ax.y0 + ax.h + 1) dot(p[0], p[1], 7, C.bright, a * fade, 16); }
  // S3 readout
  if (t < 30.6) {
    let k = -1; for (let i = 0; i < 10; i++) if (t >= beatAt(i + 1) - .03) k = i;
    if (k >= 0) { const ra = a * (1 - ss(29.9, 30.4, t)); text(`第 ${k + 1} 次`, 1760, 200, { size: 26, color: C.dim, align: 'right', alpha: ra }); text(fmt(D.p10[k]), 1760, 160, { size: 56, font: SERIF, weight: 700, color: C.bright, align: 'right', alpha: ra }); }
    // tally chips
    for (let i = 0; i < 10; i++) { const ti = beatAt(i + 1) - .03; const ca = ss(ti, ti + .15, t) * a * (1 - ss(29.9, 30.5, t)); miniCoin(m.x(i + 1), 840, 24, D.seq10[i] === 1, ca); }
  }
  // range brackets at n = 10, 1000, 10000
  const br = [[10, 34.3, 38.3], [1000, 38.6, 42.4], [10000, 42.7, 46.7]];
  for (const [n, b0, b1] of br) {
    const ba = win(t, b0, b1 + (n === 10000 ? 0 : 0), .4, .4) * fade; if (ba <= 0) continue;
    const [lo, hi] = D.ranges[String(n)]; const x = m.x(n), y0 = m.y(hi), y1 = m.y(lo);
    ui.save(); ui.globalAlpha = ba; ui.strokeStyle = C.bright; ui.lineWidth = 2; ui.beginPath(); ui.moveTo(x - 10, y0); ui.lineTo(x, y0); ui.lineTo(x, y1); ui.lineTo(x - 10, y1); ui.stroke(); ui.restore();
    const right = n === 10000, ly = right ? ax.y0 + ax.h - 22 : y0 - 18;
    text(`第 ${n.toLocaleString('en-US')} 次：${fmt(lo, n >= 1000 ? 1 : 0)} – ${fmt(hi, n >= 1000 ? 1 : 0)}`, right ? x - 6 : x + 10, ly, { size: 26, weight: 600, color: C.bright, align: right ? 'right' : 'left', alpha: ba, halo: 1 });
  }
  // Kerrich point
  const ka = ss(55.3, 56.0, t) * fade;
  if (ka > 0) { const x = m.x(10000), y = m.y(.5067); dot(x, y, 9, '#FFE7A8', ka, 24); ui.save(); ui.globalAlpha = ka * .7; ui.strokeStyle = '#FFE7A8'; ui.lineWidth = 1.2; ui.beginPath(); ui.moveTo(x, y - 12); ui.lineTo(x, ax.y0 + 44); ui.stroke(); ui.restore();
    text('克里奇 1946 · 50.67%', x, ax.y0 + 30, { size: 26, weight: 600, color: '#FFE7A8', align: 'right', alpha: ka, halo: 1 }); }
}
// S5: 10,000 dots -> 5,067 / 4,933
const RD = rng(1946); const order = Array.from({ length: 10000 }, (_, i) => i); for (let i = 9999; i > 0; i--) { const j = Math.floor(RD() * (i + 1)); [order[i], order[j]] = [order[j], order[i]]; }
const isHead = new Uint8Array(10000); for (let i = 0; i < 5067; i++) isHead[order[i]] = 1;
function S5dots(t) {
  if (t < 50.8 || t > 60.6) return; const a = ss(51.0, 51.4, t) * (1 - ss(59.6, 60.4, t));
  const grow = clamp((t - 51.1) / 3.6), shown = Math.floor(10000 * eio(grow)), split = eio((t - 55.2) / 1.6);
  ui.save(); ui.globalAlpha = a; let hc = 0, tc = 0;
  for (let i = 0; i < 10000; i++) {
    if (i >= shown) break;
    const gx = 170 + (i % 100) * 6.6, gy = 240 + Math.floor(i / 100) * 5.2;
    let bx, by; if (isHead[i]) { bx = 260 + (hc % 40) * 6; by = 760 - Math.floor(hc / 40) * 4.0; hc++; } else { bx = 560 + (tc % 40) * 6; by = 760 - Math.floor(tc / 40) * 4.0; tc++; }
    const x = lerp(gx, bx, split), y = lerp(gy, by, split);
    ui.fillStyle = split > .5 ? (isHead[i] ? C.bright : 'rgba(237,230,214,0.55)') : 'rgba(242,211,140,0.85)'; ui.fillRect(x, y, 2.6, 2.6);
  }
  ui.restore();
  text(`${shown.toLocaleString('en-US')} 次`, 500, 214, { size: 34, font: SERIF, weight: 700, color: C.bright, align: 'center', alpha: a * (1 - split) });
  const la = a * ss(56.3, 56.9, t);
  text('正面 5,067', 380, 806, { size: 30, weight: 600, color: C.bright, align: 'center', alpha: la });
  text('反面 4,933', 680, 806, { size: 30, weight: 600, color: C.ivory, align: 'center', alpha: la * .8 });
}
// S6: exact counting
function S6count(t) {
  if (t < 59.6 || t > 79) return;
  const a = ss(59.9, 60.5, t);
  // phase A: 16 sequences of four tosses stacked by number of heads
  const seqs = []; for (let s = 0; s < 16; s++) { const b = [3, 2, 1, 0].map(k => (s >> k) & 1); seqs.push(b); }
  const byK = [[], [], [], [], []]; seqs.forEach(b => byK[b.reduce((x, y) => x + y, 0)].push(b));
  const aA = a * (1 - ss(67.4, 68.2, t));
  if (aA > 0) {
    let idx = 0;
    for (let k = 0; k <= 4; k++) {
      const cx = 480 + k * 240;
      byK[k].forEach((b, r) => { const ti = 60.3 + idx * .19; idx++; const u = eout((t - ti) / .45); if (u <= 0) return; const y = 770 - r * 62 - (1 - u) * 40;
        b.forEach((h, j) => miniCoin(cx - 72 + j * 48, y, 21, h === 1, aA * u * ((k === 2 || t < 63.9) ? 1 : 1 - .55 * ss(63.9, 64.5, t)))); });
      text(`${k} 次正面`, cx, 836, { size: 26, color: C.dim, align: 'center', alpha: aA * ss(60.4, 61, t) });
      text(String(byK[k].length) + ' 种', cx, 880, { size: 30, font: SERIF, weight: 700, color: k === 2 ? C.bright : C.ivory, align: 'center', alpha: aA * ss(63.0, 63.6, t) });
    }
    text('抛 4 次 · 全部 16 种可能', 960, 250, { size: 34, font: SERIF, weight: 700, color: C.ivory, align: 'center', alpha: aA * ss(60.2, 60.8, t) });
    const ha = aA * ss(63.9, 64.5, t);
    if (ha > 0) { ui.save(); ui.globalAlpha = ha; ui.strokeStyle = C.bright; ui.lineWidth = 2; ui.strokeRect(960 - 110, 770 - 5 * 62 - 34, 220, 6 * 62 + 8); ui.restore();
      text('6 / 16 = 37.5%', 1090, 450, { size: 40, font: SERIF, weight: 700, color: C.bright, alpha: ha }); }
  }
  // phase B: fixed proportion axis, histograms narrowing as n grows
  const aB = ss(67.6, 68.3, t) * (1 - ss(77.6, 78.6, t) * 0);
  if (aB <= 0) return;
  const ax = { x0: 300, y0: 290, w: 1320, h: 500 };
  const stages = [[4, 67.6], [10, 68.0], [100, 71.5], [1000, 72.9]];
  let si = 0; for (let i = 0; i < stages.length; i++) if (t >= stages[i][1]) si = i;
  const n = stages[si][0], u = eio((t - stages[si][1]) / .8);
  const collapse = eio((t - 77.6) / 1.0); // bars squeeze into the 50% line for S7
  const bandA = aB * (1 - collapse);
  ui.save(); ui.globalAlpha = bandA; ui.fillStyle = 'rgba(217,180,106,0.10)'; ui.fillRect(ax.x0 + ax.w * .4, ax.y0 - 10, ax.w * .2, ax.h + 10); ui.restore();
  text('40%–60%', ax.x0 + ax.w * .5, ax.y0 - 22, { size: 22, color: C.gold, align: 'center', alpha: bandA });
  ui.save(); ui.globalAlpha = bandA; ui.strokeStyle = 'rgba(237,230,214,0.35)'; ui.lineWidth = 1.5; ui.beginPath(); ui.moveTo(ax.x0, ax.y0 + ax.h); ui.lineTo(ax.x0 + ax.w, ax.y0 + ax.h); ui.stroke(); ui.restore();
  for (const v of [0, .25, .5, .75, 1]) text(fmt(v), ax.x0 + ax.w * v, ax.y0 + ax.h + 36, { size: 22, color: C.dim, align: 'center', alpha: bandA });
  text('正面所占比例', ax.x0 + ax.w, ax.y0 + ax.h + 72, { size: 22, color: C.dim, align: 'right', alpha: bandA });
  text('柱高按本组最高柱归一（只比较形状）', ax.x0, ax.y0 + ax.h + 72, { size: 20, color: C.faint, alpha: bandA });
  function bars(nn, alpha, wmul) {
    const pm = D.pmf[String(nn)], mx = Math.max(...pm), bw = Math.max(1.2, ax.w / (nn + 1) * .78 * wmul);
    ui.save(); ui.globalAlpha = alpha;
    for (let k = 0; k <= nn; k++) { const p = k / nn, x = ax.x0 + ax.w * lerp(p, .5, collapse), h = pm[k] / mx * ax.h; if (h < .3) continue; const inB = p >= .4 - 1e-9 && p <= .6 + 1e-9; ui.fillStyle = inB ? 'rgba(242,211,140,0.92)' : 'rgba(237,230,214,0.42)'; ui.fillRect(x - bw / 2, ax.y0 + ax.h - h, bw, h); }
    ui.restore();
  }
  if (si > 0 && u < 1) bars(stages[si - 1][0], aB * (1 - u), 1);
  bars(n, aB * (si === 0 ? ss(67.6, 68.2, t) : u), 1);
  const share = { 4: '37.5%', 10: D.facts.share10, 100: D.facts.share100, 1000: '>' + D.facts.share1000_gt }[n];
  const ra = aB * (1 - collapse);
  text(`抛 ${n.toLocaleString('en-US')} 次`, 1620, 210, { size: 28, color: C.dim, align: 'right', alpha: ra });
  text(`落在带内：${share}`, 1620, 258, { size: 40, font: SERIF, weight: 700, color: C.bright, align: 'right', alpha: ra });
}
// S7: the same path — gap grows, proportion settles
function S7two(t) {
  if (t < 77.9 || t > 94.4) return; const a = ss(78.1, 78.9, t) * (1 - ss(93.5, 94.1, t));
  const top = { x0: 300, y0: 190, w: 1380, h: 270, xmin: 0, xmax: 1, lxmin: 1, lxmax: 10000, log: 1, ymin: -250, ymax: 250 };
  const bot = { ...top, y0: 560, h: 270, ymin: .3, ymax: .7 };
  const mt = mapper(top), mb = mapper(bot);
  drawAxes(top, mt, a, { yticks: [-200, -100, 0, 100, 200], ylab: v => (v > 0 ? '+' : '') + v, xticks: [1, 10, 100, 1000, 10000], xlab: v => v.toLocaleString('en-US'), ytitle: '差额：正面 − 反面（次）' });
  drawAxes(bot, mb, a, { yticks: [.3, .4, .5, .6, .7], ylab: v => fmt(v), xticks: [1, 10, 100, 1000, 10000], xlab: v => v.toLocaleString('en-US'), ytitle: '正面所占比例', xtitle: '抛掷次数（对数刻度）' });
  hline(mt, top, 0, C.gold, [6, 8], a * .7, '0'); hline(mb, bot, .5, C.gold, [6, 8], a * .7, '50%');
  const ln = 4 * eio((t - 78.4) / 5.2), nmax = Math.pow(10, ln);
  const pt = [], pb = []; for (let j = 0; j < PTS.length && PTS[j] <= nmax; j++) { pt.push([mt.x(PTS[j]), mt.y(D.hl_diff[j])]); pb.push([mb.x(PTS[j]), mb.y(D.paths[HL][j])]); }
  polyline(pt, C.ivory, 2.4, a, top); polyline(pb, C.ivory, 2.4, a, bot);
  // markers at n = 100 and n = 10,000
  const ma = a * ss(81.9, 82.5, t);
  if (ma > 0) {
    const j100 = PTS.indexOf(100), jE = PTS.length - 1;
    for (const [j, n] of [[j100, 100], [jE, 10000]]) {
      const x = mt.x(n); ui.save(); ui.globalAlpha = ma * .5; ui.fillStyle = C.gold; ui.fillRect(x, top.y0, 1, bot.y0 + bot.h - top.y0); ui.restore();
      dot(x, mt.y(D.hl_diff[j]), 7, C.bright, ma, 14); dot(x, mb.y(D.paths[HL][j]), 7, C.bright, ma, 14);
      const al = n === 100 ? 'left' : 'right', dx = n === 100 ? 16 : -16;
      text(`${D.hl_diff[j]}`, x + dx, mt.y(D.hl_diff[j]) + 38, { size: 30, font: SERIF, weight: 700, color: C.bright, align: al, alpha: ma, halo: 1 });
      text(n === 100 ? D.facts.hl_prop100 : D.facts.hl_prop, x + dx, mb.y(D.paths[HL][j]) - 28, { size: 30, font: SERIF, weight: 700, color: C.bright, align: al, alpha: ma * ss(85.8, 86.4, t), halo: 1 });
    }
  }
  // 1/sqrt(n) envelope
  const ea = a * ss(89.6, 90.4, t);
  if (ea > 0) { for (const s of [-1, 1]) { const p = []; for (let n = 1; n <= 10000; n *= 1.05) p.push([mb.x(n), mb.y(.5 + s * .5 / Math.sqrt(n))]); ui.save(); ui.setLineDash([5, 7]); polyline(p, C.bright, 1.6, ea, bot); ui.restore(); }
    text('虚线 50% ± 50%/√n：n = 100 → ±5%，n = 10,000 → ±0.5%', bot.x0 + bot.w, bot.y0 - 22, { size: 24, weight: 600, color: C.bright, align: 'right', alpha: ea, halo: 1 }); }
}
// S8a: history cards
function S8hist(t) {
  if (t < 93.6 || t > 101.9) return; const a = ss(93.8, 94.5, t) * (1 - ss(101.2, 101.8, t));
  const roll = eio((t - 97.6) / .9), year = Math.round(lerp(1713, 1837, roll));
  ui.save(); ui.globalAlpha = a;
  text(String(year), 960, 430, { size: 170, font: SERIF, weight: 900, color: C.bright, align: 'center', spacing: 6 });
  ui.restore();
  const fa = a * (1 - ss(97.4, 97.9, t));
  text('P( |频率 − p| > ε )  →  0', 960, 590, { size: 54, font: SERIF, color: C.ivory, align: 'center', alpha: fa });
  text('次数 n → ∞ 时，对任意小的 ε 都成立', 960, 650, { size: 26, color: C.dim, align: 'center', alpha: fa });
  const fb = a * ss(98.1, 98.8, t);
  text('“大数定律”', 960, 590, { size: 64, font: SERIF, weight: 700, color: C.ivory, align: 'center', alpha: fb });
  text('la loi des grands nombres', 960, 650, { size: 28, font: SERIF, color: C.gold, align: 'center', alpha: fb, spacing: 3 });
}
// S8b + S9: dice mean, then Cauchy counter-example on the same frame
function S8dice(t) {
  if (t < 101.4 || t > 120) return;
  const r0 = beatAt(Math.ceil((101.6 - ANCHOR) / BEAT));
  const land = k => r0 + k * 2 * BEAT + 2 * BEAT * .62;
  const A8 = { x0: 860, y0: 230, w: 900, h: 470, xmin: 0, xmax: 1, lxmin: 1, lxmax: 3000, log: 1, ymin: 1, ymax: 6 };
  const A9 = { ...A8, x0: 300, w: 1420, y0: 230, h: 520, lxmax: 10000 };
  const mv = Math.ceil(Math.max(...D.cauchy_mean.map(Math.abs))) + 1;
  const toC = eio((t - 110.6) / 1.2);
  const fade = ss(101.6, 102.2, t) * (1 - ss(119.1, 119.8, t));
  const dA = fade * (1 - toC);
  if (dA > 0) {
    const ax = mixAxis(A8, A9, toC), m = mapper(ax);
    drawAxes(ax, m, dA, { yticks: [1, 2, 3, 4, 5, 6], ylab: v => String(v), xticks: [1, 10, 100, 1000, 3000], xlab: v => v.toLocaleString('en-US'), ytitle: '平均点数', xtitle: '掷骰次数（对数刻度）' });
    hline(m, ax, 3.5, C.gold, [6, 8], dA * .8, '3.5');
    let nmax = 0; for (let k = 0; k < 6; k++) if (t >= land(k)) nmax = k + 1;
    if (t > 107.9) nmax = Math.max(6, Math.pow(10, lerp(Math.log10(6), Math.log10(3000), eio((t - 107.9) / 2.3))));
    const pts = []; for (let j = 0; j < D.dice_pts.length && D.dice_pts[j] <= nmax; j++) pts.push([m.x(D.dice_pts[j]), m.y(D.dice_mean[j])]);
    polyline(pts, C.ivory, 2.6, dA, ax); if (pts.length) { const p = pts[pts.length - 1]; dot(p[0], p[1], 7, C.bright, dA, 16); }
    if (nmax >= 1) { const j = Math.min(D.dice_pts.length - 1, D.dice_pts.findLastIndex(v => v <= nmax)); text(`第 ${Math.round(D.dice_pts[j]).toLocaleString('en-US')} 次 · 平均 ${D.dice_mean[j].toFixed(3)}`, ax.x0 + ax.w, ax.y0 - 22, { size: 28, weight: 600, color: C.bright, align: 'right', alpha: dA }); }
    // rolled values row under the die
    text('前 6 次点数', 440, 800, { size: 22, color: C.dim, align: 'center', alpha: dA * ss(land(0), land(0) + .3, t) * (1 - ss(108.5, 109.2, t)) });
    for (let k = 0; k < 6; k++) { const ca = ss(land(k), land(k) + .2, t) * dA * (1 - ss(108.5, 109.2, t)); text(String(D.dice_first[k]), 280 + k * 64, 850, { size: 40, font: SERIF, weight: 700, color: C.bright, align: 'center', alpha: ca }); }
  }
  const cA = fade * toC;
  if (cA > 0) {
    const ax = { ...A9, ymin: -mv, ymax: mv }, m = mapper(ax);
    drawAxes(ax, m, cA, { yticks: [-mv + 1, -Math.round(mv / 2), 0, Math.round(mv / 2), mv - 1], ylab: v => String(v), xticks: [1, 10, 100, 1000, 10000], xlab: v => v.toLocaleString('en-US'), ytitle: '样本平均（标准柯西分布）', xtitle: '抽样次数（对数刻度）' });
    hline(m, ax, 0, C.gold, [6, 8], cA * .6, '中心 0');
    const nmax = Math.pow(10, 4 * eio((t - 111.4) / 6.0)); const pts = [];
    for (let j = 0; j < D.cauchy_pts.length && D.cauchy_pts[j] <= nmax; j++) pts.push([m.x(D.cauchy_pts[j]), m.y(D.cauchy_mean[j])]);
    polyline(pts, C.red, 2.6, cA, ax); if (pts.length) { const p = pts[pts.length - 1]; dot(p[0], p[1], 7, '#E06A4E', cA, 16); }
    text('反例：均值不收敛', ax.x0 + ax.w, ax.y0 - 22, { size: 28, weight: 600, color: '#E06A4E', align: 'right', alpha: cA });
  }
}

// ---------- frame ----------
window.renderFrame = async (t) => {
  const draftTime = t, isDraft = params.get('draft') === '1';
  // Draft mode deliberately reuses authored scenes: 0–5s opening, 5–15s core experiment, 15–20s conclusion.
  if (params.get('draft') === '1') {
    if (t < 5) t = lerp(0, 8.45, t / 5);
    else if (t < 15) t = lerp(30.5, 46.6, (t - 5) / 10);
    else t = lerp(123.5, 128.6, (t - 15) / 5);
  }
  drawBackground(t, 1 - .4 * ss(77.5, 79, t) + .4 * ss(93.4, 94, t));
  render3D(t);
  ui.clearRect(0, 0, W, H);
  // S1/S2 title
  const ta = ss(10.9, 12.4, t) * (1 - ss(17.05, 17.75, t));
  drawTitle(t, ta, lerp(500, 380, eio((t - 17.05) / .7)), lerp(.97, 1, ss(10.9, 14, t)));
  S3chart(t); S5dots(t); S6count(t); S7two(t); S8hist(t); S8dice(t);
  // end title + sources
  const ea = ss(125.6, 127.0, t);
  if (ea > 0) { drawTitle(t, ea, 300, .8);
    SB.sources.forEach((s, i) => text(s, 960, 938 + i * 30, { size: 19, color: 'rgba(237,230,214,0.5)', align: 'center', alpha: ss(127.0, 127.8, t) })); }
  drawMeta(t);
  if (!isDraft) drawCaptions(t);
  else {
    const lines = [[0.5,4.7,'抛一次，看运气；重复一万次呢？'],[5.4,8.6,'60 人各抛 10,000 次：比例逐渐收窄'],[8.8,11.8,'第 1,000 次：44.6%–54.6%'],[12,14.7,'第 10,000 次：48.8%–51.2%'],[15.4,19.4,'单次仍随机，整体比例趋近 50%']];
    for (const [a,b,line] of lines) text(line,960,990,{size:44,weight:600,align:'center',alpha:win(draftTime,a,b,.18,.18)});
  }
  drawGrain(t);
  if (isDraft) {
    const f = Math.max(1-clamp(Math.abs(draftTime-5)/.25),1-clamp(Math.abs(draftTime-15)/.25));
    if(f>0){ui.fillStyle=`rgba(0,0,0,${f})`;ui.fillRect(0,0,W,H);}
  }
  const black = ss(129.0, 130.0, t); if (black > 0) { ui.fillStyle = `rgba(0,0,0,${black})`; ui.fillRect(0, 0, W, H); }
  return true;
};
const COMP = new OffscreenCanvas(PW, PH), cc = COMP.getContext('2d');
window.grabFrame = async (t, q = 0.93) => {   // composite bg + 3D + UI and return a JPEG data URL (no page screenshot)
  await window.renderFrame(t);
  cc.drawImage(document.getElementById('bg'), 0, 0); cc.drawImage(document.getElementById('gl'), 0, 0); cc.drawImage(document.getElementById('ui'), 0, 0);
  const blob = await COMP.convertToBlob({ type: q >= 1 ? 'image/png' : 'image/jpeg', quality: q });
  return await new Promise(r => { const fr = new FileReader(); fr.onload = () => r(fr.result); fr.readAsDataURL(blob); });
};
window.captionReport = () => CAPS.map(c => ({ t0: c.t0, text: c.segs.map(s => s.s).join(''), width: Math.round(captionWidth(c)) }));
window.filmReady = true;
