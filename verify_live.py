"""Verify real workflow files against live ComfyUI."""
import sys

sys.path.insert(0, '.')

from pathlib import Path

from lfo.comfy.client import ComfyApiClient
from lfo.core.workflow_registry import WorkflowRegistry

wf_dir = Path(r'C:\Users\Administrator\Documents\comfy\ComfyUI\user\workflows')
reg = WorkflowRegistry(wf_dir)

# Register all
results = reg.register_all()
for wf_id, status in results.items():
    m = reg.get_manifest(wf_id)
    print(f'{wf_id}: register={status}, hash={m.workflow_hash[:16]}..., '
          f'algo={m.workflow_hash_algorithm}, production_ready={m.production_ready}')

# Validate
for wf_id in results:
    v = reg.validate_workflow(wf_id)
    print(f'{wf_id}: valid={v["valid"]}, level={v["level"]}')

# Runtime compatibility (live)
client = ComfyApiClient()
for wf_id in results:
    r = reg.check_runtime_compatibility(wf_id, comfy_client=client)
    print(f'{wf_id}: compatible={r["compatible"]}, level={r["level"]}, checks={len(r["checks"])}')
    for c in r['checks']:
        if c['status'] != 'pass':
            print(f'  !! {c["name"]}: {c["message"]}')
