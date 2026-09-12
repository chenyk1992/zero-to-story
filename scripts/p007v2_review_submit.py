# -*- coding: utf-8 -*-
"""P007 (run 46a069c8) claim-review + review submit (INCONCLUSIVE)."""
import json, urllib.request

BASE = "http://127.0.0.1:8765"
RID = "5e297812-9d4f-4754-9b0b-c6e34e095ed9"
OUT = r"E:\ideaProjects\zero-to-story\workspace\projects\861ebeb3-0381-42fb-819a-c7b6ad8fecf0\outputs\5e297812-9d4f-4754-9b0b-c6e34e095ed9\video_00001_.mp4"

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
        "【v2 修复确认】林燃朝向：入画 8.5s 即四分之三侧面朝画左沈默、视线锁定沈默（zoom_linran_95s），sheet 8.5-13.9s 全程保持，末态侧脸朝沈默咧嘴笑——第四面墙彻底修复，大脸占前景效果保留",
        "v2 背景：master REJECT 反馈 v1 林燃正对镜头说话（像对观众）——v1 提示词 very close to the camera 诱导；v2 仅重写林燃段朝向约束（凑近对象=沈默+负约束 never looks at the camera），时序/首帧不变",
        "首帧承接 4.10 中优（快照 sha256 498fab35 与 v1 同帧一致）；时序链与 v1 同构：0-1s 近静止 → 1.5-9s 持续运动（后拉→低头翻手→扫向窗外→林燃 8.5s 入画 LINRAN 峰 68）→ 9.5s 后趋稳",
        "EV013 达成度提升：低头+翻手动作形态完整（v1 为平视），景别仍中景（手部 ~10% 画面高，无老茧不可辨）——景别裁决项维持",
        "黑板无字（zoom_board_1s 板面完全干净；BOARD_UR stddev 30-38 系区域含墙面灯管非文字）；窗外操场跑道+打球人影清晰",
        "色彩三段天然达标 S_mean 0.292-0.352 / S_p90 0.563-0.856（验收线 0.18/0.30）——不调色，入库版=原片 sha256 a6f4ceec…9d16",
        "林燃形象与 v1 一致（圆脸寸头红外套拉链立领）；沈默深蓝外套白衬衫袖卷小臂；老师低发髻侧影开场在画",
        "音频：1.0-6.5s 持续中能量（BGM 连续垫底形态，优于 v1 零星段）→ 9.5s 峰 7314（D010 语音起，后移 ~2s）→ 10.5-13.5 梳状强能量（BGM 强段 vs 额外语音待耳听拆分）",
        "末态冻结 max 8.94 略弱（14.0-14.5 小波动，记录级）；v1 run 46a069c8 作废留档，P008 首帧将取 v2 尾帧",
    ],
    "end_state": {
        "situation": "林燃侧脸朝沈默凑近咧嘴笑保持至末帧，D010 邀约已发出（内容待耳听）",
        "visible": "林燃四分之三侧面朝画左沈默（绝不看镜头）；窗外操场跑道+人影；沈默画缘",
        "hand": "林燃前倾撑近；沈默双手桌面（末段静止）",
        "props": "课桌旧木纹+堆书；窗棂隔窗视角",
        "audio": "BGM 1.0-6.5 连续垫底形态；D010 9.5s 起（后移 ~2s）；10.5-13.5 强能量段性质待拆分",
        "blocking": "三项耳听（D010 内容 / 10.5-13.5 段性质 / BGM 音色）+ EV013 景别裁决；朝向修复已确认（档案：review/P007_v2_run_5e297812/acceptance.md）",
    },
    "unverified": [
        "D010 发声内容（实测 9.5s 起，后移 ~2s）",
        "10.5-13.5s 梳状强能量段性质（BGM 强段 vs 额外语音）",
        "BGM 音色（存在性数据倾向成立；是否轻快吉他、是否压语音）",
    ],
}
resp = post(f"/api/runs/{RID}/review", body)
print("review submitted (resp may omit fields)")
