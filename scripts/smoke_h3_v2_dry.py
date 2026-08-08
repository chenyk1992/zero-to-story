"""Dry-run: just submit each workflow and capture the immediate response.
Doesn't wait for completion — just verifies the workflow is accepted by ComfyUI
or sees what error it returns.
"""
import json
import sys
import time
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lfo.comfy.client import ComfyApiClient

WORKFLOW_DIR = PROJECT_ROOT / "tests" / "fixtures" / "workflows"
COMFY_URL = "http://127.0.0.1:8188"

# Load each workflow
for name in ["h3_standard_t2v", "h3_standard_i2v", "h3_standard_r2v"]:
    wf = json.loads((WORKFLOW_DIR / f"{name}.json").read_text(encoding="utf-8"))
    print(f"\n{'='*60}")
    print(f"Submitting: {name}")
    print(f"{'='*60}")
    print(f"  node count: {len(wf)}")
    client = ComfyApiClient(base_url=COMFY_URL)
    client_id = f"smoke-{uuid.uuid4().hex[:8]}"
    try:
        r = client.submit_prompt(wf, client_id)
        print(f"  ✓ Accepted: {r}")
    except Exception as e:
        print(f"  ✗ Rejected: {e}")
        # Try to get the response body
        if hasattr(e, 'response'):
            try:
                print(f"  body: {e.response.text[:1000]}")
            except:
                pass
