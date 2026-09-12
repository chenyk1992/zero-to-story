"""Poll canvas run status until terminal state. Usage: python p004_poll.py <run_id>"""
import json, sys, time, urllib.request

RID = sys.argv[1] if len(sys.argv) > 1 else "91636a6f-4aad-4318-851e-bb8540933918"
TERMINAL = {"succeeded", "failed", "rejected", "cancelled"}

for i in range(60):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/api/runs?summary=1", timeout=10) as r:
            runs = json.load(r)["runs"]
        me = [x for x in runs if x.get("id") == RID]
        if me:
            s = me[0].get("status")
            st = me[0].get("stage", "")
            print(f"[{i*30}s] {s} {st}", flush=True)
            if s in TERMINAL:
                print(json.dumps(me[0], ensure_ascii=False), flush=True)
                break
        else:
            print(f"[{i*30}s] run not in summary list", flush=True)
    except Exception as e:
        print(f"[{i*30}s] poll error: {e}", flush=True)
    time.sleep(30)
