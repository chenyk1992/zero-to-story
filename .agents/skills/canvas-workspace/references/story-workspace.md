# 把故事资料放入一个工作空间

先按用户指定的故事范围盘点，准备一份普通画布清单 `{name, graph}`。清单放系统临时目录；正式内容保存在画布 SQLite，图片和视频保留媒体文件。现有故事或章节的具体目录规则属于调用方资料，不固化在画布基础代码。

graph.workspace 保存 story、chapter、summary 和可选 source。nodes、edges、viewport、selection 与页面相同。

- `document`：data.content 是可编辑文字；可带 category=storyboard、panel_id、description、source_path。
- `section`：data.label、width、height 定义背景分区。其余节点使用绝对画布坐标，不依赖目录层级。
- `image` / `video`：data.asset 为已有成品 `{path,kind,name}`；data.prompt 和参数是当前草稿，generation_snapshot 是原成品实际使用的只读记录。category 区分 character、board、image、video，panel_id 指明镜头，status 保留原判定；不伪造生成任务。
- 旧版本保存在 data.history 的 `{id,label,asset,generation_snapshot,status?,source_path?}` 中。实际末帧放 data.derived_outputs 的 `{id,label,asset,source_version?}` 中。相同镜头在同卡查阅版本，不同镜头的旧资料可以保留独立媒体卡。
- 提示词属于媒体组件；没有独立 prompt 或 result 类型。缺少原提示词明确说明，不能从新草稿推测原生成记录。媒体可带 prompt_source_path 从选定的 UTF-8 文本读取草稿。
- 资料关联边：sourceHandle=output、targetHandle=related，执行解析跳过这些线。实际生成输入使用 first_frame、reference_image 等端口；派生图片使用 sourceHandle=output:<派生输出id>。

推荐按“章节概览和剧本、共享角色、分镜资料、按场景排列的镜头”布局。逐镜头故事板可放视频 data.content，旧版本和末帧在卡内查看。数量较多时保持稳定的镜头顺序，由分类搜索和定位帮助导航。

## 导入工具

从项目根使用项目解释器运行：

```powershell
.venv/Scripts/python.exe .agents/skills/canvas-workspace/scripts/import_workspace.py <系统临时目录中的清单.json> --dry-run
.venv/Scripts/python.exe .agents/skills/canvas-workspace/scripts/import_workspace.py <同一清单.json>
```

先检查所有指定文件与图结构，再导入媒体并创建工作空间。document 缺少 content 时读取 source_path；image/video 缺少 prompt 时读取 prompt_source_path。已有显式文本会保留。当前成品、history、derived_outputs 内的媒体均检查并去重导入，工作区内文件直接复用。

每次实际执行创建一张新工作空间，返回带 `?canvas=<id>` 的地址。不要重复执行来更新已有画布；更新用最新版本和普通编辑接口，保留用户在页面上的改动。此工具不提交、领取或伪造任何生成任务。
