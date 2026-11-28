---
name: comfy-h3-face-refine-executor
description: 由 Canvas worker 使用本地 H3 FaceRefine 修复单镜头内单人（solo）或双人（duet）的小脸，支持同镜头 17k+5 窗口裁切与回贴，沿用原始画面与音轨。
---

# H3 FaceRefine 局部修脸

只由画布服务执行已确认的脚本任务，遵守[本地 ComfyUI](../../../guides/local-windows.md)的机器锁、预检、单次提交、取回和验收规则。

- 支持两种模式：
  - `solo`（单人局部修脸）：连接 1 段视频和 1 张对应角色定妆图，填写 `anchor_frame`、`face_x`、`face_y`。
  - `duet`（双人同框修脸）：连接 1 段视频和按画面左右顺序排列的 2 张不同角色定妆图，填写 `anchor_frame`、`left_x`、`right_x`、`anchor_y`（右脸纵坐标不同时可另填 `right_y`）。
- 窗口对齐与长镜头支持：输入须为 24 fps 恒定帧率同一连续镜头。≤ 96 帧且未填窗口字段时整段送入；超过 96 帧的长镜头或仅需局部修脸时，在参数中填写 `start_frame`、`frame_count`（单窗最多 90 帧）及可选镜头边界 `shot_start_frame`、`shot_end_frame`，执行器会在同一连续镜头内自动按最小 `17k + 5`（5、22、39、56、73、90 帧）裁出工作窗口送入 Comfy，完成后自动将目标区间精准回贴原片并原样复制源音轨。
- 依赖 Carasibana 的 ComfyUI-H3-FaceRefine（当前接线基于 d8521d14）、face_yolov8m.pt、本地 H3 的 FL2VA INT8、NVFP4 文本编码器、H3 VAE 和 FL2V 8 步 LoRA。用 Comfy 核心视频节点保留画面时序，最终复用源音轨。
- 先核对跟踪预览视频（`track-solo` 或 `track-left` / `track-right`），再以原声、完整构图和逐帧抽查比较原片与修复版。失败或遮挡导致身份证据不足时保留未知，不用清晰度代替身份判断。

## 粗剪选段、对齐与验收

执行 Agent 按[粗剪触发与授权](../canvas-workspace/references/creative-handoff.md#粗剪审片中的局部修脸)准备输入和审片。以下为手动 FFmpeg 对照规则；在 Canvas 节点直接传入 `start_frame` / `frame_count` / `shot_start_frame` / `shot_end_frame` 时，执行器已自动完成 1～3 步裁切与回贴。

1. **对齐到同一个镜头。** 从实际采用片或合法粗剪源写下单一连续镜头边界 `[shotStart, shotEnd)` 和需要替换的画面窗口 `[start, end)`，帧号从 0 开始，出点不含该帧。对 24 fps 恒帧率源，目标帧数为 `N = end - start`。送入 H3 前，以真实画面取不小于 N 的最小 `17k+5`（5、22、39、56、73、90 帧，当前执行器输入最多 96 帧）。优先从目标出点往后取同镜头帧，尾部不足再向前取同镜头帧。同镜头帧不足或对齐长度超过执行器上限时，保留原镜头并说明缺口。不要用跨切点画面、复制末帧或等待 H3 补潜变量来凑长度。
2. **冻结左右人物和回剪偏移。** 记下扩展范围 `[workStart, workEnd)`、偏移 `offset = start - workStart` 和 N。用 FFprobe 核对实际输入帧数，检查扩展边界没有切镜。挑扩展片段中两人都可辨的一帧，以扩展片起点为 0 填锚点帧号及两张脸的坐标，并按该帧的画面左右顺序绑定本场定妆图。保存并确认独立 FaceRefine 节点，沿用原镜头的表情、视线和动作要求。原 run、定妆和既有尾帧绑定保留。
3. **裁回原长度，沿用原声。** 先核对 worker 返回的帧数、画幅和帧率与扩展片一致，再从修复画面取 `[offset, offset + N)`。原粗剪中只替换这个范围的画面，原对白、环境声和音乐保留在原轨原位置。需要独立对照时，从原 N 帧基线复用原窗口的音轨，无声源保持无声。核对回剪恰为 N 帧，帧率、画幅与原段一致，音轨按原窗口对齐。能原样封装时复制音轨并比对音频流摘要。
4. **看对照、逐帧看尾部。** 同步看原版和修复版的完整构图，结合两路跟踪预览核对左右身份，尤其是靠近、侧转和遮挡。抽出裁回后的最后 17 帧（短于 17 帧则全看），逐帧比较两张脸有没有彩色纹样、突变或闪烁，并回看首尾接缝和有关声音。保存实际检查的时间范围、路径与观察，用既有审片流程绑定裁回后的实际采用文件。证据不足标待核实，保留可用原片。

实测示例为 48 帧目标，取同镜头后续 8 帧得到 56 帧，重绘后取前 48 帧。原先第 39–47 帧两张脸的彩色伪影在对齐复测中消失。不同镜头按实际入出点算，向前取了几帧就从重绘结果跳过几帧。

### 本地确定性后期命令

在 PowerShell 中使用已检查的本机 FFmpeg。把 `$source`、`$workInput`、`$refined`、`$candidate`、`$baseline` 和 `$tailPattern` 绑定到实际路径。基线是同一目标窗口的 N 帧版本，含需沿用的原音轨。图片输出使用新的目录和含 `%03d` 的路径。把镜头边界和目标窗口分别填入 `$shotStart`、`$shotEnd`、`$start`、`$end`，并先核实镜头边界。以下两阶段在 worker 返回前后分别执行。

~~~powershell
# 只准备画面输入。将此文件导入画布并按授权确认，等待 worker 实际返回 $refined。
if ($shotStart -lt 0 -or $start -lt $shotStart -or $end -gt $shotEnd -or $start -ge $end) {
    throw 'FaceRefine 目标窗口必须在同一个镜头内'
}
$keepFrames = $end - $start
$workFrames = 5 + 17 * [int][Math]::Max(0, [Math]::Ceiling(($keepFrames - 5) / 17.0))
if ($workFrames -gt 96 -or $workFrames -gt ($shotEnd - $shotStart)) {
    throw 'FaceRefine 缺少可用的同镜头对齐帧'
}
$workStart = [Math]::Min($start, $shotEnd - $workFrames)
$workEnd = $workStart + $workFrames
$offset = $start - $workStart
ffmpeg -nostdin -v error -n -i $source -an -vf "trim=start_frame=${workStart}:end_frame=${workEnd},setpts=PTS-STARTPTS" -c:v libx264 -crf 16 $workInput
if ($LASTEXITCODE -ne 0) { throw 'FaceRefine 输入裁切失败' }

# $keepFrames 为 N。将修复画面裁回目标窗口，并接回基线音轨。
$cropEnd = $offset + $keepFrames
ffmpeg -nostdin -v error -n -i $refined -i $baseline -map 0:v:0 -map '1:a?' -vf "trim=start_frame=${offset}:end_frame=${cropEnd},setpts=PTS-STARTPTS" -c:v libx264 -crf 16 -c:a copy $candidate
if ($LASTEXITCODE -ne 0) { throw 'FaceRefine 回剪失败' }

# 左原片，右裁回后的候选。文件编号对应零基帧号。
$tailStart = [Math]::Max(0, $keepFrames - 17)
ffmpeg -nostdin -v error -n -i $baseline -i $candidate -filter_complex "[0:v][1:v]hstack=inputs=2:shortest=1,trim=start_frame=${tailStart},setpts=PTS-STARTPTS[v]" -map '[v]' -start_number $tailStart $tailPattern
if ($LASTEXITCODE -ne 0) { throw 'FaceRefine 尾帧取证失败' }
~~~
