# 操作图谱｜抖音创作者中心（本机实测）

以下选择器、坐标、判据来自 2026-10-27～10-30 连续发布《天海禁声》EP1–EP4 的实测。页面会随平台改版漂移：**坐标是当次截图标定值，每次用之前重新截图或重新 query**，不要照抄旧坐标硬点。

## 坐标换算

浏览器 viewport 950×1055；显式 `screenshot` 输出 1663×1847 ⇒ **截图坐标 ÷ 1.75 = CSS 坐标**。
clip 截图同理：clip 区域左上角是 CSS 坐标，输出图按 1.75 放大。

## 页面 URL

| 用途 | URL |
| --- | --- |
| 上传页 | `https://creator.douyin.com/creator-micro/content/upload` |
| 发布表单 | `https://creator.douyin.com/creator-micro/content/post/video?enter_from=publish_page` |
| 作品列表 | `https://creator.douyin.com/creator-micro/content/manage?tab=works` |
| 作品合集 | `https://creator.douyin.com/creator-micro/content/manage?tab=collections` |
| 新建合集 | `https://creator.douyin.com/creator-micro/content/collection/create` |

**导航限制**：`navigate` 对已加载页报 `CURRENT_TAB_OCCUPIED`；加 `replaceCurrentTab:true` 报 `Browser action failed in Electron main`。⇒ **站内跳转改用左侧导航栏按钮**（点「内容管理」「作品发布」等）。普通 `click` 触发 SPA 路由变化时会返回 `UNEXPECTED_NAVIGATION`，那通常意味着跳转已发生，接着 inspect/query 即可，不要重试。

## 表单字段

| 字段 | 定位方式 |
| --- | --- |
| 标题 | `fill` + selector `input[placeholder*="填写作品标题"]` |
| 简介 | `fill` + selector `div[contenteditable="true"]`（slate 编辑器） |
| 合集下拉 | 语义 query「请选择合集」→ `div.semi-select-selection` |
| 合集选项 | `div.semi-select-option.collection-option` |
| 序号 | 选完合集自动出现「第N集」，读页面确认 |
| 封面槽 | `div.coverControl-CjlzqC`（第一个＝横 4:3，第二个＝竖 3:4） |
| 自主声明 | 语义 query「请选择自主声明」→ `div.selectBox-buZRzi` |
| 定时时间框 | `input.semi-input[placeholder="日期和时间"]`，**`query(kind="dom", selector="input")` 查不到它**（只有标题 input 命中），要用 `query(kind="editable")` 拿 ref |
| 作品搜索框 | `input[placeholder="搜索作品"]` |
| 发布按钮 | 语义 query「发布」→ `button`（class 形如 `button-XXXX primary-XXXX fixed-XXXX`，构建哈希会变，别硬编码） |

`fill` 简介后 `ACTION_EFFECT_MISMATCH` 属正常：编辑器每段末尾插入零宽字符。用 `query(kind="dom", selector='div[contenteditable="true"]')` 看 `data-string` 文本是否逐段正确即可。

## radio 坐标（发布设置区，页面滚到底部时）

| 项 | 坐标（CSS） |
| --- | --- |
| 谁可以看 → 公开 | ≈(166, 730) |
| 保存权限 → 允许 | ≈(166, 787) |
| 保存权限 → **不允许** | ≈(305, 787) |
| 发布时间 → 立即发布 | ≈(166, 842) |
| 发布时间 → 定时发布 | ≈(305, 842) |

这些 radio 没有 semantic ref，只能按坐标点；页面滚动位置一变坐标就失效，每次点之前重新截图取坐标。

自主声明弹窗内：radio「内容由AI生成」≈(101, 355)，「确定」≈(830, 603)（同样是当次值，坐标以截图为准）。

## 封面编辑器

- 弹窗宽度超过 viewport（950），**底部「完成」按钮在竖封面模式下会跑到视口外**。解决：用 `query(kind="semantic", text="完成")` 拿 ref 直接点击，浏览器会把它滚进视口——不必切回横封面模式。
- 步骤页签：「设置横封面」≈(500, 112)、「设置竖封面」≈(628, 112)；弹窗左移时坐标同步左移，务必重算。竖封面模式下底部还会出现一个黑底「设置竖封面」按钮（≈(867, 703)），是进入竖版编辑的入口。
- 帧条容器：`.selectArea-BCIYQD`（**不是** `.preview-frames-*`，后者 scroll 恒 `atStart`）。`scroll(selector=".selectArea-BCIYQD", direction="right")` 可滚到底。
- 帧元素：`.preview-frame-rt7Mc1` 共 10 个，只在**可见范围内**才能点；用 `nth-child(N)` 点屏幕外的帧无效。
- **点缩略图会让帧条重绘并把选中项滚入视口，之前算的坐标全部失效** ⇒ 每次点之前重新 clip 一张帧条截图再算坐标。
- 点完缩略图后预览画布可能短暂全黑，等 1～2 秒再截图；画布正常时可读（有青色裁切框）。
- 裁切比例是固定的：4:3 从 1920×1080 取满高 1080，3:4 取满高 1080 ⇒ **竖排裁切后画面里若有烧录字幕，字幕一定在框内**，横排同理，无法通过拖动裁切框把底部字幕挪出去。
- 自定义上传（「上传封面」按钮）对隐藏 file input 调 `upload_files` 报 `Browser action failed in Electron main` ⇒ 只能用帧选择器。

## 作品列表与权限弹窗

- 作品列表条目含：时长、标题+简介全文、发布日期时间、状态（已发布／审核中／定时）、播放等指标。
- 搜索框对某些关键词**不会真正过滤**（例如「第二接收者已确认」命中多条），此时按卡片顺序数目标作品：`第1张卡的操作行 ≈y235，第2张 ≈y427，第3张 ≈y619`。
- 每张卡片的操作区有「编辑作品 / 设置权限 / 作品置顶 / 删除作品」；「设置权限」span ≈x718。
- 权限弹窗含「谁可以看」（公开／好友可见／仅自己可见，合集内作品该项置灰并提示「合集中的视频无法更改隐私权限」）与「允许他人保存视频」（允许／不允许）两组 radio，以及「取消 / 保存」。
- ⚠ **该弹窗是复用组件，会沿用上一次打开时的 radio 状态** ⇒ 回读落库值前先 `reload` 页面；「改完立刻重开看到新值」是内存残留，属于自证成功。逐条作品核对时每条之间都要 reload。

## 状态判据

| 观察 | 结论 |
| --- | --- |
| 点发布后跳到 `/content/manage?enter_from=publish` | 发布成功 |
| 停在原地或回上传页 | **静默失败**，作品没进后台 |
| 作品列表搜到标题且「发布日期」= 定时目标时间 | 定时已生效（未到点显示「审核中」或「定时发布中」） |
| 作品合集页「N个作品」 | 合集计数 |

定时作品在「内容管理 → 全部」里显示**「定时发布中」标记并带「修改定时」入口**；也可能显示「审核中」（审核通过后到点自动发出）。两种都算定时生效。

发布前右侧「发文助手」必须显示**作品未见异常**；否则点了也会静默失败。

## 上传页提示

- 「**超过 40 秒的视频建议上传横版视频**」——16:9 的横版长片合规，不要为此改画幅。
- 建议画幅列表含 16:9 / 9:16 / 3:4 / 4:3 / 9:19.5。
- 发文助手会提示「横/竖双封面缺失，为增加作品的流量，建议同时设置横版和竖版的封面」——双封面是平台明确建议。

## 封面来源的两条路

1. **平台帧选择器**（本 Skill 默认）：只有 10 个推荐帧，自定义上传对隐藏 file input 调 `upload_files` 报 `Browser action failed in Electron main`（隐藏 input 在弹窗重渲染下 ref 反复 `stale_element_ref`）。
2. **封面片头**：把设计好的封面做成 2～3 秒无声片头接在原片最前，平台**自动从首帧裁**横 4:3 与竖 3:4。
   ⚠ 16:9 首帧裁 3:4 只有 **810px 宽**（不是 1080），关键文字必须收进中央 810px 安全区，否则会被切掉（曾把 `zero-to-story` 切成 `ro-to-story`）。

## 多标签页与验证码

- **不要为重传另开标签页**：新开的创作者中心页可能一直停在「加载中…」，元素拿不到可交互 ref，`upload_files` / `back` 相继报 `stale_element_ref` / `BROWSER_OPERATION_TIMEOUT`；原标签页正常。⇒ 需要人工在 FilePanel 点回原标签页。
- **发布可能触发短信本人验证**：由用户在 FilePanel 弹层内自行输入验证码，Agent 只代点「获取验证码」。
