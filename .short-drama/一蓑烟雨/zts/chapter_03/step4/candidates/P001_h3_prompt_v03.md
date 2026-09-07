# P001 H3 Prompt Review — v03

## Input / reference mapping

- Panel: P001｜无名池开题。
- Revision: v03; `step4/speaker_registry.md` is authoritative for the episode-global voice binding, with Wang Fang fixed as `S1`; D001 therefore uses `<Subject 2> (S1)` below.
- Approved operation: `R2V / video.reference_to_video`; this is a new chapter and new location, so no reference image is an exact first-frame lock.
- Duration: 10.0 seconds; vertical 9:16 output; two actual Camera Setups only: C001 at 00:00.000–00:04.000 and C002 at 00:04.000–00:10.000.
- Output profile: approved 0.4 MP generation size; this execution setting is unchanged.
- Beat ownership: all six P001 beats are effective new beats. C001 establishes the pond, pavilion, fish, seating, and the positions of Wang Fang and Su Shi; C002 raises Wang Fang's hand, delivers D001 once, and ends with only the other writers beginning to write while the right-front older literatus remains fully framed with his fan visible and is about to look toward Su Shi.
- Boundary: new-scene hard cut from the previous chapter; P001 has no inherited tail-frame input. Its final B006 state will later be converted into a real tail frame for P002, but that future frame is not an input here.
- Approved spoken line: D001, spoken by Wang Fang once and verbatim: `此池无名已久。今日请诸位为它赐个名字——取得好者，老夫奉为上宾。`
- Visual anchors: Northern Song realistic live-action film texture, restrained performance, clear blue-green pond water with visible fish, old timber waterside pavilion, gray stone railing, gravel bank, soft afternoon light through thin cloud, natural depth of field, subtle film grain. No visible generated text is required in this Panel.
- Reference order used by the final prompt:
  1. `<Picture 1>` — `E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\codex_director\chapter_01\assets\characters\char_su_shi_1056.png` — approved Su Shi identity/costume reference.
  2. `<Picture 2>` — `E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\characters\char_wang_fang_1056.png` — approved Wang Fang identity/costume reference.
  3. `<Picture 3>` — `E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P001.png` — approved 2×3 black-and-white storyboard planning reference for [Shot 1] and [Shot 2], not a rendered-frame or style reference.
- Path and asset checks: all three files exist. Su Shi card is 1024×1536; Wang Fang card is 1536×1024; board_P001 is 1672×941. The board was visually inspected as six equal cells in two rows and three columns, with the requested pond/pavilion group, centered Wang Fang, left-edge Su Shi, fish movement, hand-raise, rule announcement, and writing start.
- No scene keyframe, video reference, or audio reference is supplied. The final prompt below is the only text intended for later prompt transmission; the review metadata above is not part of that prompt.

## v03 change note

This is the single-point repair after the v02 semantic continuity failure. The approved story beats, reference order, R2V operation, 10.0-second duration, D001 wording, speaker binding, and two Camera Setups are unchanged. The C001/C002 composition is made slightly wider and steadier on the right-front seat: Qian Weng must remain visible from chest through his right hand inside the vertical frame, holding exactly one folding fan; only the other writers may take brushes or touch paper. The final second explicitly preserves the fan, keeps Qian Weng's mouth closed, and limits him to a slight head turn and side-eye toward Su Shi. v01 and v02 remain immutable candidates.

## Final H3 prompt — copy only the content inside this block

```text
subject_definitions:
<Subject 1> is 19-year-old adult Su Shi in <Picture 1>, a slim upright Northern Song scholar with a broad forehead, straight nose, warm bright eyes, a clean-shaven face, black hair in a topknot beneath a pale simple scholar cap, and a moon-white cross-collar robe with light-gray edging. His identity, age, costume, and restrained posture are referenced by <Picture 1>.
<Subject 2> is approximately 50-year-old Northern Song local literatus Wang Fang in <Picture 2>, with a square face, neatly trimmed short beard, tied hair under a plain dark cloth cap, a deep indigo-gray cross-collar robe, and a brown sash. His identity, age, costume, open scholarly bearing, and measured authority are referenced by <Picture 2>.
<Picture 3> is the approved six-cell black-and-white storyboard planning reference for [Shot 1] and [Shot 2], defining the pond-side composition, subject placement, fish movement, shot order, and the transition from establishing space to Wang Fang's rule announcement. It is not an exact first frame, not a last-frame lock, and not the final rendering medium.

summary:
[reference generation] The target video is a 10-second, 9:16 live-action Northern Song historical sequence set beside the clear pond and waterside pavilion at Qing Shen Zhongyan. <Subject 2> opens a restrained literati naming gathering while <Subject 1> remains at the far-left edge quietly watching the fish. The two-setup progression uses <Picture 3> for composition and beat order and preserves the identities from <Picture 1> and <Picture 2>; Wang Fang speaks the complete approved Chinese line once, and the sequence ends as the writers begin to take up their brushes.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - Su Shi's near-adult identity, clean-shaven face, pale scholar cap, moon-white robe, left-edge seating position, side-facing posture, and quiet gaze toward the pond are retained.
<Subject 2> (appears in [Shot 1], [Shot 2]): fully_preserved - Wang Fang's mature local-literatus identity, square face, short beard, dark indigo-gray robe, brown sash, central hosting position, and measured authority are retained.
<Picture 3> (storyboard planning for [Shot 1] and [Shot 2]): partially_preserved - its six ordered visible moments, pond/pavilion geography, central-versus-edge placement, fish movement, hand-raise, and writing-start state are transferred into two continuous camera setups, while the target is newly rendered as realistic live action in vertical 9:16 rather than as a black-and-white board.

detailed_description:
The target video uses restrained, realistic Northern Song live-action film language in a vertical 9:16 composition: natural mature anatomy, real cotton and linen, weathered timber, gray stone, clear blue-green water, soft afternoon light through thin cloud, shallow natural depth of field, and subtle film grain. Recompose the approved wide storyboard beats into the vertical frame; do not show storyboard borders, six panels, or black-and-white line art in the target video. Keep all writing surfaces blank or too shallow to read, with no generated Chinese characters, pseudo-writing, subtitles, watermarks, or UI.
[Shot 1] From a slightly elevated camera position on the far side of the pond, a wide establishing view looks across the clear water toward an old timber waterside pavilion, low gray stone railing, and gravel bank. Begin with the pond, pavilion, and a few visible fish; let the fish glide slowly from screen right to screen left beneath the surface as the view settles on the literati gathering along the shore. <Subject 1> sits at the far-left end of the gathering, his body turned toward the pond and his gaze lowered to the fish, while <Subject 2> stands centered behind the pavilion-side table facing the seated writers. The self-satisfied older literatus at the right foreground is Qian Weng. Keep him seated in the nearest right-front position with his upper torso and right hand fully inside the vertical frame; he keeps exactly one clearly visible folding fan in his right hand throughout and never touches a brush or paper. The remaining adult writers form a quiet low-detail group. The camera dollies in with small amplitude at slow speed, preserving the shore axis, the lateral positions, and the right-front fan hand. End this four-second establishing setup with <Subject 2> poised to address the gathering and no dialogue yet.
[Shot 2] At 00:04.000, the camera cuts to a stable, slightly wider medium group shot from the seating side on the same shore axis. Leave enough lateral room that Qian Weng, the nearest right-front older literatus, remains fully visible from chest through his right hand inside the vertical frame; do not crop him at the right edge, push in past him, or let a pan, focus change, or foreground obstruction make his hand or fan disappear. Keep <Subject 2> central, facing toward the lower-left seating area; he raises one hand to call for attention and the group becomes still. In a clear, steady, but slightly fast middle-aged male voice, <Subject 2> (S1) says exactly once; punctuation receives only brief pauses so the complete 27-character line finishes within this six-second setup: <d>[Chinese] 此池无名已久。今日请诸位为它赐个名字——取得好者，老夫奉为上宾。</d> Hold this steady group framing while only the other adult writers reach toward the table for brushes and blank slips after the rule is announced. Qian Weng keeps exactly one folding fan visibly in his right hand; his left hand stays away from all writing surfaces, and he never takes a brush, touches a slip, or writes. The paper remains unreadable. During the final second, keep Qian Weng's chest, right hand, and fan continuously visible: as the final word lands, he makes only a slight head turn and side-eyes <Subject 1> without speaking, with his lips closed, and without beginning any taunt. By 00:10.000, the other writers' brush tips have already touched blank title slips while Qian Weng's single right-hand folding fan remains clearly identifiable and unchanged. End on this restrained group state, with <Subject 1> still oriented toward the pond.

overall_soundscape:
Clear water laps softly against the gray stone edge while a light afternoon breeze moves the pavilion eaves and nearby foliage. Paper slips shift, wooden seats creak lightly, and brush fibers begin to touch blank paper only after the rule is spoken; restrained human room tone remains beneath the single spoken line.

non_diegetic_music:
N/A
```
