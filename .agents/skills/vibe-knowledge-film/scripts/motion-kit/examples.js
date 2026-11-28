/* examples.js — two migrations of the same motion idea, both pure functions of t.
 *  coin : coin -> dot -> curve head   (one object id "sample" carried across three meanings)
 *  brake: foot -> pedal -> master cylinder -> pipe -> caliper -> wheel (one causal chain "force")
 * Each scene returns {duration, pauses, handoffs, state(t), movers(t,W,H), draw(ctx,t,W,H)}.
 * World units are a 1920x1080 board; the camera track frames it. Pressure timing in "brake" is a
 * schematic pacing choice, NOT the physical propagation speed of brake fluid pressure.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory(require('./motion.js'));
  else root.MotionExamples = factory(root.Motion);
})(typeof self !== 'undefined' ? self : this, function (M) {
  'use strict';
  const { track, relay, action, stagger, polyline, camera, project, integrate, smooth, clamp, lerp } = M;
  const GOLD = '#D9B46A', IVORY = '#EDE6D6', DIM = 'rgba(237,230,214,0.45)', BG = '#07060a';

  /* ------------------------------ coin -> dot -> curve ------------------------------ */
  function coinScene() {
    // seeded flips -> running frequency of heads (data, not decoration)
    let s = 11; const flips = Array.from({ length: 200 }, () => ((s = (s * 1103515245 + 12345) & 0x7fffffff) % 2));
    const freq = []; let h = 0; flips.forEach((f, i) => { h += f; freq.push(h / (i + 1)); });
    const AX = { x0: 980, y0: 300, w: 760, h: 440 };                           // chart in world units
    const chart = (n, f) => [AX.x0 + AX.w * Math.log(n) / Math.log(200), AX.y0 + AX.h * (1 - f)];
    const nAt = t => Math.exp(Math.log(200) * smooth(3.0, 7.0, t) ** 1.15);   // 1 -> 200 samples
    const freqAt = n => { const i = Math.floor(n) - 1, k = n - Math.floor(n); return i >= 199 ? freq[199] : lerp(freq[i], freq[i + 1], k); };
    const head = t => chart(nAt(t), freqAt(nAt(t)));
    const SLOT = [700, 660], TOSS = 300;                                         // toss height (world px)
    // prepare (thumb dip) -> toss (parabola) -> contact on the slot -> carried on as the curve head
    const prep = track([{ t: 0, v: [700, 720], d: 0 }, { t: 0.45, v: [700, 732], d: 0 }, { t: 0.6, v: [702, 700], d: [(SLOT[0] - 702) / 1.2, (SLOT[1] - 700 - 4 * TOSS) / 1.2] }]);
    const toss = t => { const u = (t - 0.6) / 1.2; return [lerp(702, SLOT[0], u), lerp(700, SLOT[1], u) - TOSS * 4 * u * (1 - u)]; };
    const land = track([{ t: 1.8, v: SLOT, d: [0, 260] }, { t: 2.05, v: [SLOT[0], SLOT[1] + 10], d: [0, 0] }, { t: 2.35, v: SLOT, d: [140, -60] }]);
    const sample = relay([{ fn: prep, from: 0, to: 0.6 }, { fn: toss, from: 0.6, to: 1.8 }, { fn: land, from: 1.8, to: 2.35 }, { fn: head, from: 3.1, to: 8 }]);
    const radius = track([{ t: 0, v: 64, d: 0 }, { t: 2.0, v: 64, d: 0 }, { t: 2.9, v: 9 }, { t: 3.4, v: 8, d: 0 }]);
    const spinT = track([{ t: 0.6, v: 0, d: 9 * Math.PI }, { t: 1.8, v: 8 * Math.PI, d: 0 }]);   // lands face-up
    const spin = t => (t < 0.6 ? 0 : t > 1.8 ? 8 * Math.PI : spinT(t)[0]);
    // camera follows the toss up, then pulls back to reveal the chart while the dot is already travelling
    const cam = camera([{ t: 0, v: [760, 640, 1.7], d: 0 }, { t: 1.2, v: [720, 480, 1.35] }, { t: 2.4, v: [900, 600, 1.1] },
      { t: 3.8, v: [1200, 540, 0.98] }, { t: 7.0, v: [1300, 520, 1.08], d: 0 }, { t: 8, v: [1300, 520, 1.08], d: 0 }]);
    const state = t => ({ sample: sample(t), r: radius(t)[0], spin: spin(t), cam: cam(t), n: nAt(t) });
    const movers = (t, W, H) => { const c = cam(t); return [project(c, sample(t), W, H), project(c, [AX.x0, AX.y0 + AX.h], W, H)]; };
    function draw(ctx, t, W, H) {
      const c = cam(t), P = p => project(c, p, W, H), z = c[2];
      ctx.fillStyle = BG; ctx.fillRect(0, 0, W, H);
      // slot row (world-anchored, so the camera move reads as one space)
      for (let i = 0; i < 5; i++) { const q = P([SLOT[0] + i * 60, SLOT[1]]); ctx.strokeStyle = 'rgba(217,180,106,0.25)'; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(q[0], q[1], 12 * z, 0, 6.283); ctx.stroke(); }
      // axes appear BEFORE the dot arrives and then stay fixed (stable, readable)
      const axA = smooth(2.2, 2.9, t); if (axA > 0) {
        ctx.globalAlpha = axA; ctx.strokeStyle = DIM; ctx.lineWidth = 1.5; const o = P([AX.x0, AX.y0 + AX.h]), xe = P([AX.x0 + AX.w, AX.y0 + AX.h]), ye = P([AX.x0, AX.y0]);
        ctx.beginPath(); ctx.moveTo(ye[0], ye[1]); ctx.lineTo(o[0], o[1]); ctx.lineTo(xe[0], xe[1]); ctx.stroke();
        const half = P([AX.x0, AX.y0 + AX.h / 2]), halfE = P([AX.x0 + AX.w, AX.y0 + AX.h / 2]); ctx.setLineDash([6, 6]); ctx.beginPath(); ctx.moveTo(half[0], half[1]); ctx.lineTo(halfE[0], halfE[1]); ctx.stroke(); ctx.setLineDash([]);
        ctx.fillStyle = DIM; ctx.font = `${14 * z}px sans-serif`; ['1', '10', '100'].forEach((lab, i) => { const q = P(chart([1, 10, 100][i], 0)); ctx.fillText(lab, q[0] - 4, q[1] + 22 * z); });
        ctx.globalAlpha = stagger(t, 2.5, 1) * axA; ctx.fillText('50%', half[0] - 44 * z, half[1] + 5); ctx.globalAlpha = 1;
      }
      // curve = trail of the same sample object
      const n = nAt(t); if (t > 3.1 && n > 1.01) { ctx.strokeStyle = GOLD; ctx.lineWidth = 2.2; ctx.beginPath();
        for (let k = 1; k <= n; k += Math.max(0.25, k / 40)) { const q = P(chart(k, freqAt(k))); k === 1 ? ctx.moveTo(q[0], q[1]) : ctx.lineTo(q[0], q[1]); }
        const q = P(head(t)); ctx.lineTo(q[0], q[1]); ctx.stroke(); }
      // the sample itself: coin (edge-on flip) -> dot -> curve head
      const p = P(sample(t)), r = state(t).r * z, flip = Math.abs(Math.cos(spin(t)));
      ctx.fillStyle = GOLD; ctx.beginPath(); ctx.ellipse(p[0], p[1], r, Math.max(r * 0.12, r * flip), 0, 0, 6.283); ctx.fill();
      // labels trail the subject; a reading pause is declared at the end
      ctx.fillStyle = IVORY; ctx.font = `600 ${18 * z}px sans-serif`;
      ctx.globalAlpha = stagger(t, 1.95, 0) * (1 - smooth(2.9, 3.3, t)); const lp = P([SLOT[0], SLOT[1] - 50]); ctx.fillText('HEADS', lp[0] - 30 * z, lp[1]);
      ctx.globalAlpha = stagger(t, 6.4, 0); const tp = P([AX.x0 + AX.w - 220, AX.y0 - 30]); ctx.fillText('FREQUENCY → 50%', tp[0], tp[1]); ctx.globalAlpha = 1;
      ctx.fillStyle = DIM; ctx.font = '13px sans-serif'; ctx.fillText(`coin → dot → curve  t=${t.toFixed(2)}s  n=${Math.floor(n)}`, 16, H - 16);
    }
    return { name: 'coin', duration: 8, pauses: [[7.0, 8.0]], contacts: [1.8], handoffs: [[0.6, 0.6], [1.8, 1.8], [2.35, 3.1]], track: sample, camera: cam, state, movers, draw };
  }

  /* --------------------- foot -> pedal -> master cylinder -> wheel --------------------- */
  function brakeScene() {
    const PIV = [380, 560], ARM = 220;                         // pedal pivot and arm length (world)
    const ang = action({ start: 0.0, prep: 0.45, contact: 0.8, settle: 1.6, rest: 0, hit: 0.32, back: 0.03, over: 0.15 });
    const pad = t => { const a = ang(t)[0]; return [PIV[0] + Math.sin(a) * ARM, PIV[1] + Math.cos(a) * ARM]; };
    const foot = track([{ t: 0, v: [220, 820], d: 0 }, { t: 0.45, v: [300, 790] }, { t: 0.8, v: pad(0.8), d: [260, -30] }]);
    const footAt = t => (t <= 0.8 ? foot(t) : [pad(t)[0] - 2, pad(t)[1] + 2]);  // after contact the foot rides the pad
    const MC = [640, 560];
    const rod = t => { const a = ang(t)[0]; return [MC[0] - 90 + Math.sin(a) * 260, MC[1]]; };   // kinematic coupling: cause -> effect
    const PIPE = [[MC[0] + 80, MC[1]], [1000, 560], [1000, 380], [1380, 380]], pipe = polyline(PIPE);
    const WHEEL = [1520, 380], WR = 120, A = 0.32;
    // the force token's route, in the pressed pose: pad -> rod attachment -> piston -> pipe -> caliper
    const route = polyline([[PIV[0] + Math.sin(A) * ARM, PIV[1] + Math.cos(A) * ARM], [PIV[0] + Math.sin(A) * 90, PIV[1] + Math.cos(A) * 90],
      [MC[0] - 90 + Math.sin(A) * 260, MC[1]], ...PIPE, [WHEEL[0] - WR - 6, WHEEL[1]]]);
    const pipeStart = route.total - pipe.total - Math.hypot(WHEEL[0] - WR - 6 - PIPE[3][0], 0);
    // schematic pacing (NOT the physical propagation speed of brake pressure): slow while force builds
    // at the pedal, quicker along the pipe, contact at the caliper at 2.4 s
    const routeU = track([{ t: 0.8, v: 0, d: 0.25 }, { t: 1.3, v: pipeStart / route.total }, { t: 2.4, v: 1, d: 0 }]);
    const tokenU = t => (t < 0.8 ? 0 : t > 2.4 ? 1 : clamp(routeU(t)[0]));
    const token = t => route.at(tokenU(t)).p;
    const frontAt = t => clamp((tokenU(t) * route.total - pipeStart) / pipe.total);
    const clampAmt = action({ start: 2.1, prep: 2.25, contact: 2.4, settle: 3.0, rest: 0, hit: 1, back: 0.06, over: 0.1 });
    const omegaRate = t => { const k = clamp(clampAmt(t)[0]); const decel = smooth(2.4, 6.2, t); return 9 * (1 - decel) * (1 - 0.15 * k * (1 - decel)); };
    const wheelAng = t => integrate(omegaRate, 0, t, 400);
    // one focus point carried along the causal chain; the camera chases it with matched velocity
    const focus = relay([{ fn: footAt, from: 0, to: 0.8 }, { fn: token, from: 0.8, to: 2.4 }, { fn: () => [WHEEL[0] - WR - 6, WHEEL[1]], from: 2.4, to: 8 }]);
    const cam = camera([{ t: 0, v: [380, 640, 1.6], d: 0 }, { t: 1.2, v: [620, 580, 1.4] }, { t: 2.3, v: [1150, 430, 1.25] },
      { t: 3.4, v: [1420, 400, 1.35] }, { t: 5.2, v: [960, 520, 0.92] }, { t: 6.4, v: [960, 520, 0.92], d: 0 }, { t: 8, v: [960, 520, 0.92], d: 0 }]);
    const state = t => ({ ang: ang(t)[0], foot: footAt(t), rod: rod(t), front: frontAt(t), clamp: clampAmt(t)[0], wheel: wheelAng(t), cam: cam(t), focus: focus(t), token: token(t) });
    const movers = (t, W, H) => { const c = cam(t), wa = wheelAng(t); return [project(c, pad(t), W, H), project(c, pipe.at(frontAt(t)).p, W, H),
      project(c, [WHEEL[0] + Math.cos(wa) * WR, WHEEL[1] + Math.sin(wa) * WR], W, H), project(c, [0, 0], W, H)]; };
    function draw(ctx, t, W, H) {
      const c = cam(t), P = p => project(c, p, W, H), z = c[2], S = state(t);
      ctx.fillStyle = BG; ctx.fillRect(0, 0, W, H);
      const ln = (a, b, col, w) => { const p = P(a), q = P(b); ctx.strokeStyle = col; ctx.lineWidth = w * z; ctx.beginPath(); ctx.moveTo(p[0], p[1]); ctx.lineTo(q[0], q[1]); ctx.stroke(); };
      // pedal + foot
      ln(PIV, pad(t), IVORY, 6); const fp = P(S.foot); ctx.fillStyle = 'rgba(237,230,214,0.6)'; ctx.beginPath(); ctx.ellipse(fp[0] - 30 * z, fp[1] + 10 * z, 46 * z, 18 * z, -0.4, 0, 6.283); ctx.fill();
      // push rod and master cylinder
      ln([PIV[0] + Math.sin(S.ang) * 90, PIV[1] + Math.cos(S.ang) * 90], S.rod, GOLD, 3);
      const mc0 = P([MC[0] - 60, MC[1] - 34]); ctx.strokeStyle = IVORY; ctx.lineWidth = 2 * z; ctx.strokeRect(mc0[0], mc0[1], 140 * z, 68 * z);
      const pist = P([S.rod[0], MC[1] - 30]); ctx.fillStyle = GOLD; ctx.fillRect(pist[0], pist[1], 10 * z, 60 * z);
      // pipe: dim route, gold where the (schematic) pressure front has reached
      ctx.strokeStyle = 'rgba(217,180,106,0.22)'; ctx.lineWidth = 4 * z; ctx.beginPath(); pipe.pts.forEach((q, i) => { const p = P(q); i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]); }); ctx.stroke();
      if (S.front > 0) { ctx.strokeStyle = GOLD; ctx.beginPath(); let started = false; for (let u = 0; u <= S.front + 1e-9; u += 0.01) { const p = P(pipe.at(Math.min(u, S.front)).p); started ? ctx.lineTo(p[0], p[1]) : (ctx.moveTo(p[0], p[1]), started = true); } ctx.stroke(); }
      const tk = P(token(t)); if (t > 0.8 && t < 2.6) { ctx.fillStyle = '#F2D38C'; ctx.beginPath(); ctx.arc(tk[0], tk[1], 7 * z, 0, 6.283); ctx.fill(); }
      // wheel (rotates by integrated angular speed) + caliper clamping
      const wc = P(WHEEL); ctx.strokeStyle = IVORY; ctx.lineWidth = 2 * z; ctx.beginPath(); ctx.arc(wc[0], wc[1], WR * z, 0, 6.283); ctx.stroke();
      for (let k = 0; k < 6; k++) { const a = S.wheel + k * Math.PI / 3; ln(WHEEL, [WHEEL[0] + Math.cos(a) * WR * 0.9, WHEEL[1] + Math.sin(a) * WR * 0.9], 'rgba(237,230,214,0.55)', 1.5); }
      const gap = 26 - 18 * clamp(S.clamp, 0, 1.2); ctx.fillStyle = GOLD; [-1, 1].forEach(sg => { const q = P([WHEEL[0] - WR - 6 + sg * 0, WHEEL[1] + sg * (gap + 14)]); ctx.fillRect(q[0] - 10 * z, q[1] - 10 * z, 20 * z, 20 * z); });
      // labels trail the cause by a beat, never lead it
      ctx.fillStyle = IVORY; ctx.font = `600 ${17 * z}px sans-serif`;
      const lab = (s, p, t0) => { ctx.globalAlpha = stagger(t, t0, 0); const q = P(p); ctx.fillText(s, q[0], q[1]); ctx.globalAlpha = 1; };
      lab('PEDAL', [PIV[0] - 40, PIV[1] - 30], 0.9); lab('MASTER CYLINDER', [MC[0] - 60, MC[1] - 50], 1.25); lab('PRESSURE', [1020, 360], 1.9); lab('CLAMP', [WHEEL[0] - WR - 40, WHEEL[1] + 90], 2.6);
      ctx.fillStyle = DIM; ctx.font = '13px sans-serif'; ctx.fillText(`foot → pedal → master cylinder → wheel  ·  pressure timing is schematic  t=${t.toFixed(2)}s`, 16, H - 16);
    }
    return { name: 'brake', duration: 8, pauses: [[6.4, 8.0]], contacts: [0.8, 2.4], handoffs: [[0.8, 0.8], [1.3, 1.3], [2.4, 2.4]], track: focus, camera: cam, state, movers, draw };
  }

  return { coin: coinScene(), brake: brakeScene(), naiveBrakeCamera: () => camera([
    // anti-pattern for the checker: every leg eases in from zero and stops again
    { t: 0, v: [380, 640, 1.6], d: 0 }, { t: 1.2, v: [620, 580, 1.4], d: 0 }, { t: 2.3, v: [1150, 430, 1.25], d: 0 }, { t: 3.4, v: [1420, 400, 1.35], d: 0 }, { t: 5.2, v: [960, 520, 0.92], d: 0 }]) };
});
