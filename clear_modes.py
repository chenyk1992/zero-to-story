"""Clear generation_hint.preferred_mode to let prompt_service auto-decide R2V."""
import json

path = 'workspace/我今天不上班/chapter_01/storyboard.decomposed.json'
data = json.load(open(path, encoding='utf-8'))
for s in data.get('shots', []):
    s['generation_hint'] = {
        'preferred_family': '',
        'preferred_mode': '',
        'notes': 'auto-decide R2V based on character ref',
    }
    print('Cleared preferred_mode for', s['shot_id'])
json.dump(data, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('Saved')
