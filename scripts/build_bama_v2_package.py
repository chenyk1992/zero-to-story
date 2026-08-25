"""Build one approved V2 execution package for the family episode."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


PANEL_REFS: dict[str, list[str]] = {
    "P001": ["characters/laoba-character-card.png", "panels/P001/storyboard-board.png"],
    "P002": ["lastframes/v2-20260824/P001.png", "panels/P002/storyboard-board.png", "characters/laoma-character-card.png", "characters/qidagu-character-card.png"],
    "P003": ["lastframes/v2-20260824/P002.png", "panels/P003/storyboard-board.png", "characters/xiaopang-character-card.png", "characters/xiaomei-character-card.png", "characters/laoba-character-card.png"],
    "P004": ["lastframes/v2-20260824/P003-r008.png", "panels/P004/storyboard-board.png", "characters/laoba-character-card.png"],
    "P005": ["lastframes/v2-20260824/P004.png", "panels/P005/storyboard-board.png", "characters/laoma-character-card.png", "characters/laoba-character-card.png"],
    "P006": ["lastframes/v2-20260824/P005.png", "characters/laoma-character-card.png", "characters/badaiyi-character-card.png"],
    "P007": ["lastframes/v2-20260824/P006.png", "characters/badaiyi-character-card.png", "characters/laoba-character-card.png"],
    "P008": ["lastframes/v2-20260824/P007.png", "characters/xiaopang-character-card.png", "characters/laoba-character-card.png"],
    "P009": ["lastframes/v2-20260824/P008.png", "characters/laoba-character-card.png", "characters/xiaopang-character-card.png"],
    "P010": ["lastframes/v2-20260824/P009.png", "characters/xiaopang-character-card.png"],
    "P011": ["lastframes/v2-20260824/P010.png", "characters/xiaopang-character-card.png"],
    "P012": ["lastframes/v2-20260824/P011.png", "characters/laoba-character-card.png"],
    "P013": ["lastframes/v2-20260824/P012.png", "characters/laoba-character-card.png"],
    "P014": ["lastframes/v2-20260824/P013.png", "characters/jiujiu-character-card.png", "characters/laoba-character-card.png"],
    "P015": ["lastframes/v2-20260824/P014.png", "characters/laoba-character-card.png"],
    "P016": ["lastframes/v2-20260824/P015.png", "characters/laoma-character-card.png", "characters/laoba-character-card.png"],
    "P017": ["lastframes/v2-20260824/P016.png", "panels/P017/target-group-r059-7_9s.png"],
    "P018": ["lastframes/v2-20260824/P017.png", "lastframes/v2-20260824/P015.png"],
}


H3_TEXT_FIREWALL = """[HIGHEST PRIORITY — AUDIO-ONLY SPEECH / ZERO GLYPHS]
The <d>[zh]... </d> tokens below are hidden soundtrack instructions only. Generate natural spoken Mandarin and matching mouth movement, but never visualize the written tokens. At every frame the rendered picture must contain zero writing-system glyphs: no Chinese characters, Latin letters, Arabic numerals, punctuation, subtitles, captions, dialogue labels, speaker names, colons, quotation marks, speech bubbles, UI text, signs, watermarks or logos. Speech is voice and lip movement only. If the speech instruction conflicts with the visual layer, keep the voice and remove every visual glyph. Phone, screen, code, IP, money, app and icon content must remain abstract color blocks or geometry with no symbols that can be read."""


H3_TEXT_FIREWALL_MINIMAL = """[HIGHEST PRIORITY — AUDIO-ONLY SPEECH / ZERO GLYPHS]
Spoken Mandarin is soundtrack and mouth movement only. The rendered picture contains zero writing-system glyphs at every frame. Keep all visible room surfaces plain and empty. Do not add captions, dialogue labels, speaker names, speech graphics, interface graphics, logos, watermarks or any readable symbols."""


NO_TRANSCRIPT_MODE = """[NO-TRANSCRIPT GENERATION MODE]
This visual generation pass intentionally contains no written transcript. Any spoken line is only a natural Mandarin voice cue; do not repeat, spell, transcribe or render its words. Do not generate a subtitle layer."""


LEAN_PROMPT_MARKER = "prompt-mode: lean-dialogue-locked"

LEAN_AUDIO_ONLY_FIREWALL = """[AUDIO-ONLY / ZERO-GLYPH]
Every <d>[zh]... </d> token is hidden audio metadata, never visual content. Speak the exact line and match the lips, but do not write, type, draw, transcribe or visualize any spoken words: no subtitles, captions, karaoke, speaker labels, bubbles, UI, logos, punctuation or readable glyphs anywhere in the frame."""

LEAN_IDENTITY_FIREWALLS = {
    "P003": """[P003 VISUAL LOCK]
Render polished full-color animation in every shot; never a white storyboard page, line art, contact sheet, panel grid or gray-haired substitute. Keep at most one canonical XiaoPang, one XiaoMei, one QiDaGu, one LaoMa and one LaoBa; no partial edge bodies, duplicate people or unlisted relatives. Shot 1 preserves the supplied three-person tail without adding anyone. The hallway and entry-door shots contain one complete character at a time. If a reaction two-shot is needed, show only one canonical QiDaGu and one canonical XiaoPang. Never show a group wide shot, gray-haired older man, seated extra woman or laptop crowd. The final shot and exact final frame must contain LaoBa alone at the sofa cushion, with no LaoMa, QiDaGu, XiaoPang, XiaoMei, laptop, monitor or extra person.""",
    "P013": """[P013 VISUAL LOCK]
The entire frame is a tight full-color living-room close-up of one canonical LaoBa against only plain sofa fabric and one uninterrupted matte beige wall. No monitor, television, projection, display rectangle, chart, diagram, browser, dashboard, UI, computer, laptop, phone screen, poster or framed information surface exists anywhere. Use exactly two phones with blank backs/abstract surfaces; no other person or duplicate hand enters.""",
}


PANEL_IDENTITY_FIREWALLS = {
    "P003": """[P003 IDENTITY FIREWALL]
Never show a full group wide shot with duplicate people. Each shot may contain at most one XiaoPang, one XiaoMei and one QiDaGu. Prefer clean single-character or two-character hard-cut compositions; established family members may remain off-screen or as partial background silhouettes only. Never instantiate a second XiaoPang or a second high-ponytail woman. The final handoff shot must contain exactly one canonical LaoBa and no other face. Never place a monitor, television, laptop, wall display, chart, sign or readable interface in the hallway or close-up shots. Any phone screen must face away or be a blank dark rectangle.""",
    "P004": """[P004 IDENTITY FIREWALL]
Picture 1 override: trust the actual supplied P003-r008 last frame, which is one canonical LaoBa at the sofa; ignore any earlier generic wording that mentions XiaoPang or a seated family. The action lead is LaoBa only. Never replace LaoBa with XiaoPang, QiDaGu, LaoMa or an undefined older person. After the opening hand-and-cushion detail, every shot must contain exactly one canonical LaoBa and no other face or full body. No family reaction, no two-shot, no group wide shot. End with exactly one LaoBa holding one phone. Absolutely no comic speech bubble, thought bubble, text bubble, callout balloon, pictogram balloon or floating glyph of any kind; do not visualize sound effects or reaction marks. Any dialogue is audio-only with natural lip movement and must never appear as a bubble or written mark.""",
    "P006": """[P006 IDENTITY FIREWALL]
Only two canonical identities may appear in the entire clip: LaoMa in shots 1-4 and BaDaYi in shot 5. LaoMa must keep long dark hair, pink top, cream apron and one wooden rolling pin. BaDaYi must keep sharp face, purple hair, cream fur stole, black dress, gold handbag and one phone. Do not generate any male body, any gray-haired orange-shirt person, LaoBa, XiaoPang, XiaoMei, QiDaGu, JiuJiu, background relative, bystander or extra woman. This package intentionally omits the crowded storyboard board: use only the clean room continuity and the two identity cards. Use hard-cut single-character compositions; do not render a group reaction shot or a chase partner. No laptop, monitor, computer, brand mark, sign, speech bubble, thought bubble, comic glyph or readable phone content; all screens are abstract blocks only. Never swap LaoMa and BaDaYi attributes or create a second version of either woman.""",
    "P007": """[P007 IDENTITY FIREWALL]
Only two canonical identities may appear: BaDaYi and LaoBa. BaDaYi must keep sharp face, purple hair, cream fur stole, black dress, gold handbag and one phone. LaoBa must keep round face, small moustache, brown rectangular glasses and checked shirt. Do not generate LaoMa, XiaoPang, XiaoMei, QiDaGu, JiuJiu, any other relative, bystander or background reaction. This package intentionally omits the crowded storyboard board; use the clean living-room continuity and the two identity cards only. Shots 1-3 are BaDaYi alone. Shot 4 must show the complete upper bodies and faces of exactly one BaDaYi and exactly one LaoBa side by side, not cropped, not partial and not a floating arm. Shot 5 must show the complete upper bodies of those same two people and one clear high-five: one BaDaYi hand meets one LaoBa hand at center, with both faces and both torsos visible. No disembodied limbs, duplicate hands, duplicate phones, merged bodies, laptop, logo, sign, speech bubble, comic glyph or readable phone content. All dialogue is audio-only and all screens are abstract color geometry.""",
    "P008": """[P008 IDENTITY FIREWALL]
Only BaDaYi, LaoBa and XiaoPang may appear. The opening must continue the actual P007 high-five with exactly one BaDaYi and one LaoBa; BaDaYi then exits. XiaoPang is one young heavy-set male with black hair, thick rectangular glasses, headphones around his neck and dark gaming shirt; never render gray hair, an older man or a second XiaoPang. LaoBa must keep round face, moustache, brown rectangular glasses and checked shirt. Shots 2-3 must show exactly one complete LaoBa and exactly one complete XiaoPang in a controlled medium two-shot, both visible from head to waist, with no edge-cropped silhouette, shoulder, hand or third body. Shot 4 must show one closed plain unbranded laptop alone; its screen is not visible. Shot 5 must contain LaoBa alone. No LaoMa, XiaoMei, QiDaGu, JiuJiu, any background relative, group reaction, extra laptop, floating limb, speech bubble, caption or written mark.""",
    "P009": """[P009 IDENTITY FIREWALL]
Only one canonical LaoBa and one canonical XiaoPang may appear in this clip. LaoBa is the older round-faced man with small black moustache, brown rectangular glasses, short black hair and light checked shirt; XiaoPang is the younger heavy-set boy with black hair, thick rectangular glasses, headphones around his neck and dark gaming shirt. Keep both identities stable for the entire uninterrupted shot. Do not show XiaoMei, QiDaGu, BaDaYi, LaoMa, JiuJiu, any other woman, family group, duplicate sibling or partial edge figure. This is one coherent full-width 16:9 living-room two-shot for the whole 10 seconds, not a montage, collage, storyboard contact sheet, split-screen or white-panel layout. Keep both hands visible and empty; no laptop, computer, phone or other electronic prop appears anywhere. Any off-screen dialogue is audio-only. No speech bubbles, captions, role names, floating limbs, logos or readable marks.""",
    "P010": """[P010 IDENTITY FIREWALL]
Only one canonical XiaoPang may be newly visible in this clip: young heavy-set boy, black hair, thick rectangular glasses, headphones around his neck and dark gaming shirt. The supplied previous tail is continuity only; do not copy any partial edge figure from it and do not introduce XiaoMei, LaoBa, LaoMa, QiDaGu or any family group as a second full body. Every cut is one coherent full-frame shot, never a storyboard board, collage or split-screen. No wall projection, monitor, television, screen, interface, code panel, poster or display exists anywhere. One closed plain laptop may be carried or placed on a desk, showing only its blank outer shell; its screen is never visible. No code syntax, labels, UI, arrow, logo, speech bubble, subtitle or floating limb. Never duplicate XiaoPang or turn him into a gray-haired adult.""",
    "P011": """[P011 IDENTITY FIREWALL]
Only one canonical XiaoPang may appear: young heavy-set boy, black hair, thick rectangular glasses, headphones around his neck and dark gaming shirt. This intentionally preserves the actual P010 tail identity for a stable reaction beat; QiDaGu and LaoMa remain off-screen voices only. Make one uninterrupted full-frame living-room close-up for the entire clip with no transition, montage, collage, split layout, graphic decoration or marks on the wall. No other face, body, relative, prop, label or readable mark; all dialogue is off-screen audio only.""",
    "P012": """[P012 IDENTITY FIREWALL]
Only one canonical LaoBa may be active: round face, small black moustache, brown rectangular glasses, short black hair, light checked shirt and slippers. The family can remain only as indistinct continuity background silhouettes; no new face is introduced. Show exactly two distinct phones only in the reveal, one in each hand; never duplicate a phone or hand. Any screen is a blank light rectangle or abstract color blocks with zero icons, letters, digits, labels or interface. Every hard cut is one coherent full-frame shot, never a storyboard board, collage or split-screen. No speech bubbles, subtitles, role names, logos or readable marks.""",
    "P013": """[P013 IDENTITY FIREWALL]
LaoBa is the only active speaker and must remain the same canonical man: round face, small black moustache, brown rectangular glasses, short black hair and checked shirt. Use exactly two phones, physically distinct, and never add a third phone or extra fingers. The complete camera view is a tight living-room medium close-up whose background is filled only by plain sofa upholstery and one uninterrupted matte beige wall. There is no background electronics, wall furniture, rectangular display surface or framed information surface anywhere inside or outside the crop. The entire scene contains no television, monitor, projection, diagram, chart, flowchart, browser window, dashboard, screen, interface or graphical insert; all explanation is audio-only. Family reaction may be off-screen only. Use full-frame coherent shots, not the storyboard board, collage, split-screen or contact sheet. No duplicate LaoBa, role names, subtitles, speech bubbles or visual writing.""",
    "P014": """[P014 IDENTITY FIREWALL]
Only one canonical LaoBa and one canonical JiuJiu may be active in the clip. LaoBa keeps round face, small black moustache, brown rectangular glasses and checked shirt. JiuJiu keeps square face, black rectangular glasses, serious expression, dark suit, white shirt and one briefcase. Use only clean full-frame tight single-character medium close-ups; never put LaoBa and JiuJiu in the same frame. Every visible person has a complete head, face and torso; never show a partial arm, cropped headless torso, edge body or second uncle. Every shot uses the same simple living-room background filled only by plain sofa upholstery and one uninterrupted matte beige wall. Do not show an entrance, doorway, door, refrigerator, appliance, cabinet, sign, paper, label, picture frame, wall decoration or readable mark. Phones remain abstract and unbranded. No crowded group, storyboard board, collage or split-screen. No QiDaGu or other relative, no face blend, no duplicate briefcase, speech bubble, subtitles, labels or readable text. End on LaoBa alone for the next panel.""",
    "P015": """[P015 IDENTITY FIREWALL]
Only one canonical LaoBa is active in the foreground: round face, small moustache, brown rectangular glasses, checked shirt and slippers. No family member or background silhouette appears. During the first second he lowers the two inherited phones completely below frame; after that, no phone returns. From 01.500 seconds through the final frame show exactly one already-lit cigarette and one thin smoke curl only. Never show any lighter, flame, matchbox, second cigarette or extra smoking prop. Use coherent full-frame single-character shots, never the storyboard board, collage or split-screen. No actor likeness, film reference, brand, speech bubble, caption, role name, subtitle or readable mark; dialogue is audio-only.""",
    "P016": """[P016 IDENTITY FIREWALL]
Only canonical LaoMa and LaoBa may appear, always in separate full-frame shots. LaoMa has long dark hair, pink top and cream apron; LaoBa has round face, moustache, brown rectangular glasses and checked shirt. For every LaoBa shot, reproduce the supplied P015 continuity image as an unchanged wide living-room composition: identical camera distance, room axis, sofa, window, door, lamp, body pose and visible object state. Both hands stay below the bottom edge and he makes only a subtle blink or smile. LaoMa appears alone in a simple waist-up composition with both hands below frame, making only a small natural smile. Use ordinary instantaneous cuts with no transition artwork. Do not add any person, object, furniture or background element beyond what is already visible in the corresponding clean shot. No duplicate family member, merged face, face obstruction, label, subtitle, role name, actor likeness or visual writing.""",
    "P017": """[P017 IDENTITY FIREWALL]
Picture 1 is the exact first frame and Picture 2 is the exact final frame. LaoBa may appear only in the opening Picture 1 continuity hold; after the single cut he disappears permanently and never returns. Picture 2 is an already approved full-frame target image containing exactly four identities from left to right: BaDaYi, JiuJiu, QiDaGu and XiaoPang. Preserve those exact four faces, bodies, clothing, spacing, room background and blank prop surfaces from Picture 2; do not reinterpret or replace any person. Show exactly four people after the cut. Do not render a fifth relative, duplicate person, high-ponytail woman, gray-haired substitute, moustached substitute, edge body, fading body or merged body. Never use a contact sheet, collage, split-screen, white field or transition artwork. No graphic marks, speech graphics, subtitles, role names, UI or readable text; all dialogue is audio-only.""",
    "P018": """[P018 IDENTITY FIREWALL]
Picture 1 is the exact first frame and Picture 2 is the exact final frame. The four relatives in Picture 1 appear only during the opening continuity hold and disappear completely at the single cut. After that cut, only one canonical LaoBa is visible: round face, small black moustache, brown rectangular glasses, checked shirt and exactly one cigarette with one thin smoke curl, matching Picture 2 exactly. Do not introduce any second person, relative, duplicate LaoBa, substitute face, extra cigarette, lighter, phone, screen, display, transition artwork, collage or split-screen. Keep the right side visually quiet for a later approved post-production icon overlay; do not generate any icon, title or graphic in this H3 pass. No speaker names, colons, quotations, subtitles, title text, labels, readable marks, speech bubbles, UI or brand symbols.""",
}


PANEL_SHOT_REWRITES = {
    "P003": """[Shot 1] Continue Picture 1 exactly with LaoBa, LaoMa and QiDaGu as the only visible established people; keep one instance of each and preserve the sofa-cushion state.
[Shot 2] At 01.200, hard cut to a clean blank hallway with plain walls and one door, containing exactly one XiaoPang, wearing thick glasses and headphones around his neck. No monitor, television, computer, poster or display exists anywhere in this shot. He walks two steps into frame and produces only a natural Mandarin voice; no other full body is visible.
[Shot 3] At 03.000, hard cut to a clean blank entry-door shot containing exactly one XiaoMei, with one high ponytail, red top and blue jeans. Her single phone is turned away with a blank dark screen; no UI or symbols. She opens the door and produces only a natural Mandarin voice; no other woman or full body is visible.
[Shot 4] At 04.800, hard cut to exactly one canonical XiaoPang in a tight close-up against a plain blank door and wall. An off-screen adult female voice asks one natural Mandarin question, but no other person, face, monitor or display is visible. XiaoPang freezes, keeps thick rectangular glasses and headphones around his neck, and looks toward the off-screen voice. No Qidagu body, no second XiaoPang and no high-ponytail woman appears.
[Shot 5] At 07.000, hard cut to exactly one canonical LaoBa at the sofa cushion, with round face, moustache, brown rectangular glasses and checked shirt. He remains alone, presses the cushion once and holds a calm reaction. No XiaoPang, no XiaoMei, no other face, no group wide shot. End on this single LaoBa for the next panel.""",
    "P004": """[Shot 1] Continue Picture 1 only as a tight detail of the sofa cushion and one canonical LaoBa hand pressing it. Do not show any face or any other person.
[Shot 2] At 01.200, hard cut to exactly one canonical LaoBa in a clean medium close-up. He reaches under the cushion and lifts one phone. Preserve round face, moustache, brown rectangular glasses, checked shirt and slippers; no other face or full body is visible.
[Shot 3] At 03.000, hard cut to the same single phone in LaoBa's hands. The screen is abstract color blocks only, with zero glyphs, digits or interface.
[Shot 4] At 04.600, hold exactly one LaoBa in a proud generic card-player-like pose while he produces only natural Mandarin voice. No family reaction bodies, no duplicate LaoBa and no named actor likeness.
[Shot 5] At 07.000, hold exactly one canonical LaoBa in a stable close-up holding exactly one phone. No other person enters and no other face appears. This is the handoff pose for the next panel.""",
    "P006": """[Shot 1] Continue Picture 1 with exactly one canonical LaoMa alone in the clean living room, preserving long dark hair, pink top, cream apron and one wooden rolling pin. Do not show any other face or body.
[Shot 2] At 01.500, hard cut to the same single LaoMa in a tight waist-up view. She raises the one rolling pin in an emphatic but harmless gesture and produces only natural Mandarin voice; no second character is present.
[Shot 3] At 03.000, hold a clean sofa detail with the rolling pin entering and leaving frame, then cut back to LaoMa alone. No chase partner, family reaction, bystander or technology appears.
[Shot 4] At 05.400, hard cut to LaoMa alone lowering the rolling pin and stepping out of frame. Keep the room empty after she exits; no male body and no extra woman enters.
[Shot 5] At 07.800, hard cut to exactly one canonical BaDaYi alone in the same room. Preserve sharp face, purple hair, cream fur stole, black dress and gold handbag; she raises one hand and holds one phone with an abstract color-block screen. End on this single BaDaYi for the next panel. No gray-haired person, no group wide shot, no extra faces and no visual speech marks.""",
    "P007": """[Shot 1] Continue Picture 1 exactly with one canonical BaDaYi alone in the clean living room, preserving purple hair, sharp face, cream fur stole, black dress, gold handbag and one phone. No other face or body enters.
[Shot 2] At 01.200, hold BaDaYi's single face and one phone as she gestures once and produces only natural Mandarin voice. Keep the phone screen abstract color blocks with no glyphs.
[Shot 3] At 03.200, hard cut to her single phone showing only an abstract rising colored shape made of rectangles; no letters, digits, icons or interface. Return to BaDaYi alone before the next cut.
[Shot 4] At 04.800, hard cut to a stable medium two-shot. Show the complete upper body and face of exactly one canonical LaoBa on the left and exactly one canonical BaDaYi on the right, side by side, both fully visible from head to waist. LaoBa keeps round face, moustache, brown glasses and checked shirt; BaDaYi keeps purple hair, fur stole, black dress and gold handbag. No cropped body, floating hand, third person or background reaction.
[Shot 5] At 07.000, keep the same stable two-shot and show one clear high-five at center: exactly one hand from LaoBa and exactly one hand from BaDaYi meet once, while both faces and torsos remain visible. No disembodied limbs or extra hands. End on this complete two-person high-five pose for the next panel. No family group, no names, no subtitles, no speech bubble and no visual writing.""",
    "P008": """[Shot 1] Continue Picture 1 exactly with the completed high-five of one canonical BaDaYi and one canonical LaoBa. Let BaDaYi exit cleanly; no other person enters.
[Shot 2] At 01.200, hard cut to exactly one complete canonical LaoBa on the left and exactly one complete canonical XiaoPang on the right in a clean medium two-shot, both visible from head to waist. LaoBa keeps round face, small moustache, brown rectangular glasses and checked shirt. XiaoPang keeps young black hair, thick rectangular glasses, headphones around his neck and dark gaming shirt. No cropped edge person, back-of-head foreground, third body or duplicate face.
[Shot 3] At 03.000, hold the same complete LaoBa-and-XiaoPang two-shot. XiaoPang places one plain laptop on the table while LaoBa watches; the laptop is closed or turned away so no screen UI is visible. No other person, silhouette, shoulder or hand enters.
[Shot 4] At 05.200, hard cut to one closed plain unbranded laptop alone on the table, showing only its blank outer shell and no screen, logo, label, symbol or writing.
[Shot 5] At 07.200, hard cut to exactly one canonical LaoBa alone in a clean sofa close-up, round face, small moustache, brown rectangular glasses and checked shirt. He makes one proud dismissive gesture. No XiaoPang, no BaDaYi, no family group and no other face. End on this single LaoBa for the next panel.""",
    "P009": """[Shot 1] Continue Picture 1 exactly and hold one uninterrupted full-width living-room two-shot for the entire clip. Show exactly one canonical LaoBa on the left and exactly one canonical XiaoPang on the right, both complete from head to waist. LaoBa must match the supplied LaoBa card, including small black moustache, brown rectangular glasses and light checked shirt. XiaoPang must match his supplied card, including thick glasses, headphones and dark gaming shirt. No other face, body, silhouette or edge fragment enters.
[Shot 2] During the same uninterrupted two-shot, XiaoPang points once toward the empty table while LaoBa listens. Keep both hands otherwise empty; no laptop, computer, phone or screen exists anywhere in the frame.
[Shot 3] During the same uninterrupted two-shot, LaoBa makes one dismissive wave while XiaoPang remains seated. An off-screen female voice may be heard naturally, but no woman appears in the picture.
[Shot 4] During the same uninterrupted two-shot, both characters hold their positions and make only natural mouth movement. Do not cut, zoom into an insert, create a second panel or show a phone screen.
[Shot 5] End on the same clean complete LaoBa-and-XiaoPang two-shot for the next panel. The whole 10-second output must be one coherent shot with no montage, no split-screen, no white side panels, no collage and no visual writing.""",
    "P010": """[Shot 1] Continue Picture 1 only for the living-room lighting and axis, then settle on exactly one canonical XiaoPang carrying one plain closed laptop. Do not show any partial edge person, wall projection, monitor, poster or display.
[Shot 2] At 01.200, hard cut to one full-frame hallway-to-bedroom shot containing exactly one XiaoPang, with thick rectangular glasses, headphones around his neck and dark gaming shirt. He walks alone carrying the closed laptop and produces only natural Mandarin voice. The walls and bedroom are plain and contain no screen or writing.
[Shot 3] At 03.000, hard cut to one full-bleed close-up of the laptop's blank outer shell with the lid closed and the screen completely hidden. No letters, digits, code syntax, arrows, labels, icons, interface, logo or monitor. No face or extra hand enters.
[Shot 4] At 05.200, hard cut to one clean waist-up close-up of exactly one canonical XiaoPang in the plain bedroom, with the closed laptop resting out of frame. He turns once toward camera and produces only natural Mandarin voice. No second XiaoPang, gray-haired adult, family member or written mark.
[Shot 5] At 07.400, hard cut to exactly one canonical XiaoPang back in a clean living-room close-up with the closed laptop out of frame. No group reaction, projection, monitor, screen or visual writing. End on this single XiaoPang for the next panel, with no collage or split-screen.""",
    "P011": """[Shot 1] For the entire 10-second clip, use one uninterrupted full-frame living-room close-up of exactly one canonical XiaoPang alone. Preserve young black hair, thick rectangular glasses, headphones around his neck and dark gaming shirt, matching the supplied card and the actual P010 tail. Keep him seated with only subtle natural facial movement for off-screen Mandarin family voices; the camera never cuts and no other character enters. Use a plain sofa-and-wall background with no decorative symbols or marks. Do not show QiDaGu, LaoMa, LaoBa or any other person. End on this single XiaoPang with a clean unmarked frame for the next panel.""",
    "P012": """[Shot 1] For the entire 10-second clip, use one uninterrupted full-frame living-room medium close-up of exactly one canonical LaoBa alone. Preserve round face, small black moustache, brown rectangular glasses, short black hair, light checked shirt and slippers. He reaches under the sofa cushion once and then holds exactly two physically distinct plain phones, one in each hand, while producing only natural Mandarin audio. Both phone screens face away or remain blank dark rectangles with no interface. Do not show XiaoPang, QiDaGu, LaoMa, any other face, extra fingers, duplicate phone, graphic or writing. End on this single LaoBa holding the two phones for the next panel.""",
    "P013": """[Shot 1] For the entire 10-second clip, use one uninterrupted tight living-room medium close-up of exactly one canonical LaoBa alone, continuing the actual P012 pose. Frame him from chest to head so the whole visible background is filled only by plain sofa upholstery and one uninterrupted matte beige wall. Keep exactly two distinct plain phones, one in each hand, with their display faces turned away from camera. LaoBa explains naturally in Mandarin audio and makes only small hand movements; no cut, insert or graphic appears.
[Shot 2] Keep the same single LaoBa and the same two phones while he continues the calm explanation. Preserve the tight crop: behind him there is only soft sofa fabric and a solid blank wall, with no other furniture, equipment, frame, panel or rectangular surface.
[Shot 3] Keep the camera stable on LaoBa; any flow explanation is audio-only. The complete image contains no television, display, monitor, projection, dashboard, browser window, diagram, chart, flowchart, colored graph, UI or visual geometry.
[Shot 4] LaoBa makes one restrained gesture, keeping both phones separate and fully visible. No extra fingers, face or prop enters.
[Shot 5] End on this same single canonical LaoBa holding exactly two phones against the same sofa-and-blank-wall background, with no group shot, no new person, no electronic display surface and no visual writing.""",
    "P014": """[Shot 1 | 00.000-03.000] Continue Picture 1 with exactly one canonical LaoBa alone in a tight living-room medium close-up, holding exactly two phones. He turns his gaze once toward the off-screen JiuJiu and produces only natural Mandarin voice. Behind him there is only sofa fabric and one solid matte beige wall. No part of any second person or doorway appears.
[Shot 2 | 03.000-06.000] Hard cut to exactly one complete canonical JiuJiu alone in a tight medium close-up against the same sofa-and-solid-wall background: square face, black rectangular glasses, dark suit, white shirt and one briefcase held fully inside the crop. He produces only natural Mandarin voice. Do not show an entrance, door, refrigerator, appliance, cabinet, paper, label, picture frame or wall decoration. Never crop his head or show only an arm or torso.
[Shot 3 | 06.000-10.000] Hard cut to exactly one canonical LaoBa alone in the same tight medium close-up against only sofa fabric and the solid blank wall, holding exactly two phones and gesturing once toward the off-screen uncle. No part of JiuJiu, suit, hand, arm, briefcase or any second body remains inside the frame. Keep LaoBa complete and alone through the final frame. No third person, labels or text. End on this single LaoBa pose for the next panel.""",
    "P015": """[Shot 1 | 00.000-01.500] Continue Picture 1 with exactly one canonical LaoBa alone. He lowers both inherited phones together until they are completely below the bottom edge. No new prop or person enters.
[Shot 2 | 01.500-10.000] Hard cut once to one uninterrupted tight living-room medium close-up of exactly one canonical LaoBa alone holding exactly one already-lit unbranded cigarette. No phone, lighter, flame, matchbox or second cigarette is visible anywhere. One thin smoke curl rises beside him without covering his face. He produces only natural Mandarin voice with small facial movements; the camera never cuts again and the background stays plain. End and hold on this same LaoBa with the same single cigarette and one thin smoke curl for the next panel. No duplicate LaoBa, extra hand, speech bubble, caption or visual writing.""",
    "P016": """[Shot 1 | 00.000-03.000] Reproduce Picture 1 as an unchanged wide living-room shot with exactly one canonical LaoBa alone. Preserve the supplied camera distance, sofa, window, door, lamp, body pose and every visible object state. Both hands remain below frame. He makes only a subtle blink; nothing else changes.
[Shot 2 | 03.000-06.500] Use one ordinary instantaneous cut to exactly one canonical LaoMa alone in a clean waist-up shot against plain sofa upholstery and an uninterrupted matte beige wall. Preserve long dark hair, pink top and cream apron. Both hands remain below frame. She makes a small natural smile and produces only natural Mandarin voice; no object or second person enters.
[Shot 3 | 06.500-10.000] Use one ordinary instantaneous cut back to the exact unchanged Picture 1 wide composition with exactly one canonical LaoBa alone. Preserve the same camera distance, room layout, body pose and visible object state. Both hands stay below frame. He makes only a slight smile and holds still through the final frame. No person or object is added. End on this single LaoBa for the next panel.""",
    "P017": """[Shot 1 | 00.000-00.800] Hold Picture 1 exactly unchanged as the first frame and opening room-continuity shot with one canonical LaoBa. No other person or graphic appears.
[Shot 2 | 00.800-01.000] Use one ordinary instantaneous full-frame cut with no dissolve, morph, white field, split or transition artwork. LaoBa disappears completely.
[Shot 3 | 01.000-10.000] Show Picture 2 as the exact full-frame four-person composition and hold it unchanged through the exact final frame: BaDaYi, JiuJiu, QiDaGu and XiaoPang, left to right. Preserve all four identities, spacing, room background and blank prop surfaces exactly as supplied. Only subtle blinking and breathing are allowed. Do not cut again, remove a person, fade a person, add a person, change the camera or display any visual mark.""",
    "P018": """[Shot 1 | 00.000-00.800] Hold Picture 1 exactly unchanged as the first-frame continuity image with the same four relatives and no LaoBa.
[Shot 2 | 00.800-01.000] Use one ordinary instantaneous full-frame cut with no dissolve, morph, white field, split or transition artwork. The four relatives disappear completely.
[Shot 3 | 01.000-10.000] Show Picture 2 as the exact full-frame composition of one canonical LaoBa alone with exactly one cigarette and one thin smoke curl. Preserve his face, clothing, pose and living-room background. Allow only subtle blinking, mouth movement and smoke movement while he produces one calm natural Mandarin final line. Hold this same single-person camera through the exact final frame. Keep the right half quiet for post-production icons, but do not generate any icon or graphic in this H3 pass.""",
}


def _panel_number(panel_id: str) -> int:
    return int(panel_id[1:])


def _read_prompt(prompt_file: Path, panel_id: str) -> str:
    text = prompt_file.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"^## {re.escape(panel_id)}｜.*?\n.*?最终提示词：\n\n(.*?)(?=\n---\n\n## P\d+｜|\n## V[23] (?:审批与执行状态|状态))",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        raise ValueError(f"Prompt section not found for {panel_id}")
    prompt = match.group(1).strip()
    if not prompt or "Picture 1" not in prompt:
        raise ValueError(f"Prompt for {panel_id} is empty or missing Picture references")
    forbidden = ("台词：", "字幕：", "老爸\"", "七大姑：")
    if any(token in prompt for token in forbidden):
        raise ValueError(f"Prompt for {panel_id} contains a forbidden visual dialogue pattern")
    return prompt


def _is_lean_prompt_file(prompt_file: Path) -> bool:
    return LEAN_PROMPT_MARKER in prompt_file.read_text(encoding="utf-8")


def _asset_key(uri: str) -> str:
    stem = Path(uri).stem
    if uri.startswith("audio/"):
        return f"audio.v3.{stem.lower()}"
    if uri.startswith("lastframes/"):
        version = "v3" if uri.startswith("lastframes/v3-") else "v2"
        return f"lastframe.{version}.{stem.lower()}"
    if stem.startswith("target-group-"):
        return f"keyframe.v2.{stem.lower()}"
    if uri.startswith("panels/"):
        panel = uri.split("/", 2)[1]
        return f"storyboard.v2.{panel.lower()}"
    return f"character.v2.{stem.replace('-character-card', '').lower()}"


def _provenance(uri: str) -> dict[str, str]:
    if uri.startswith("audio/"):
        return {
            "source_type": "external_skill",
            "producer": "mmx-speech",
            "operation": "audio.synthesize",
            "producer_version": "2026-08-25",
        }
    if uri.startswith("lastframes/"):
        return {
            "source_type": "runtime_artifact",
            "producer": "lfo",
            "operation": "frame.extract",
            "producer_version": "v3-20260825" if uri.startswith("lastframes/v3-") else "v2-20260824",
        }
    if Path(uri).stem.startswith("target-group-"):
        return {
            "source_type": "runtime_artifact",
            "producer": "lfo",
            "operation": "frame.extract",
            "producer_version": "v2-20260825",
        }
    return {
        "source_type": "external_skill",
        "producer": "imagegen",
        "operation": "image.generate",
        "producer_version": "2026-08-24",
    }


def _asset(uri: str) -> dict[str, Any]:
    media_type = "audio" if uri.startswith("audio/") else "image"
    return {
        "asset_key": _asset_key(uri),
        "media_type": media_type,
        "source": {"uri": uri},
        "provenance": _provenance(uri),
        "review": {"required": True},
    }


def _reference(uri: str, index: int) -> dict[str, Any]:
    if uri.startswith("audio/"):
        return {
            "reference_id": f"{Path(uri).stem}-audio",
            "asset_key": _asset_key(uri),
            "semantic_usage": "audio.dialogue_reference",
            "instruction": "Audio 1; exact spoken Mandarin reference for timing, words and natural delivery. Use it for sound and lip movement only; never render any audio content as visible text.",
            "binding": {
                "required": False,
                "priority": 105,
                "placement": "fixed",
                "on_unsupported": "drop",
                "slot": "ref_audio_0",
            },
        }
    if index == 0 and uri.startswith("lastframes/"):
        usage = "continuity.last_frame_lock"
        lock_version = "V3" if uri.startswith("lastframes/v3-") else "V2"
        instruction = f"Picture 1; exact {lock_version} real last-frame lock from the completed previous panel. Preserve opening pose, screen direction, lighting, hands, prop state and room axis before any new motion."
        priority = 110
    elif index == 1 and uri.startswith("panels/"):
        usage = "composition.motion"
        instruction = "Picture 2; use only as composition, spatial layout, action-order and rhythm reference. Never render the storyboard board, panels, line art or labels."
        priority = 99
    elif uri.startswith("panels/"):
        usage = "composition.motion"
        instruction = "Use this picture only for composition and action order; render the polished color animation, never the storyboard itself."
        priority = 99
    else:
        usage = "subject.identity"
        instruction = "Use this picture only to preserve the canonical identity, face, hair, clothing colors and signature prop of the named character; do not copy any storyboard face or duplicate the person."
        priority = max(90, 99 - index)
    return {
        "reference_id": f"{Path(uri).stem}-{index + 1}",
        "asset_key": _asset_key(uri),
        "semantic_usage": usage,
        "instruction": instruction,
        "binding": {
            "required": True,
            "priority": priority,
            "placement": "fixed",
            "on_unsupported": "fail",
            "slot": f"ref_image_{index}",
        },
    }


def build_package(
    prompt_file: Path,
    panel_id: str,
    project_root: Path,
    revision: int | None = None,
    continuity_tail: str | None = None,
    audio_reference: str | None = None,
    target_last_frame: str | None = None,
) -> dict[str, Any]:
    if panel_id not in PANEL_REFS:
        raise ValueError(f"Unknown panel {panel_id}")
    lean_prompt = _is_lean_prompt_file(prompt_file)
    prompt = _read_prompt(prompt_file, panel_id)
    if audio_reference:
        prompt = re.sub(
            r"audio_dialogue_policy:.*?(?=\n\n)",
            "audio_reference_policy: Audio 1 is the exact Mandarin dialogue reference for this clip. Follow Audio 1 for the spoken words, timing and delivery; visible characters may move their mouths naturally, but no spoken words may ever appear as subtitles, captions, karaoke, labels or other glyphs.",
            prompt,
            flags=re.DOTALL,
        )
        prompt = re.sub(
            r"<d>\s*\[zh\].*?</d>",
            "<Audio 1> exact Mandarin dialogue reference; audio-only, never visual text",
            prompt,
            flags=re.DOTALL,
        )
        prompt = re.sub(r"Speak exactly the five .*?readable marks\.", "Follow Audio 1 exactly and keep the image free of readable marks.", prompt, flags=re.DOTALL)
    if target_last_frame and panel_id == "P003":
        prompt = """subject_definitions:
  <Picture 1>: exact first-frame continuity from the preceding P002 tail; preserve the opening room axis and initial pose.
  <Picture 2>: exact approved final-frame target; preserve one canonical LaoBa alone at the sofa cushion.

summary: [reference generation + keyframe completion] Move from the supplied P002 opening frame through clean color-animation cuts and finish on the supplied LaoBa-only target frame.

retention_analysis:
  <Picture 1>: fully_preserved at the opening
  <Picture 2>: fully_preserved at the exact final frame

detailed_description: [Shot 1] Hold Picture 1 exactly at the opening with no added person. [Shot 2] At 01.400, use a clean full-color cut to one canonical XiaoPang alone in a plain hallway; no storyboard, line art or extra person. [Shot 3] At 03.200, use a clean full-color cut to one canonical XiaoMei alone at a plain entry door; no extra person. [Shot 4] At 05.200, use a restrained color-animation reaction beat with at most one XiaoPang and one QiDaGu, no group wide shot, gray-haired substitute or unlisted relative. [Shot 5] At 07.200, cut toward the sofa and resolve into Picture 2: exactly one canonical LaoBa alone, holding the cushion state. Picture 2 is the exact final frame; hold it unchanged through the end. Never render a storyboard page, contact sheet, white line-art field, subtitle, caption, UI, logo or readable glyph.

overall_soundscape: Hallway steps, door opening, room tone and a brief awkward pause.

non_diegetic_music: N/A"""
    elif target_last_frame and panel_id == "P004":
        prompt = """subject_definitions:
  <Picture 1>: exact first-frame continuity from the preceding P003 tail; preserve the single LaoBa pose and room axis.
  <Picture 2>: exact approved final-frame target; preserve one canonical LaoBa alone holding one phone.

summary: [reference generation + keyframe completion] Continue the sofa-cushion reveal with one canonical LaoBa and finish on the supplied LaoBa-only target frame.

retention_analysis:
  <Picture 1>: fully_preserved at the opening
  <Picture 2>: fully_preserved at the exact final frame

detailed_description: [Shot 1] Hold Picture 1 exactly as one LaoBa hand and cushion detail, with no other person. [Shot 2] At 01.200, cut to the same single canonical LaoBa in a clean medium close-up and lift one phone. [Shot 3] At 03.000, show the same single phone with only abstract color blocks and zero glyphs. [Shot 4] At 04.600, hold one LaoBa alone in a restrained proud reaction. [Shot 5] At 07.000, resolve into Picture 2: exactly one canonical LaoBa alone holding one phone, and hold Picture 2 unchanged through the final frame. No LaoMa, QiDaGu, XiaoPang, XiaoMei, JiuJiu, white-haired woman, rolling pin, duplicate body, storyboard, contact sheet, subtitle, caption, UI, logo or readable glyph.

overall_soundscape: Sofa fabric, one phone handling sound, quiet room tone and short pauses.

non_diegetic_music: N/A"""
    elif target_last_frame and panel_id == "P005":
        prompt = """subject_definitions:
  <Picture 1>: exact first-frame continuity from the preceding P004 tail; preserve the LaoBa phone pose and room axis.
  <Picture 2>: exact approved final-frame target; preserve one canonical LaoMa alone with one phone and one rolling pin.

summary: [reference generation + keyframe completion] Resolve the phone tug-of-war into a clean LaoMa-only final target.

retention_analysis:
  <Picture 1>: fully_preserved at the opening
  <Picture 2>: fully_preserved at the exact final frame

detailed_description: [Shot 1] Hold Picture 1 exactly with one LaoBa and one phone; no extra person. [Shot 2] At 01.200, cut to one canonical LaoMa entering the same clean living room; preserve long dark hair, pink top and cream apron. [Shot 3] At 03.000, show one controlled phone tug with only one LaoMa and one LaoBa, two complete bodies and no duplicate hands. [Shot 4] At 05.500, use a brief restrained reaction with the same two canonical people; no shouting crowd, no slap, no white-haired substitute or extra woman. [Shot 5] At 07.500, resolve into Picture 2: exactly one canonical LaoMa alone holding one phone and one rolling pin, and hold Picture 2 unchanged through the final frame. Never render a storyboard page, contact sheet, subtitle, caption, UI, logo or readable glyph.

overall_soundscape: Phone handling, fabric movement, two controlled voices and quiet room tone.

non_diegetic_music: N/A"""
    elif target_last_frame and panel_id == "P006":
        prompt = """subject_definitions:
  <Picture 1>: exact first-frame continuity from the preceding P005 tail; preserve the LaoMa phone/rolling-pin state.
  <Picture 2>: exact approved final-frame target; preserve one canonical BaDaYi alone with one phone and one handbag.

summary: [reference generation + keyframe completion] Move through the family argument and finish on the supplied BaDaYi-only target frame.

retention_analysis:
  <Picture 1>: fully_preserved at the opening
  <Picture 2>: fully_preserved at the exact final frame

detailed_description: [Shot 1] Hold Picture 1 exactly with one canonical LaoMa and no extra person. [Shot 2] At 01.200, show the same LaoMa alone in a clean color-animation close-up. [Shot 3] At 03.000, cut to one canonical BaDaYi entering with one phone and one gold handbag; preserve purple hair, black dress and cream stole. [Shot 4] At 05.500, use a restrained two-person phone beat with only one LaoMa and one BaDaYi; no male body, gray-haired substitute, extra woman, duplicate phone or rolling-pin strike. [Shot 5] At 07.500, resolve into Picture 2: exactly one canonical BaDaYi alone holding one phone, and hold Picture 2 unchanged through the final frame. Never render a storyboard page, contact sheet, subtitle, caption, UI, logo or readable glyph.

overall_soundscape: Quiet room tone, phone handling, footsteps and restrained argument voices.

non_diegetic_music: N/A"""
    elif target_last_frame and panel_id == "P007":
        prompt = """subject_definitions:
  <Picture 1>: exact first-frame continuity from the preceding P006 tail; preserve the BaDaYi pose and room axis.
  <Picture 2>: exact approved final-frame target; preserve one canonical BaDaYi and one canonical LaoBa completing one high-five.

summary: [reference generation + keyframe completion] Continue the family deal beat and finish on the supplied BaDaYi/LaoBa high-five target.

retention_analysis:
  <Picture 1>: fully_preserved at the opening
  <Picture 2>: fully_preserved at the exact final frame

detailed_description: [Shot 1] Hold Picture 1 exactly with one canonical BaDaYi and no extra person. [Shot 2] At 01.200, show BaDaYi alone with one phone and one handbag. [Shot 3] At 03.000, cut to one canonical LaoBa entering; preserve round face, moustache, brown rectangular glasses and checked shirt. [Shot 4] At 05.500, show exactly one BaDaYi and one LaoBa side by side with complete bodies and one clear hand gesture; no gray-haired substitute, extra relative, duplicate hand or second phone. [Shot 5] At 07.500, resolve into Picture 2: exactly one canonical BaDaYi and one canonical LaoBa completing one high-five, and hold Picture 2 unchanged through the final frame. Never render a storyboard page, contact sheet, subtitle, caption, UI, logo or readable glyph.

overall_soundscape: Phone handling, room tone, two conversational voices and one soft high-five sound.

non_diegetic_music: N/A"""
    elif target_last_frame and panel_id == "P010":
        prompt = """subject_definitions:
  <Picture 1>: exact first-frame continuity from the preceding P009 tail; preserve the LaoBa/XiaoPang room axis.
  <Picture 2>: exact approved final-frame target; preserve one canonical XiaoPang alone holding one closed blank laptop.

summary: [reference generation + keyframe completion] XiaoPang carries one closed laptop through the living room and finishes on the supplied XiaoPang-only target frame.

retention_analysis:
  <Picture 1>: fully_preserved at the opening
  <Picture 2>: fully_preserved at the exact final frame

detailed_description: [Shot 1] Hold Picture 1 exactly with LaoBa and XiaoPang in the living-room axis. [Shot 2] At 01.200, follow one canonical XiaoPang carrying exactly one closed plain silver laptop toward the bedroom. [Shot 3] At 03.000, show a close view of the same closed silver laptop with a smooth blank outer shell. [Shot 4] At 05.200, return to one XiaoPang seated in the same warm living room and speaking with natural mouth movement; keep the background as the same plain room. [Shot 5] At 07.400, resolve into Picture 2: exactly one canonical XiaoPang alone holding one closed blank laptop, and hold Picture 2 unchanged through the final frame. Keep the cast to the named people only and keep all surfaces blank and unmarked.

overall_soundscape: Footsteps, laptop handling, quiet room tone and restrained voices.

non_diegetic_music: N/A"""
    elif target_last_frame and panel_id == "P012":
        prompt = """subject_definitions:
  <Picture 1>: exact first-frame continuity from the preceding P011 tail; preserve the quiet living-room axis.
  <Picture 2>: exact approved final-frame target; preserve one canonical LaoBa holding exactly two blank phones.

summary: [reference generation + keyframe completion] LaoBa calmly reveals two blank phones and finishes on the supplied LaoBa-only target frame.

retention_analysis:
  <Picture 1>: fully_preserved at the opening
  <Picture 2>: fully_preserved at the exact final frame

dialogue_script_audio_only: 其实……；我早就知道了；我只是假装上钩。Speak these three lines exactly in order as audio only; never put their characters into the image.

detailed_description: [Shot 1] Hold Picture 1 briefly with the quiet room axis. [Shot 2] At 01.200, cut cleanly to one canonical LaoBa lifting a second phone from under the cushion. [Shot 3] At 03.200, show the second phone as a smooth blank dark rectangle. [Shot 4] At 04.800, show one canonical LaoBa holding exactly two separate phones with natural hand anatomy. [Shot 5] At 07.400, resolve into Picture 2: exactly one canonical LaoBa holding exactly two blank phones, and hold Picture 2 unchanged through the final frame. Keep the cast to the named people only and keep both phone faces blank and unmarked.

overall_soundscape: Cushion fabric, two phones handled, reveal pause, calm voice and stunned silence.

non_diegetic_music: N/A"""
    elif target_last_frame and panel_id == "P013":
        prompt = """subject_definitions:
  <Picture 1>: exact first-frame continuity from the preceding P012 tail; preserve one LaoBa and the two-phone hand state.
  <Picture 2>: exact approved final-frame target; preserve one canonical LaoBa holding exactly two blank phones.

summary: [reference generation + keyframe completion] LaoBa calmly explains the situation while holding two blank phones and finishes on the supplied LaoBa-only target frame.

retention_analysis:
  <Picture 1>: fully_preserved at the opening
  <Picture 2>: fully_preserved at the exact final frame

dialogue_script_audio_only: 骗子让我转十万，我用 AI 模拟了一笔假流水；IP 也锁定了；警察已经去了。Speak these three lines exactly in order as audio only; never put their characters into the image.

detailed_description: [Shot 1] Hold Picture 1 exactly as one canonical LaoBa in a tight medium close-up. [Shot 2] At 02.000, keep the same LaoBa and two phones while he makes one small explanatory gesture. [Shot 3] At 04.000, keep the background to plain sofa upholstery and one matte beige wall. [Shot 4] At 06.000, keep both phones as smooth blank light surfaces while LaoBa continues speaking. [Shot 5] At 08.000, resolve into Picture 2: exactly one canonical LaoBa holding exactly two blank phones, and hold Picture 2 unchanged through the final frame. The frame has only the named person, the two phones and the plain room; all surfaces remain blank and unmarked.

overall_soundscape: Small phone clicks, calm explanation, restrained pause and room silence.

non_diegetic_music: N/A"""
    elif target_last_frame and panel_id == "P014":
        prompt = """subject_definitions:
  <Picture 1>: exact first-frame continuity from the preceding P013 tail; preserve one LaoBa and the two-phone state.
  <Picture 2>: exact approved final-frame target; preserve one canonical LaoBa holding the same two blank phones.

summary: [reference generation + keyframe completion] LaoBa and JiuJiu take turns speaking in clean color-animation cuts, then the clip returns to the supplied LaoBa-only target frame.

retention_analysis:
  <Picture 1>: fully_preserved at the opening
  <Picture 2>: fully_preserved at the exact final frame

audio_dialogue_note: Use the supplied replacement audio; natural mouth movement only, never visual words.

detailed_description: [Shot 1] Hold Picture 1 with one canonical LaoBa in the warm sofa close-up. [Shot 2] At 03.000, make one clean ordinary color-animation cut to exactly one complete adult man matching the supplied JiuJiu card: square face, short black hair, black rectangular glasses, dark navy suit, white shirt and one briefcase. The background is only a flat matte beige wall and a plain sofa, with no decoration. [Shot 3] At 05.000, make one clean cut back to exactly one LaoBa in the same sofa close-up. [Shot 4] At 08.100, make one clean cut to exactly one complete adult JiuJiu man with the same square face, black glasses, navy suit and briefcase, showing a restrained shocked reaction against only the flat matte beige wall and plain sofa. [Shot 5] At 09.200, make one clean cut back to Picture 2: exactly one canonical LaoBa holding two blank phones, and hold Picture 2 unchanged through the final frame. Keep only the named speaker in each shot, with stable edges and no transition ghosting, extra doorway, appliance, window, plant, painting, poster, frame, sign, writing, added person, prop, label or mark.

overall_soundscape: Quiet room, brief movement, one confession, dry pause and a short reaction.

non_diegetic_music: N/A"""
    elif target_last_frame and panel_id == "P015":
        prompt = """subject_definitions:
  <Picture 1>: exact first-frame continuity from the preceding P014 tail.
  <Picture 2>: exact approved final-frame target; copy this supplied frame exactly.

summary: [reference generation + keyframe completion] One clean hard cut from Picture 1 to Picture 2, then a still hold.

retention_analysis:
  <Picture 1>: fully_preserved at the opening
  <Picture 2>: fully_preserved at the exact final frame

audio_dialogue_note: Use the supplied replacement audio; natural mouth movement only, never visual words.

detailed_description: [Shot 1] At the first frame, make one immediate ordinary hard cut from Picture 1 to Picture 2. [Shot 2] From 00.000 through the end, hold Picture 2 unchanged except for a very thin smoke curl and a subtle blink. Do not invent any transition action, hand prop, flame, lighter, phone, extra person, text, label or mark. Picture 2 is the exact final image and must remain unchanged through the final frame.

overall_soundscape: Soft room tone, one calm line and a clean quiet ending.

non_diegetic_music: N/A"""
    elif target_last_frame and panel_id == "P016":
        prompt = """subject_definitions:
  <Picture 1>: exact first-frame continuity from the preceding P015 tail.
  <Picture 2>: exact approved final-frame target; copy this supplied frame exactly.

summary: [reference generation + keyframe completion] Clean hard cuts between LaoMa and LaoBa, then a still hold on the supplied LaoBa target frame.

retention_analysis:
  <Picture 1>: fully_preserved at the opening
  <Picture 2>: fully_preserved at the exact final frame

audio_dialogue_note: Use the supplied replacement audio; natural mouth movement only, never visual words.

detailed_description: [Shot 1] Hold Picture 1 for a short opening beat. [Shot 2] At 00.800, make one clean cut to exactly one canonical LaoMa matching the supplied card: long dark hair, pink top and cream apron; plain sofa and matte wall only. [Shot 3] At 03.000, make one clean cut to exactly one canonical LaoBa in a plain sofa close-up. [Shot 4] At 06.500, make one clean cut to exactly one LaoMa alone raising one rolling pin without contact. [Shot 5] At 08.800, make one clean cut to Picture 2 and hold it unchanged through the final frame. Keep every background free of screens, appliances, framed art, writing and extra props; no added person, injury, duplicate or readable mark.

overall_soundscape: Low natural voices, light laughter and quiet room ambience.

non_diegetic_music: N/A"""
    if lean_prompt:
        prompt = LEAN_AUDIO_ONLY_FIREWALL + "\n\n" + prompt
        if panel_id in LEAN_IDENTITY_FIREWALLS:
            prompt += "\n\n" + LEAN_IDENTITY_FIREWALLS[panel_id]
    if not lean_prompt and panel_id in PANEL_SHOT_REWRITES:
        soundscape_match = re.search(
            r"overall_soundscape:.*?(?:\n\nnon_diegetic_music:.*)?$",
            prompt,
            flags=re.DOTALL,
        )
        prompt = PANEL_SHOT_REWRITES[panel_id]
        if soundscape_match:
            prompt += "\n\n" + soundscape_match.group(0).strip()
    if not lean_prompt and panel_id == "P016":
        prompt = prompt.replace(
            "overall_soundscape: Low voice, sudden loud reply, rolling-pin lift, light laughter growing into family laughter and room ambience.",
            "overall_soundscape: Low natural voices, light laughter and quiet room ambience.",
        )
    if not lean_prompt and panel_id == "P018":
        prompt = prompt.replace(
            "overall_soundscape: Soft room tone, one calm Chinese final line, light clothing and cigarette movement, sparse icon chimes and a clean quiet ending.",
            "overall_soundscape: Soft room tone, one calm Chinese final line, light clothing and cigarette movement, and a clean quiet ending.",
        )
    if not lean_prompt:
        prompt = re.sub(
            r"<d>\s*\[zh\].*?</d>",
            "<d>[zh] natural Mandarin voice only; no transcript or visible words</d>",
            prompt,
            flags=re.DOTALL,
        )
        if panel_id != "P001":
            prompt += "\n\n" + NO_TRANSCRIPT_MODE
        prompt += "\n\n" + (H3_TEXT_FIREWALL_MINIMAL if panel_id in {"P016", "P017", "P018"} else H3_TEXT_FIREWALL)
        if panel_id in PANEL_IDENTITY_FIREWALLS:
            prompt += "\n\n" + PANEL_IDENTITY_FIREWALLS[panel_id]
    refs = list(PANEL_REFS[panel_id])
    if target_last_frame and panel_id in {"P003", "P004", "P005", "P006", "P007", "P010", "P012", "P013", "P014", "P015", "P016"}:
        refs = [refs[0], target_last_frame.replace("\\", "/")]
    if target_last_frame and panel_id == "P014":
        refs.append("characters/jiujiu-character-card.png")
    if target_last_frame and panel_id == "P016":
        refs.append("panels/P016/laoma-clean-reference-v3.png")
        refs.append("characters/laoma-character-card.png")
        refs.append("characters/laoba-character-card.png")
    elif lean_prompt and panel_id == "P003":
        refs = [refs[0], "characters/xiaopang-character-card.png", "characters/xiaomei-character-card.png", "characters/laoba-character-card.png"]
    if continuity_tail and panel_id != "P001":
        refs[0] = continuity_tail.replace("\\", "/")
    if audio_reference:
        refs.append(audio_reference.replace("\\", "/"))
    for uri in refs:
        source = project_root / uri
        if not source.is_file():
            raise FileNotFoundError(f"Missing package asset for {panel_id}: {source}")
    sequence = _panel_number(panel_id)
    previous = f"P{sequence - 1:03d}" if sequence > 1 else None
    assets = [_asset(uri) for uri in refs]
    references = [_reference(uri, index) for index, uri in enumerate(refs)]
    if target_last_frame and panel_id in {"P003", "P004", "P005", "P006", "P007", "P010", "P012", "P013", "P014", "P015", "P016"}:
        references[0]["semantic_usage"] = "continuity.first_frame_lock"
        references[0]["instruction"] = "Picture 1; exact first-frame lock from the accepted P002 dialogue-locked tail."
        references[0]["binding"].update({"placement": "first", "slot": "first_frame"})
        references[1]["semantic_usage"] = "continuity.target_keyframe"
        references[1]["instruction"] = "Picture 2; exact approved LaoBa-only target frame. Preserve it unchanged as the final frame."
        references[1]["binding"].update({"placement": "last", "slot": "last_frame", "priority": 109})
    if panel_id == "P017":
        references[0]["semantic_usage"] = "continuity.first_frame_lock"
        references[0]["instruction"] = "Picture 1; exact first-frame lock from the accepted P016 real tail."
        references[0]["binding"].update({"placement": "first", "slot": "first_frame"})
        references[1]["semantic_usage"] = "continuity.target_keyframe"
        references[1]["instruction"] = "Picture 2; exact clean four-person final-frame lock extracted from the accepted portion of r059. Preserve the full frame and all four identities exactly."
        references[1]["binding"].update({"placement": "last", "slot": "last_frame", "priority": 109})
    if panel_id == "P018":
        references[0]["semantic_usage"] = "continuity.first_frame_lock"
        references[0]["instruction"] = "Picture 1; exact first-frame lock from the accepted P017 real tail."
        references[0]["binding"].update({"placement": "first", "slot": "first_frame"})
        references[1]["semantic_usage"] = "continuity.target_keyframe"
        references[1]["instruction"] = "Picture 2; exact clean LaoBa-with-one-cigarette final-frame lock from accepted P015."
        references[1]["binding"].update({"placement": "last", "slot": "last_frame", "priority": 109})
    story_version = "prompt-v3-dialogue-locked" if lean_prompt else "prompt-v2"
    package_suffix = "v3" if lean_prompt else "v2"
    prompt_list_name = prompt_file.name
    project_title = f"爸妈听我解释｜episode-001｜{package_suffix.upper()}"
    clip: dict[str, Any] = {
        "clip_id": f"panel-{sequence:03d}",
        "sequence": sequence,
        "duration_ms": 10_000,
        "generation": {
            "operation": "video.first_last_frame" if panel_id in {"P017", "P018"} or (panel_id in {"P003", "P004", "P005", "P006", "P007", "P010", "P012", "P013", "P014", "P015", "P016"} and target_last_frame) else "video.reference_to_video",
            "prompt": prompt,
            "requirements": {
                "aspect_ratio": "16:9",
                "megapixels": 0.6,
                "fps": 24,
                "native_audio": "allowed",
                "reference_image_size": "match",
            },
            "references": references,
        },
        "audio": {"native_audio": "preserve"},
        "subtitles": {"cues": []},
        "source_context": {
            "skill": "zero-to-story",
            "creative_unit": "panel",
            "story_version": story_version,
            "panel_id": panel_id,
            "prompt_tier": "precise",
            "execution_beat_count": 4 if panel_id == "P001" else (3 if panel_id in {"P017", "P018"} else 5),
            "continuity_role": "initial_panel" if previous is None else "real_last_frame_handoff",
        },
    }
    if panel_id == "P002":
        clip["generation"]["seed"] = 2002
    elif panel_id == "P003":
        clip["generation"]["seed"] = 30015
    elif panel_id == "P007":
        clip["generation"]["seed"] = 7007
    elif panel_id == "P008":
        clip["generation"]["seed"] = 8011
    elif panel_id == "P009":
        clip["generation"]["seed"] = 9009
    elif panel_id == "P010":
        clip["generation"]["seed"] = 10010
    elif panel_id == "P012":
        clip["generation"]["seed"] = 12012
    elif panel_id == "P013":
        clip["generation"]["seed"] = 13013
    elif panel_id == "P014":
        clip["generation"]["seed"] = 14015
    elif panel_id == "P015":
        clip["generation"]["seed"] = 15017
    elif panel_id == "P016":
        clip["generation"]["seed"] = 16018
    if previous is not None:
        clip["source_context"]["previous_panel"] = previous
        clip["source_context"]["last_frame_lock"] = refs[0]
    return {
        "schema": "lfo.video-execution.v1",
        "package_id": f"ba-ma-ting-wo-jie-shi-episode-001-{package_suffix}",
        "revision": revision or sequence,
        "project": {
            "title": project_title,
            "project_id": "爸妈听我解释-episode-001",
            "locale": "zh-CN",
        },
        "assets": assets,
        "clips": [clip],
        "output": {
            "fps": 24,
            "subtitles_mode": "both",
            "directory": f"episode-001-{package_suffix}-panels",
        },
        "timeline": {
            "total_duration_ms": 10_000,
            "transition": "cut",
            "panel_order": [panel_id],
        },
        "approval": {
            "approved_by": "user",
            "notes": f"提示词版本 {story_version}；每段完成后必须检查角色身份、对白内容和文字入画，再提取真实末帧进入下一段。",
        },
        "extensions": {
            "zero-to-story": {
                "storyboard": "storyboard_brief.md",
                "prompt_list": prompt_list_name,
                "story_version": story_version,
                "last_frame_lock_policy": "P002+ uses the new real extracted last frame as ref_image_0",
                "resolution_policy": "generation megapixels=0.6; preserve provider output; skip media.normalize",
                "verification_policy": "after each panel inspect identity continuity and baked readable text before handoff",
            }
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("panel", choices=sorted(PANEL_REFS))
    parser.add_argument("--prompt-file", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--revision", type=int, default=None)
    parser.add_argument("--continuity-tail", type=str, default=None)
    parser.add_argument("--audio-reference", type=str, default=None)
    parser.add_argument("--target-last-frame", type=str, default=None)
    args = parser.parse_args()
    package = build_package(
        args.prompt_file.resolve(),
        args.panel,
        args.project_root.resolve(),
        args.revision,
        args.continuity_tail,
        args.audio_reference,
        args.target_last_frame,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"panel": args.panel, "output": str(args.output.resolve()), "references": len(package["clips"][0]["generation"]["references"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
