# -*- coding: utf-8 -*-
"""P007 (run 46a069c8) claim-review + review submit (INCONCLUSIVE)."""
import json, urllib.request

BASE = "http://127.0.0.1:8765"
RID = "46a069c8-78e3-4669-a8da-760bccbfaa9c"
OUT = r"E:\ideaProjects\zero-to-story\workspace\projects\861ebeb3-0381-42fb-819a-c7b6ad8fecf0\outputs\46a069c8-78e3-4669-a8da-760bccbfaa9c\video_00001_.mp4"

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
        "镜头链完整落实：0-2.5s 缓慢后拉（黑板中近景→过肩机位）→ 2.5-5s 过肩看沈默翻手 → 5.5-7.5s 随视线扫向窗外（窗棂+操场跑道/场地入画）→ ~8.5s 林燃大脸入画（LINRAN 区帧差峰 76）→ push-in 大脸 → 10.5s 后趋稳末态冻结",
        "首帧承接 4.17 中优：boundary.P006.last_frame 落实，快照冻结 sha256 498fab35 与本地一致，开场构图与 P006 末帧同",
        "林燃形象一次到位：圆脸寸头壮实+咧嘴笑生动+红白运动外套（白肩拼黑领口），大脸占前景最大（zoom_linran_10s）；与沈默清瘦对比明确",
        "EV013 部分达成【待裁决】：翻看手背动作执行（4.0s 双手胸前翻转清晰）但景别为中景而非特写——「手背无老茧」不可辨，「低头」形态未执行；must_show 的 visible_proof 传达打折",
        "黑板无字目视铁证（zoom_board_1s 板面完全干净）；BOARD_UR stddev 33-38 偏高系区域含墙面+灯管结构（非文字）",
        "色彩三段天然达标 S_mean 0.300-0.375 / S_p90 0.581-0.834（验收线 0.18/0.30）——不调色；无黑场前置（无切黑设计），入库版=生成原片 sha256 80e40ea0…f891",
        "末态（13.9s）：林燃咧嘴大笑占前景最大、操场背景、沈默肩部画缘存在（state_after 落实）；末态冻结 max 6.34 中等（记录级）",
        "沈默校服深蓝外套+白衬衫袖卷小臂符合设定；老师低发髻深色正装侧影开场在画（承接 P006，master ACCEPT 定型口径）",
        "音频实测：0-1s 近静音（RMS 173，BGM 开头缺失疑点）→ 1.5-2.5 / 5.0-6.5 中能量段 → 9.0-13.5 梳状强能量（RMS 峰 7605-11808）；D010 预期 7.5-10.0 实测起于 9.0 后移 ~1.5s 且跨度超设计窗",
    ],
    "end_state": {
        "situation": "林燃大脸凑近咧嘴笑保持至末帧，D010 邀约已发出（内容待耳听），沈默面对他",
        "visible": "林燃大脸占前景最大（圆脸寸头红白外套咧嘴笑）；窗外操场跑道+场地+远处人影；沈默肩部画缘存在",
        "hand": "林燃身体前倾撑近；沈默双手在桌面（末段静止）",
        "props": "课桌旧木纹+堆书+书包；窗棂隔窗视角；无新增道具",
        "audio": "9.0-13.5 梳状强能量（语音+BGM 成分待耳听拆分）；0-1s 近静音",
        "blocking": "三项耳听（D010 内容 / 10.5-13.5 段性质 / BGM 存在性音色）+ EV013 景别裁决（接受或补特写镜头）；画面侧镜头链与林燃形象已到位（档案：review/P007_run_46a069c8/acceptance.md）",
    },
    "unverified": [
        "D010 发声内容（实测 9.0s 起强能量，后移 ~1.5s）",
        "10.5-13.5s 梳状强能量段性质（BGM 强段 vs 额外语音——若额外语音则违反唯一语音负约束）",
        "BGM 存在性/音色（0-1s 近静音与「从头低垫」不符；是否轻快吉他、是否压语音）",
    ],
}
resp = post(f"/api/runs/{RID}/review", body)
print("review submitted (resp may omit fields)")
