import json, sys, time, urllib.request

BASE = "http://127.0.0.1:8765"
RID = sys.argv[1]
MAX = int(sys.argv[2]) if len(sys.argv) > 2 else 900
START = time.time()

for i in range(MAX):
    try:
        r = json.loads(urllib.request.urlopen(BASE + "/api/runs/" + RID, timeout=30).read().decode())
    except Exception as e:
        print("[%s +%ds] POLL-ERR %s" % (time.strftime("%H:%M:%S", time.localtime(START)), int(time.time() - START), e), flush=True)
        time.sleep(10)
        continue
    st, sg, er = r.get("status"), r.get("stage"), r.get("error")
    el = int(time.time() - START)
    if i % 3 == 0 or st != "running":
        print("[%s +%dm%02ds] %s/%s err=%s" % (
            time.strftime("%H:%M:%S", time.localtime(START)), el // 60, el % 60, st, sg, er), flush=True)
    if st in ("succeeded", "failed", "cancelled", "unknown"):
        print("FINAL: " + json.dumps({k: r.get(k) for k in (
            "status", "stage", "error", "outputs", "provider_task_id")}, ensure_ascii=False)[:3000], flush=True)
        break
    time.sleep(10)
else:
    print("POLLER-TIMEOUT after %d polls" % MAX, flush=True)
