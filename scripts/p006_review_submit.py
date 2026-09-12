# -*- coding: utf-8 -*-
"""P006 (run 8d7eb676) claim-review + review submit (INCONCLUSIVE)."""
import json, urllib.request

BASE = "http://127.0.0.1:8765"
RID = "8d7eb676-19b9-4ad2-bd82-6f6eb4c11268"
OUT = r"E:\ideaProjects\zero-to-story\workspace\projects\861ebeb3-0381-42fb-819a-c7b6ad8fecf0\outputs\8d7eb676-19b9-4ad2-bd82-6f6eb4c11268\video_00001_.mp4"

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
        "眩光脉冲落实（「光刺进来」）：逐帧亮度基线 98 → 0.79s 起升 → 峰值 t=1.12s 185.6（1.89x）→ 1.62s 回基线；单峰平滑 rise-fall 约 0.8s，非死白，画面内容全程可辨",
        "黑板无字铁证：BOARD_UR stddev 2.9-3.1（纯色 <3.2）+ 浅色像素占比 0.0000（全程 345 帧）；zoom_board_14s 目视仅余擦拭痕迹，UI-001 叠字区干净可用",
        "色彩天然达标：S_mean 0.321 / S_p90 0.590（验收线 0.18/0.30）——低于线才调原则首次正向案例，本片不调色",
        "时序链完整：0-0.75 静 → 眩光 → 1.5-3.5 坐起 → 4.5-5.5 敲黑板×3（粉笔声脉冲 5.05-5.45 吻合）→ D009 语音 7.0-8.5（预期 6.5-8.5，仅后移 ~0.5s，显式窗写法见效）→ push-in ~8.5-13.0（提前 ~1.5s 开始、按时收尾，记录级）→ 13.5 后静止",
        "I2V 首帧承接 diff 6.24 中等（布局/人物/色调目视一致，差异为细节重构噪声）；首帧 = master 已核验的场景 C 关键帧",
        "沈默形象符合设定：蓝白校服（白衬衫+深蓝外套）+ 短软发型；低头-抬头被斥-低头节奏合理",
        "末态构图（zoom_end_full）：push-in 落定，老师侧身面向黑板、沈默前景低头、黑板无字、讲台细节在位；末态冻结 max 7.85 偏弱（收尾拖尾，记录级）",
        "音频结构干净：0-0.5 静 → 敲击脉冲 5.05-5.45 → 唯一语音 7.0-8.5 → 之后无语音；无音乐负约束起效",
        "【偏差待裁决】老师露正脸：6.0/7.5/8.0s 三帧放大眉眼清晰+张嘴斥责——违反三层约束（brief L117 仅背影/侧影 / 分镜板 L215 不出现正脸五官 / L282 出镜约束表）；低发髻+深色正装符合 36 岁女班主任设定",
        "成片管线：前置 0.5s 黑场+静默（切黑归属管线执行；验证 t=0.2s 亮度 0.0 / t=0.8s 亮度 98.13 平移正确），不调色；入库版 P006_final_black05.mp4（14.9s）sha256 c474e3c0b222ce9cb9f7f691746ac1203e65c4124d71dc06ea3a67f9640eba9e",
    ],
    "end_state": {
        "situation": "D009 斥责已说完（内容待耳听），push-in 落定于黑板右上角叠字区，全场静止",
        "visible": "老师侧身面向黑板（侧脸轮廓）；沈默前景低头靠窗；黑板全程无字（UI-001 叠字区干净留白）；暖黄光斑",
        "hand": "老师手持书本/粉笔垂落，沈默双手伏案静止",
        "props": "讲台粉笔盒+翻开的书本；黑板矩形干净；无电子设备",
        "audio": "唯一语音 7.0-8.5s 后无语音；敲击脉冲 5.05-5.45；无音乐",
        "blocking": "老师露正脸偏差（brief 级约束被生成违反，接受或重出属导演裁决）+ D009 发声内容耳听；通过则 ACCEPT 入库版 P006_final_black05.mp4；P007 依赖本片真实尾帧（档案：review/P006_run_8d7eb676/acceptance.md）",
    },
    "unverified": [
        "D009 发声内容（实测 7.0-8.5s，成品时间轴 7.5-9.0s）",
        "老师露正脸偏差的创作裁决（接受形象定型 vs 强化背影约束重出）",
        "眩光脉冲幅度观感（峰值 1.89x 基线，形态数据达标，刺眼度待目视感受）",
    ],
}
resp = post(f"/api/runs/{RID}/review", body)
print("review submitted (resp may omit fields)")
