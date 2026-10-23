# SOURCES.md · 数据源台账

> 维护规则：**只改这个文件和对应 adapter，不碰判定逻辑。**
> 每月复核一次「合规与额度」清单，结论写回本文件。
> 最后验证：2026-10-23（本机实测）

---

## 1. 在用源

### `sixty` · 60s API

| 项 | 值 |
|---|---|
| 仓库 | https://github.com/vikiboss/60s |
| 协议 | **MIT**（允许商用） |
| 鉴权 | 无 |
| 公共实例 | `https://60s-api.viki.moe/v2`（备用 `https://60s.viki.moe/v2`） |
| 自部署 | `docker run -d -p 4399:4399 vikiboss/60s:latest`（推荐，公共实例有每日额度） |
| 更新机制 | GitHub Actions 定时抓取 → 静态 JSON → CDN |
| 端点 | `/v2/douyin` `/v2/rednote` `/v2/quark` `/v2/ai-news` `/v2/weibo` `/v2/zhihu` `/v2/toutiao` `/v2/baidu/realtime` `/v2/ncm-rank` `/v2/maoyan` |
| 已知失效 | `60s/bili` 间歇性 HTTP 500（B 站端点不稳）→ **本链路不依赖它**，B 站走官方 API |
| 已知失效 | 公共实例会 **HTTP 429** 限频 → 已内置 3 次指数退避；仍失败则端点级降级并记录 |
| 字段注意 | 热度是**带中文量级的字符串**（`"947.5w"` / `"9.5万"`），解析必须处理 万/亿/k 后缀，否则差 10^4 倍 |
| 商业使用 | ✅ 允许 |

### `bilibili` · B 站官方公开接口

| 项 | 值 |
|---|---|
| 端点 | `api.bilibili.com/x/web-interface/popular`（热门 20）<br>`api.bilibili.com/x/web-interface/ranking/v2?rid=N&type=all`（分区榜，**rid=0 为全站榜，100 条**）<br>`api.bilibili.com/x/web-interface/view?bvid=`（视频详情）<br>`api.bilibili.com/x/web-interface/popular/series/list`（**394 天历史索引**） |
| 鉴权 | **全部免登录**（带 UA + Referer 即可） |
| 返回 | 每条含完整 `stat`：`view / like / coin / favorite / danmaku / reply`；含 `tname`（分区名 = 赛道）、`pubdate`、`bvid` |
| 已知失效 | `popular/series/one`（取历史某天的榜单）需 **wbi 签名**，实测 -352（裸请求 / UA+Referer / buvid3 cookie 三种都试过）→ **不接生产** |
| 已知失效 | 频繁调用会被限流（`code=-352` 或空列表）→ adapter 已内置端点间隔与失败上报 |
| 字段变化 | 2026-10-23 实测 `popular` 新增 `ai_rcmd` / `cover43` / `pid_name_v2` / `short_link_v2` / `tnamev2` / `attribute_v3` 六个字段 → 契约闸报 CHANGED。**纯增量**，抽取的 stat/tname/bvid/pubdate 全部不受影响（215 条 0 缺失） |
| 商业使用 | ✅ 官方公开接口；**但不要引入 `bilibili-API-collect`（CC-BY-NC 禁商用）的代码** |
| 备选 | 官方开放平台 `member.bilibili.com/open`（合规但需实名认证、字段少、限频严） |

### `youtube` · 官方 RSS + Data API v3

| 项 | 值 |
|---|---|
| RSS | `https://www.youtube.com/feeds/videos.xml?channel_id=UC...` → 频道最近 ~15 条视频（标题/时间/链接），**零 key、官方** |
| Data API v3 | `search.list`（候选池）+ `videos.list?part=statistics`（播放量），两次请求 → **近 7 天高播放新视频** = 早期爆发信号的官方来源 |
| 鉴权 | RSS 无；Data API 需 `YOUTUBE_API_KEY`（免费额度 **10000 units/天**，Google Cloud 自助申请） |
| 已知失效 | `feeds/trending.xml` / `trending.rss` → **404，官方已下线** |
| 已知失效 | `youtube.com/feed/trending` 的视频列表**不在 SSR 的 `ytInitialData` 里**（由前端 continuation 拉取）→ 改用 Data API 的近期高播放查询，**比 trending 更贴题** |
| 商业使用 | ✅ 官方接口 |

**Data API 的正确用法（全部为 2026-10-23 实测，不是文档抄写）**

| 事项 | 结论 |
|---|---|
| `order=viewCount` | ❌ **`search.list` 没有这个枚举值。传了照样返回 200，但结果根本不按播放量排** —— 静默失效，最危险。正确做法：`order=relevance` 取候选 → `videos.list` 取 statistics → **本地按 viewCount 排** |
| `items[i].id` | 是嵌套对象 `{"kind":"youtube#video","videoId":"..."}`，**不是字符串**。直接 f-string 会把整个 dict 拼进 URL |
| 排序取值 | 同一关键词 `AI\|LLM\|agent\|GPT\|Claude`、7 天窗口、top20 命中 AI 的条数：`date` 16/20 但播放量仅 6k–284k（只给刚上传的，增速信号不可用）；**`relevance` 18/20、播放量 166k–3.46M（用这个）**；`rating` 19/20 但混进大量 shorts 噪声；`title` 16/20 但混进非英语电视剧 |
| 赛道词必须带 | 不带 `q`（全球）时 top20 命中 AI **0/20**，全是国际新闻/体育 → 这一层不带赛道词等于没有 |
| 单次成本 | `search.list` 100 units + `videos.list` 1 unit = **101 units/次采集** → 免费额度够跑 ~99 次/天 |

**环境变量**

| 变量 | 作用 | 默认 |
|---|---|---|
| `YOUTUBE_API_KEY` | Data API 凭据。未配置 → 该端点跳过并**明确报告**「未配置」，不静默 | 无 |
| `YOUTUBE_API_QUERY` | 赛道词（`\|` 分隔）。改了它就改了这一层关注的题材 | `AI\|LLM\|agent\|GPT\|Claude` |

**key 的注册（本机已配好，2026-10-23）**

- Google Cloud 项目 `aigc-hotspot`（无 organization，父资源 = 无）
- 启用 API：**YouTube Data API v3**
- key 名 `hotspot-youtube-data-v3`，**API 限制 = 只允许 YouTube Data API v3**，应用限制 = None
  （本机走 `127.0.0.1:10808` 代理，出口 IP 会变，绑 IP 会误伤；API 限制已经收窄了爆炸半径）
- key **只写进用户级环境变量，不进仓库、不进日志**
- 未启动免费试用、未绑信用卡 → 不产生费用

**RSS 端点本身在抖（实测）**

同一个 URL、同一 UA，在 3 秒内出现 `200 / 404 / 500` 混合，成功率约 40–50%，**与 UA 无关**。
因此 adapter 对 RSS 做了 4 次退避重试；并且 **RSS 与 Data API 是独立层，RSS 挂掉不能把整个 YouTube 源判死**（否则一个 404 就把唯一带播放量的那层一起带走）。


---

## 2. 备选源（未接入，附理由）

| 源 | 能力 | 不接的原因 |
|---|---|---|
| 巨量算数 `trendinsight.oceanengine.com` | 抖音官方：热点追踪 / 话题分析 / 人群洞察 / **创作指南**（垂类内容形式、黄金时长） | ✅ HTTP 200 可达，但**无开放 API**，数据在内部接口里；页面级取数需要逆内部接口，稳定性与合规都不明。**待接入**，先只当人工查询工具 |
| `ReaJason/xhs` | 小红书笔记详情/搜索/评论/笔记监控 | 需 Cookie + Playwright 签名，1–2 周过期，有滑块风控；小红书对本号是次要分发渠道，**先用 60s 的小红书热榜** |
| `NiNamerR/xhs_spider` | 小红书采集 | 370 star 但主体是引流到 TG 卖 API，灰产倾向，不采用 |
| `SocialSisterYi/bilibili-API-collect` | B 站 API 文档 | **CC-BY-NC 禁商用** → 只读文档借鉴，代码不进链路 |
| `scrapebb` | B 站搜索+弹幕数据集 | MIT 但本质是爬虫；B 站官方接口已够用，不引入 |
| 第三方聚合（极致了数据 / Apify 等） | 全平台视频级数据 | **按量付费**，与「不花钱」的前提冲突 |
| 红狐数据 redfox.hk | 抖音热榜/日榜/飙升榜/搜索/聚类/违禁词 | **收费**。其能力已被上面三个免费源覆盖大部分，剩余部分（飙升榜/泛化词拓展/聚类）自研，见 `topic-scout` |

---

## 2.5 对标语料（非热点源，单独一个采集面）

### `tiktok` · Hugging Face 公开元数据语料

**先说结论：TikTok 没有免费、合规、实时的视频级 API。** 2026-10-23 逐条实测：

| 路线 | 实测结果 |
|---|---|
| 官方 Research API | 需学术/机构身份 + 审批，禁商用 |
| 官方 for Business API | 只给自家广告数据 |
| **Creative Center**（官方免登录） | `creative_radar_api` 返回 `{"code":40101,"msg":"no permission"}` → 需 cookie，按规则**不做登录态** |
| TikTok 话题页 HTML | 200 / 388KB，但视频数据已不在 HTML（纯前端拉取），`itemStruct` 0 条 |
| tikwm.com（免费第三方） | `/api/feed/list?region=US` → `code=0 success`；但 `/api/feed/search` 与 `/api/user/posts` 撞 Cloudflare **403**，限 1 req/s，**无关键词能力** |
| 第三方付费（Apify / SociaVault / TikLiveAPI） | 收费，与「不花钱」冲突 |

→ **不接实时链路**。可用的替代是**语料型对标**：

| 项 | 值 |
|---|---|
| 数据集 | `datasocial/tiktok-5.6B-videos`（Hugging Face） |
| 规模 | 5.6B 条公开视频元数据，148 个月度 Parquet 分区，共 460GB |
| 实际只用 | **最新月一个分区 191MB**（部分月）；历史月每个 10–12GB，**不要整月下载** |
| 取数方式 | HTTP range read 可用（`resolve/main/data/data/YYYY-MM.parquet`），不必下全量 |
| 字段 | 31 个，含 `caption` `hashtags` `on_screen_text` `views` `likes` `comments` `shares` `saves` `downloads` `engagement_rate` **`is_ai_generated`** `not_recommended_for_fyp` `country` `language` `posted_at` `duration_ms` `sound_id` |
| 时效 | ⚠️ **月更且滞后**。实测最新分区只覆盖 **2026-10-01 ~ 10-03**（2.5 天），**滞后约 20 天** |
| 许可 | ⚠️ **CC BY-NC 4.0（禁商用）**。数据集卡片原文：*"free for research and personal use. **Commercial use**, creator profiles and daily updates: datasocial.ai."* → **发布方明确切走了商业使用**，本号变现即属其定义的 commercial use |
| 来源合规 | ⚠️ 第三方**逆向 TikTok 私有移动 API** 采集（伪造设备身份、反解签名），违反 TikTok 服务条款 3.4 |
| 定位 | **只做本地私有对标**（别人怎么写、播放量多少、屏幕文字怎么设计） |
| 硬规则 | ✅ 读它形成**自己的判断**、发布**自己的话**、用**聚合统计**；❌ 不把 caption/屏幕文字**原文**搬进发布物、不再分发数据、不做生产采集链路。**用 `tiktok_bench.py check <稿子>` 守住**（实测 3/3 用例：抄原文 FAIL、干净稿 PASS） |
| 商业使用 | ❌ **禁商用**。账号要变现的话，这条边界要自己把关；规模上去应走 datasocial.ai 的商业授权 |
| 替代（许可干净） | ✅ **TikTok 官方 Creative Center hashtag 趋势榜**：`ads.tiktok.com/creative/creativeCenter/trends/hashtag?region=US&period=7`，浏览器**免登录**可读 hashtag + posts + views + 趋势曲线 + 行业分类 + 地区 + 周期（DOM 可完整抽成文本）。**但官方 API `creative_radar_api` 即使带浏览器会话也返 40101**（数据是服务端渲染的，没有可直连接口），且**免登录只给 top 3**（更多要 TikTok for Business 登录）→ **只能按需用浏览器读，做不进 cron 管线** |
| 不做 | ❌ 不进 `snapshots/` ❌ 不进 `contracts/` ❌ **不参与五信号打分**（滞后数据会把三周前的话题伪装成"正在火"） |

**两条轴必须分开**（实测 2026-10 分区，2.5 天）：

| 轴 | 条数 | 含义 |
|---|---:|---|
| `is_ai_generated = 1` | **84,804** | 这条视频**是用 AI 做的**（CapCut 特效、AI 短剧） |
| 主题是 AI（严格口径） | **2,434** | 这条视频**在讲 AI** ← 这才是对标语料 |

差 35 倍。TikTok 上「AI」流量的大头是「用 AI 做内容」，不是「讲 AI 工具」。

用法与过滤规则见 [SKILL.md](SKILL.md) 与 [references/tiktok_filter.md](references/tiktok_filter.md)。

---

---

## 3. 不纳入本工作流的 skill

`douyin-viral-content` 插件（红狐数据）提供的 7 个 skill **全部不纳入本工作流**：

| 原 skill | 由谁替代 |
|---|---|
| `douyin-hot-trend` | `sixty/douyin` |
| `douyin-daily-hot`（28 赛道） | `bilibili` 分区榜（`tname`，100+ 赛道，更细） |
| `douyin-content-surge`（新增点赞飙升） | **自建**：快照差分 |
| `douyin-weekly-surge` | **自建**：快照差分 |
| `douyin-search`（泛化词拓展） | **自建**（LLM） |
| `douyin-ai-feed`（自动聚类） | `sixty/ai-news` + **自建**（LLM） |
| `douyin-prohibited-word` | **自建**（本地词库） |

本机未配置 `REDFOX_API_KEY`，调用这 7 个 skill 会直接报错（不会静默失败），但**建议在应用的插件管理界面卸载该插件**，避免以后又走付费路线。

---

## 4. 月度合规与额度复核清单

- [ ] 各平台用户协议 / 开发者条款是否变化（尤其抖音、B 站、YouTube）
- [ ] 是否有 CC-BY-NC / 非商用协议的库被误引入生产链路
- [ ] 60s 公共实例的每日额度是否被收紧（考虑自部署）
- [ ] YouTube `YOUTUBE_API_KEY` 额度是否被调整
- [ ] 是否新增了登录态依赖（Cookie 过期 / 小号轮换）
- [ ] 本季度是否接入了新的源（先加到「备选源」，验证后再移入「在用源」）
