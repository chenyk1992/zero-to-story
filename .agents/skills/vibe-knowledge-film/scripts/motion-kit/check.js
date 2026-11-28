#!/usr/bin/env node
/* check.js — numeric motion checks for the examples (or your own scene with the same shape).
 *   node check.js            run both examples + the anti-pattern control
 * Passing means: no position/velocity jump at hand-offs, no stop-and-restart dip inside a hand-off,
 * identical states under shuffled/random seeks, and no undeclared still spans.
 * It does NOT prove the film looks smooth — watch the risky 2–4 s windows at target fps for that. */
const M = require('./motion.js'), E = require('./examples.js');
const { continuity, handoffDip, seekDeterminism, stalls } = M.checks;
const W = 1280, H = 720, FPS = 24;
let fail = 0; const ok = (c, msg) => { console.log((c ? 'PASS ' : 'FAIL ') + msg); if (!c) fail++; };
const velTol = r => Math.max(4, 0.08 * r.speed);   // finite-difference residual allowance

for (const s of [E.coin, E.brake]) {
  console.log(`\n# ${s.name}`);
  const bounds = [...new Set(s.handoffs.flat())];
  const cj = continuity(s.track, bounds);
  const contact = r => (s.contacts || []).some(c => Math.abs(c - r.t) < 1e-9);
  ok(cj.every(r => r.posJump < 0.5 && (contact(r) || r.velJump < velTol(r))), `carried object continuous at ${bounds.join(', ')} s (velocity may change only at declared contacts ${JSON.stringify(s.contacts || [])})  ` +
    cj.map(r => `[dp ${r.posJump.toFixed(3)} dv ${r.velJump.toFixed(1)} v ${r.speed.toFixed(0)}]`).join(' '));
  const camKeys = s.camera.keys.map(k => k.t).filter(t => t > 0 && t < s.duration);
  const cc = continuity(s.camera, camKeys);
  ok(cc.every(r => r.posJump < 0.5 && r.velJump < velTol(r)), `camera continuous through keys ${camKeys.join(', ')} s`);
  const dips = s.handoffs.filter(([a, b]) => b > a).map(([a, b]) => handoffDip(s.track, a, b));
  ok(dips.every(d => !d.dip), `no stop-and-restart inside hand-offs  ` + dips.map(d => `[${d.a}-${d.b}: min ${d.minSpeed.toFixed(0)} / ends ${d.endSpeed.toFixed(0)}]`).join(' '));
  const times = Array.from({ length: s.duration * FPS }, (_, f) => f / FPS);
  ok(seekDeterminism(s.state, times).equal, `shuffled + repeated seeks give identical state (${times.length} frames)`);
  const st = stalls(t => s.movers(t, W, H), { t0: 0, t1: s.duration - 1 / FPS, fps: FPS, pauses: s.pauses });
  ok(st.length === 0, `no undeclared still span > 0.75 s (declared reading pauses: ${JSON.stringify(s.pauses)})` + (st.length ? ' found ' + JSON.stringify(st) : ''));
}

console.log('\n# control: every camera leg eases in from zero and stops (should be flagged)');
const naive = E.naiveBrakeCamera();
const nd = [[1.0, 1.4], [2.1, 2.5], [3.2, 3.6]].map(([a, b]) => handoffDip(naive, a, b));
ok(nd.every(d => d.dip), 'checker flags the stop-and-restart camera  ' + nd.map(d => `[min ${d.minSpeed.toFixed(1)} / ends ${d.endSpeed.toFixed(0)}]`).join(' '));

console.log(fail ? `\n${fail} check(s) failed` : '\nall numeric checks passed (visual smoothness still needs a continuous look at target fps)');
process.exit(fail ? 1 : 0);
