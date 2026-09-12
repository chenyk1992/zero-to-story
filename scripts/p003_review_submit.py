# -*- coding: utf-8 -*-
"""P003 run 972c26c7 — claim-review + review ACCEPT 提交."""
import json, urllib.request

BASE = "http://127.0.0.1:8765"
RID = "972c26c7-e007-406c-81af-e470174160d9"
OUT = r"E:\ideaProjects\zero-to-story\workspace\projects\861ebeb3-0381-42fb-819a-c7b6ad8fecf0\outputs\972c26c7-e007-406c-81af-e470174160d9\video_00001_.mp4"

def post(path, body):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Canvas-Request": "1"},
        method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)

claim = post(f"/api/runs/{RID}/claim-review", {})
print("claim:", json.dumps(claim, ensure_ascii=False))
TOKEN = claim["owner_token"]

evidence = [
    "首帧一致性：video 首帧与 P002 run e95dd7ce 真实尾帧同构图（五屏 4 战斗+正中灰、四空椅+中间坐人、背影居中；mean abs diff 3.7-4.1/255，重生成像素级差异）",
    "静止锁定：0-2.0s 全帧帧差 0.06-0.22（静止）；中心站位区 2.5-4.0s 局部微动 0.14->0.59（肩/手先动），符合 stir 规格",
    "起身：4.0-5.5s 中心区帧差 1.25->3.40；5.5s 3x 放大帧确认站立姿态、黑底橙滚边队服、背面伪文字块",
    "track left：6.0s 起全局运动峰值（whole 12.7 @7.0s）；6.5-10.0s 八个采样点 ±3px 位移残差全部 content RIGHT = 镜头向左，与蓝图 camera_moves=track left 一致",
    "屏幕出画前持续播放：7.0/7.5s 帧 station row 右滑中四战斗屏仍亮仍在动，8.5s 全部出画；中段几何完整无崩坏、无第二人形",
    "人群纪律：左缘带亮度 7.0s 前稳定 61-63（无凭空人群）；7.5-9.0s 暗色剪影逐步从左缘填入（49.5->17.9->3.5）；8.5s 帧人群由 truck 揭示；~9.5s 起背影被吞没",
    "末态锁定：10.75s 起 whole 1.95->0.32，11.0-11.5s 冻结；末帧=人群剪影行列+舞台边缘 LED 灯带+右上桁架，沈默不可辨（吞没态）",
    "文字合规：1.0s 屏幕带 2x 放大=抽象水墨战斗光影无字母数字；全片无新增可读文字；队服背面伪文字块与 P002 已接受先例一致",
    "音频 RMS：-35.6 开场近静 -> -14.1 dBFS 峰值@2.0-2.5s（起身欢呼绽放）-> 渐衰减 -36.3@10.5s（随离场远去）-> -30.8 尾部（通道声）；无音乐床。偏差不阻断：欢呼为早峰后衰减（非持续绽放，利于切 P004 安静场景）；椅响/脚步瞬态 0.5s 粒度不可分，未作判定项；track 起幅 -0.4s、吞没 -0.7s、冻结 +0.8s、时长 +0.54s 均在容差内",
]
end_state = {
    "duration_ms": 11542, "fps": 24.0, "size": "480x864",
    "final_frame": "舞台左侧通道视角：人群剪影行列吞没背影，LED 灯带曲线，右上桁架灯",
    "truck_direction": "left（内容右移，8 采样点确证）",
    "motion_tail": "11.0s 起全帧帧差 <1.2，末态冻结",
    "audio_tail": "欢呼衰减后的低电平通道声 ~-31 dBFS",
}
body = {
    "owner_token": TOKEN,
    "decision": "ACCEPT",
    "output_path": OUT,
    "evidence": evidence,
    "end_state": end_state,
    "unverified": [],
}
res = post(f"/api/runs/{RID}/review", body)
print("review:", json.dumps(res, ensure_ascii=False))
