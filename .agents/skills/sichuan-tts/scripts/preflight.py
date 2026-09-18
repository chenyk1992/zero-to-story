"""Read-only ComfyUI node and local model clues; never submits or downloads."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.request import urlopen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default=os.environ.get('LFO_COMFY_BASE_URL', 'http://127.0.0.1:8188'))
    parser.add_argument('--comfy-root', type=Path)
    parser.add_argument('--model-root', type=Path, action='append', default=[])
    args = parser.parse_args()
    report: dict = {'read_only': True, 'generation_verified': False, 'canvas_audio_verified': False}
    issues = []
    for endpoint in ('system_stats', 'object_info'):
        try:
            with urlopen(args.base_url.rstrip('/') + '/' + endpoint, timeout=10) as response:
                data = json.load(response)
            if endpoint == 'system_stats':
                report['runtime'] = {key: data.get('system', {}).get(key) for key in ('python_version', 'pytorch_version', 'comfyui_version')}
                report['devices'] = data.get('devices', [])
            else:
                node = data.get('FB_Qwen3TTSCustomVoice')
                report['custom_voice_node'] = node
                report['audio_save_nodes'] = [key for key in data if key.startswith('SaveAudio')]
                if node is None:
                    issues.append('FB_Qwen3TTSCustomVoice is not loaded')
                else:
                    fields = {**node.get('input', {}).get('required', {}), **node.get('input', {}).get('optional', {})}
                    for key, value in {'speaker': 'Eric', 'model_choice': '1.7B', 'language': 'Chinese', 'precision': 'bf16', 'attention': 'sdpa'}.items():
                        choices = fields.get(key, [None])[0]
                        if not isinstance(choices, list) or value not in choices:
                            issues.append(f'{key} does not advertise {value}')
                    if 'AUDIO' not in node.get('output', []):
                        issues.append('CustomVoice does not advertise AUDIO output')
                if not report['audio_save_nodes']:
                    issues.append('No SaveAudio node is advertised')
        except (OSError, ValueError) as error:
            issues.append(f'{endpoint}: {error}')
    roots = list(args.model_root)
    if args.comfy_root:
        report['plugin_directory_exists'] = (args.comfy_root / 'custom_nodes' / 'ComfyUI-Qwen-TTS').is_dir()
        roots.append(args.comfy_root / 'models' / 'qwen-tts')
    report['model_directory_clues'] = {}
    for name in ('Qwen3-TTS-12Hz-1.7B-CustomVoice', 'Qwen3-TTS-Tokenizer-12Hz'):
        candidates = [candidate for root in roots for candidate in (root / name, root / 'Qwen' / name)]
        report['model_directory_clues'][name] = [str(path) for path in candidates if path.is_dir()]
    report['model_note'] = 'Directory presence is not weight integrity or successful loading; custom paths and caches may be elsewhere.'
    report['issues'] = issues
    report['node_schema_ready'] = not issues
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if issues else 0


if __name__ == '__main__':
    raise SystemExit(main())
