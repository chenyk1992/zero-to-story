# -*- coding: utf-8 -*-
"""P004 (run 91636a6f) claim-review + review submit (INCONCLUSIVE)."""
import json, urllib.request

BASE = "http://127.0.0.1:8765"
RID = "91636a6f-4aad-4318-851e-bb8540933918"
OUT = r"E:\ideaProjects\zero-to-story\workspace\projects\861ebeb3-0381-42fb-819a-c7b6ad8fecf0\outputs\91636a6f-4aad-4318-851e-bb8540933918\video_00001_.mp4"

def post(path, body):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "X-Canvas-Request": "1",
                 "Origin": "http://127.0.0.1:8765"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)

claim = post(f"/api/runs/{RID}/claim-review", {})
TOKEN = claim["owner_token"]
print("claimed, token:", TOKEN[:8], "...")

body = {
    "owner_token": TOKEN,
    "decision": "INCONCLUSIVE",
    "output_path": OUT,
    "evidence": [
        "切点 frame#114 @4.708s 单帧帧差 51.92、无 morph：硬切成立（早于预期 0.292s，P003 同量级可接受）",
        "Shot1 隔玻璃构图锁定：门框黑柱前景 + 教练背影俯身 + 沈默右缘近相机虚焦头肩（zoom_shot1_full.png）",
        "Shot2 室内无门框：教练画面左侧正对俯身按烟入圆缸、沈默右侧背对低头不露正脸（zoom_shot2_full.png）",
        "L 区（教练）5.0-6.5s 帧差 1.4-1.8 = 按烟动作落实；R 区（沈默）全程 ≤0.49 = 背对静止纪律",
        "11.9-14.0s 人物区静止（R 区 0.04-0.18），whole 残差 mean 0.41 为回放屏持续播放（设计内：屏动到片尾）",
        "两镜屏幕均抽象光影无可读文字；队服无新增文字（zoom_shot1_screen / zoom_shot2_screen）",
        "音频实测四段响声 5.9-6.4 / 7.6-8.6 / 10.1-10.9 / 12.0-13.9s vs 预期两段（D005@6.8 D006@8.8）；seg4 侵占留白区",
        "D007 无声满足（11.0-11.9s RMS -86~-92dBFS）但唇动仅 1-2px 级若有若无（sheet_lip_zoom4x.png），EV009 可视化极弱",
        "陶瓷轻响 5.2-5.8s 弱峰（-55~-67dBFS）；门闷响 0.8s 弱峰 -53.8dBFS（预期 0.3s 明显闷响）",
        "无音乐床；14.0-14.375s 收尾静默",
    ],
    "end_state": {
        "situation": "教练已问出问题（发声内容待耳听），沈默低头无声",
        "visible": "教练正对沈默、按烟已完成，沈默右前景背对低头，嘴唇已合上",
        "hand": "沈默双手静止",
        "props": "烟已按灭在烟灰缸；桌面烟灰缸原位",
        "audio": "12.0-13.9s 出现人声响度额外声段（侵占留白区，性质待耳听），14.0s 后静默",
        "blocking": "音频结构四段 vs 预期两段 + D007 唇动弱可视化，待 master 耳听定夺 ACCEPT/REJECT（档案：review/P004_run_91636a6f/acceptance.md + 四段 seg wav）",
    },
    "unverified": [
        "D005 发声内容（疑似后移至 7.6-8.6s）",
        "D006 发声内容（疑似后移至 10.1-10.9s）",
        "D007 唇动可视化强度（若有若无，1-2px 级）",
        "12.0-13.9s 额外声段性质（语音或呼吸/动作声）",
    ],
}
resp = post(f"/api/runs/{RID}/review", body)
print("review status:", resp.get("status"), "| decision:", resp.get("decision"))
print("output_sha256:", resp.get("output_sha256"))
