/* motion.js — tiny absolute-time motion/camera helper for code-drawn films.
 * Every function is pure: value = f(t). No wall clock, no accumulated state, so any frame
 * can be rendered alone and in any order. Positions live in WORLD coordinates; the camera is a
 * separate track and `project` maps world -> screen. Works in Node (require) and the browser
 * (window.Motion). Dependency-free.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.Motion = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const lerp = (a, b, u) => a + (b - a) * u;
  const arr = v => (Array.isArray(v) ? v.slice() : [v]);
  const smooth = (a, b, t) => { const u = clamp((t - a) / (b - a)); return u * u * (3 - 2 * u); };

  // Cubic Hermite from (p0, velocity m0) at t0 to (p1, m1) at t1. Velocities are units/second,
  // so two pieces that share a key share position AND velocity (C1 continuity).
  function hermite(t, t0, t1, p0, p1, m0, m1) {
    const h = t1 - t0, u = (t - t0) / h, u2 = u * u, u3 = u2 * u;
    const a = 2 * u3 - 3 * u2 + 1, b = u3 - 2 * u2 + u, c = -2 * u3 + 3 * u2, d = u3 - u2;
    const da = (6 * u2 - 6 * u) / h, db = 3 * u2 - 4 * u + 1, dc = (-6 * u2 + 6 * u) / h, dd = 3 * u2 - 2 * u;
    return {
      p: p0.map((_, i) => a * p0[i] + b * h * m0[i] + c * p1[i] + d * h * m1[i]),
      v: p0.map((_, i) => da * p0[i] + db * m0[i] + dc * p1[i] + dd * m1[i]),
    };
  }

  // Numeric velocity for any f(t) -> number[] (used when a path has no analytic .vel).
  function velOf(fn, eps = 1e-4) {
    if (fn.vel) return fn.vel;
    return t => { const a = arr(fn(t - eps)), b = arr(fn(t + eps)); return a.map((x, i) => (b[i] - x) / (2 * eps)); };
  }

  /* track(keys): keyed path. keys = [{t, v, d?}], v number or array, d = velocity at the key.
   * Omitted interior d -> Catmull-Rom estimate, so the path keeps moving THROUGH the key.
   * Omitted end d -> 0. Write d: 0 only where you really want a stop (a deliberate reading pause).
   * Before the first / after the last key the value continues linearly with the end velocity. */
  function track(keys) {
    const K = keys.map(k => ({ t: k.t, v: arr(k.v), d: k.d === undefined ? null : arr(k.d) })).sort((a, b) => a.t - b.t);
    const n = K.length, dim = K[0].v.length;
    K.forEach((k, i) => {
      if (k.d) { if (k.d.length === 1 && dim > 1) k.d = Array(dim).fill(k.d[0]); return; }
      if (i === 0 || i === n - 1) { k.d = Array(dim).fill(0); return; }
      const A = K[i - 1], B = K[i + 1];
      k.d = k.v.map((_, j) => (B.v[j] - A.v[j]) / (B.t - A.t));
    });
    function seg(t) {
      if (n === 1) return { p: K[0].v.slice(), v: Array(dim).fill(0) };
      if (t <= K[0].t) return { p: K[0].v.map((x, j) => x + K[0].d[j] * (t - K[0].t)), v: K[0].d.slice() };
      if (t >= K[n - 1].t) return { p: K[n - 1].v.map((x, j) => x + K[n - 1].d[j] * (t - K[n - 1].t)), v: K[n - 1].d.slice() };
      let i = 0; while (i < n - 2 && t >= K[i + 1].t) i++;
      return hermite(t, K[i].t, K[i + 1].t, K[i].v, K[i + 1].v, K[i].d, K[i + 1].d);
    }
    const f = t => seg(t).p; f.vel = t => seg(t).v; f.keys = K; return f;
  }

  /* relay(parts): one object handed from path to path. parts = [{fn, from, to}] in time order.
   * Inside a part the object follows fn; in any gap between parts.to and next.from a Hermite
   * bridge matches position AND velocity on both sides, so the hand-off never stops and restarts.
   * Use the same relay (same object id) across shots instead of fading one object out and another in. */
  function relay(parts) {
    const P = parts.map(p => ({ ...p, vel: velOf(p.fn) }));
    function at(t) {
      if (t <= P[0].to || P.length === 1) { const p = P[0]; return { p: arr(p.fn(t)), v: arr(p.vel(t)) }; }
      for (let i = 1; i < P.length; i++) {
        const a = P[i - 1], b = P[i];
        if (t < b.from) return hermite(t, a.to, b.from, arr(a.fn(a.to)), arr(b.fn(b.from)), arr(a.vel(a.to)), arr(b.vel(b.from)));
        if (t <= b.to || i === P.length - 1) return { p: arr(b.fn(t)), v: arr(b.vel(t)) };
      }
    }
    const f = t => at(t).p; f.vel = t => at(t).v; f.boundaries = P.flatMap(p => [p.from, p.to]); return f;
  }

  /* action(spec): prepare -> contact -> response -> settle as one keyed track.
   * spec = {start, contact, settle, rest, hit, back = small anticipation, over = overshoot ratio,
   *         prep = time of the wind-up extreme}. Velocity at contact is non-zero (an impact). */
  function action(s) {
    const back = s.back ?? 0.08 * (s.hit - s.rest), over = s.over ?? 0.12, prep = s.prep ?? lerp(s.start, s.contact, 0.45);
    const peak = lerp(s.contact, s.settle, 0.38);
    // impact speed, capped so the response overshoots by about `over` instead of flying past it
    const vHit = Math.min(1.6 * (s.hit - (s.rest - back)) / (s.contact - prep), 2.5 * over * (s.hit - s.rest) / (peak - s.contact));
    return track([
      { t: s.start, v: s.rest, d: 0 },
      { t: prep, v: s.rest - back, d: 0 },
      { t: s.contact, v: s.hit, d: vHit },
      { t: peak, v: s.hit + over * (s.hit - s.rest), d: 0 },
      { t: s.settle, v: s.hit, d: 0 },
    ]);
  }

  // Staggered reveal for labels: item i starts gap*i after t0 and takes dur. Labels trail the subject.
  const stagger = (t, t0, i, gap = 0.12, dur = 0.35) => smooth(t0 + i * gap, t0 + i * gap + dur, t);

  // Arc-length walker along a polyline: point at fraction u in [0,1] (+ heading), for pipes, axes, routes.
  function polyline(pts) {
    const L = [0]; for (let i = 1; i < pts.length; i++) L.push(L[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
    const total = L[L.length - 1];
    const at = u => { const s = clamp(u) * total; let i = 1; while (i < L.length - 1 && L[i] < s) i++;
      const k = (s - L[i - 1]) / ((L[i] - L[i - 1]) || 1), a = pts[i - 1], b = pts[i];
      return { p: [lerp(a[0], b[0], k), lerp(a[1], b[1], k)], ang: Math.atan2(b[1] - a[1], b[0] - a[0]), s }; };
    return { at, total, pts };
  }

  // Camera = track of [cx, cy, zoom] in world units. project() maps a world point to the screen.
  const camera = keys => track(keys);
  const project = (cam, p, W, H) => [(p[0] - cam[0]) * cam[2] + W / 2, (p[1] - cam[1]) * cam[2] + H / 2];

  // Fixed-step Simpson integral of a pure rate function: deterministic for random seeks.
  function integrate(rate, t0, t, steps = 256) {
    if (t <= t0) return 0; const h = (t - t0) / steps; let s = rate(t0) + rate(t);
    for (let i = 1; i < steps; i++) s += (i % 2 ? 4 : 2) * rate(t0 + i * h);
    return (s * h) / 3;
  }

  /* ---------------- checks (numeric evidence, NOT visual proof) ---------------- */
  // Position/velocity jumps across boundary times.
  function continuity(fn, times, eps = 2e-4) {
    return times.map(b => {
      const g = t => arr(fn(t));
      const pL = g(b - eps), pR = g(b + eps);
      const vL = g(b - eps).map((x, i) => (x - g(b - 3 * eps)[i]) / (2 * eps));
      const vR = g(b + 3 * eps).map((x, i) => (x - g(b + eps)[i]) / (2 * eps));
      const posJump = Math.hypot(...pL.map((x, i) => (x + vL[i] * eps) - (pR[i] - vR[i] * eps)));
      const velJump = Math.hypot(...vL.map((x, i) => x - vR[i]));
      return { t: b, posJump, velJump, speed: Math.hypot(...vR) };
    });
  }
  // Within a hand-off window the object should keep moving: flags a dip to near zero
  // (the "ease-out to a stop, then ease-in again" PPT pattern).
  function handoffDip(fn, a, b, n = 48) {
    const v = velOf(fn), sp = t => Math.hypot(...arr(v(t)));
    let min = Infinity; for (let i = 0; i <= n; i++) min = Math.min(min, sp(lerp(a, b, i / n)));
    const ref = Math.min(sp(a), sp(b));
    return { a, b, minSpeed: min, endSpeed: ref, dip: ref > 1e-6 && min < 0.2 * ref };
  }
  // Same states in shuffled order and repeated = no hidden accumulated state.
  function seekDeterminism(stateFn, times, seed = 7) {
    const key = t => JSON.stringify(stateFn(t), (k, x) => (typeof x === 'number' ? Math.round(x * 1e6) / 1e6 : x));
    const seq = times.map(key);
    const idx = times.map((_, i) => i); let s = seed;
    for (let i = idx.length - 1; i > 0; i--) { s = (s * 1103515245 + 12345) & 0x7fffffff; const j = s % (i + 1); [idx[i], idx[j]] = [idx[j], idx[i]]; }
    const shuffled = Array(times.length); idx.forEach(i => { shuffled[i] = key(times[i]); });
    const again = times.map(key);
    return { equal: seq.every((x, i) => x === shuffled[i] && x === again[i]), samples: times.length };
  }
  // Frames where nothing on screen moves (all movers + camera) for longer than maxStill seconds,
  // outside declared reading pauses. moversFn(t) -> [[x,y], ...] in SCREEN pixels.
  function stalls(moversFn, { t0, t1, fps = 24, minSpeed = 6, maxStill = 0.75, pauses = [] }) {
    const out = []; let start = null; const dt = 1 / fps;
    const speed = t => { const a = moversFn(t), b = moversFn(t + dt); return Math.max(...a.map((p, i) => Math.hypot(b[i][0] - p[0], b[i][1] - p[1]) / dt)); };
    const inPause = (a, b) => pauses.some(([p, q]) => a >= p - dt - 1e-9 && b <= q + dt + 1e-9);
    for (let f = Math.round(t0 * fps); f <= Math.round(t1 * fps); f++) {
      const t = f / fps, still = speed(t) < minSpeed;
      if (still && start === null) start = t;
      if ((!still || f === Math.round(t1 * fps)) && start !== null) { const end = t; if (end - start > maxStill && !inPause(start, end)) out.push([+start.toFixed(3), +end.toFixed(3)]); start = null; }
    }
    return out;
  }

  return { clamp, lerp, smooth, hermite, velOf, track, relay, action, stagger, polyline, camera, project, integrate,
    checks: { continuity, handoffDip, seekDeterminism, stalls } };
});
