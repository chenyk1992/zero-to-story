# Motion and Camera Reference

Use this when writing the storyboard (STEP 4–5) and when reviewing transitions (STEP 5–6). It turns "make it flow" into decisions that code can execute and checks can test. The goal is a knowledge short that reads as one continuous demonstration; it is not a mandate to morph every cut or to use 3D.

## 1. Shot card (one per shot, in the storyboard)

| Field | What to write |
|---|---|
| New information | The one thing the viewer learns here. A shot with no new information is cut or merged. |
| Visual focus | The object the eye must be on, and where it sits on screen at start and end. |
| Framing | Close / medium / wide relative to the focus object (e.g. close on the coin, wide on the chart). |
| Camera start → end, purpose | World-space center and zoom at both ends, and why it moves: follow, reveal, compare, settle for reading. "No move" is valid when stated. |
| Subject action | What the main object does, written as prepare → contact → response → settle (§2). |
| Hand-off object | The object id that carries into the next shot, and how (§4). Or "motivated hard cut" with the reason. |
| Labels | Which labels appear, when, relative to the action (§3). |
| Reading pause | Whether the shot ends on a deliberate hold, and how long. |

## 2. Action causality

Every visible effect needs a visible cause just before it.

- **Prepare:** a small anticipation (wind-up, dip, foot approaching).
- **Contact:** the moment of cause; velocity is non-zero here (an impact, a push).
- **Response:** the effect, with slight overshoot or follow-through.
- **Settle:** the system comes to its new state, then something else carries the motion forward.

Derive effects from causes in code (rod displacement from pedal angle, wheel angle from integrated angular speed) instead of animating them independently. A pedal that finishes in two seconds while the rest of the scene is only labels fading in is a stalled film: the response must continue somewhere on screen (pressure moving, caliper closing, wheel slowing, camera following).

## 3. Staggering and readability

- Offset subject, camera and labels: the subject moves first, the camera follows within a beat, labels arrive after the cause they describe (about 0.1–0.4 s). Labels never announce an effect before it is visible.
- Allow reading pauses on purpose: hold a finished chart or a conclusion long enough to read it (roughly 1–1.5 s for a short label set). Declare these holds; they are not stalls.
- Charts keep stable axes: build axes before data arrives, do not rescale or move them while the viewer reads, and keep tick labels legible at the target size.

## 4. Continuity across shots

- **Shared object ids and anchors.** Give the carried object one id for the whole sequence (e.g. `sample`, `force`). Record its world position, scale, direction and speed at every shot boundary; the next shot starts from those values.
- **World vs camera.** Objects live in world coordinates; the camera is a separate track (center, zoom). An "overall pan and zoom" is a camera move, not every object being re-positioned. Keep these separate so object continuity and framing can be checked independently.
- **Hand-off preference order:**
  1. Semantic relay — the same object changes meaning (coin → result dot → head of a frequency curve).
  2. Path continuation — the motion continues along the next structure (pedal force → push rod → piston → pipe → caliper).
  3. Occlusion reveal — a foreground object passes and uncovers the next layer.
  4. Match cut — similar shape/position across a cut.
  5. Motivated hard cut — allowed for emphasis, a new chapter, or a contrast; state the reason.
- **Avoid:** every segment easing in from zero and easing out to a stop; whole-frame fade-out/fade-in used as a transition; promising continuity in the plan and then cross-fading slides.

## 5. Two worked migrations (see `scripts/motion-kit/`)

**Coin → dot → curve.** The coin is tossed (prepare: thumb dip; contact: lands on a result slot), shrinks into a result dot while already drifting toward the chart, and becomes the head of the running-frequency curve whose trail is the curve. The camera follows the toss up, then pulls back to reveal the axes before the dot arrives. Axes are built early and stay fixed; "FREQUENCY → 50%" appears only after the curve has visibly converged, followed by a declared reading hold.

**Foot → pedal → master cylinder → wheel.** The foot approaches and contacts the pedal; pedal angle drives the push rod and piston kinematically; one force token travels pad → rod → piston → pipe → caliper; the caliper clamps (contact), and the wheel's integrated angular speed slows (response) while the camera chases the token and then widens to show the whole system. The pressure front's timing is a **schematic pacing choice, not the physical propagation speed** of brake pressure; say so in the film or report if a viewer could misread it.

## 6. Helper and checks

`scripts/motion-kit/motion.js` (no dependencies, Node and browser):
- `track(keys)` keyed path with velocities; omitted interior velocities keep motion flowing through keys; `d: 0` marks an intended stop.
- `relay(parts)` carries one object across paths; gaps are bridged with matched position and velocity.
- `action(spec)` prepare → contact → response → settle; `stagger()` label offsets; `polyline()` arc-length routes; `camera()` / `project()` world-to-screen; `integrate()` deterministic accumulation (e.g. wheel angle).
- `checks`: `continuity` (position/velocity jumps at boundaries; velocity may change only at declared contacts), `handoffDip` (stop-and-restart inside a hand-off), `seekDeterminism` (shuffled and repeated seeks give identical state), `stalls` (nothing on screen moving beyond declared pauses).

Run `node scripts/motion-kit/check.js` for the examples; it also includes an anti-pattern control that the checker must flag. Open `scripts/motion-kit/preview.html?scene=coin` or `?scene=brake` to watch at target fps (`&t=` freezes a frame).

Limits: these checks are numeric evidence about state, not proof that the film looks smooth. Judge determinism on `state(t)`; Chromium may anti-alias the first dashed or blurred stroke on a page slightly differently, so treat thin sub-pixel differences as tolerance and record them, rather than masking them with long warm-up renders. Reset all canvas state each frame (alpha, dash, font, transform).

## 7. Review protocol (proportionate)

1. Identify the risky windows first (hand-offs, camera reversals, 3D ↔ 2D swaps), usually 2–4 s each.
2. Watch them continuously at the target fps (a short clip or the preview), not only as stills. Stills and numeric tests cannot support a claim of visual smoothness.
3. Must fix locally: an obvious jump in position/scale/direction, a stop-then-restart where continuity was promised, residual shadows or stale 3D, or a planned continuous hand-off that became a slide-style fade. Fix only the affected interval, re-check it, then render the full film.
4. Not acceptable fixes: lengthening the film, adding more text, changing fps, or forcing a fixed shot count.
5. Minor nits that do not break continuity or reading (a slightly early label, a soft fade on a secondary element) are recorded, not iterated.

## 8. Sound

Keep the specified BGM as the bed. Add sparse, low-level effects only where something physically happens: contact, release, reveal. Do not add a whoosh to every camera move or transition.
