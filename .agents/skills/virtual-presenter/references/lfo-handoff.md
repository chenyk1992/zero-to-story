# LFO Handoff

## 边界

Skill 只交付公共执行包和已确认素材语义。LFO Runtime 负责素材导入、后端选择、生成、标准化、QC、时间线、音频和导出；Skill 不写数据库、ComfyUI 节点、模型路径、内部素材 ID 或平台缓存路径。

适配器入口固定为：

- lfo.skill_adapter.virtual_presenter.build_shot_package
- lfo.skill_adapter.virtual_presenter.build_assembly_package

这两个函数负责把已确认的 Presenter Plan/Shot Contract 转成 LFO 可校验的执行包。若运行环境尚未提供模块或函数，保持计划为 暂停 并报告缺失接口；不要在 Skill 目录里复制一个“伪适配器”。

## Shot package 约定

对每个画幅和 shot 调用 build_shot_package，传入已经确认的 Shot Contract、H3 最终提示词、素材语义映射、项目标识、revision 和连续性信息。函数的具体 Python 签名由仓库适配器定义；Skill 不猜测位置参数，优先按仓库公开的命名参数或 Builder 使用方式调用。
当前仓库适配器公开的命名入口为：

    build_shot_package(plan, shot_id, *, previous_clip_uri=None, package_revision=1)
    build_assembly_package(plan, accepted_clips, *, package_revision=1)

shot plan 至少提供 project、inputs、output、shots 和 approval；shot 提供 shot_id、sequence、duration_ms、prompt、environment_view_uri；组装使用已接受片段的 shot_id、sequence、duration_ms 和 package-relative uri。若仓库接口发生变化，先读取实现和测试再更新本 Skill，不把这些字段猜写到 LFO 内部。

素材语义映射固定如下，不能因为缺失一项而移动编号：

| package 槽位 | 语义 | H3 提示词标签 |
|---|---|---|
| ref_image_0 | 角色图/身份锚点 | `<Picture 1>` |
| ref_image_1 | 360°全景或环境源 | `<Picture 2>` |
| ref_image_2 | 当前 yaw、pitch 0°、FOV 90°方向视图 | `<Picture 3>` |
| ref_audio_0 | 声音参考 | `<Audio 1>` |
| ref_video_0 | 同画幅上一条已接受片 | `<Video 1>` |

首片没有上一条接受片时省略 ref_video_0，绝不拿 contact sheet 或其他图片填补。第二条起，只有 PASS 或用户明确接受的 REVIEW 输出才能成为同画幅下一条的 ref_video_0；横竖画幅维护独立连续性链。上一条的路径和素材语义保持可追溯，不能把正在重做的失败片当作连续性输入。

存在 ref_video_0 时默认不再附加 ref_audio_0，让 Presenter 继承上一片视频的配对音轨。只有 Scene D 对比确认声音评分不下降且连续性不降低，才在 Shot Contract 设 `include_voice_reference: true`，让适配器同时映射独立声音参考。

每个包至少记录 project_id、package kind、shot_id、画幅、duration、prompt revision、references、dependencies 和 output 语义。包内的 duration 必须与 Shot Contract 相同且在 4–15 秒；任何修改都提升 revision。

## validate、plan、execute

每个 shot package 生成后依次运行：

1. lfo validate package；
2. lfo plan package；
3. 读取 resolved references，核对 `ref_image_0/1/2`、`ref_audio_0`、后续 `ref_video_0` 与 `<Picture 1/2/3>`、`<Audio 1>`、`<Video 1>`；
4. 把 validate 和 plan 的摘要写回 presenter_plan.md；
5. 检查本次执行是否落在已记录授权范围内，再调用 LFO execute。

计划通过不等于执行授权。完整计划确认授权两个画幅的首片；两个首片分别确认后，授权未改变方案的剩余 Shot、QC 和最终组装自动推进。授权记录包含时间、package revision、画幅、范围和用户原文/摘要；超出范围时暂停。执行失败按 LFO 恢复规则处理，不在 Skill 中直接改数据库或复制 CAS。

## 两个画幅的首片

完整 Presenter Plan 确认后，为每个目标画幅各构建并计划 S001。分别展示两个输出，分别记录用户的明确接受依据和 baseline。两者均确认后，剩余 shot 按 Shot Plan 自动生成、QC 和串接；不要求用户逐片确认。

若任一首片不接受，允许只针对对应画幅修订并重做；两个画幅的首片都通过前不启动剩余片。若用户改变方向、区域、角色、声音、时长、画幅或表演预算，所有受影响 package 作废，提升 revision，回到直接上游确认。

## Assembly package

所有目标画幅的片段均已通过 QC（或用户明确接受 REVIEW），并且没有暂停项后调用 build_assembly_package。传入已接受片段的有序清单、画幅、音频策略、字幕/文案语义、project_id 和 revision；不要让组装器重新生成语义镜头。

最终视频后端固定为 video.passthrough：片段顺序、每段时长、音频/字幕时间线和输出目录交给 LFO Runtime 的公共契约。Assembly package 同样依次 validate、plan；若没有改变已确认计划或 baseline，则沿用自动推进授权执行。最终输出必须遵守 LFO 的项目 Run artifact layout；Skill 不在 workspace 根目录创建 runs 或 exports。

## 接口假设与故障处理

当前 Skill 假设适配器公开上述两个入口，并能接受“Shot Contract + 提示词 + 引用语义 + project/revision”的构建请求，返回可被 LFO validate/plan 的 package；以及 assembly 能接受已接受片段列表并将 backend 设为 video.passthrough。具体字段名、包文件位置、字幕字段和项目路径以仓库适配器/公共契约为准。

若 validate、plan、适配器导入、引用解析或执行授权检查失败：

- 保留 presenter_plan.md、失败 package 和错误摘要；
- 不执行、不把失败片作为 accepted；
- 只在当前阶段有明确修复依据时提升 revision 后重建；
- 若缺少外部能力或同一失败连续发生，状态置为 暂停 并向用户说明需要的选择。


