# -*- coding: utf-8 -*-
"""P005 (run d9d786c5) claim-review + review submit (INCONCLUSIVE)."""
import json, urllib.request

BASE = "http://127.0.0.1:8765"
RID = "d9d786c5-0a12-4498-9d6c-82a79da7a742"
OUT = r"E:\ideaProjects\zero-to-story\workspace\projects\861ebeb3-0381-42fb-819a-c7b6ad8fecf0\outputs\d9d786c5-0a12-4498-9d6c-82a79da7a742\video_00001_.mp4"

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
        "I2V 首帧承接成立：首帧 diff [2.63, 2.63, 2.92]（P004 末帧 f_0345 为首帧资产，承接质量与 P003 同量级）",
        "单镜 fixed 纪律：静止时刻三向 ±3px 位移残差 7.6–8.4 相等 = 无平移无推近，构图全程不变（禁切镜/禁推近约束满足）",
        "教练动作链：起身 1.75-3.0s（提示词写静止，记偏差）→ 叹气 4.3-4.8s → 摆手 5.4s（sheet_coach_actions 挥臂清晰），后段站定",
        "母亲反光 EV010 visible_proof 落实：zoom_end_full 玻璃门区深色外套女性侧影、发髻、抬手擦眼，不露正脸、不与门接触（硬约束全满足）",
        "沈默区纪律：SHEN 区全程帧差 ≤0.6，背对侧立静止",
        "末态冻结：12.0-14.0s 全幅帧差 max 1.15 / mean 0.31",
        "无可读文字：zoom_screen_6s 屏幕区模糊光影无字",
        "D008 主语音段实测 7.6-8.7s（-10.5~-16 dBFS）vs 预期 ~5.9s，后移 ~1.7s，内容待耳听",
        "音频五段结构静→弱动作声(2.5-3.5s, -29.5)→叹息/动作声(5.0-5.8s, -13.3, 与摆手同步)→台词(7.6-8.7s)→钢琴雨(9.5-10.9s, -22)→尾音缓降，无侵占留白硬伤",
        "rack focus（B025）弱执行：coach_std 42.3-43.1 平坦 / door_std 32.2-36.0 微升，锐度交换数值不显，记偏差",
    ],
    "end_state": {
        "situation": "教练已说出 D008（发声内容待耳听），沈默背对侧立静止，母亲反光擦眼可见",
        "visible": "同镜同构图：教练站定画面左、沈默右侧背对，玻璃门区母亲深色外套侧影抬手擦眼（不露正脸）",
        "hand": "教练双手垂落站定，沈默双手静止",
        "props": "烟灰缸原位（P004 按灭的烟已入缸）；场景陈设不变",
        "audio": "11.0-14.0s 钢琴雨尾音 -27→-43 缓降收场，无侵占留白",
        "blocking": "D008 内容 + 5.0-5.8s 声段性质 + 钢琴音色待 master 耳听；画面侧核心全过（含 EV010 反光），倾向 ACCEPT 除非耳听发现内容错误（档案：review/P005_run_d9d786c5/acceptance.md）",
    },
    "unverified": [
        "D008 发声内容（实测 7.6-8.7s，后移 ~1.7s）",
        "5.0-5.8s -13.3dB 声段性质（叹息 vs 摆手衣料声 vs 额外发声）",
        "9.5s 起声段是否为钢琴单音+雨声（音色待耳听）",
        "rack focus 视觉可感知度（数值不显，目视不确定）",
    ],
}
resp = post(f"/api/runs/{RID}/review", body)
print("review status:", resp.get("status"), "| decision:", resp.get("decision"))
print("output_sha256:", resp.get("output_sha256"))
