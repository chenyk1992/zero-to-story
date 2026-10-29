# 数据与采样

`radar.py` 是按需执行的本机工具，不是已启动的常驻监控服务。Python 标准库即可运行；不读取浏览器 Cookie、环境密钥或 `.env`，不调用模型，不自动安装服务。它的公开来源每次最多一个 GET，不翻页、不重试、不跟随重定向；失败时退出码 2，保留该次来源状态。抖音细分搜索依靠真实浏览器观察/用户导出，小红书优先走[已安装框架接入](xiaohongshu-mcp.md)；其适配器正常读取本机服务认证，不导出浏览器凭据。

筛选词应覆盖用户当前关注的产品/模型别名，不能只搜“AI”就认定没有相关话题；例如按任务加入 DeepSeek、Agent、Qwen、Claude 或具体新版本，再人工核实语义。关键词匹配只是缩小样本，不是自动选题推荐。

已有 hot-collect 快照或 topic-scout 结果时，先按[研究交接](research-handoff.md)引用，不再为同一问题默认重采。本文的 `--store` 与热点库 `--data-root` 格式不同，不能通过改路径互相替代。

## 运行

在项目根目录，用已验证的 Python。`--store` 必须显式选择，放到用户指定位置或正确的项目研究目录；测试一律用系统临时目录。

```powershell
# 只采一次B站公开热搜；另外可显式选择 bilibili-popular 或 douyin-hot。
./.venv/Scripts/python.exe .agents/skills/ai-creator-radar/scripts/radar.py collect --source bilibili-hot --store workspace/projects/ai-creator-radar/research

# 保存真实浏览器观察；先将相关字段整理成下述JSON，不传原始登录态。
./.venv/Scripts/python.exe .agents/skills/ai-creator-radar/scripts/radar.py import --input observation.json --store workspace/projects/ai-creator-radar/research

# 离线比较，不会访问网络。多个 --keyword 是或匹配；没有匹配就返回空。
./.venv/Scripts/python.exe .agents/skills/ai-creator-radar/scripts/radar.py analyze --store workspace/projects/ai-creator-radar/research --keyword AI --keyword 编程 --output analysis.json
```

默认热搜通常不包含小众 AI 主题。它是入口验证和补充信号，不能宣称已经完成 AI 赛道调研。`bilibili-popular` 取综合热门第一页的视频当前累计指标，不是关键词检索，也不把列表位置当正式榜位。`douyin-hot` 本次返回空体；不要因脚本支持该名字而宣称该源已可用，也不要在本次失败后重新请求。

本机目录：`snapshots/*.json` 保存逐次观察，`raw/*.body` 保存公开响应或浏览器摘录；xiaohongshu-mcp 接入保存的是已移除访问材料的响应投影，明确记录删减，不能称为完整原始HTTP响应。均使用唯一文件名，不覆盖旧样本。`analyze --output` 同样拒绝覆盖。退出码 0 表示该命令完成；不代表选题有效或内容验收通过。没有任何采样时报告 `sources=[]/items=[]`，含义是没有数据。

## 浏览器/导出导入契约

下列是格式示例，标题、时间、数值和 ID 都是虚构的，不能用作真实热点证据。实际调用替换为真实观测，时间包含时区。

```json
{
  "schema_version": 1,
  "source_id": "xhs-ai-latest-day1",
  "platform": "xiaohongshu",
  "method": "browser",
  "observed_at": "2026-10-23T01:00:00+08:00",
  "source_updated_at": null,
  "source_url": "https://www.xiaohongshu.com/",
  "query": "AI 编程",
  "sort": "最新",
  "sample_scope": "一周内，前10条可见结果，视频笔记",
  "status": "ok",
  "items": [
    {
      "id": "actual-note-id",
      "kind": "note",
      "title": "示例标题，非实际热点",
      "url": "https://www.xiaohongshu.com/explore/actual-note-id",
      "published_at": null,
      "rank": null,
      "metrics": {"views": null, "likes": 12, "saves": 5, "comments": 2}
    }
  ]
}
```

- `source_id` 是固定的来源+查询/排序/筛选范围标识；重复观察同一范围沿用它，改变关键词/排序/筛选要换 ID。`platform` 为 `douyin/bilibili/xiaohongshu/other`；`method` 为 `public_web/browser/file`。
- `observed_at` 是实际采样时间，不是补录时间或视频发布时间。`source_updated_at` 仅在上游明确给出且已核实时填；未知为 null。缓存仍旧时不能通过修改采集时间冒充新一次热度测量。
- item 的 `id` 用真实内容 ID；topic 可以用稳定文本 ID。kind 为 `topic/video/note`。内容 URL 保存不含访问 token 的标准链接。用户名仅在确有对标用途时保留，评论默认匿名归纳。
- metrics 可用 `hotness/views/likes/comments/shares/saves/followers_gained`；只填实际可得、同一口径、精确的非负数字。未显示、`--`、未获权限填 null 或省略；“1.2万”是约数，保留在人工证据说明里，该数值填 null，不伪造精确计数。明确显示 0 才填 0。
- `rank` 仅用于真实平台榜位，搜索列表位置不要写成榜位。`published_at` 要有真实时间依据，没有就 null；不编造小时精度。
- 失败来源使用 `status=empty/blocked/unavailable/invalid_response` 且 `items=[]`，简短 `diagnostic` 解释原因。空200、没有权限和真零分别记录。`raw_file/raw_sha256` 由采集器生成，导入不得伪造。

## 如何解释变化

`analyze` 在同一来源+平台+内容 ID 内比较；不自动合并相似话题，也不合并不同平台的热度。可在研究报告中人工标注同题关系和依据，保留各平台独立值。相似词归并时警惕产品同名、版本变更与不同语义。

默认回看 72h，最新来源超过 6h 视为陈旧，采样间隔至少 30min，单段间隔超过 12h 不比较增速。这些是保守的可配置操作值，不是平台规律或预测模型参数。建议实际按来源刷新节奏和内容窗口选择 2–6 小时采样间隔；只有用户要求定时监控才创建正式自动化。短间隔反复读取缓存不产生新证据。

| 信号 | 含义 |
| --- | --- |
| `INSUFFICIENT_HISTORY` | 没有足够间隔的两次观察，不能算变化 |
| `RISING/COOLING/FLAT` | 最近两次同口径指标的实际变化 |
| `ACCELERATING_OBSERVED` | 至少三次间隔合适的观察中，最近正向速率高于前段正向速率；仅是描述 |
| `RANK_UP/RANK_DOWN` | 只有真实榜位能比较；不是播放量变化 |
| `UNCHANGED_OR_CACHED` | 两次指标/榜位相同；不能区分真实停滞和旧缓存，不制造新趋势证据 |
| `COUNTER_CORRECTION` | 累计指标下降，可能口径/平台修正，不当作负播放 |
| `WAIT_FOR_SPACED_SAMPLE/GAP_TOO_LONG` | 时间间隔不足或过长，暂不比较 |
| `STALE/SOURCE_UNAVAILABLE` | 数据过时或最近来源失败；不沿用历史成功装成当前成功 |
| `NOT_IN_LATEST_SAMPLE` | 最新有限样本里没有该条；不等于零、不等于删除、也不必然降温 |

热度是动态指数，可下降；播放/点赞等累计计数下降则记修正。`forecast_probability` 恒为 null。至少三次采样只是计算增速变化的最低条件，不能证明“会火”。账号规模差异、发布年龄、样本偏差、平台延迟、转载和同源聚合仍须在研究中解释。

输出的 `freshness_basis=observation_time_only` 表示只知道请求/采样时间，上游实际更新时间不明；`warnings` 保留这一缺口。不能未经查证就把上游名为 `timestamp` 的字段认定为榜单更新时间。相同指标回包标为 `UNCHANGED_OR_CACHED`，而不是确信地判断平台热度已持平。

真正评估提前发现能力需保存当时全部候选，预先约定预测时点、观察周期和“升温”定义，再在后续时间窗口比较简单基线（当前热度/近期增量）。按时间分训练/检验，纳入没火的候选，报告命中和遗漏及样本量。没有这些数据就不报告准确率，更不能保证十万粉。

## 本地媒体准备

```powershell
./.venv/Scripts/python.exe .agents/skills/ai-creator-radar/scripts/media_evidence.py --input reference.mp4 --output-dir evidence
```

它只写技术信息和有限采样帧，不执行转写，也不给内容验收结论。`--input` 仅接受真实本地文件，不从外部获取素材。输出目录须为新目录。文字研究使用已有字幕或平台正文，缺转写时准确记录缺口。
