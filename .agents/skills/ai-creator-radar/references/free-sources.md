# 免费来源与工具

核验日期：2026-10-23。以下保留选型记录，只有明确标注已接入的项才是本机能力。以后使用前核实源站状态和许可证，保留检查时版本；不能拿这张表代替实时可用性检查。

## 选择数据入口

| 来源 | 能拿到什么 | 主要缺口与免费条件 |
| --- | --- | --- |
| 平台公开热榜 | 某时刻的话题、榜位，部分有平台热度 | 综合榜常没有细分 AI 话题；不是单视频增长轨迹；网页接口会变 |
| 平台内关键词搜索/对标账号 | 近期内容、标题、发布时间、可见互动和评论需求 | 排序与个性化造成样本偏差；不可见播放量留空；登录/风控交用户 |
| 用户自己的创作者后台 | 播放、留存、主页访问、吸粉等账号指标 | 先核对正确账号；各模块统计窗口与更新时间可能不同；只在本机保存相关数据 |
| 平台官方开放接口 | 官方定义的热点或授权账号数据 | 不能假定已获权限，也不能因文档存在宣称免费可用 |
| 模型/产品官方发布、GitHub release、论文 | 发布时间、版本、能力和限制等一手事实 | 发布不是热度或实测效果；GitHub 星数不是普通用户需求 |

抖音官方[实时热点词](https://open.douyin.com/platform/resource/docs/openapi/data-open-service/hot-video-data/get-current-hot-words/)和[上升词](https://open.douyin.com/platform/resource/docs/openapi/data-open-service/hot-video-data/get-ascending-words/)要求申请 `hotsearch` 权限和 client token，文档说明榜单约两小时刷新。它们值得作为未来正规接入路线；本 Skill 不索取凭据或自动申请，也未核实用户有权限或会产生什么费用。[热门视频榜](https://open.douyin.com/platform/resource/docs/openapi/data-open-service/tops-data/hot-video-list/hot-video-list/)则是最近 24 小时的离线榜，不能称秒级实时。

## 筛选后的候选

| 工具及核验版本 | 保留什么 | 限制/不直接启用的原因 |
| --- | --- | --- |
| [NewsNow](https://github.com/newsnext/newsnow/tree/0560c993b226cd2fd07d8a79875d50551f52c584)，MIT | 抖音/B站热榜接入和 B站公开视频字段的源码参考 | 老地址 ourongxing/newsnow 已重定向；默认可依赖他人托管；该版本未发现小红书源；不是持续历史库 |
| [TrendRadar](https://github.com/sansan0/TrendRadar/tree/68c8916c450f8c8dd36cb88a189f7c2e46681ab5)，GPL-3.0 | 关键词筛选、本地存储和榜位时间线的设计参考 | 默认数据源依赖 NewsNow；AI 分析等可调用模型 API，严格免费时禁用；本机部署仍需要环境和维护 |
| [DailyHotApi](https://github.com/imsyy/DailyHotApi/tree/36c77e3bd891c11642d314cfb229bf31646704de)，MIT | 抖音热度、B站排行字段的备用参考 | 默认公共 API/缓存不是稳定免费保障；该版本未发现小红书路由；只取快照 |
| [xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp/releases/tag/v2.5.5)，Apache-2.0 | 已按用户明确请求安装官方 Windows 服务，接入免费本地搜索/笔记详情/评论读取 | 需要扫码和浏览器；使用[本机接入](xiaohongshu-mcp.md)的只读适配器。服务本身有发布/互动能力，适配器不暴露这些调用，不向宿主全局注册 |
| [RSSHub](https://github.com/DIYgod/RSSHub)，AGPL-3.0 | 长期订阅某些来源的备选 | 按具体路由核实登录、频率与反爬；公共实例没有免费稳定承诺；本次未部署/验证路线 |

证据：NewsNow [抖音源](https://github.com/newsnext/newsnow/blob/0560c993b226cd2fd07d8a79875d50551f52c584/server/sources/douyin.ts#L1-L27)、[B站源](https://github.com/newsnext/newsnow/blob/0560c993b226cd2fd07d8a79875d50551f52c584/server/sources/bilibili.ts#L91-L150)；TrendRadar [平台与数据源](https://github.com/sansan0/TrendRadar/blob/68c8916c450f8c8dd36cb88a189f7c2e46681ab5/config/config.yaml#L50-L98)、[关键词/AI 筛选](https://github.com/sansan0/TrendRadar/blob/68c8916c450f8c8dd36cb88a189f7c2e46681ab5/config/config.yaml#L177-L182)、[本地存储](https://github.com/sansan0/TrendRadar/blob/68c8916c450f8c8dd36cb88a189f7c2e46681ab5/config/config.yaml#L310-L343)；DailyHotApi [抖音字段](https://github.com/imsyy/DailyHotApi/blob/36c77e3bd891c11642d314cfb229bf31646704de/src/routes/douyin.ts#L40-L75)。

小红书候选的[搜索筛选](https://github.com/xpzouying/xiaohongshu-mcp/blob/7797fd375aba02dcd33afe143f6bee13e5870859/xiaohongshu/search.go#L24-L30)有最新、最多点赞/评论/收藏和一天内/一周内等选项；[类型定义](https://github.com/xpzouying/xiaohongshu-mcp/blob/7797fd375aba02dcd33afe143f6bee13e5870859/xiaohongshu/types.go#L69-L79)有赞、藏、分享和评论，不能由此假定能获得竞品播放量/完播率。详情读取需要当前内容的 `feed_id` 和 `xsec_token`；token 是访问材料，不进入研究输出。

## 按用途保留或暂不启用的方案

- [MediaCrawler 现行许可证](https://github.com/NanmiCoder/MediaCrawler/blob/main/LICENSE)免费授权非商业学习研究。用户本次明确为学习和个人研究，可保留该用途的学习候选；之前按未明确的经营用途直接排除，已据新说明收窄。个人身份不能自动解除商业用途限制；保留版权/许可、不大规模采集或干扰平台，商业用途须作者书面同意。本次仍按用户选择先接 xiaohongshu-mcp，没有安装 MediaCrawler。其封装 [media-crawler-skill](https://github.com/lovstudio/media-crawler-skill/blob/2647eb021550a604e40760b754959b3810a315cf/references/upstream-and-licenses.md)本身的 MIT 标示不替代上游条款。
- [bilibili-api 原仓库](https://github.com/Nemo2011/bilibili-api)于 2026-07-06 公告停止维护并永久关停；不作为新依赖，也不拿旧教程冒充当前路线。
- [xiaohongshu-ops-skill](https://github.com/Xiangyu-CAS/xiaohongshu-ops-skill/tree/5b0b80b7261396955de0494df18182f2401cabc4)该版本未发现许可证，且绑定 OpenClaw 浏览器及外发/发布流程；只作工具审查对象，不复制安装。
- 需要充值/试用 token 的“全平台采集”“爆款预测”服务不满足本任务要求。免费方案缺能力时报告缺口，不通过免费试用掩盖后续收费。

## 用户补充的现成 Skill 与框架

先查真实上游和固定版本；聚合站介绍、Skill 名称和安装命令不能证明采集已实现。2026-10-23 实时源码与旧网页索引存在差异，记录如下：

| 候选 | 源码核验与决定 |
| --- | --- |
| [OpenAkita idea-research 历史源码](https://github.com/openakita/openakita/tree/aee65056f70c15c00eb9ce964cdbdf14b68652b3/plugins/idea-research) | 确实存在过完整插件；当前 main `5f5b38da728274f0fd06461a481851be7c0bca6a` 已没有该目录，[移除提交](https://github.com/openakita/openakita/commit/154b751bf2b38a00684e12f1549676c144d2a447)把 bundled plugins 移出源码树。用户给的 `npx skills add … --skill idea-research` 不能按当前 main 路径直接安装，也不是独立 Codex Skill。保留工作流参考，不作为采集层依赖。 |
| [video-trending](https://github.com/xiaoquqi/hermes-agent-skills/blob/dbdf1c25aab33775a3940653b8cd75a0737aa9fe/media/video-trending/SKILL.md) | 真实上游为 `xiaoquqi/hermes-agent-skills`，该目录只有说明，引用 NewsNow 源ID和 B站 API示例；没有独立抖音采集实现，不含小红书。仓库未声明许可证，不复制安装。 |
| [F2](https://github.com/Johnserf-Seed/f2/tree/f6be8c0) | Apache-2.0；适合指定作品/主页等用途。该版抖音 handler 的关键词搜索限定用户作品，未实现所需全站关键词搜索；没有小红书。不是本任务双平台替代。 |
| [Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API/tree/0661234) | Apache-2.0；有抖音作品详情/评论等能力，当前功能表明确抖音关键词搜索不支持（TikTok 支持不能等同抖音），没有小红书。完整服务有数据库/队列等部署负担，本次未安装。 |

idea-research 的宣传能力需进一步收窄：[Engine A](https://github.com/openakita/openakita/blob/aee65056f70c15c00eb9ce964cdbdf14b68652b3/plugins/idea-research/idea_collectors.py#L288-L302)对抖音/小红书走 RSSHub 用户路由，[路由要求 UID](https://github.com/openakita/openakita/blob/aee65056f70c15c00eb9ce964cdbdf14b68652b3/plugins/idea-research/idea_engine_api.py#L1792-L1829)，radar 没传 UID；[Engine B](https://github.com/openakita/openakita/blob/aee65056f70c15c00eb9ce964cdbdf14b68652b3/plugins/idea-research/idea_engine_crawler.py#L889-L959)读取热榜/探索页后本地过滤关键词，不能等同站内关键词搜索。其[模型费用](https://github.com/openakita/openakita/blob/aee65056f70c15c00eb9ce964cdbdf14b68652b3/plugins/idea-research/idea_models.py#L582-L660)包括可计费的文本、视觉和云语音路径，不能把“采集估价0”扩展成整条视频拆解/脚本免费。历史插件清单自称 Apache-2.0，但目录无独立 LICENSE、仓库根为 AGPL-3.0，复制前仍需核清适用许可。

**当前选择**：小红书使用已安装的[官方 Windows 发行版](https://github.com/xpzouying/xiaohongshu-mcp/releases/tag/v2.5.5)和[只读接入](xiaohongshu-mcp.md)；抖音细分搜索沿用当前宿主已登录页面。MediaCrawler 保留非商业学习候选，本次不替换抖音方案。不为凑“全平台”引入收费服务；自有脚本只做薄适配与证据存储，不另造爬虫、签名或登录内核。

用户已取消 faster-whisper：本 Skill 不安装、不依赖、不调用它。文字研究用平台正文/字幕/评论；配音制作沿用已有 ComfyUI/mmx 能力，研究阶段不会由此触发生成或计费。

## 本次真实可用性证据

2026-10-23（北京时间）一次无 Cookie/签名 GET：B站热搜端点返回业务码 0 和 30 条，字段包含 `keyword/show_name/pos/heat_score`；它们是话题数据，没有视频播放量。抖音公开网页热榜端点返回 HTTP 200 但空体，记为不可用，不重试；不能宣称已打通抖音无登录HTTP采集。NewsNow 的抖音源码还涉及获取登录域名 Cookie，不能把它包装为当前无登录稳定能力。

`radar.py` 独立实现有界读取与本机快照，没有复制上述项目实现。默认只读取 B站热搜；其他来源显式选择。抖音通过当前宿主浏览器按契约导入；小红书优先通过本地框架，`method=browser` 且 scope 标明实际框架与版本。浏览器宿主读取与框架读取分别保留来源范围，不混算成同一连续序列。
