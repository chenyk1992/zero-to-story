"""Quick doctor diagnostic — print failed checks."""
import sys
sys.path.insert(0, 'src')
from lfo.cli.doctor_cmd import cmd_doctor
import json

result = cmd_doctor(machine_id='local-windows')
print(f"passed={result['passed']} failed={result['failed']} skipped={result['skipped']} blockers={result['blockers']}")
for r in result['results']:
    if r['status'] == 'failed':
        print(f"  [{r['severity']}] {r['check_id']}: {r['message']}")
