import json
with open(r'E:\ideaProjects\zero-to-story\workspace\我今天不上班\chapter_01\storyboard.decomposed.json', encoding='utf-8') as f:
    d = json.load(f)
print(f"project: {d['project']['title']}")
print(f"novel: {d['project'].get('novel_id')} / chapter: {d['project'].get('chapter_id')}")
print(f"scenes: {len(d['scenes'])}")
for s in d['scenes']:
    print(f"  - {s['scene_id']}: {s['name']}")
print(f"props: {len(d['props'])}")
for p in d['props']:
    print(f"  - {p['prop_id']}: {p['name']}")
print(f"shots: {len(d['shots'])}")
for s in d['shots']:
    cont = s.get('continuity', {})
    hint = s.get('generation_hint', {})
    print(f"  - {s['shot_id']} [{hint.get('preferred_mode')}] scene={s['scene_id']} dur={s['desired_duration_ms']}ms")
    print(f"      desc: {s['description'][:80]}")
    print(f"      cam:  {s['camera']['shot_size']} / {s['camera']['angle']} / {s['camera']['movement']}")
    if s.get('characters'):
        for c in s['characters']:
            print(f"      char: {c['character_id']} ({c['action']})")
