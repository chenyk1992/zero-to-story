# 第二章 H3 提示词确认记录

## 结果

- 12/12 个 Panel 均已编写最终 H3 提示词，并按 `h3-prompt-writing` 的对应模式组织。
- R2V / full-reference：P001、P005、P007、P010；引用角色图只承担身份/服装参考，不冒充精确首帧。
- I2V：P002–P004、P006、P008–P009、P011–P012；每个提示词以真实上一 Panel 尾帧作为 `<Picture 1>` 的 0.00 秒精确首帧。
- 每个 Panel 均按批准的 3 个 Camera Setup 编写 3 个 `[Shot]`，未把六格 Beat 机械当成 6 个剪辑镜头。
- 关键对白逐字保留中文原文；说话人使用全章稳定 ID：程夫人 S1、苏轼 S2、苏辙 S3、巢儿 S4、老仆 S5。
- 非叙事配乐按 Panel 隔离；未把古琴、箫声或丝竹写成跨 Panel 音乐桥。书页/灰面可读文字留给确定性后期，不依赖模型伪文字。
- 最新执行记录：P001–P012 已按上述模式完成本地 H3 生成；同场 Panel 使用实际接受尾帧作为下一 Panel 的 `first_frame`，硬切场景重新绑定角色图与对应分镜板。P006 的对白顺序固定为“苏辙先揭短 → 苏轼再反驳 → 苏轼离开 → 苏辙说‘最亮的一个’”。

## 文件索引

| Panel | 模式 | 时长 | 提示词 |
|---|---|---:|---|
| P001 | full-reference R2V | 10.0s | `h3_prompts/P001_h3_prompt.md` |
| P002 | I2V | 15.0s | `h3_prompts/P002_h3_prompt.md` |
| P003 | I2V | 13.0s | `h3_prompts/P003_h3_prompt.md` |
| P004 | I2V | 14.0s | `h3_prompts/P004_h3_prompt.md` |
| P005 | full-reference R2V | 10.0s | `h3_prompts/P005_h3_prompt.md` |
| P006 | I2V | 11.0s | `h3_prompts/P006_h3_prompt.md` |
| P007 | full-reference R2V | 10.0s | `h3_prompts/P007_h3_prompt.md` |
| P008 | I2V | 11.0s | `h3_prompts/P008_h3_prompt.md` |
| P009 | I2V | 10.0s | `h3_prompts/P009_h3_prompt.md` |
| P010 | full-reference R2V | 8.0s | `h3_prompts/P010_h3_prompt.md` |
| P011 | I2V | 13.0s | `h3_prompts/P011_h3_prompt.md` |
| P012 | I2V | 10.0s | `h3_prompts/P012_h3_prompt.md` |

## 确认

用户已授权导演代理自动完成后续流程；上述提示词由导演代理按故事板、Camera Setup、角色资产和对白原文自审确认，可进入 LFO 执行包阶段。
