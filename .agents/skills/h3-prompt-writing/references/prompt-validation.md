# H3 定稿提示词检查

只在完整 H3 提示词已经保存到当前 Canvas 草稿、且准备确认生成前按需读取。本检查器读取当前版本，不修改提示词、Canvas、素材、蓝图或运行状态；它不是页面强制门禁，也不替代实际视频验收。

## 适用范围

检查器覆盖当前 Canvas 已支持的 T2VA、I2VA、FL2VA 和 R2V/Ref2VA。它核对 H3 字段顺序、基础模式首行、Shot 编号和切点、实际参考槽、`<d>` 标签、S 编号、reference retention，以及可用时的当前 Panel 蓝图和锁定对白。

它只从当前快照判断机械事实。以下内容仍需创作者或实际验收处理：素材画面中的人物身份、空间与表演是否正确、人物和 `(Sx)` 的身份绑定、蓝图没有记录的准确切点、复杂跨镜/合唱/复用音频对白，以及最终画面和声音是否可用。

当前格式依据见[基础格式](base-en.txt)和[全参考格式](ref-en.txt)。检查项的外部问题清单参考来自 [chenyk1992/manju-laoli-skill](https://github.com/chenyk1992/manju-laoli-skill) 固定版本 [`079df685f7cf2f0de635362bd359c233db38f9fe`](https://github.com/chenyk1992/manju-laoli-skill/tree/079df685f7cf2f0de635362bd359c233db38f9fe)；脚本按本项目 Canvas 契约独立实现，未移植其代码。

## 调用时机与命令

调用方先保存当前 Panel 的草稿，再使用其 Canvas ID、视频节点 ID 和刚读到的版本号运行：

~~~powershell
./.venv/Scripts/python.exe .agents/skills/h3-prompt-writing/scripts/validate_prompt.py `
  --canvas-id CANVAS_ID --node-id NODE_ID --expected-version VERSION --json
~~~

有现成 `creative_blueprint.json` 时，`--blueprint` 和 `--panel-id` 必须一起提供：

~~~powershell
./.venv/Scripts/python.exe .agents/skills/h3-prompt-writing/scripts/validate_prompt.py `
  --canvas-id CANVAS_ID --node-id NODE_ID --expected-version VERSION `
  --blueprint path/to/creative_blueprint.json --panel-id P001 --json
~~~

可选 `--project` 指定项目根目录，`--url` 指定已经运行的 Canvas 服务。脚本只发送 `GET` 请求；服务离线时报告缺口，不会调用 `ensure_server`、启动服务、冻结输入、确认生成或重试。检查依据中的 `canvas_version`、`input_digest` 和可选 `blueprint_digest` 用于标识本次读取，不是授权或锁。

## 结果解释

| 状态 | 退出码 | 含义与下一步 |
| --- | --- | --- |
| `passed` | 0 | 已覆盖的机械检查没有错误，也没有相关未知项；仍需按原流程确认当前输入和验收实际媒体。 |
| `needs_review` | 0 | 没有确定性错误，但有警告或 `unverified`；主会话核对相关事实，不自动增加用户审批。 |
| `failed` | 1 | 当前草稿存在明确的格式、时序、槽位或可比对计划错误；修正草稿后重新读取并检查。 |
| `unavailable` | 2 | 服务、readiness、版本、有效输入或 JSON 输入无法作为本次结论的可靠依据；先解决具体缺口，再从当前版本检查。 |

`unverified` 不是通过，也不等同错误。它表示现有结构没有足够依据去自动判断，例如 R2V 的第 0 帧视频引导、蓝图未记录的切点，或不能唯一归属的跨镜对白。检查通过只代表该版本的文本和当前可检查输入没有发现确定性错误；它不表示生成已提交、媒体已产生或结果已经 `ACCEPT`。

提示词、参数、运行时素材、相关蓝图或 Canvas 版本改变后，重新检查受影响的当前 Panel。输入没有变化时，不需要为了形式重复扫描整章。草稿阶段可以继续创作；生成前 Canvas readiness 报出的实际素材或能力缺口不能由本检查器覆盖。
