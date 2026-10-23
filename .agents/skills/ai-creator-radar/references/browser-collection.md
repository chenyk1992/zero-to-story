# 抖音和小红书免费浏览器采集

采集优先按[免费来源与工具](free-sources.md)复用成熟框架；未接通或不适用时，使用用户正常扫码登录的浏览器页面，通过当前宿主浏览器工具读取渲染DOM，作为已验证的补充路线。此路线不增加付费API、代理或库，不读取Cookie、localStorage、隐藏应用状态或签名。它依赖宿主浏览器能力和有效登录，不能说成脱离宿主的无人值守HTTP爬虫。不要把此薄适配扩展成自研爬虫内核。

## 一次采样

1. 按当前宿主浏览器文档，绑定正确页面。需要登录时显示该平台扫码页并保留供用户操作；看到搜索结果可读后继续，遇安全验证停在页面，不代过验证码或轮换身份。
2. 使用站内搜索输入关键词；先确认真实结果，再按需选时间范围和排序。记录**实际已生效**的筛选，不把计划中要选的值写进样本。例如抖音近一周+最多点赞、小红书一周内+最多点赞；也应取一些最新或普通样本，以免只研究赢家。
3. 用[只读DOM提取函数](../scripts/browser_extractors.js)在工具支持的 `tab.playwright.evaluate` 中运行，传入 `platform/query/sort/sample_scope/limit`。不要把函数另改成读取接口、登录态或内部React/Vue状态的爬虫。提取器最多取40条已渲染卡片，不自动滚动、点击或发请求。
4. 把工具返回的JSON原样保存到当前研究目录的 `captures/` 唯一文件名中，调用 `radar.py browser-import`。不要改采样时间、补不存在的计数或伪造原响应。原DOM摘录保留日期/时长/约数显示；归一化只计算精确指标。
5. 为推荐项补查2–3条详情：从真实卡片进入，验证内容ID、标题、实际发布时间与可见赞藏评论。详情用宿主当前DOM观察保存，避免把用户身份或访问token带入研究输出。研究评论只保留匿名问题/需求。

```powershell
./.venv/Scripts/python.exe .agents/skills/ai-creator-radar/scripts/radar.py browser-import --input captures/douyin-ai-coding.json --source-id dy-ai-coding-week-likes --store workspace/projects/ai-creator-radar/research
./.venv/Scripts/python.exe .agents/skills/ai-creator-radar/scripts/radar.py browser-import --input captures/xhs-ai-tools.json --source-id xhs-ai-tools-week-likes --store workspace/projects/ai-creator-radar/research
./.venv/Scripts/python.exe .agents/skills/ai-creator-radar/scripts/radar.py analyze --store workspace/projects/ai-creator-radar/research
```

用户要求打通采集时，至少完成“真实检索→提取→保存→导入→离线分析”并记录结果；只有打开网页或看到二维码不能算接通。保留来源、筛选与数量；没拿到的详情指标留空，不能用列表点赞数冒充播放。

## 目前验证的DOM边界

- 抖音视频卡片：`.search-result-card` 内标题 `.BjLsdJMi`、作者 `.WldPmwm5`、显示日期 `.dO8W7uoF`、点赞 `.pMq55q1M span`、时长 `.FnM1bbIQ`。内容ID来自其渲染祖先 `id=waterfall_item_<视频ID>`。相关搜索卡、无标题/无时长卡不计。选择器变化时记空缺，不从封面签名URL或应用内部对象猜ID。
- 同日站内入口可能转到 `/jingxuan/search/`；该布局本轮核对过的对应字段为 `.hu36PKCP`、`.vgw3V2Fj`、`.iOLHOuw4`、`.g5BarT4O span`、`.ZYKiUg6O`。提取器兼容这两种已核实布局；直达搜索地址502时，正常首页的站内检索可以作为诊断后的入口，不遇风控换身份或绕过验证。
- 小红书卡片：`section.note-item[data-note-id]`、`a.title`、`.name`、`.time`、`.count`。卡片统一记 `note`；没有可靠视频标识时，不推断它一定是视频。访问URL保存不带query的 `/explore/<ID>`，不输出 `xsec_token`。
- 标题可能是截取的长文案，提取器抖音上限220字；不是对视频内容的完整理解。列表时间保留原显示，归一化 `published_at=null`。详情须再区分首发与“编辑于”；列表的“4天前”不能直接解释为四天内积累了全部互动。`3.3万` 等约数保留原文，精确likes为null；显示`700`才存700。

选择器是2026-10-23实测页面结构，可能漂移。以后先小样本核对标题/ID/点赞含义，变更时更新本文件和提取器并做代表检查；不能静默把空列表判为真实无数据。

## 采样建议

围绕同一批账号受众问题，选少量宽词与产品别名，再根据第一轮结果收窄。例如AI编程、AI工具、AI视频，之后深入Agent、免费范围、某个具体模型。每一组来源ID绑定关键词、排序和时间范围；结果数只是当前有限样本，不能声称覆盖全站。

单次接通后可给出当前选题建议，但仍没有连续趋势证据。用户另行要求定时采样时再走正式自动化；浏览器登录可能失效或出现验证，需准确报告中断，不宣称永久稳定。
