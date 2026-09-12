# -*- coding: utf-8 -*-
"""P005 v2 (run 08de5aa0) claim-review + review submit (INCONCLUSIVE)."""
import json, urllib.request

BASE = "http://127.0.0.1:8765"
RID = "08de5aa0-a090-486d-9bec-ba30ec08192c"
OUT = r"E:\ideaProjects\zero-to-story\workspace\projects\861ebeb3-0381-42fb-819a-c7b6ad8fecf0\outputs\08de5aa0-a090-486d-9bec-ba30ec08192c\video_00001_.mp4"

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
        "视线揭示版落实：母亲反光开场即隐约在场（首帧合成 alpha0.35）→ 4s 淡虚 → 8s 微显 → 11s/13s 清晰可辨（sheet_mother_reveal 四时刻），全程无跳变无位移",
        "教练视线动因成立：说完话 ~9.0s 转身看向玻璃（提示词为微侧头瞥，实为大幅转身，幅度偏差记录），末态焦点在玻璃、教练虚焦（rack focus 目视落实，zoom_coach_13s）",
        "I2V 首帧承接 2.74 优（合成首帧冻结 sha256 2ae2ed25 已核对）；单镜 fixed 无运镜无切镜",
        "摆手 5.4s 吻合预期；动作链系统性后移 ~1.5s（叹气 5.5-6.0 vs 4.3、语音 7.5-9.0 vs 5.9-8.4），v1 同款模型固有行为",
        "音频负约束起效：9.0s 后无人声、无侵占留白段（v1 同位置问题未复现）；结构=弱响段(3.0s 衣料)+叹气?(5.5-6.0)+唯一语音(7.5-9.0)+钢琴雨(10.0-11.0)+尾音缓降",
        "色彩结论：提示词色彩指令对 I2V 无效（S_mean 0.100 = v1 0.103，首帧锚定锁死）→ 管线后处理定版 eq=saturation=1.6:contrast=1.03，调色后 S_mean 0.19/S_p90 0.50 达标（验收线 0.18/0.30），成品 P005_v2_graded_sat1.6.mp4",
        "末态冻结 12-14s 全幅 max 1.29；沈默区背对静止；全片无可读文字",
        "母亲硬约束满足：仅玻璃反光侧影、不露正脸、不与门接触、无对白",
        "D008 语音内容待耳听（铁律）；5.5-6.0s 短响段性质待耳听（疑叹气，紧随摆手）",
        "蓝图四处手术（EV010/C005/bridge）validator PASS，brief 六处同步（含新增全集色彩规范：S_mean>=0.18/S_p90>=0.30 验收线）",
    ],
    "end_state": {
        "situation": "教练已说出 D008（内容待耳听）并转身看向玻璃，母亲反光清晰可见，沈默背对静止",
        "visible": "焦点在玻璃门：母亲深色外套侧影抬手擦眼清晰可辨；教练左前景虚焦侧身；同镜同构图无切镜",
        "hand": "教练手臂垂落，沈默双手静止",
        "props": "烟灰缸原位；场景陈设不变",
        "audio": "钢琴雨 10.0-11.0 入场后缓降收场，9.0s 后无人声",
        "blocking": "D008 内容 + 5.5-6.0s 响段性质 + 钢琴音色待 master 耳听；画面侧 master 两项反馈均已解决（突兀→视线揭示版落实；色彩→后处理定版达标）；倾向 ACCEPT 以调色版入库（档案：review/P005_v2_run_08de5aa0/acceptance.md）",
    },
    "unverified": [
        "D008 发声内容（实测 7.5-9.0s，后移 ~1.6s）",
        "5.5-6.0s 短响段性质（疑叹气声 vs 额外发声）",
        "10.0-11.0s 起声段是否为钢琴单音+雨声（音色待耳听）",
    ],
}
resp = post(f"/api/runs/{RID}/review", body)
print("review submitted (resp may omit fields)")
