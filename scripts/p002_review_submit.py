# -*- coding: utf-8 -*-
"""Submit P002 (run e95dd7ce) INCONCLUSIVE review to canvas."""
import json, sys, urllib.request

sys.stdout.reconfigure(encoding='utf-8')
RID = "e95dd7ce-d4ae-482c-b320-96eef1b06d05"
TOKEN = "c88561a9e6e349669e5c96cacd27ee8b"

body = {
    "owner_token": TOKEN,
    "decision": "INCONCLUSIVE",
    "output_path": r"E:\ideaProjects\zero-to-story\workspace\projects\861ebeb3-0381-42fb-819a-c7b6ad8fecf0\outputs\e95dd7ce-d4ae-482c-b320-96eef1b06d05\video_00001_.mp4",
    "evidence": [
        "硬切1 一帧完成：4.958s 中心亮度 5.6（黑）→ 5.000s 101.1（灰屏+反光），无叠化无中间值（实测 ~4.98s，规格 4.6s，+0.4s）",
        "硬切2 一帧落地：8.833s 反光特写 → 8.875s 完整全景构图，无过渡运镜（规格 8.8s ✓）",
        "Shot1：中屏战斗画面持续（0.25s 爆炸→0.9s 黑影落地→2.5–4.2s 帽檐逼近）；黑影纯剪影无五官（3.5s 放大）；前景键盘鼠标无手；push-in 在场",
        "Shot2 静止：5.2/6.8/8.4s 区域帧差 2.3–3.8≈0；灰屏+反光脸；屏幕无文字",
        "Shot3 全景：恰 5 块大屏四动一静（列差分中段 1.1 vs 两侧 2.1–5.6）；四空椅仅中间坐人；9.5→11.5s 无人移动（列差分 ≤1.9）；背影静止（帧差 1.0–1.2）",
        "音频：两段解说按序在槽（~1.9–3.8s 战斗段、~5.1–8.5s 灰屏段，句尾距切点 2 约 0.35s）；静默口袋 3.8–5.1s；尾床低电平（8.9–12.25s，约为语音 1/10）",
        "偏差不阻断：技能音效 @0.3s 未检出；弦乐床整段缺失（无骤停拍）；切点 1 +0.4s；肩部伪文字标不可读（板审查先例合规）",
    ],
    "end_state": {
        "video": "workspace/projects/861ebeb3-0381-42fb-819a-c7b6ad8fecf0/outputs/e95dd7ce-d4ae-482c-b320-96eef1b06d05/video_00001_.mp4",
        "duration_ms": 12250,
        "fps": 24,
        "resolution": "480x864",
        "has_audio": True,
        "final_frame": "12.25s：全景静态保持——五块大屏四动一静（中间屏灰），四空椅仅中间坐人，沈默背影静止",
        "cuts": "硬切1 ~4.98s（黑帧保持后切灰屏反光特写）；硬切2 ~8.85s（特写→全景）",
        "audio_tail": "8.9–12.25s 低电平闷响床，10.5s 前后微 swell 后渐弱",
    },
    "unverified": [
        "D003（~1.9–3.8s）发声内容待 master 耳听：应为「影流之主，影分身！」",
        "D004（~5.1–8.5s）发声内容待 master 耳听：应为「silence 被秒了！首尔鹰拿下决胜局！」",
        "解说场馆混响/兴奋语气与整体听感待 master 主观确认",
    ],
}

req = urllib.request.Request(
    f"http://127.0.0.1:8765/api/runs/{RID}/review",
    data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
    headers={"Content-Type": "application/json", "X-Canvas-Request": "1"},
    method="POST",
)
try:
    resp = urllib.request.urlopen(req)
    print("REVIEW OK", resp.status, resp.read().decode()[:500])
except urllib.error.HTTPError as e:
    print("REVIEW FAIL", e.code, e.read().decode()[:800])
    sys.exit(1)
