# 《一蓑烟雨》EP001 视频生成 · 交接手册

> 用于外部 agent 继续诊断 + 跑通 P001 H3 推理。
> 本机环境：Windows + PowerShell + Python 3.13 + RTX 5080 (17GB VRAM) + ComfyUI 8188 + sage-attention 2.2.0 + triton-windows 3.7.1

## 1. 项目定位

- 剧本：`.short-drama/一蓑烟雨/episodes/ep001.md`（北宋苏轼传第一集《囚车里的少年郎》）
- 当前阶段：**zero-to-story 流水线 STEP 5 实际执行**（P001 已交付 LFO，但真实视频生成卡在 ComfyUI H3 模型加载阶段）
- pipeline 已就绪：storyboard_brief.md + 5 张角色卡 + 10 张分镜板 + 10 份 H3 提示词 + execution-package.json r1 全部已确认

## 2. 当前工作目录（绝对路径）

| 路径 | 内容 |
|------|------|
| `E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\` | 剧本 + zts 流水线产物 |
| `E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_01\` | STEP 0-4 产物（brief/卡/板/H3 提示词） |
| `E:\ideaProjects\zero-to-story\workspace\一蓑烟雨\chapter_01\` | 正式 workspace 副本（含 execution-package.json） |
| `E:\ideaProjects\zero-to-story\workspace\projects\一蓑烟雨-chapter_01\` | LFO 输出根目录（run/final） |

## 3. 真实状态（关键事实，不是观点）

### 3.1 ComfyUI 服务

| 时间 | 8188 状态 | 备注 |
|------|----------|------|
| 01:14 任务开始前 | LISTENING pid=40712，rss 3.63GB，CPU 3427s 累计 | 历史已加载过 H3 |
| 01:37 后 | 8188 NOT LISTENING | daemon 已退出但 comfy-cli 内存里还有旧 PID 记录 |
| 01:48 | comfy stop 成功清理 | |
| 01:49 | comfy launch --background 成功（pid 30976） | 8188 重新 LISTENING |
| 01:49 ~ 02:19 | rss 0.97GB 僵持 30 分钟，CPU 6.5s 几乎不动，H3 模型从未真正加载到 VRAM（system_stats 显示 `torch_vram_total=0`） | 启动后一直"半死不活" |
| 02:19 | /system_stats 接口在 LFO execute 提交 H3 任务后连续 5 分钟完全无响应，最终 8188 整体崩掉 | |

### 3.2 H3 节点注册

- ComfyUI 0.33.4
- H3 节点全部可见：`EmptyMiniMaxH3LatentAV`, `MiniMaxH3ImageToVideo`, `MiniMaxH3ReferenceToVideo`, `MiniMaxH3SigmaShift`
- 启动参数：`--use-sage-attention --enable-manager`
- **关键异常**：system_stats 报 `torch_vram_total=0, torch_vram_free=0`——H3 节点虽在，但 H3 模型权重（20GB 那个）从未成功分配到 VRAM

### 3.3 LFO 行为

- `lfo validate` ✅ PASS（0 errors / 0 warnings）
- `lfo plan` ✅ PASS，锁定后端 `comfyui.h3` revision 3.0.0
- `lfo execute --approve` 第一次（前台）：0.3s CPU、0.03GB RSS 启动后立即退出，stdout/stderr 都空
- `lfo execute --approve` 第二次（Start-Process 隔离）：连续 5 分钟 lfo 进程仍在，CPU 不增长，stderr 抓不到，疑似卡在 HTTP 调用

### 3.4 验证过的环境事实

- 8188 HTTP `/system_stats` 启动后**能**返回 17GB VRAM 数据
- 启动后 0-15s 窗口内 vram 从 15.7GB 跌到 2.22GB → 暗示 H3 权重**开始过 PCIe**了
- 之后 /system_stats 完全僵死，5 分钟后 8188 daemon 死亡

## 4. 待诊断的具体问题

请外部 agent 按以下顺序排查：

### Q1. 第一次"历史 H3 加载"是怎么成功的？→ 现在的差异在哪？

- `pid 40712` 在跑 H3 时累计 CPU 3427s（≈57 分钟），VRAM 满载 12-15GB 是成功状态
- 现在的 pid 30976（comfy launch 新建）rss 0.97GB 僵持 30 分钟——H3 节点注册了但模型未加载
- **差异可能是**：
  - a) LFO execute 提交的 workflow 触发了某个**破坏性节点**（如错误的 latents 形状 / 错误的 ref_image_0 引用）
  - b) ComfyUI 启动时 torch.cuda 初始化失败但被 sage attention 兜底成功，而 H3 节点加载时才暴露
  - c) Triton-windows 3.7.1 编译触发 H3 节点路径上的某个不兼容
  - d) 模型文件本身有损坏

### Q2. 验证 H3 模型文件是否完整

- 默认位置：`D:\cyuiEnv\models\`（不在 ComfyUI 自带 models/）
- 三盘 `comfy.desktop_0/1/2` 配 shared_model_paths.yaml
- 需要确认 H3 关键 4 个文件：
  - `minimax_h3_fl2va_pruned_int8_convrot.safetensors` (20GB)
  - `minimax_h3_ref2va_pruned_int8_convrot.safetensors` (20GB)
  - `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` (16GB) — CLIP
  - H3 audio_vae (~605MB) + VAE (~5GB)
- 用文件大小+checksum 验证（如 git-lfs 校验）

### Q3. ComfyUI daemon 崩溃时是否有 Python traceback 或 Windows Application Error 日志？

- 检查 `ComfyUI\ComfyUI\user.log` 或 stdout 日志（如有重定向）
- 检查 Windows Event Viewer → Application → 最近 5 分钟的 Python / ComfyUI 崩溃
- 若 sage attention / triton 编译错误：检查 `~/.cache/torch_extensions/` 是否有半编译产物

### Q4. 用最小 workflow 独立测 H3 加载能否成功

构造一个仅 1 个 `MiniMaxH3ImageToVideo` 节点、空 prompt、空 latent 的最简 workflow，提交到 8188 看：
- 模型能否在 60-120s 内加载到 VRAM（VRAM 占用应跳到 12-15GB）
- 生成能否跑通

## 5. 可立即执行的复现命令

```powershell
# 1) 清理旧 daemon
comfy stop

# 2) 重新启动（前台而非 --background，便于看完整日志）
#    在 ComfyUI 安装目录: D:\ComfyUI\Comfy-Desktop\ComfyUI\ComfyUI
#    直接执行 main.py
cd D:\ComfyUI\Comfy-Desktop\ComfyUI\ComfyUI
python main.py --use-sage-attention --enable-manager

#    应该会看到: "got prompt" → 模型开始加载 → 几个 GB RSS 增长 → 1-3 分钟后 8188 准备好
#    观察: torch_vram_total 是否从 0 增长到 12+ GB
#    如果卡死: Ctrl+C 中断,看完整 traceback
```

```powershell
# 3) 8188 起来后立即用浏览器/curl 检查 model 加载状态
curl http://127.0.0.1:8188/system_stats

# 看 vram_total, vram_free, torch_vram_total 是否都从 0 起步
```

```powershell
# 4) LFO 这边单独试执行（前台运行能看到错误）
cd E:\ideaProjects\zero-to-story
$env:PYTHONPATH = "src"
python -m lfo.cli.main execute workspace\一蓑烟雨\chapter_01\execution-package.json --approve --verbose
```

## 6. 执行包关键信息（已确认 r1）

- `project_id`: `一蓑烟雨-chapter_01`
- `clip_id`: `panel-001`（唯一）
- `duration_ms`: 10000
- `operation`: `video.reference_to_video`
- `requirements.aspect_ratio`: `9:16`
- `requirements.megapixels`: `2.0`
- `requirements.fps`: 24
- `references` 槽位:
  - `ref_image_0` → `assets/char_su_shi_middle.jpg`（苏轼中年卡）
  - `ref_image_1` → `assets/char_chaoer_middle.jpg`（巢儿中年卡）
  - `ref_image_2` → `assets/board_P001.jpg`（分镜板）
- `prompt`: 3945 字符的 H3 six-section 提示词，逐字复制自 `zts/chapter_01/h3_prompts/P001_h3_prompt.md`

## 7. 关键文件路径清单

| 用途 | 路径 |
|------|------|
| 完整 H3 提示词 | `E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_01\h3_prompts\P001_h3_prompt.md` |
| 执行包 | `E:\ideaProjects\zero-to-story\workspace\一蓑烟雨\chapter_01\execution-package.json` |
| workspace assets | `E:\ideaProjects\zero-to-story\workspace\一蓑烟雨\chapter_01\assets\`（3 张 jpg） |
| LFO plan 摘要 | run_id = `plan-26548b9f224f`（plan 报告已生成，输出路径完整） |
| 临时执行日志 | `C:\Users\Administrator\AppData\Local\Temp\_p001_exec.log`（空） |
| 临时执行日志 v2 | `C:\Users\Administrator\AppData\Local\Temp\_p001_exec2.log`（空） |
| comfy-cli 路径 | `C:\Users\Administrator\AppData\Local\Programs\Python\Python312\Scripts\comfy.exe` |
| comfy 配置 | `C:\Users\Administrator\AppData\Local\comfy-cli\config.ini` |

## 8. 不需要重做的事

- 不需要重做 P001 H3 提示词（已通过用户审查）
- 不需要重做角色卡/分镜板（已 6/6 PASS）
- 不需要重做执行包（validate + plan 都通过）
- 不需要重做 workspace 资产落位（已复制完成）

## 9. 下一步推荐流程

1. 用前台 `python main.py` 启动 ComfyUI，看完整加载日志
2. 若加载成功：直接 `lfo execute` 重跑 P001
3. 若加载失败：根据 traceback 修复（最可能是 H3 模型文件损坏 / triton 编译失败 / CUDA 状态问题）
4. 若本机 8188 持续无法恢复：用 mcode-tools 的 `submit_video_generation` 走外部 H3 推理，产物放回 workspace 目录让 LFO `review` 登记入库

---

## 附：失败时间线（外部 agent 不在上下文里，给出重建现场的全量信息）

```
01:14  任务开始。检查到 8188 LISTENING pid=40712 rss=3.63GB CPU 3427s（历史累计）
01:30  落位资产到 workspace（execution-package.json + 3 张 jpg）
01:31  lfo validate ✅ PASS
01:33  lfo plan ✅ PASS，backend=comfyui.h3
01:35  用户批准执行
01:37  lfo execute 前台启动 → 立即退出（0.3s CPU 0.03GB RSS，stdout/stderr 都空）
01:38  发现 8188 已 NOT LISTENING（pid 40712 早已退）
01:43  comfy stop 成功清理
01:44  comfy launch --background 成功，pid 30976
01:45~  8188 LISTENING 但 rss 0.97GB 僵持，CPU 5.8→6.5s
01:48  第二次执行 → lfo 进程持续 5 分钟无变化，/system_stats 第一次抓到了 vram 2.22GB
01:50  8188 完全无响应
01:55  确认 ComfyUI 8188 已彻底崩溃（NOT LISTENING）
02:19  后台任务被系统判定失败
```

**外部 agent 工作目标：先恢复 ComfyUI 能独立加载 H3（前台模式，捕获完整日志）；恢复后再让 LFO 接管。**
