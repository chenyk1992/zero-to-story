# STEP 3 生成与版本台账（暂停前临时版）

更新时间：2026-08-30（Asia/Shanghai）  
范围：本轮 image_gen 缓存目录 `C:\Users\Administrator\.codex\generated_images\01a05148-da39-7950-84d4-c6fc7a8c177c`，以及本章 `assets/boards/candidates/`。本台账只记录 STEP 3；未进入 STEP 4。

## 判定口径

- `G`：网格为三列两行（即 2 行 × 3 列）、六格等大、整板生成。
- `S`：真正的无脸简单线框/火柴人；不得有五官、发丝/发髻、衣纹、肌肉或写实材质；环境只保留动作所需结构。
- `T`：无文字、伪文字、标签、编号、水印。
- `M`：无箭头、速度线、动作短线、漫画强调线或装饰符号。
- `B`：六格 Beat 顺序完整，后五格不重复/漏掉新 Beat。
- `A`：P002 起左上格是上一板右下格的零时长静态边界锚点；同一 Setup 的轴线和相对位置连续。
- `P`：道具状态与四肢数量可执行（每人两臂两腿；纸笺、扇子不得凭空增加手臂）。

判定是目视硬门禁；只要一项硬门禁失败，候选就不能晋级。生成缓存原图保留不动；每个原图均已补存为唯一候选路径，未覆盖候选。

## 本轮全部 image_gen 原图逐项清点

### 1. P001 v01

- 生成时间：2026-08-30 14:15:31；原图：`C:\Users\Administrator\.codex\generated_images\01a05148-da39-7950-84d4-c6fc7a8c177c\exec-24ae1a0a-d3d5-46f5-825d-009e8ebc2021.png`
- 原图：1672×941，2,095,850 bytes，SHA-256 `4EC9602180E844CB62D98BB7D68182CB7F9F26DF7C5BFF9EB8246F709EB35C49`。
- 候选归档：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P001_v01.png`；已归档；哈希与原图一致。
- 判定：FAIL。
- 硬门禁：`G=PASS`；`S=FAIL`（屋顶瓦线、水岸/石块与材质细节偏写实，多个头部出现发髻/发丝小点，扇面也有细节，不是严格的无脸火柴人）；`T=PASS`；`M=PASS`；`B=基本可读`；`A=N/A`；`P=未见明确多臂，但受 S 失败影响不可晋级`。
- 完整失败原因：本候选虽为三列两行且无文字/漫画符号，但人物与环境仍是细化的古装写实线稿，违反用户要求的“真正简单线框人偶”。不能因为网格正确就通过。

### 2. P002 v01

- 生成时间：2026-08-30 14:18:23；原图：`C:\Users\Administrator\.codex\generated_images\01a05148-da39-7950-84d4-c6fc7a8c177c\exec-c598e559-874c-45d3-ac74-be32dafe29a8.png`
- 原图：1672×941，2,022,960 bytes，SHA-256 `7F64A8C3DC15F22F670F7E03BBED85A76A70B78B7E328FD7F7824FEBE1C84751`。
- 候选归档：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P002_v01.png`；已归档；哈希与原图一致。
- 判定：FAIL。
- 硬门禁：`G=PASS`；`S=FAIL`（仍有细化屋顶、岸线和写实背景结构）；`T=PASS`；`M=FAIL`（右上格人物附近出现两条短漫画强调线）；`B=基本可读`；`A=依赖未通过的 P001 v01`；`P=PASS`。
- 完整失败原因：右上格存在明确的两条动作/强调短线；同时整体仍未达到严格火柴人样式。候选不能晋级。

### 3. P002 v02

- 生成时间：2026-08-30 14:21:21；原图：`C:\Users\Administrator\.codex\generated_images\01a05148-da39-7950-84d4-c6fc7a8c177c\exec-97a79e92-031b-48de-8ffd-84da17d4a4cc.png`
- 原图：1672×941，1,884,858 bytes，SHA-256 `9D5D3B9F07F9CA0BFCB077DA44360B09C1F43C72A8AC23587CFE5BF31B457C81`。
- 候选归档：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P002_v02.png`；已归档；哈希与原图一致。
- 判定：FAIL。
- 硬门禁：`G=PASS`；`S=不通过`（继承较细化的环境/人物线稿）；`T=PASS`；`M=PASS`；`B=基本可读`；`A=FAIL`（后续锚点本身不可用）；`P=FAIL`（右下格从画面右侧伸入多只手/多张纸笺，单一钱翁身体出现不可能的多臂、多手递笺结构）。
- 完整失败原因：右下格不是“一个钱翁、两臂、题笺待呈”的可执行末态，而是多个悬空手臂/纸笺从右边同时出现；这会污染 P003 左上格。无漫画短线不等于道具/肢体逻辑正确。

### 4. P003 v01

- 生成时间：2026-08-30 14:23:22；原图：`C:\Users\Administrator\.codex\generated_images\01a05148-da39-7950-84d4-c6fc7a8c177c\exec-1620250b-776e-4a83-b938-9860fd8ea5d7.png`
- 原图：1672×941，1,800,488 bytes，SHA-256 `FFFB875525D14EE9C1BA77E983FFB1A739E7F165C0B29F351B9094E960077743`。
- 候选归档：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P003_v01.png`；已归档；哈希与原图一致。
- 判定：FAIL。
- 硬门禁：`G=PASS`；`S=基本线框但环境仍偏细`；`T=PASS`；`M=FAIL`（右上格人物头部两侧出现多条短动作线）；`B=不完整`；`A=FAIL`（左上格未可靠复现 P002 v02 右下末态）；`P=PASS`。
- 完整失败原因：出现漫画式短线，且左上锚点没有稳定承接上一板的“题笺待呈/钱翁未报题”状态；候选不能晋级。

### 5. P003 v02

- 生成时间：2026-08-30 14:25:30；原图：`C:\Users\Administrator\.codex\generated_images\01a05148-da39-7950-84d4-c6fc7a8c177c\exec-7ba14c28-40c1-45ed-877f-511fc0011fe7.png`
- 原图：1672×941，1,761,142 bytes，SHA-256 `C23D0ADEBC6A07AA5D97BA2B394442D0E6FFA0CD78EA184F2D10523AB87A89C4`。
- 候选归档：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P003_v02.png`；已归档；哈希与原图一致。
- 判定：FAIL。
- 硬门禁：`G=PASS`；`S=PASS/可接受`；`T=PASS`；`M=PASS`；`B=FAIL`（下排末两格近似重复“钱翁举笺”，没有清晰落到 B016“众人将笑未笑”）；`A=FAIL`（左上格不是 P002 v02 右下格的静态边界）；`P=PASS`。
- 完整失败原因：无明显文字或漫画线，但连续性和 Beat 覆盖不成立：首格没有复现上一板末态，且末两格没有把“聚宝塘”落音推进到将笑未笑。不能以“画面看起来像同一场景”替代边界锚点和 Beat 证据。

### 6. P003 v03

- 生成时间：2026-08-30 14:28:58；原图：`C:\Users\Administrator\.codex\generated_images\01a05148-da39-7950-84d4-c6fc7a8c177c\exec-91103dad-4a29-4238-99ce-032691912bc0.png`
- 原图：1672×941，1,860,016 bytes，SHA-256 `C45A670A8FA6AB2FD34B9794C786A32A883BFC00BB741A3170DFB93C834BF685`。
- 候选归档：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P003_v03.png`；已补存；哈希与原图一致。
- 判定：FAIL。
- 硬门禁：`G=PASS`；`S=PASS/可接受`；`T=PASS`；`M=PASS`；`B=FAIL`（末格仍未明确出现群体将笑未笑）；`A=FAIL`（左上格是一般水榭群像/钱翁站立举笺，不是 P002 v02 右下的静态待呈末态）；`P=PASS`。
- 完整失败原因：针对 v02 的提示词虽然要求复现边界，但图像仍把左上格推进成了新的呈笺/站立状态，且 B016 仍缺失或被重复的举笺动作替代。该候选是 P003 v03，不能与后来的 P003 v04 混写。

### 7. P003 v04

- 生成时间：2026-08-30 14:32:04；原图：`C:\Users\Administrator\.codex\generated_images\01a05148-da39-7950-84d4-c6fc7a8c177c\exec-15e0cdb0-6a73-475a-8673-bd43d9fe6ec1.png`
- 原图：1672×941，1,855,215 bytes，SHA-256 `931DE89BAB73D0A8415FF0D74AB3316DF5F92CF79CC12180388B390BB2C230D9`。
- 候选归档：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P003_v04.png`；已归档；哈希与原图一致。
- 判定：FAIL。
- 硬门禁：`G=PASS`；`S=PASS/可接受`；`T=PASS`；`M=PASS`；`B=基本覆盖`；`A=语义上更接近 P002 v02 右下，但依赖的末态本身无效`；`P=FAIL`（左上锚点重现了多张纸笺/悬空手臂的多臂结构）。
- 完整失败原因：v04 是在针对 v03 锚点失败后继续尝试的版本，所以编号到 v04；它改善了“坐着的钱翁+右侧待呈”的语义，但把 P002 v02 的错误多手结构一起复制，仍不具备可执行道具/肢体状态。该板不能晋级。

### 8. P002 v03（14:33:43、2,044,899 bytes 的输出）

- 生成时间：2026-08-30 14:33:43；原图：`C:\Users\Administrator\.codex\generated_images\01a05148-da39-7950-84d4-c6fc7a8c177c\exec-853f7187-236b-42f4-aa89-bdff26da10f3.png`
- 原图：1672×941，2,044,899 bytes，SHA-256 `AAD37639A849152109DDBE078818A17E17DB6D0C3C5112449EA89470D1B56304`。
- 候选归档：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P002_v03.png`；已补存；哈希与原图一致。
- 判定：FAIL。
- 硬门禁：`G=PASS`；`S=FAIL`（头部出现发髻/小发点，屋顶瓦线、水面、岸石和背景过度细化，仍不是严格火柴人样式）；`T=PASS`；`M=PASS`；`B=基本可读`；`A=依赖当时的 P001 v01，后续需以通过版 P001 重新核对`；`P=基本PASS`（未见 P002 v02 那种悬空多手，但全板已因 S 失败）。
- 完整失败原因：这是 P002 的第三个版本，不是 P003 或 P001 的回退。14:33:43 的 2,044,899-byte 文件经原图路径和哈希核对，明确归属 P002 v03；它因严格风格门禁失败，未晋级。

### 9. P001 v02

- 生成时间：2026-08-30 14:35:26；原图：`C:\Users\Administrator\.codex\generated_images\01a05148-da39-7950-84d4-c6fc7a8c177c\exec-8b0805c6-8be4-435d-923b-5260517c1ef8.png`
- 原图：1536×1024，2,191,540 bytes，SHA-256 `A8B1F6966F4D3037D1CD49BBD9FE4900B2249889D9BAEBC315106E34E09BC63E`。
- 候选归档：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P001_v02.png`；已归档；哈希与原图一致。
- 判定：FAIL。
- 硬门禁：`G=FAIL`（图像为两列三行，不是规定的三列两行）；`S=FAIL`（右下人物头部出现可识别的面部点，且版式不符合目标粗线框）；`T=PASS`；`M=PASS`；`B=FAIL`（错误网格方向使既定阅读顺序不可直接成立）；`A=N/A`；`P=PASS`。
- 完整失败原因：这是对 P001 重新生成的 v02，不是 P003 v02。它的 1536×1024 尺寸不能证明网格正确；目视网格为 2 列 × 3 行，且右下头部有面部点，因此不能通过。

### 10. P001 v03

- 生成时间：2026-08-30 14:36:45；原图：`C:\Users\Administrator\.codex\generated_images\01a05148-da39-7950-84d4-c6fc7a8c177c\exec-beac3269-0390-498d-b52b-2d4933b39a33.png`
- 原图：1536×1024，1,460,762 bytes，SHA-256 `C5A257566C57F07A64DD383B186206DD53B08792F383B35962ED0C70B334184D`。
- 候选归档：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P001_v03.png`；已补存；哈希与原图一致；外层调用虽在 14:36:45 后被中止，生成缓存中的原图已完整存在，不能丢失或改记版本。
- 判定：PASS（候选级、待主代理最终门禁；尚未替换正式板）。
- 硬门禁：`G=PASS`（三列两行、六格等大）；`S=PASS`（空白圆头、简单线段四肢、无发丝/五官/衣纹；环境只保留水池、棚架、桌凳结构）；`T=PASS`；`M=PASS`；`B=PASS`（P001 B001–B006 由建立池畔到主持/动笔顺序清晰）；`A=N/A`；`P=PASS`（扇子为单一简单道具，未见多臂）。
- 结论：这是本轮唯一达到候选级全硬门禁的输出；由于当前任务已要求停机清点，未将它晋级为 `assets/boards/board_P001.png`，由主代理作最终门禁决定。

## 为什么 P003 到了 v04，又出现 P001 v02

版本号按 Panel 独立计数，不是全局计数，也没有回退：

1. P003 依次在 14:23:22、14:25:30、14:28:58、14:32:04 生成 v01、v02、v03、v04；每次都保留了失败候选。
2. P003 v04 之后，工作对象切换回 P002 做其自己的第三次修订，产生 14:33:43 的 P002 v03。
3. 随后重新审查 P001，产生 P001 v02（14:35:26）和 P001 v03（14:36:45）。因此“P001 v02”是 P001 的版本号，不是 P003 从 v04 回退到 v02。
4. 所有本轮原图均在同一生成缓存目录，但 Panel/版本绑定由生成时的任务记录和候选文件名确定；不能仅按文件大小或文件夹顺序推断归属。

## 候选归档补齐结果

本轮十个 raw image_gen 输出现已全部有不可变候选路径：

- P001：v01、v02、v03；其中 v03 为候选级 PASS，v01/v02 FAIL。
- P002：v01、v02、v03；全部 FAIL，v02 的多手/多笺错误不得作为后续锚点。
- P003：v01、v02、v03、v04；全部 FAIL；v03 已补存，不能再出现“raw 有文件、候选缺 v03”的断档。

同时，既有正式板已保存为旧证据 v00（不是本轮 image_gen 输出）：`board_P001_v00.png` 至 `board_P012_v00.png` 均为 1672×941，且旧板全部未达到本轮严格火柴人风格门禁。P003–P012 的 v00 是本次补齐的旧正式板副本，未删除任何旧文件。

当前正式文件状态需注意：`assets/boards/board_P001.png` 仍是先前 v01 内容，`board_P002.png` 仍是先前 v02 内容；本次独立复检已经判定二者不通过，但暂停清点期间没有再次覆盖正式文件。P003–P012 正式文件仍是旧板，均只作为 v00 证据。

## 本次追加候选（P001 严格极简火柴人风格修订）

### P001 v05

- 生成时间：2026-08-30 约 15:00；原始生成图：`C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-0f358892-e202-4848-bd1e-2ed3f8854531.png`
- 原始图尺寸：1672×941，1,099,750 bytes，SHA-256 `90A9AFEECB27D10EED8D238F4F14C9EF57F55F0E6CC2C727DBE4D9E850BAB46D`。
- 候选归档：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P001_v05.png`；已复制归档，原始图保持不动，未覆盖正式 `board_P001.png`。
- 生成子代理说明：按主代理指令仅完成一次 ImageGen 调用与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 生成子代理说明：按主代理指令仅完成一次 ImageGen 调用与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 针对性修订：修正 `STYLE-MODALITY-001`；将人物约束收紧为“空白圆头、单线躯干、线段四肢”，最多使用极简帽形/圆扇区分身份；禁止完整袍服轮廓、发髻、发丝、衣纹、材质、排线、写实人物；环境仅保留池岸弧、棚架/栏线、桌凳几何线和少量鱼形，禁止瓦片、竹叶、岩石纹理、水面排线、精细建筑；保持无文字、无符号、无漫画动作线。
- 完整 Prompt：

```text
Use case: illustration-story
Asset type: production storyboard board for STEP 3, Panel P001.
Create exactly one complete black-and-white storyboard board for a Northern Song historical film sequence. This is a director's rough blocking sheet, not final art and not a character concept sheet.

Canvas and grid: exact landscape 16:9. One clean board with exactly 2 rows by 3 columns, six equal rectangular cells, thin black dividers, reading order top-left to top-right then bottom-left to bottom-right. No title strip, no outer mini-panels, no merged cells, no extra cells.

Drawing language: extremely minimal rough blocking sheet. White paper, sparse black pencil or charcoal lines with only tiny light-gray geometric blocks where needed. Every human is a faceless empty circle head, one single-line torso, and simple line-segment arms and legs. Use no complete robe silhouette, no clothing outline, no fabric folds, no hair, no topknot, no face marks, no anatomy, no shading on bodies. At most, distinguish Wang Fang with a tiny simple hat shape and Qian Weng with one small circular fan; these are single geometric marks only. Anonymous scholars are identical simple stick figures. The environment is only a few straight or curved geometry lines: one pool-edge arc, a simple pavilion rail or canopy line, a table/bench line, and a few tiny fish outlines. No roof tiles, bamboo leaves, rock texture, water hatching, architectural details, material texture, crosshatching, perspective rendering, or realistic people.

Scene facts: Qing Shen Zhongyan pool and a simple waterside pavilion in daylight. Su Shi is the slim young adult man at the far-left end of the gathering, side-facing the water. Wang Fang is the middle-aged host near the center in later beats. Qian Weng is a seated scholar nearer the right foreground and may carry one tiny circular fan. Keep the same left-right axis and spatial arrangement across adjacent beats.

Six static beats, with no labels or writing visible:
1. Top-left, setup C001: wide schematic establishing view of a clear pool and simple waterside pavilion, a few tiny fish shapes in the water, small scholar gathering arranged along the bank.
2. Top-middle, setup C001, same camera and axis: fish shapes are closer/more visible in the foreground water while the scholar seating remains along the bank.
3. Top-right, setup C001, same camera and axis: Wang Fang, distinguished only by a tiny simple hat, stands at the center addressing the seated gathering; Su Shi remains at the far-left end in side profile, quietly looking toward the fish instead of the host.
4. Bottom-left, setup C002, hard cut to a simple medium group view from the same side of the waterside setting: Wang Fang raises exactly one line arm to settle the group, and scholars become attentive.
5. Bottom-middle, setup C002, same camera and axis as beat 4: Wang Fang continues speaking with one line arm raised, scholars listen. No written speech or caption.
6. Bottom-right, setup C002, same camera and axis as beat 4: scholars begin writing at their simple table line using tiny brush-line marks; Qian Weng, identified only by one small circular fan, makes a slight side glance toward distant peripheral Su Shi. No action arrows or motion lines.

Continuity: each cell is one still moment, not an animation strip. Keep Wang Fang central in beats 3–6; keep Su Shi far-left/peripheral and oriented toward the pool. No extra limbs, no duplicate people, no repeated props, no visual symbols, no movement trails.

Absolutely no visible text, pseudo-text, letters, numbers, labels, captions, subtitles, watermark, logo, UI, signature, arrow, speed line, comic emphasis mark, or motion trail. Do not make it photorealistic, cinematic, colorful, anime, manga, comic, polished illustration, detailed costume art, or realistic architecture.
```

## 同一根因连续失败与停机状态

- 已触发停机条件：P003 v02 与紧接其后的 P003 v03 都是同一根因 `CONTINUITY_ANCHOR_BEAT` 失败——左上格没有稳定复现 P002 右下边界，且 B016“众人将笑未笑”没有被可靠呈现。按规则，v03 判定失败后就应停止继续 image_gen。
- P003 v04 虽然随后已产生，但它的主失败根因已转为 `PROP_LIMB_STATE`（把上游多手/多笺错误复制进锚点），作为越过停机边界后的证据保留，不视为成功，也不再继续 P003 重试。
- 其他失败不构成连续同根因两次：P002 v01 是漫画短线，v02 是多手/多笺；P001 v01 是风格细化，v02 是网格方向/面部点；P003 v01 是漫画短线，随后 v02/v03 才是连续性根因。
- 本轮没有 image_gen 限额或工具故障；10 个缓存原图都完整存在。已按本台账补齐所有 raw→candidate 归档后停止，不进入 STEP 4。

## 本次追加候选（严格重接 P001）

### P001 v04

- 生成时间：2026-08-30 14:53:49 左右；原图：`C:\Users\Administrator\.codex\generated_images\01a0516c-58a5-7f30-a2e2-9f07973dc73b\exec-fae9fbdc-8337-4a20-a3be-47df92f1137a.png`
- 候选归档：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P001_v04.png`；原图保持不动，候选为新文件，未覆盖正式板。
- 文件尺寸：1672×941；2799208 bytes；SHA-256 `A826905E2814EDBDC4100541777CFB83455EC0DCF6E0FAAEB52E268FC1C6BA05`。
- 版本链：P001 v00–v03 既有证据均保留；v04 为本次严格重接 P001 的新候选；尚未独立 QC，未晋级正式板。
- 所用 Prompt（本次修订重点：强调精确 16:9、2 行×3 列、P001 六 Beat、火柴人/无脸/无文字/无漫画强调线；以角色卡只做身份参考）：

```text
Use case: illustration-story
Asset type: production storyboard board for STEP 3
Primary request: Create one complete black-and-white six-panel storyboard board for Panel P001 of a Northern Song historical film sequence. The image itself must be only the storyboard board, not a final film frame.
Canvas and layout: EXACT LANDSCAPE 16:9 aspect ratio, never 3:2 or portrait; one clean board with exactly 2 rows × 3 columns, six equal rectangular panels, thin dark dividers, no title band, no margins that create an extra row, no nested panels, no merged cells. Read left-to-right across the top row, then left-to-right across the bottom row.
Scene/backdrop: Qing Shen Zhongyan scenic pool beside a simple wooden waterside pavilion in daylight. Keep the setting schematic: pool edge, pavilion rail/bench, a few bamboo or stone marks, and visible fish shapes in the water. Use only structures needed to understand the action.
Subjects: use simple faceless stick-figure/line-art people only. Su Shi is the slim young man at the far left end of the gathering, in side profile toward the pool. Wang Fang is the middle-aged host standing near the center in the later panels. Other scholars are anonymous simplified line figures only, never detailed character art.
Style/medium: rough black pencil and charcoal storyboard thumbnail, monochrome black, white, and sparse gray blocks. Empty simplified heads, line limbs, minimal silhouette cues, no facial features, no hair strands, no hair buns, no clothing folds, no realistic costumes, no textures, no polished illustration.
Six static beats in exact order, with no written labels inside the image:
1. Top-left: wide establishing view of the clear scenic pool and waterside pavilion; a few fish visibly swim in the water; a small scholar gathering is arranged along the bank.
2. Top-middle: same camera/viewpoint and axis; the fish are closer/more visible in the foreground water while the scholar seating remains along the bank.
3. Top-right: same camera/viewpoint and axis; Wang Fang stands in the center addressing the seated gathering; Su Shi remains at the far left end, in profile, quietly looking toward the fish instead of the host.
4. Bottom-left: a new medium view from the same Northern Song waterside setting, axis held; Wang Fang raises one hand to settle the group, and the scholars become attentive.
5. Bottom-middle: same setup as beat 4; Wang Fang is speaking to the group with one hand raised, the group listens. Do not depict readable speech or captions.
6. Bottom-right: same setup as beat 4; the scholars begin writing on their tables with simple brush strokes, and the seated moneyed scholar Qian Weng only has a slight side glance toward the distant Su Shi. No action arrows or motion lines.
Continuity: every panel is a single static moment; no action sequence arrows, no speed lines, no repeated extra limbs. Keep Wang Fang central in beats 3–6, Su Shi far left in beats 1–3 and still peripheral in beats 4–6. The board must communicate the two setups without changing the axis.
Do not add any text, pseudo-text, characters, numbers, letters, subtitles, labels, watermark, logo, UI, speech bubbles, arrow, speed line, comic emphasis marks, motion trails, or signatures. Do not make it photorealistic, cinematic, colorful, anime, comic, manga, concept-art character sheet, or polished finished art.
```

### P001 v05 promotion

- 独立 QC 结论：PASS（主代理确认，SHA-256 `90A9AFEECB27D10EED8D238F4F14C9EF57F55F0E6CC2C727DBE4D9E850BAB46D`）。
- 提升来源：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P001_v05.png`。
- 正式文件：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P001.png`。
- 提升后正式文件与候选逐字节一致；提升后 SHA-256 `90A9AFEECB27D10EED8D238F4F14C9EF57F55F0E6CC2C727DBE4D9E850BAB46D`。候选与原始生成图均保留。

### P002 v04

- 生成时间：2026-08-30 约 15:10；原始生成图：`C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-6581ef86-40a4-4e72-9361-3b1cc1ad37c6.png`
- 原始图尺寸：1672×941，1,055,805 bytes，SHA-256 `C44C916A46B323E09BB0F306302157B368B8D4ABAEBD6D42E06EAACB278690C8`。
- 候选归档：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P002_v04.png`；已复制归档，原始图保持不动，未覆盖正式 `board_P002.png`。
- 参考素材：不可变连续性参考 `E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P001_v05.png`（P001 独立 QC PASS）。
- 生成子代理说明：按主代理指令仅完成一次 ImageGen 调用与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 针对性修订：严格承接 P001 v05 右下 B006 的静态完成态；左上仅为零时长锚点；后五格覆盖 B007–B011；强化钱翁一人两臂、单扇与单笺的道具/肢体约束；保持极简火柴人/几何环境、16:9、2×3；禁止多手、多笺从身体伸出、漫画线和任何文字。
- 完整 Prompt：

```text
Use case: illustration-story
Asset type: production storyboard board for STEP 3, Panel P002.
Input image: Image 1 is the immutable continuity reference, the approved P001 v05 storyboard board. Use it only to preserve the rough blocking-sheet drawing language, the simplified geometric pool/pavilion environment, and the B006 end-state. Do not copy the whole reference board and do not create a second board inside the image.

Create exactly one complete black-and-white storyboard board for a Northern Song historical film sequence. This is a director's rough blocking sheet, not final art and not a character concept sheet.

Canvas and grid: exact landscape 16:9. One clean board with exactly 2 rows by 3 columns, six equal rectangular cells, thin black dividers, reading order top-left to top-right then bottom-left to bottom-right. No title strip, no outer mini-panels, no merged cells, no extra cells.

Drawing language: match Image 1's extremely minimal rough blocking style. White paper, sparse black pencil or charcoal lines with only tiny light-gray geometric blocks where needed. Every human must be a faceless empty circle head, one single-line torso, and simple line-segment arms and legs. No complete robe silhouette, clothing outline, fabric folds, hair, topknot, face marks, anatomy, realistic costume, shading on bodies, material texture, crosshatching, or polished illustration. The environment is only a few geometric lines: pool-edge arc, simple pavilion rail or bench, one table/bench line, and a few tiny fish outlines. No roof tiles, bamboo leaves, rock texture, water hatching, detailed architecture, or realistic people.

Scene facts and identity marks: the same Qing Shen Zhongyan pool and simple waterside pavilion in daylight as Image 1. Su Shi is the slim young adult man at the far-left/peripheral end, side-facing and quietly watching the water. Qian Weng is the seated foreground scholar nearer the right, identified only by one small circular fan. Keep the original left-right axis, pool-side position, and simple environment. Wang Fang and the anonymous scholars remain only as minimal stick figures where required by the beat; do not add a new detailed character.

Critical boundary rule: the top-left cell is a zero-duration static boundary anchor only. It must reproduce the bottom-right B006 completion state of Image 1: scholars have begun writing at the simple table line; Qian Weng is on the right side, looking left toward peripheral Su Shi, has not spoken, and is not yet standing. Preserve one fan and ordinary two-arm/two-leg stick-figure anatomy. Do not show a new action, dialogue, timing, or transition in this anchor. The other five cells are new P002 beats and must not repeat the anchor or any other reference cell.

Six static beats, with no labels or writing visible:
1. Top-left, boundary anchor B006: the exact completed state described above, scholars writing, Qian Weng seated on the right and only side-glancing left toward Su Shi, not speaking, no new motion.
2. Top-middle, B007 / setup C003: immediately continue from the anchor; Qian Weng makes a small turn toward Su Shi while lifting or slightly waving his single circular fan. Su Shi remains at the pool edge, still oriented toward the fish. Keep Qian Weng in foreground and Su Shi in the rear/peripheral position.
3. Top-right, B008 / setup C003: same camera and axis; Qian Weng now faces left toward Su Shi in a smug speaking pose, fan in one hand, while Su Shi remains quiet and looks at the water. Convey the completed mockery only through posture and gaze; no speech text, no speech bubble, no extra action lines.
4. Bottom-left, B009 / setup C003: same camera and axis; Qian Weng has stopped and waits for a reaction, fan lowered but still in one hand; nearby anonymous scholars turn their simple empty heads toward Su Shi. Su Shi has not turned back. No repeated waving and no comic emphasis marks.
5. Bottom-middle, B010 / setup C004: hard cut to a medium close-up from the pool railing side; Su Shi alone as a minimal faceless stick figure, side-facing left toward the water and following a few tiny fish shapes. The insult is ignored. Use only the pool edge and railing geometry needed for the view.
6. Bottom-right, B011 / setup C004: same pool-side axis as beat 5; Su Shi continues looking at the fish. At a simple presentation area, show several blank, unreadable paper slips waiting to be presented, and Qian Weng with exactly one blank slip in one hand and the one circular fan in the other, still seated or just preparing to rise. There must be no duplicated paper, no floating arms, no extra hands, no readable or pseudo-text.

Continuity and anatomy: each cell is one still moment. The left-to-right relationship and axis must remain stable in C003 and C004. Qian Weng has exactly two arms: one hand can hold the fan and the other can hold one paper slip only in beat 6. The papers are blank shapes, not text. No extra limbs, duplicate props, floating hands, action arrows, speed lines, motion trails, comic emphasis marks, or symbols. Do not show Qian Weng and Wang Fang as the same person. Do not make Su Shi reply, turn away from the pool, or leave the scene.

Absolutely no visible text, pseudo-text, letters, numbers, labels, captions, subtitles, watermark, logo, UI, signature, speech bubbles, arrow, speed line, comic emphasis mark, motion trail, or decorative symbol. Do not make it photorealistic, cinematic, colorful, anime, manga, comic, polished illustration, detailed costume art, or realistic architecture.
```

### P002 v05

- 生成时间：2026-08-30 约 15:20；原始生成图：`C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-198071ed-88f2-4a60-b79a-0d920a9aa55c.png`
- 原始图尺寸：1672×941，1,263,779 bytes，SHA-256 `731115F0648D5019A84FD21C77A8303C5CF5A91E1FEB60C7E4EB10C76DA3608E`。
- 候选归档：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P002_v05.png`；已复制归档，原始图保持不动，未覆盖正式 `board_P002.png`。
- 唯一连续性参考：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P001_v05.png`；该参考由主代理独立 QC 判定 PASS。
- 生成子代理说明：按主代理指令仅完成一次 ImageGen 调用与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 针对性修订：修复 `CONTINUITY-ANCHOR-001`；将 P002 左上格设为最高优先级零时长静态边界，明确承接 P001 v05 右下 B006，同时保留中央站立王方、案边挥毫文士、右侧转头但未开口的钱翁与左侧池边苏轼；后五格才推进 B007–B011；强化单人两臂、单扇、单笺约束，禁止多手、多笺、漫画线和文字。
- 完整 Prompt：

```text
Use case: illustration-story
Asset type: production storyboard board for STEP 3, Panel P002.
Input image: Image 1 is the sole immutable continuity reference: the approved P001 v05 storyboard board. Use Image 1 only to preserve its extremely minimal stick-figure blocking language, geometric pool/pavilion layout, and the exact bottom-right B006 boundary state. Do not copy the whole six-cell board into the new image.

Create exactly one complete black-and-white storyboard board for Panel P002 of a Northern Song historical film sequence. This is a director's rough blocking sheet, not final art and not a character concept sheet.

HIGHEST PRIORITY — TOP-LEFT BOUNDARY ANCHOR:
The top-left cell is a zero-duration static boundary anchor, not a new establishing shot and not a reset. Reproduce the completed state shown in Image 1's bottom-right B006 cell. It must visibly contain all of these simultaneously: Wang Fang still standing at the center of the gathering; several anonymous scholars still seated at the simple table/bench line and already writing; Qian Weng still seated in the right-side seat, turning his empty round head toward the left-side pool edge where Su Shi sits, not yet speaking and not yet standing; Su Shi still peripheral at the left pool edge, oriented toward the fish. Preserve the pool-edge arc, simple pavilion/canopy line, table/seat positions, left-right axis, and relative placement from Image 1's bottom-right cell. Do not delete Wang Fang. Do not make everyone sit. Do not make Qian Weng stand, wave, present a paper, or begin the insult in this anchor. Do not add any new action, dialogue, timing, or transition to this anchor.

Canvas and grid: exact landscape 16:9. One clean board with exactly 2 rows by 3 columns, six equal rectangular cells, thin black dividers, reading order left-to-right across the top row and then left-to-right across the bottom row. No title strip, no outer mini-panels, no merged cells, no extra cells.

Drawing language: match Image 1's strict minimal rough blocking style. White paper, sparse black pencil/charcoal lines and tiny light-gray geometric blocks only. Every person is a faceless empty circle head with one single-line torso and simple line-segment arms and legs. No complete robe silhouette, no clothing outline, no fabric folds, no hair or topknot, no facial marks, no anatomy, no realistic costume, no body shading, no textures, no crosshatching, no polished illustration. Environment only uses a pool-edge arc, simple pavilion rail/canopy line, table/bench geometry, and a few tiny fish outlines. No roof tiles, bamboo leaves, rock texture, water hatching, detailed architecture, or realistic people. Use at most one tiny simple hat shape for Wang Fang and one small circular fan for Qian Weng as identity marks.

Scene and axis: same Qing Shen Zhongyan pool and waterside pavilion in daylight. Keep Wang Fang central, Su Shi left/peripheral by the pool, Qian Weng on the right foreground, and the anonymous scholars between/behind them. C003 and C004 must preserve their own stable axis and relative screen positions. The two setups are communicated by a view change only in the lower row; no textual labels are drawn.

The other five cells are new P002 beats only; do not repeat the anchor and do not copy other reference cells:
1. Top-left: boundary B006 exactly as specified above; static completed state only.
2. Top-middle, B007 / C003: immediately after the anchor, Qian Weng remains seated in the right foreground and turns his simple empty head toward Su Shi while lifting or making a small wave with his one circular fan. Su Shi remains at the left pool edge, still watching fish. One body, exactly two arms, fan in one hand.
3. Top-right, B008 / C003: same camera position and axis as beat 2. Qian Weng faces left toward Su Shi in a smug speaking pose with the one fan in one hand; Su Shi remains quiet, turned toward the water. Show only posture and gaze, never speech text or a speech bubble.
4. Bottom-left, B009 / C003: same C003 camera and axis. Qian Weng has stopped and waits for a response, fan lowered in one hand; nearby anonymous scholars turn their empty heads toward Su Shi. Su Shi still does not turn back. No repeated waving and no comic emphasis lines.
5. Bottom-middle, B010 / C004: hard cut to a simple medium close-up from the pool-railing side. Su Shi alone as a minimal faceless stick figure, side-facing left toward the water, following a few tiny fish outlines. He ignores the insult. Use only the pool-edge and rail geometry needed for this view.
6. Bottom-right, B011 / C004: same pool-side axis as beat 5. Su Shi continues watching fish. At a simple presentation area, a few blank paper-slip shapes wait to be presented; Qian Weng is still a single stick figure with exactly two arms, one blank paper slip in one hand and the one circular fan in the other, seated or only beginning to prepare to stand. Paper slips are blank shapes, never text. No floating arms, duplicated paper, or extra hands.

Anatomy and prop lock: every stick figure has exactly two arms and two legs. Qian Weng has exactly one body, one head, one fan, and at most one paper slip in beat 6. No extra detached hands or arms entering from the edge. No duplicate Qian Weng, no duplicate Su Shi, no duplicated props. Do not turn Qian Weng into Wang Fang. Do not make Su Shi answer, turn away from the pool, or leave.

Absolutely no visible text, pseudo-text, letters, numbers, labels, captions, subtitles, watermark, logo, UI, signature, speech bubbles, arrow, speed line, motion trail, comic emphasis mark, or decorative symbol. Do not make it photorealistic, cinematic, colorful, anime, manga, comic, polished illustration, detailed costume art, or realistic architecture.
```

### P002 v05 promotion

- 独立 QC 结论：PASS（主代理确认，SHA-256 `731115F0648D5019A84FD21C77A8303C5CF5A91E1FEB60C7E4EB10C76DA3608E`）。
- 提升来源：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P002_v05.png`。
- 正式文件：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P002.png`。
- 提升后正式文件与候选逐字节一致；提升后 SHA-256 `731115F0648D5019A84FD21C77A8303C5CF5A91E1FEB60C7E4EB10C76DA3608E`。候选与原始生成图均保留。

### P003 v05

- 生成时间：2026-08-30 约 15:30；原始生成图：`C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-8748a87a-a917-41ba-bffb-bd95058203f2.png`
- 原始图尺寸：1672×941，1,278,544 bytes，SHA-256 `066FE82FA722E743AEE1C20D12F76538CB6AFFD369BD353A3BCA1D182748A2AB`。
- 候选归档：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P003_v05.png`；已复制归档，原始图保持不动，未覆盖正式 `board_P003.png`。
- 唯一连续性参考：不可变 `E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P002_v05.png`；该参考由主代理独立 QC 判定 PASS。
- 生成子代理说明：按主代理指令仅完成一次 ImageGen 调用与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 针对性修订：严格承接 P002 v05 右下 B011 的静态状态；左上不推进报题，后五格按 B012→B013→B014→B015→B016 顺序推进；保持文士甲、王方、文士乙、钱翁的单人单笺关系；右下明确为“聚宝塘”落音后的将笑未笑，禁止提前爆笑、漏掉否题或重复举笺；保持极简火柴人、几何环境、16:9、2×3、无文字和无多手多笺。
- 完整 Prompt：

```text
Use case: illustration-story
Asset type: production storyboard board for STEP 3, Panel P003.
Input image: Image 1 is the sole immutable continuity reference: the approved P002 v05 storyboard board. Use Image 1 only to preserve its strict minimal stick-figure blocking language, geometric pool/pavilion environment, left-right axis, and exact B011 completion state from its bottom-right cell. Do not copy the entire reference board into the new image.

Create exactly one complete black-and-white storyboard board for Panel P003 of a Northern Song historical film sequence. This is a director's rough blocking sheet, not final art and not a character concept sheet.

HIGHEST PRIORITY — TOP-LEFT ZERO-DURATION BOUNDARY:
The top-left cell is a static continuation anchor only. Reproduce the bottom-right B011 state of Image 1 without re-establishing the setting and without advancing the action. Su Shi remains at the left-side pool edge, turned toward and watching the water. The simple presentation table/area still contains several blank, unreadable paper-slip shapes. Qian Weng remains on the right side as one seated stick figure with exactly one small circular fan in one hand and exactly one of his own blank paper slips in the other; he is preparing to rise but has not yet presented, reported, or spoken. Preserve the pool-edge arc, pavilion/canopy geometry, table position, and all relative placements from Image 1's bottom-right cell. Do not show a presented answer, a raised reporting pose, readable writing, or the final group reaction in this anchor. It is zero duration and has no new beat.

Canvas and grid: exact landscape 16:9. One clean board with exactly 2 rows by 3 columns, six equal rectangular cells, thin black dividers, reading order left-to-right across the top row then left-to-right across the bottom row. No title strip, extra cells, merged cells, nested boards, or unequal panels.

Drawing language: match Image 1's strict minimal director blocking-sheet style. White paper, sparse black pencil/charcoal lines and tiny light-gray geometric blocks only. Every person is a faceless empty circle head, one single-line torso, and simple line-segment arms and legs. No complete robe silhouette, clothing outline, fabric folds, hair, topknot, facial marks, anatomy, realistic costume, body shading, texture, crosshatching, or polished illustration. Environment only uses a pool-edge arc, a simple pavilion rail/canopy line, table/bench geometry, and a few tiny fish outlines. No roof tiles, bamboo leaves, rock texture, water hatching, detailed architecture, or realistic people. Use at most one tiny simple hat shape for Wang Fang and one small circular fan for Qian Weng as identity marks.

Scene and axis: same daylight Qing Shen Zhongyan pool and waterside pavilion. Wang Fang remains the central standing host; Su Shi stays peripheral at the left pool edge; Qian Weng stays on the right foreground; the anonymous scholars stay around the presentation table. C005 and C006 must each hold a stable axis and relative screen positions. Do not turn any stick figure into detailed character art.

The other five cells are new P003 beats only and must appear in this exact causal order; do not repeat the anchor:
1. Top-left, boundary B011: static completed state exactly as specified above. Qian Weng is preparing to rise, not reporting.
2. Top-middle, B012 / setup C005: immediately after the anchor, one anonymous scholar, literati A, presents exactly one blank paper slip to the central standing Wang Fang. Show a single clear handoff with simple two-arm anatomy. Su Shi remains at the left pool edge; Qian Weng remains on the right holding his own one slip and fan, waiting. No answer text is visible.
3. Top-right, B013 / setup C005: same camera and axis as beat 2. Wang Fang, identified only by a tiny simple hat, gives a clear head-shake/rejection after seeing the first blank slip; the first slip is being withdrawn or held back. This is the first answer denied. Do not show a second answer, a proud Qian Weng pose, or a smiling crowd.
4. Bottom-left, B014 / setup C006: hard cut to the next answer. A different anonymous scholar, literati B, presents exactly one blank paper slip toward Wang Fang. Keep Qian Weng on the right waiting with his own single slip and fan. Do not duplicate the first presenter or create extra papers or arms.
5. Bottom-middle, B015 / setup C006: same C006 camera and axis as beat 4. Qian Weng now proudly raises/presents his one personal blank paper slip, keeping the one circular fan in his other hand. Wang Fang and the group look toward him. This is the proud presentation immediately before the joke lands; no written answer is visible.
6. Bottom-right, B016 / setup C006: the “聚宝塘” declaration has just finished through posture only, with no visible text. Qian Weng still holds his single paper slip and fan. The nearby scholars are restrained and only just about to laugh: empty heads angle toward him, mouths are not drawn, bodies show a small anticipatory reaction but no open laughter. The rightmost cell must clearly be different from the B015 presentation pose and must not skip directly to full laughter. Qian Weng still holds the slip.

Beat logic: the five new cells must read as one blank answer presented -> Wang Fang rejects it -> a different blank answer presented -> Qian Weng proudly presents his blank slip -> the group is on the verge of laughing. Do not skip the rejection or the “almost laughing” final state. Spoken answer names are not drawn; all paper remains blank and unreadable.

Anatomy and prop lock: every stick figure has exactly two arms and two legs. Qian Weng is one body with one head, one fan, and one paper slip only. Each presenting scholar is one body and one paper slip only. No floating hands, detached limbs, duplicated paper slips beyond the few already on the table, duplicate characters, or merged bodies. Wang Fang is not Qian Weng. Su Shi does not answer, leave, or turn away from the pool.

Absolutely no visible text, pseudo-text, letters, numbers, labels, captions, subtitles, watermark, logo, UI, signature, speech bubbles, arrows, speed lines, motion trails, comic emphasis marks, or decorative symbols. Do not make it photorealistic, cinematic, colorful, anime, manga, comic, polished illustration, detailed costume art, or realistic architecture.
```

### P003 v06

- 生成时间：2026-08-30 约 15:45；原始生成图：`C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-8a8ebc3b-a3cd-42ba-9c8d-06c61e514369.png`
- 原始图尺寸：1672×941，1,295,175 bytes，SHA-256 `832DE11E7BF39C4E724634910E78401BDBAE39C5834616BBE60C4800887FB484`。
- 候选归档：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P003_v06.png`；已复制归档，原始图保持不动，未覆盖正式 `board_P003.png`。
- 唯一连续性参考：不可变 `E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P002_v05.png`；该参考由主代理独立 QC 判定 PASS。
- 生成子代理说明：按主代理指令仅完成一次 ImageGen 调用与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 针对性修订：修复 `FORBIDDEN-COMIC-MARK-001`；保留 P003 v05 已正确的 B011 锚点、B012–B016 顺序、C005/C006 轴线、题笺/肢体状态和右下将笑未笑收束；B013 仅用王方安静的头部轻转与一手掌心向下的自然拒绝姿态，彻底排除弧线、短线、感叹符、波纹、光芒、漫画强调及装饰符号，全板仍为真正极简火柴人、16:9、2×3、无文字。
- 完整 Prompt：

```text
Use case: illustration-story
Asset type: production storyboard board for STEP 3, Panel P003.
Input image: Image 1 is the sole immutable continuity reference: the approved P002 v05 storyboard board. Use it only to preserve the strict minimal stick-figure blocking language, the geometric pool/pavilion environment, the left-right axis, and the exact B011 completion state in its bottom-right cell. Do not copy the whole reference board.

Create exactly one complete black-and-white storyboard board for Panel P003 of a Northern Song historical film sequence. It is a director's rough blocking sheet, not final art and not a character concept sheet.

TOP-LEFT BOUNDARY ANCHOR — HIGHEST PRIORITY:
The top-left cell is a zero-duration static continuation anchor. Reproduce the completed bottom-right B011 state of Image 1 without re-establishing or advancing the action: Su Shi remains at the left-side pool edge turned toward and watching the water; a simple presentation table holds several blank, unreadable paper-slip shapes; Qian Weng remains on the right as one seated stick figure with exactly one small circular fan in one hand and exactly one of his own blank paper slips in the other, preparing to rise but not yet presenting, reporting, or speaking. Preserve the pool-edge arc, pavilion/canopy geometry, table position, and all relative placements from Image 1's bottom-right cell. Do not show the answer presentation or any group reaction in the anchor. Do not add a new action, dialogue, timing, or transition.

Canvas and grid: exact landscape 16:9. One clean board with exactly 2 rows by 3 columns, six equal rectangular cells, thin black dividers, reading order left-to-right across the top row then left-to-right across the bottom row. No title band, extra cells, merged cells, nested boards, or unequal panels.

DRAWING LANGUAGE — STRICTLY MINIMAL:
Match Image 1's rough director blocking-sheet style. White paper, sparse black pencil/charcoal lines and tiny light-gray geometric blocks only. Every person is a faceless empty circle head, one single-line torso, and simple line-segment arms and legs. No complete robe silhouette, clothing outline, fabric folds, hair, topknot, facial marks, anatomy, body shading, texture, crosshatching, realistic costume, or polished illustration. Environment only uses a pool-edge arc, a simple pavilion rail/canopy line, table/bench geometry, and a few tiny fish outlines. No roof tiles, bamboo leaves, rock texture, water hatching, detailed architecture, or realistic people. At most one tiny simple hat shape identifies Wang Fang and one small circular fan identifies Qian Weng.

FORBIDDEN GRAPHIC MARKS — ABSOLUTE:
There must be no arcs or curved marks around a head or body, no short emphasis strokes, no action lines, no speed lines, no motion trails, no rays, no sparkles, no exclamation marks, no question marks, no comic symbols, no reaction marks, no ripples drawn as graphic effects, no halo, no starburst, no decorative symbol anywhere in any cell. All changes of pose must be shown only by the positions of the stick figure's head, torso, arms, and legs. No drawn marks may surround a person to indicate emotion or motion.

Scene and axis: same daylight Qing Shen Zhongyan pool and waterside pavilion. Wang Fang remains central standing host; Su Shi stays peripheral at the left pool edge; Qian Weng stays on the right foreground; anonymous literati remain around the presentation table. Keep C005 and C006 each on a stable axis and relative screen positions. No detailed character art.

The other five cells are new P003 beats in this exact order and must not repeat the anchor:
1. Top-left, boundary B011: static completed state exactly as specified above; Qian Weng is preparing to rise but has not presented or reported.
2. Top-middle, B012 / setup C005: immediately after the anchor, one anonymous scholar, literati A, presents exactly one blank paper slip forward to the central standing Wang Fang. Show one clear handoff with simple two-arm anatomy. Su Shi remains at the left pool edge; Qian Weng remains on the right holding his own one slip and fan, waiting. No answer text.
3. Top-right, B013 / setup C005: same camera and axis as beat 2. Wang Fang quietly rejects the first answer only through a small natural head turn away from the slip and one arm lowered with palm facing down toward the table, as a calm “no”. His empty head and body remain completely clean: no surrounding arcs, short strokes, symbols, rays, ripples, or comic marks. The first blank slip is being withdrawn or held back. Do not show a second answer, pride, or crowd laughter.
4. Bottom-left, B014 / setup C006: hard cut to the next answer. A different anonymous scholar, literati B, presents exactly one blank paper slip toward Wang Fang. Keep Qian Weng on the right waiting with his own single slip and fan. No duplicate presenter or extra papers or arms.
5. Bottom-middle, B015 / setup C006: same C006 camera and axis. Qian Weng proudly raises/presents his one personal blank paper slip, keeping the one circular fan in his other hand. Wang Fang and the group look toward him. This is the proud presentation immediately before the joke lands; no visible writing and no graphic reaction marks.
6. Bottom-right, B016 / setup C006: the “聚宝塘” declaration has just finished through posture only, with no visible text. Qian Weng still holds his single paper slip and fan. Nearby scholars are restrained and only just about to laugh, shown only by slight head angles and quiet body posture; no open laughter, no mouths, no action lines, no arcs, no exclamation marks, no symbols. The final cell must clearly differ from B015's presentation pose and must not jump to full laughter. Qian Weng still holds the slip.

Beat logic: the five new cells read as one blank answer presented -> Wang Fang calmly rejects it -> a different blank answer presented -> Qian Weng proudly presents his blank slip -> the group is just about to laugh. Do not skip B013 or B016. Spoken answer names are not drawn; every paper is blank and unreadable.

Anatomy and prop lock: every stick figure has exactly two arms and two legs. Qian Weng is one body with one head, one fan, and one paper slip only. Each presenting scholar is one body and one paper slip only. No floating hands, detached limbs, duplicate paper slips beyond the few already on the table, duplicate characters, or merged bodies. Wang Fang is not Qian Weng. Su Shi does not answer, leave, or turn away from the pool.

Absolutely no visible text, pseudo-text, letters, numbers, labels, captions, subtitles, watermark, logo, UI, signature, speech bubbles, arrows, speed lines, motion trails, arcs, rays, ripples as graphic effects, comic emphasis marks, or decorative symbols. Do not make it photorealistic, cinematic, colorful, anime, manga, comic, polished illustration, detailed costume art, or realistic architecture.
```

### P005 v01

- 生成时间：2026-08-30 约 16:20；原始生成图：`C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-49bb4249-3013-44ac-b30d-5882d75b2588.png`
- 原始图尺寸：1672×941，1,308,347 bytes，SHA-256 `845146607B69C897557B118220BE3CB4C5F5EB1A3DCFE568BC215CD8F261CD79`。
- 候选归档：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P005_v01.png`；已复制归档，原始图保持不动，未覆盖正式 `board_P005.png`。
- 唯一连续性参考：不可变 `E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P004_v01.png`；该参考由主代理独立 QC 判定 PASS。
- 生成子代理说明：按主代理指令仅完成一次 ImageGen 调用与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 针对性要求：左上严格复现 P004 v01 右下 B021 的题名完成、纸面空白、双手抬起未接触状态；后五格依次表现三次击掌后的静态状态、三圈自然水纹、群鱼聚拢跃起、全场静一拍后注意右后路径、丫鬟托唯一空白题笺未交接；保持极简火柴人、极简几何环境、16:9、2×3、无文字、伪字、漫画线、箭头、多手和题笺复制。
- 完整 Prompt：

```text
Use case: illustration-story
Asset type: production storyboard board for STEP 3, Panel P005.
Input image: Image 1 is the sole immutable continuity reference: the approved P004 v01 storyboard board. Use it only to preserve the strict minimal stick-figure blocking language, the geometric waterside environment, the left-right axis, and the exact B021 completion state in the bottom-right cell. Do not copy the whole reference board into the new image.

Create exactly one complete black-and-white storyboard board for Panel P005 of a Northern Song historical film sequence. It is a director's rough blocking sheet, not final art and not a character concept sheet.

TOP-LEFT ZERO-DURATION BOUNDARY — HIGHEST PRIORITY:
Reproduce P004 v01 bottom-right B021 exactly as a completed static state, without re-establishing or advancing it: Su Shi is at the simple writing table; the single paper slip has a finished writing action but its surface is blank and unreadable; the brush is set aside; Su Shi's two hands are raised apart, ready to clap but not touching. No clap has happened in this anchor. Preserve the pool/pavilion geometry, table position, axis, and ordinary two-arm anatomy. The anchor contains no new clap, ripple, fish reaction, maid entrance, dialogue, timing, or transition.

Canvas and grid: exact landscape 16:9. One clean board with exactly 2 rows by 3 columns, six equal rectangular cells, thin black dividers, reading order left-to-right across the top row then left-to-right across the bottom row. No title strip, extra cells, merged cells, nested boards, or unequal panels.

DRAWING LANGUAGE — STRICTLY MINIMAL:
Match Image 1's director blocking-sheet style: white paper, sparse black pencil/charcoal lines and tiny light-gray geometric blocks only. Every person is a faceless empty circle head, one single-line torso, and simple line-segment arms and legs. No complete robe silhouette, clothing outline, fabric folds, hair, topknot, facial marks, anatomy, body shading, textures, crosshatching, realistic costume, or polished illustration. Environment only uses a pool-edge arc, a simple pavilion rail/canopy line, table/bench geometry, and a few tiny fish outlines. No roof tiles, bamboo leaves, rock texture, water hatching, detailed architecture, or realistic people. Distinguish the blue-clad maid only with one tiny simple gray torso block/short outer shape, never a detailed costume. No color.

FORBIDDEN GRAPHIC MARKS — ABSOLUTE:
No arcs or curved marks around a head or body, no short emphasis strokes, no action lines, no speed lines, no motion trails, no rays, no sparkles, no exclamation marks, no question marks, no comic symbols, no reaction marks, no halos, no starbursts, and no decorative symbols in any cell. Natural water ripples in beat 3 may be shown only as three clean, concentric water-surface curves within the pool itself, never around a person and never as comic effects. Show changes only through stick-figure posture, simple props, fish shapes, and the three natural pool ripples.

Scene and axis: same Qing Shen Zhongyan pool and simple waterside pavilion in daylight. Su Shi remains left/peripheral by the pool; Wang Fang remains central in the waterside gathering; Qian Weng remains on the right where present; the maid enters only at the right-rear stone path in the final beat. Keep C009's pool-side axis and C010's path-to-pavilion axis coherent. All paper is blank and unreadable. The words “唤鱼池” must not appear: they are a deterministic post-production overlay.

The six static beats are in this exact order:
1. Top-left, boundary B021: completed writing action, single blank paper, brush set aside, Su Shi's two hands raised apart ready to clap but not touching; no clap yet.
2. Top-middle, B022 / setup C009: the third clap has already been completed, shown as a single static aftermath with only Su Shi's same two hands now naturally separated after the final clap, no extra hands, no numeral, no written count, no clap marks, no action lines. Su Shi faces the pool; the gathering is about to observe the water.
3. Top-right, B023 / setup C009: same pool-side view; the water surface shows exactly three natural concentric ripples spreading from the point below the railing. Keep the ripples confined to the water, not around people; no graphic effects. Su Shi and the gathering look toward the water.
4. Bottom-left, B024 / setup C009: same pool-side axis; a few simple fish shapes that were scattered are now gathered under the railing and one or two tiny fish shapes leap just above the water. Show a natural fish-and-water action through static positions only; no speed lines, arcs around bodies, or repeated fish copies.
5. Bottom-middle, B025 / setup C010: after a brief silent beat and the beginning of distant cheer, the gathering is oriented toward the right-rear stone path. Heads and simple bodies turn toward the path; the path is visible. The maid is not yet standing in the scene. No cheer symbols or action lines.
6. Bottom-right, B026 / setup C010: a single blue-clad maid stands at the right-rear path, clearly separated from the gathering, holding exactly one blank paper slip with both hands at chest height; she has not handed it over. The fish remain gathered in the distant pool; the group notices her. Distinguish her only by one tiny simple gray torso block/short outline, no detailed clothing, no hair or face.

Beat logic: completed writing with hands waiting -> third clap already finished -> exactly three natural ripples -> fish gather and jump -> silent aftermath/attention to the right-rear path -> maid stands holding one and only one blank slip, no handoff yet. Do not show a fourth clap or any presentation/transfer before the next Panel.

Anatomy and prop lock: every stick figure has exactly two arms and two legs. Su Shi has two hands only; no ghost hands or contact in the anchor. The maid is one body with two arms holding one paper slip, not two slips and not a floating extra pair of hands. All papers are blank shapes. No duplicate characters, duplicate fish clusters, duplicate props, detached limbs, arrows, or symbols.

Absolutely no visible text, pseudo-text, letters, numbers, labels, captions, subtitles, watermark, logo, UI, signature, speech bubbles, arrows, speed lines, motion trails, comic emphasis marks, or decorative symbols. Natural pool ripples are allowed only inside the water in beat 3 as exactly three clean concentric curves. Do not make it photorealistic, cinematic, colorful, anime, manga, comic, polished illustration, detailed costume art, or realistic architecture.
```

### P004 v01 promotion

- 独立 QC 结论：PASS（主代理确认，SHA-256 `C84EB5E68D25FE202AC555DC221370BD8FA304A7B35C72FF68B19BF4DE71E99C`）。
- 提升来源：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P004_v01.png`。
- 正式文件：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P004.png`。
- 提升后正式文件与候选逐字节一致；提升后 SHA-256 `C84EB5E68D25FE202AC555DC221370BD8FA304A7B35C72FF68B19BF4DE71E99C`。候选与原始生成图均保留。

### P003 v06 promotion

- 独立 QC 结论：PASS（主代理确认，SHA-256 `832DE11E7BF39C4E724634910E78401BDBAE39C5834616BBE60C4800887FB484`）。
- 提升来源：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P003_v06.png`。
- 正式文件：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P003.png`。
- 提升后正式文件与候选逐字节一致；提升后 SHA-256 `832DE11E7BF39C4E724634910E78401BDBAE39C5834616BBE60C4800887FB484`。候选与原始生成图均保留。

### P004 v01

- 生成时间：2026-08-30 约 16:00；原始生成图：`C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-a5b3102c-a23f-44c3-be02-586203c5fe3e.png`
- 原始图尺寸：1672×941，1,121,020 bytes，SHA-256 `C84EB5E68D25FE202AC555DC221370BD8FA304A7B35C72FF68B19BF4DE71E99C`。
- 候选归档：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P004_v01.png`；已复制归档，原始图保持不动，未覆盖正式 `board_P004.png`。
- 唯一连续性参考：不可变 `E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P003_v06.png`；该参考由主代理独立 QC 判定 PASS。
- 生成子代理说明：按主代理指令仅完成一次 ImageGen 调用与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 针对性要求：左上严格承接 B016 的“钱翁举单笺、众人将笑未笑”；后五格按 B017–B021 顺序推进全场笑、账本反击、再笑转笔墨、落笔和题名完成；所有纸面空白不可读，“唤鱼池”留给后期；右下锁定双手抬起待击且绝不击掌；保持极简火柴人、几何环境、16:9、2×3、无漫画符号和无多手/题笺复制。
- 完整 Prompt：

```text
Use case: illustration-story
Asset type: production storyboard board for STEP 3, Panel P004.
Input image: Image 1 is the sole immutable continuity reference: the approved P003 v06 storyboard board. Use it only to preserve the strict minimal stick-figure blocking language, geometric poolside environment, left-right axis, and the exact B016 end-state in its bottom-right cell. Do not copy the entire reference board into the new image.

Create exactly one complete black-and-white storyboard board for Panel P004 of a Northern Song historical film sequence. It is a director's rough blocking sheet, not final art and not a character concept sheet.

TOP-LEFT ZERO-DURATION BOUNDARY — HIGHEST PRIORITY:
The top-left cell must reproduce P003 v06's bottom-right B016 completed state, without re-establishing the scene and without advancing it. Qian Weng is on the right holding his own single blank paper slip and one small circular fan; the nearby scholars are only just about to laugh, shown by restrained empty-head angles and quiet posture; nobody is openly laughing yet. Wang Fang remains central in the gathering, Su Shi remains peripheral at the left pool edge. Preserve the pool-edge arc, pavilion/canopy line, simple table/seat positions, one paper slip and one fan. The top-left anchor has no new laugh, retort, writing, clap, dialogue, timing, or transition.

Canvas and grid: exact landscape 16:9. One clean board with exactly 2 rows by 3 columns, six equal rectangular cells, thin black dividers, reading order left-to-right across the top row then left-to-right across the bottom row. No title strip, extra cells, merged cells, nested boards, unequal panels.

DRAWING LANGUAGE — STRICTLY MINIMAL:
Match Image 1's director blocking-sheet style: white paper, sparse black pencil/charcoal lines and tiny light-gray geometric blocks only. Every person is a faceless empty circle head, one single-line torso, and simple line-segment arms and legs. No complete robe silhouette, clothing outlines, fabric folds, hair, topknot, facial marks, anatomy, realistic costumes, body shading, textures, crosshatching, or polished illustration. Environment only uses a pool-edge arc, simple pavilion rail/canopy, table/bench geometry, and a few tiny fish outlines. No roof tiles, bamboo leaves, rock texture, water hatching, detailed architecture, or realistic people. At most one tiny simple hat identifies Wang Fang and one small circular fan identifies Qian Weng.

FORBIDDEN GRAPHIC MARKS — ABSOLUTE:
No arcs or curved marks around a head or body, no short emphasis strokes, no action lines, no speed lines, no motion trails, no rays, no sparkles, no exclamation marks, no question marks, no comic symbols, no reaction marks, no halos, no starbursts, and no decorative symbols in any cell. Show every change only through the positions of stick-figure heads, torsos, arms, legs, and simple props. No written labels or drawn indicators.

Scene and axis: same daylight Qing Shen Zhongyan pool and waterside pavilion. Wang Fang central, Qian Weng right foreground, Su Shi left/peripheral by the pool, anonymous scholars at the table. Keep C007 and C008 as stable axes for their respective views. All paper is blank and unreadable. The words “唤鱼池” are a deterministic post-production overlay and must not appear in this storyboard image.

Six static beats in exact order:
1. Top-left, boundary B016: static completed state from P003 v06 bottom-right — Qian Weng still holds exactly one blank slip and one fan; scholars are restrained and just about to laugh, not openly laughing; Wang Fang remains central; Su Shi remains left at the pool; no new action.
2. Top-middle, B017 / setup C007: immediately release the pending reaction: the whole small gathering laughs through simple body posture and head angles, while Qian Weng's posture becomes stiff and embarrassed. Do not use mouths, laughter symbols, arcs, short lines, rays, or comic marks. Qian Weng still has only one slip and one fan.
3. Top-right, B018 / setup C007: same camera and axis; Su Shi calmly turns from the poolside toward Qian Weng and gives a composed ledger/account-book retort through a relaxed speaking pose. The account book is one simple blank rectangular prop with no writing; do not draw the spoken words. Qian Weng remains foreground and embarrassed; the group watches.
4. Bottom-left, B019 / setup C007: same camera and axis; the group laughs again through restrained posture only, Qian Weng remains visibly embarrassed with a small light-gray geometric tone block if needed, and Su Shi turns from the group toward the writing table/ink area. No laughter marks, no red color, no text.
5. Bottom-middle, B020 / setup C008: hard cut to a simple side view at the writing table. Su Shi takes exactly one simple brush and leans over one blank paper slip, wrist poised and beginning to write. Keep the sheet blank and unreadable; no generated characters or pseudo-text. Use only table, brush, hand, paper, and minimal poolside geometry.
6. Bottom-right, B021 / setup C008: same writing-side axis; the writing action is complete but the paper remains blank for post-production. Su Shi has finished the motion, has said the line only through a composed speaking posture, and now holds both hands raised, ready to clap but not clapping. There is no hand contact, no clap marks, no action lines, no visible “唤鱼池” text. The single paper slip remains on the table, blank, with the brush set aside.

Beat logic: pending almost-laughter -> full group laughter with Qian Weng stiff -> Su Shi's calm ledger retort -> a second restrained laugh and Su Shi turns to ink -> one blank slip is written on -> writing complete, both hands raised waiting to clap but not clapping. Do not show any clapping before the next Panel. Do not duplicate writing slips, brushes, fans, or hands.

Anatomy and prop lock: every stick figure has exactly two arms and two legs. Qian Weng is one body with one fan and one blank slip. Su Shi has at most one blank account book in beat 3 and exactly one brush plus one blank slip in beats 5–6; the brush is set aside by beat 6. The account book must not become a second paper slip. No floating hands, detached limbs, duplicate characters, duplicate props, or merged bodies. Wang Fang is not Qian Weng.

Absolutely no visible text, pseudo-text, letters, numbers, labels, captions, subtitles, watermark, logo, UI, signature, speech bubbles, arrows, speed lines, motion trails, arcs, rays, ripples as graphic effects, comic emphasis marks, or decorative symbols. Do not make it photorealistic, cinematic, colorful, anime, manga, comic, polished illustration, detailed costume art, or realistic architecture.
```

### P006 v01

- 生成时间：2026-08-30 15:46:17 +08:00；原始生成图：`C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-434afc3d-fa87-4599-83f5-effb88d47022.png`
- 原始图尺寸：1672×941，1,262,855 bytes，SHA-256 `FECC4AE61653F2471C4281838B0A1B02D8D0B99F9F8736C59570747DF75B0336`。
- 候选归档：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P006_v01.png`；已复制归档，原始图保持不动，未覆盖正式 `board_P006.png`。
- 唯一连续性参考：不可变 `E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P005_v01.png`；该参考由主代理独立 QC 判定 PASS。
- 生成子代理说明：按主代理指令仅完成一次 ImageGen 调用与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 针对性要求：左上严格复现 B026 丫鬟右后来路站定、双手托唯一空白题笺且尚未交接；后五格依次完成唯一题笺交接展开、王方自然后仰再大笑、王方持唯一展开题笺向众人长宣告、满座起身围看、苏轼独自停在原地朝向题笺怔住；保持真正极简火柴人、极简几何环境、16:9、2×3、无文字/伪字、无漫画符号、多手或题笺复制。
- 完整 Prompt：

```text
Use case: illustration-story
Asset type: production storyboard board for STEP 3, Panel P006.
Input image: Image 1 is the sole immutable continuity reference: the approved P005 v01 storyboard board. Use it only to preserve the strict minimal stick-figure blocking language, the geometric Qing Shen Zhongyan poolside environment, the right-rear path axis, and the exact B026 end-state in its bottom-right cell. Do not copy the whole reference board into the new image.

Create exactly one complete black-and-white storyboard board for Panel P006 of a Northern Song historical film sequence. This is a director's rough blocking sheet, not final art, not a character sheet, and not six separate images.

TOP-LEFT ZERO-DURATION BOUNDARY — HIGHEST PRIORITY:
Reproduce P005 v01 bottom-right B026 exactly as a completed static state, without re-establishing or advancing the scene: one simple blue-clad maid is already standing at the right-rear path, clearly separated from the gathering, holding exactly one blank paper slip with both hands at chest height; she has not handed it over. The gathered figures remain by the waterside pavilion and notice her. Preserve the right-rear path, pool and pavilion geometry, the spatial axis, the maid's small light-gray torso block, and the single blank slip. The anchor must not show transfer, unfolding, surprise, laughter, proclamation, standing crowd, or Su Shi's stunned reaction.

Canvas and grid: exact landscape 16:9. One clean board with exactly 2 rows by 3 columns, six equal rectangular cells, thin black dividers, reading order left-to-right across the top row then left-to-right across the bottom row. No title strip, extra cells, merged cells, nested boards, or unequal panels.

DRAWING LANGUAGE — STRICTLY MINIMAL:
Match Image 1's director blocking-sheet style: white paper, sparse black pencil/charcoal lines and tiny light-gray geometric blocks only. Every person is a faceless empty circle head, one single-line torso, and simple line-segment arms and legs. No facial marks, mouth, eyes, hair, topknot, anatomy, complete robe silhouette, clothing folds, realistic costume, shading, texture, crosshatching, polished illustration, or realistic people. Environment only uses a few simple geometric lines for the pool edge, waterside pavilion/rail, table/bench, and the right-rear stone path. Distinguish the blue-clad maid only by one tiny light-gray torso block or short outer contour, never detailed clothing. Wang Fang may have only one tiny simple hat shape. No color.

FORBIDDEN GRAPHIC MARKS — ABSOLUTE:
No arcs or curved marks around a head or body, no short emphasis strokes, no action lines, speed lines, motion trails, rays, sparkles, exclamation marks, question marks, comic symbols, reaction marks, halos, starbursts, arrows, speech bubbles, or decorative symbols in any cell. Show all changes only through stick-figure posture, head angle, simple geometry, and the one paper slip. Do not use facial expression to depict surprise or laughter.

SCENE, AXIS, AND PROP CONTINUITY:
Use the same daylight Qing Shen Zhongyan pool and waterside pavilion. The right-rear path-to-pavilion axis is stable for C011 and C012. The maid enters only at the right-rear path in the anchor and remains there until the transfer. Wang Fang is the central recipient; Su Shi stays at the left/peripheral pool area until the final cell, where he is the only figure left standing in the original place. All paper surfaces are blank and unreadable. The words “唤鱼池” are deterministic post-production and must not appear in this storyboard image. There is exactly one paper slip in the entire board: it may change from held folded to a single unfolded blank rectangle, but it is never duplicated, copied, or replaced. In a handoff, both characters may hold the same one slip with their natural existing hands; never add extra hands.

SIX STATIC BEATS IN EXACT ORDER:
1. Top-left, boundary B026 / setup C010: exact completed static state from P005 v01 bottom-right — the single maid stands at the right-rear path, both hands holding exactly one blank slip at chest height, no handoff yet; the gathering notices her. Keep the maid separated from the group.
2. Top-middle, B027 / setup C011: Wang Fang and the maid have completed the only handoff and the same single slip is unfolded between them. Show Wang Fang receiving the one blank rectangle with his natural two-arm anatomy while the maid's hands have released or are withdrawing; do not create a second paper, floating hands, or another presenter. The slip remains blank and unreadable.
3. Top-right, B028 / setup C011: Wang Fang has seen the one unfolded blank slip and reacts with natural surprise followed by a broad laugh shown only through body blocking: his empty head and single-line torso lean slightly back, his two arms open naturally. Nearby figures may lean with him, but no face marks, laughter symbols, arcs, short strokes, action lines, or comic effects. The same one unfolded slip stays with Wang Fang.
4. Bottom-left, B029 / setup C011: Wang Fang holds the same single unfolded blank slip up toward the gathered people and completes a long proclamation through an open speaking posture. The crowd faces him. Do not write the spoken content or draw any lettering; the paper remains a single blank rectangle. No extra slip, no speech bubble, no mouth, no declaration marks.
5. Bottom-middle, B030 / setup C012: the full gathering has stood up and moved only enough to surround/lean in and look at the same one unfolded blank slip. Show several simple empty heads and line bodies standing around Wang Fang. Preserve the one-slip lock: only the same rectangle is visible, no copied papers, no extra hands, no duplicate characters. The maid can remain at the path edge after the handoff.
6. Bottom-right, B031 / setup C012: Su Shi is alone in the original poolside position, still standing where he was, with head and torso turned toward the same single blank slip held in the distant gathering; his posture is quietly stunned and motionless, conveyed only by a slight backward/forward stop in the torso and fixed head direction. Keep the gathered figures and one slip small or distant; do not add a second paper. Do not show Su Shi walking, speaking, or touching the slip. The maid is no longer handing anything over.

BEAT LOGIC:
exact B026 maid waiting with one blank slip -> sole transfer and unfold -> Wang Fang natural body surprise then laugh -> Wang Fang makes a long blank-slip proclamation -> everyone stands and crowds around to look -> Su Shi alone remains stopped and stunned. Do not jump from the anchor to the proclamation; do not omit B028 or B030. No fourth character action, no new paper, and no post-production title.

ANATOMY AND SINGLE-PROP LOCK:
Every stick figure has exactly two arms and two legs. The maid is one body with two arms holding the one slip in B026; in B027 she and Wang Fang share that same slip during the transfer using only their existing hands. Wang Fang has exactly two arms and owns the same one unfolded slip from B027 through B030. Su Shi has exactly two arms and no paper in B031. No ghost hands, detached limbs, duplicate characters, merged bodies, duplicate fish or paper, or floating objects. The paper must be a simple blank shape without writing or pseudo-writing.

Absolutely no visible text, pseudo-text, letters, numbers, labels, captions, subtitles, watermark, logo, UI, signature, speech bubbles, arrows, speed lines, motion trails, arcs, rays, ripples as graphic effects, comic emphasis marks, or decorative symbols. Do not make it photorealistic, cinematic, colorful, anime, manga, comic, polished illustration, detailed costume art, or realistic architecture.
```

### P005 v01 promotion

- 独立 QC 结论：PASS（主代理确认，SHA-256 `845146607B69C897557B118220BE3CB4C5F5EB1A3DCFE568BC215CD8F261CD79`）。
- 提升来源：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P005_v01.png`。
- 正式文件：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P005.png`。
- 提升后正式文件与候选逐字节一致；提升后 SHA-256 `845146607B69C897557B118220BE3CB4C5F5EB1A3DCFE568BC215CD8F261CD79`。候选与原始生成图均保留。

### P006 v01 promotion

- 独立 QC 结论：PASS（主代理确认，SHA-256 `FECC4AE61653F2471C4281838B0A1B02D8D0B99F9F8736C59570747DF75B0336`）。
- 提升来源：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P006_v01.png`。
- 正式文件：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P006.png`。
- 提升后正式文件与候选逐字节一致；提升后 SHA-256 `FECC4AE61653F2471C4281838B0A1B02D8D0B99F9F8736C59570747DF75B0336`。候选与原始生成图均保留。

### P007 v01

- 生成时间：2026-08-30 15:51:51 +08:00；原始生成图：`C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-f230b81d-6e56-4787-ab0c-c01efe735791.png`
- 原始图尺寸：1672×941，1,081,050 bytes，SHA-256 `F92A2F4EA6205CE6B4B6805F9DB05781C76141D973940E3682936BD79CBF0129`。
- 候选归档：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P007_v01.png`；已复制归档，原始图保持不动，未覆盖正式 `board_P007.png`。
- 唯一连续性参考：不可变 `E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P006_v01.png`；该参考由主代理独立 QC 判定 PASS。
- 生成子代理说明：按主代理指令仅完成一次 ImageGen 调用与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 针对性要求：左上严格复现 B031 苏轼独自怔住、朝向王方手中唯一继承空白题笺且文会群体在场；上中硬切同日竹径，王弗左后、丫鬟后侧退半步且无题笺；上右苏轼从右前进入与王弗相向；左下王弗自然抬手提问；下中 C014 苏轼带笑拱手回应；右下王弗停一拍后以头肩放松表现笑意；保持 C013/C014 轴线、左右位置、距离、真正极简火柴人、16:9、2×3、无文字/符号/题笺（锚点继承单张除外）/额外肢体。
- 完整 Prompt：

```text
Use case: illustration-story
Asset type: production storyboard board for STEP 3, Panel P007.
Input image: Image 1 is the sole immutable continuity reference: the approved P006 v01 storyboard board. Use it only to preserve the strict minimal stick-figure blocking language, the geometric Qing Shen Zhongyan poolside environment, and the exact B031 end-state in the bottom-right cell. Do not copy the whole reference board into the new image.

Create exactly one complete black-and-white storyboard board for Panel P007 of a Northern Song historical film sequence. This is a director's rough blocking sheet, not final art, not a character sheet, and not six separate images.

TOP-LEFT ZERO-DURATION BOUNDARY — HIGHEST PRIORITY:
Reproduce P006 v01 bottom-right B031 exactly as a completed static state, without re-establishing or advancing it: Su Shi is alone in the original poolside position, stopped and quietly stunned, with head and torso turned toward Wang Fang holding the one inherited blank paper slip in the distant gathering; the Wen gathering remains present. Preserve the pool edge, pavilion geometry, left/peripheral Su Shi position, distant gathering, axis, and the single inherited blank slip. This anchor alone may contain that inherited blank slip. It must not show the bamboo path, Wang Fu, the maid, an approach, a question, a response, or a smile. It is a zero-duration continuity cell.

Canvas and grid: exact landscape 16:9. One clean board with exactly 2 rows by 3 columns, six equal rectangular cells, thin black dividers, reading order left-to-right across the top row then left-to-right across the bottom row. No title strip, extra cells, merged cells, nested boards, or unequal panels.

DRAWING LANGUAGE — STRICTLY MINIMAL:
Match Image 1's director blocking-sheet style: white paper, sparse black pencil/charcoal lines and tiny light-gray geometric blocks only. Every person is a faceless empty circle head, one single-line torso, and simple line-segment arms and legs. No facial marks, eyes, mouth, hair, topknot, anatomy, complete robe silhouette, clothing folds, realistic costume, shading, texture, crosshatching, polished illustration, or realistic people. Wang Fu and the maid must be distinguished only by extremely few simple outline anchors: Wang Fu may have one tiny restrained hair/garment contour, and the maid one tiny light-gray torso block or short outer contour; do not draw detailed clothing or hair. Su Shi remains an undecorated stick figure. The bamboo path uses only a few vertical bamboo lines and a simplified path line. No color.

FORBIDDEN GRAPHIC MARKS — ABSOLUTE:
No arcs or curved marks around a head or body, no short emphasis strokes, no action lines, speed lines, motion trails, rays, sparkles, exclamation marks, question marks, comic symbols, reaction marks, halos, starbursts, arrows, speech bubbles, or decorative symbols in any cell. Show question, response, and smile only by natural stick-figure head angle, hand position, shoulder level, and torso posture. No eyes, mouths, or facial expression marks.

SCENE, AXIS, AND PROP CONTINUITY:
The anchor is the same poolside setting on the same day. At the hard cut in B032, move to a quiet bamboo path later that same day, with C013's axis: Wang Fu stands at the left-rear of the path and the maid is half a step behind her, both clearly separated. At C014, preserve a reverse/answer axis: Su Shi enters from the right front and faces Wang Fu, with a believable distance between them. Keep left-right positions and screen direction stable within each setup. After the top-left inherited anchor, there must be no paper slip or other writing prop in any cell. The words “唤鱼池” and all dialogue must be post-production only and must not appear in this storyboard.

SIX STATIC BEATS IN EXACT ORDER:
1. Top-left, boundary B031 / prior setup C012: exact completed state from P006 v01 bottom-right — Su Shi alone remains stopped at the poolside, head and torso turned toward Wang Fang's distant one inherited blank slip; the gathering is present. No new action or transition.
2. Top-middle, B032 / setup C013: hard cut to the same-day bamboo path. Wang Fu is standing at the left-rear of frame; the maid stands half a step behind her, slightly farther back, with no paper or writing prop. Use a few vertical bamboo lines and a simple path line only. Both are waiting before the question.
3. Top-right, B033 / setup C013: Su Shi enters from the right front and comes to a natural standing distance facing Wang Fu. Keep Wang Fu left-rear and the maid behind her; show only the approach-complete standing state, no gesture yet. No paper.
4. Bottom-left, B034 / setup C013: Wang Fu naturally raises one hand with a calm open-palm/questioning gesture toward Su Shi. Keep the hand attached to her normal two-arm anatomy, no extra limb, and show the maid behind her. Do not draw a question mark, speech bubble, mouth, or gesture lines.
5. Bottom-middle, B035 / setup C014: cut/reverse to Su Shi facing Wang Fu from the right-front side; he gives a composed response through a slight smile implied only by a gentle head angle and a respectful two-hand cupped greeting. Keep C014 distance and axis coherent. No facial marks, no text, and no paper.
6. Bottom-right, B036 / setup C014: Wang Fu first holds still for a beat, then her head and shoulders relax slightly to imply a quiet smile; no eyes, mouth, facial marks, arcs, short strokes, or comic signs. Su Shi remains opposite in his calm response posture, and the maid stays a half-step behind Wang Fu. No paper.

BEAT LOGIC:
inherited poolside stunned anchor -> hard cut to bamboo path with Wang Fu and maid waiting -> Su Shi enters from the right and faces Wang Fu -> Wang Fu raises a natural questioning hand -> reverse angle with Su Shi smiling and answering through a respectful cupped-hands greeting -> Wang Fu's delayed, restrained smile shown only by head/shoulder relaxation. Do not merge the poolside and bamboo-path settings, do not move Wang Fu to the right, do not put the maid beside or in front of her, and do not turn the question into a comic reaction.

CHARACTER AND ANATOMY LOCK:
Every stick figure has exactly two arms and two legs. Wang Fu is one body at left-rear with only minimal distinguishing contour; the maid is one body half a step behind her with only a tiny gray torso anchor. Su Shi is one body entering from the right front. The inherited paper slip may appear only in the top-left continuity anchor and must not be duplicated or carried into B032–B036. No ghost hands, detached limbs, duplicate characters, merged bodies, extra props, or floating objects.

Absolutely no visible text, pseudo-text, letters, numbers, labels, captions, subtitles, watermark, logo, UI, signature, speech bubbles, arrows, speed lines, motion trails, arcs, rays, ripples as graphic effects, comic emphasis marks, or decorative symbols. Do not make it photorealistic, cinematic, colorful, anime, manga, comic, polished illustration, detailed costume art, or realistic architecture.
```

### P007 v01 promotion

- 独立 QC 结论：PASS（主代理确认，SHA-256 `F92A2F4EA6205CE6B4B6805F9DB05781C76141D973940E3682936BD79CBF0129`）。
- 提升来源：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P007_v01.png`。
- 正式文件：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P007.png`。
- 提升后正式文件与候选逐字节一致；提升后 SHA-256 `F92A2F4EA6205CE6B4B6805F9DB05781C76141D973940E3682936BD79CBF0129`。候选与原始生成图均保留。

### P008 v01

- 生成时间：2026-08-30 15:57:14 +08:00；原始生成图：`C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-85fc1987-cb8c-499a-bddc-421ee91e8931.png`
- 原始图尺寸：1672×941，1,130,724 bytes，SHA-256 `A85820B77EF1F0675FDFB557C9AEF14021840F45305A0FEC5C9151E62B643ADB`。
- 候选归档：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P008_v01.png`；已复制归档，原始图保持不动，未覆盖正式 `board_P008.png`。
- 唯一连续性参考：不可变 `E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P007_v01.png`；该参考由主代理独立 QC 判定 PASS。
- 生成子代理说明：按主代理指令仅完成一次 ImageGen 调用与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 针对性要求：左上严格复现 B036 王弗左、苏轼右、丫鬟后景的自然笑意完成态；后五格依次表现王弗收笑敛衽一礼、同镜完整陈述“快/稳”、苏轼轻松姿态收住略怔、同一未翻轴回应视点下苏轼追问、王弗转向池水方向准备解释；保持 C013/C014 轴线、左右位置、距离、真正极简火柴人、竹径简线、16:9、2×3、无文字/符号/题笺/额外肢体。
- 完整 Prompt：

```text
Use case: illustration-story
Asset type: production storyboard board for STEP 3, Panel P008.
Input image: Image 1 is the sole immutable continuity reference: the approved P007 v01 storyboard board. Use it only to preserve the strict minimal stick-figure blocking language, the quiet same-day bamboo-path environment, the C013/C014 screen axis, and the exact B036 end-state in the bottom-right cell. Do not copy the whole reference board into the new image.

Create exactly one complete black-and-white storyboard board for Panel P008 of a Northern Song historical film sequence. This is a director's rough blocking sheet, not final art, not a character sheet, and not six separate images.

TOP-LEFT ZERO-DURATION BOUNDARY — HIGHEST PRIORITY:
Reproduce P007 v01 bottom-right B036 exactly as a completed static state, without re-establishing or advancing it: Wang Fu stands on screen-left, already relaxed into a restrained natural smile shown only by slight head and shoulder release; Su Shi stands on screen-right opposite her in a calm response posture; the maid remains a half-step behind Wang Fu in the rear. Preserve the bamboo-path geometry, the left-right positions, distance, C014 axis, and the three-person blocking. This anchor must not show Wang Fu bowing, speaking, turning toward the pool, or any new gesture.

Canvas and grid: exact landscape 16:9. One clean board with exactly 2 rows by 3 columns, six equal rectangular cells, thin black dividers, reading order left-to-right across the top row then left-to-right across the bottom row. No title strip, extra cells, merged cells, nested boards, or unequal panels.

DRAWING LANGUAGE — STRICTLY MINIMAL:
Match Image 1's director blocking-sheet style: white paper, sparse black pencil/charcoal lines and tiny light-gray geometric blocks only. Every person is a faceless empty circle head, one single-line torso, and simple line-segment arms and legs. No facial marks, eyes, mouth, hair, topknot, anatomy, complete robe silhouette, clothing folds, realistic costume, shading, texture, crosshatching, polished illustration, or realistic people. Wang Fu and the maid are distinguished only by extremely few simple outline anchors: Wang Fu may have one tiny restrained hair/garment contour; the maid keeps one tiny light-gray torso block or short outer contour. Su Shi remains an undecorated stick figure. The bamboo path has only a few vertical bamboo lines and a simplified path line, with no detailed foliage. No color.

FORBIDDEN GRAPHIC MARKS — ABSOLUTE:
No arcs or curved marks around a head or body, no short emphasis strokes, no action lines, speed lines, motion trails, rays, sparkles, exclamation marks, question marks, comic symbols, reaction marks, halos, starbursts, arrows, speech bubbles, or decorative symbols in any cell. Show courtesy, speech, hesitation, questions, and restrained smile only through natural head angle, hand placement, shoulder level, and torso posture. No eyes, mouths, or facial expression marks. Do not add any visual mark that reads as surprise lines or comic emphasis.

SCENE, AXIS, AND PROP CONTINUITY:
All cells after the inherited B036 anchor remain on the same-day quiet bamboo path beside the waterside grounds. Keep the C013/C014 axis unflipped: Wang Fu remains screen-left and Su Shi remains screen-right in every two-shot; the maid remains behind Wang Fu, slightly farther back. A response/reverse viewpoint may change framing but must not mirror the left-right positions or reverse screen direction. The pool direction is only a simple implied opening beyond the bamboo; no detailed landscape. There are no paper slips, writing props, labels, or other hand props anywhere in this board. All dialogue, including the meaning “快/稳”, is post-production only and must not appear as text.

SIX STATIC BEATS IN EXACT ORDER:
1. Top-left, boundary B036 / prior setup C014: exact completed state from P007 v01 bottom-right — Wang Fu screen-left has already relaxed into a quiet restrained smile through head/shoulder posture; Su Shi screen-right remains opposite; the maid is a half-step behind Wang Fu. No new action.
2. Top-middle, B037 / setup C013: Wang Fu收起笑意 and gives a restrained courtesy: her head and torso make a shallow respectful inclination, her hands gather naturally at the front of her single-line body, and the maid stays behind her. Do not draw a robe, hand fan, text, or bowing lines. Su Shi remains screen-right, receiving the courtesy.
3. Top-right, B038 / setup C013: same camera and same left-right axis; Wang Fu holds a complete calm speaking posture for her full “快/稳” statement, represented only by an upright torso, a slight head orientation toward Su Shi, and one natural open hand near chest height. The other arm remains attached and ordinary. Do not write “快”, “稳”, or any dialogue; no mouth, speech bubble, or emphasis mark. The maid stays rear-left.
4. Bottom-left, B039 / setup C013: Su Shi's relaxed posture settles and he pauses with a slight restrained startle/hesitation, conveyed only by a small change of head angle and a briefly held torso; keep him screen-right facing Wang Fu. No surprise lines, facial marks, or comic reaction. Wang Fu and maid remain screen-left/rear.
5. Bottom-middle, B040 / setup C014 response viewpoint: keep the same unflipped axis and screen positions while framing Su Shi as the responding foreground figure on screen-right; he naturally asks a follow-up question through an attentive head angle and one calm open-hand gesture. Wang Fu remains screen-left, maid behind her. Do not draw a question mark, speech bubble, mouth, or gesture lines.
6. Bottom-right, B041 / setup C014: Wang Fu remains screen-left and briefly turns her head and torso toward the simple pool-water direction beyond the bamboo, preparing to explain; the turn is small and natural, with no pointing arm required. Su Shi remains screen-right watching her; the maid stays half a step behind Wang Fu. No text, paper, or added gesture.

BEAT LOGIC:
quiet restrained smile -> Wang Fu gathers herself into a courtesy -> she gives the complete “快/稳” explanation through a sustained speaking pose -> Su Shi's relaxed posture stops with a slight hesitation -> same-axis response view as Su Shi naturally asks -> Wang Fu turns head and torso toward the pool direction, ready to explain. Do not advance the pool explanation itself; B041 is only the preparation turn. Do not change the screen-left/screen-right axis, merge characters, or create comic reactions.

CHARACTER AND ANATOMY LOCK:
Every stick figure has exactly two arms and two legs. Wang Fu is one body at screen-left with the same minimal contour in every cell; the maid is one body half a step behind her with one tiny gray torso anchor; Su Shi is one body at screen-right. All gestures use only each character's existing arms. No ghost hands, detached limbs, duplicate characters, merged bodies, extra props, paper slips, or floating objects.

Absolutely no visible text, pseudo-text, letters, numbers, labels, captions, subtitles, watermark, logo, UI, signature, speech bubbles, arrows, speed lines, motion trails, arcs, rays, ripples as graphic effects, comic emphasis marks, or decorative symbols. Do not make it photorealistic, cinematic, colorful, anime, manga, comic, polished illustration, detailed costume art, or realistic architecture.
```

### P008 v01 promotion

- 独立 QC 结论：PASS（主代理确认，SHA-256 `A85820B77EF1F0675FDFB557C9AEF14021840F45305A0FEC5C9151E62B643ADB`）。
- 提升来源：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P008_v01.png`。
- 正式文件：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P008.png`。
- 提升后正式文件与候选逐字节一致；提升后 SHA-256 `A85820B77EF1F0675FDFB557C9AEF14021840F45305A0FEC5C9151E62B643ADB`。候选与原始生成图均保留。

### P009 v01 promotion

- 独立 QC 结论：PASS（主代理确认，SHA-256 `C59E8AFF152C2FED3149935B49E52379ABD0799F3651750D5D9A3646C66C620C`）。
- 提升来源：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P009_v01.png`。
- 正式文件：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P009.png`。
- 提升后正式文件与候选逐字节一致；提升后 SHA-256 `C59E8AFF152C2FED3149935B49E52379ABD0799F3651750D5D9A3646C66C620C`。候选与原始生成图均保留。

### P010 v01

- 生成时间：2026-08-30 16:07:39 +08:00；原始生成图：`C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-762bed7e-ddac-4b0d-b0f3-264a032eb99d.png`
- 原始图尺寸：1672×941，1,085,379 bytes，SHA-256 `92C57BC2068766607660B934FCF443D4FB428EBF23D7D4F0AD4C6189C15E7A07`。
- 候选归档：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P010_v01.png`；已复制归档，原始图保持不动，未覆盖正式 `board_P010.png`。
- 唯一连续性参考：不可变 `E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P009_v01.png`；该参考由主代理独立 QC 判定 PASS。
- 生成子代理说明：按主代理指令仅完成一次 ImageGen 调用与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 针对性要求：左上严格复现 B046 竹径稳定双人全身构图，王弗左、苏轼右、丫鬟后景；上中硬切夜书房，两烛、低案、苏辙与苏轼隔案对坐；后五格依次为苏辙以唯一毛笔圈点唯一策论纸、劝稳、苏轼一次轻敲桌面、手停在纸边完成反问；兄弟以简化冠帽/体型区分；保持唯一毛笔/纸归属、无文字/伪字/漫画线/多手/道具复制、16:9、2×3。
- 完整 Prompt：

```text
Use case: illustration-story
Asset type: production storyboard board for STEP 3, Panel P010.
Input image: Image 1 is the sole immutable continuity reference: the approved P009 v01 storyboard board. Use it only to preserve the strict minimal stick-figure blocking language and the exact B046 end-state in the bottom-right cell. Do not copy the whole reference board into the new image.

Create exactly one complete black-and-white storyboard board for Panel P010 of a Northern Song historical film sequence. This is a director's rough blocking sheet, not final art, not a character sheet, and not six separate images.

TOP-LEFT ZERO-DURATION BOUNDARY — HIGHEST PRIORITY:
Reproduce P009 v01 bottom-right B046 exactly as a completed static state, without re-establishing or advancing it: a stable full-body two-person composition on the quiet bamboo path, Wang Fu screen-left and Su Shi screen-right facing one another, the maid still visible half a step behind Wang Fu in the rear. Preserve the bamboo path, left-right positions, distance, and axis. This anchor must not show the night study, candles, a room, a paper, a brush, or any new action. It is a zero-duration continuity cell.

Canvas and grid: exact landscape 16:9. One clean board with exactly 2 rows by 3 columns, six equal rectangular cells, thin black dividers, reading order left-to-right across the top row then left-to-right across the bottom row. No title strip, extra cells, merged cells, nested boards, or unequal panels.

DRAWING LANGUAGE — STRICTLY MINIMAL:
Match the director's rough blocking-sheet style: white paper, sparse black pencil/charcoal lines and tiny light-gray geometric blocks only. Every person is a faceless empty circle head, one single-line torso, and simple line-segment arms and legs. No facial marks, eyes, mouth, hair, topknot, anatomy, complete robe silhouette, clothing folds, realistic costume, shading, texture, crosshatching, polished illustration, or realistic people. Distinguish the brothers only with two minimal anchors: Su Zhe has a small simple cap and slimmer/shorter stick-figure proportion; Su Shi has a slightly broader/taller stick-figure proportion and a different simple cap. Do not draw detailed costume or faces. Night study-room geometry is only one simple window, one low table, and two small candle shapes/flames. No other furniture, architecture, props, or background detail. No color.

FORBIDDEN GRAPHIC MARKS — ABSOLUTE:
No arcs or curved marks around a head or body, no short emphasis strokes, no action lines, speed lines, motion trails, rays, sparkles, exclamation marks, question marks, comic symbols, reaction marks, halos, starbursts, arrows, speech bubbles, or decorative symbols in any cell. Show reading, circling, advising, tapping, and questioning only through natural body posture and contact with the simple props. No eyes, mouths, written marks, pseudo-writing, or visualized dialogue.

SCENE, AXIS, AND PROP CONTINUITY:
The top-left is the same-day bamboo-path anchor. At the hard cut in B047, move to a sparse Northern Song night study room with one simple window behind the low table, two candle shapes/flames, and nothing else. Establish a stable two-shot axis: Su Zhe is screen-left and Su Shi is screen-right, seated across the low table in B047–B051. Do not carry Wang Fu, the maid, the bamboo, or any path prop into the night room. There is exactly one blank策论 paper on the low table in the night-room cells B047–B051 and exactly one simple brush associated with that paper. The paper remains blank and unreadable; no generated text, circles, characters, or pseudo-writing. The single brush belongs to Su Zhe when he uses it in B048–B049; by B050–B051 it is still his prop, either held or resting beside the same paper, clearly not duplicated. Su Shi never acquires a second brush or paper.

SIX STATIC BEATS IN EXACT ORDER:
1. Top-left, boundary B046 / prior setup C016: exact completed state from P009 v01 bottom-right — stable full-body bamboo-path two-shot, Wang Fu screen-left, Su Shi screen-right, both facing one another, maid behind Wang Fu. No night-room props or transition.
2. Top-middle, B047 / setup C019: hard cut to the night study room. Two candle shapes/flames are lit beside a low table; Su Zhe and Su Shi sit reading across the table, Su Zhe screen-left and Su Shi screen-right. Show only the simple window, low table, two candles, two seated stick figures, and one blank paper on the table. No text on the paper.
3. Top-right, B048 / setup C019: same night-room axis. Su Zhe screen-left uses the one simple brush to circle/mark the one blank策论 paper through a poised brush tip touching the paper. Do not draw any actual circle, writing, lettering, or pseudo-text on the paper; the action is shown only by the brush position and his leaning posture. Su Shi reads/listens opposite. Exactly one paper and one brush.
4. Bottom-left, B049 / setup C019: Su Zhe keeps the same paper and brush ownership and maintains a composed advising posture toward Su Shi, one palm lowered or gently open to convey “稳” without any symbol. The paper remains on the table, blank; the brush remains with Su Zhe or immediately beside his paper. Su Shi listens across the table. Keep the two candles, window, low table, and axis unchanged.
5. Bottom-middle, B050 / setup C020: cut to a slightly closer but still same-axis view. Su Shi is visibly unconvinced through a firm torso and head angle, and one of his hands has just completed one light tap on the low table; show the static hand resting on the table once, with no second hand gesture, no tap mark, no action line, and no repeated tapping. Su Zhe remains opposite with the single paper and single brush clearly on his side of the table.
6. Bottom-right, B051 / setup C020: same closer axis. Su Shi's one hand has stopped at the edge of the same single blank paper, not taking or moving it, and he completes a calm questioning posture toward Su Zhe. Su Zhe remains opposite; the one brush is clearly still Su Zhe's prop, held or set immediately beside the one paper. No second paper, no extra brush, no text, no question mark, and no new prop. Both brothers remain seated across the low table.

BEAT LOGIC:
bamboo-path two-shot anchor -> hard cut to night study with two candles and brothers reading -> Su Zhe uses one brush on one blank paper -> Su Zhe holds a steady advising posture -> unconvinced Su Shi makes exactly one light table tap -> Su Shi's hand stops at the paper edge as he asks a question. Do not show actual writing, circles, or words. Do not transfer ownership of the paper or brush, duplicate props, or change the screen-left/screen-right axis.

CHARACTER, ANATOMY, AND PROP LOCK:
Every stick figure has exactly two arms and two legs. Su Zhe is one slimmer body on screen-left with one minimal cap; Su Shi is one slightly broader/taller body on screen-right with another minimal cap. The brothers use only their existing arms. There is exactly one paper, blank, on the table and exactly one brush associated with Su Zhe; the same items persist through B047–B051 without copies. The two candle shapes are the only additional props, plus the simple window and low table. No ghost hands, detached limbs, duplicate characters, merged bodies, extra props, floating objects, or transferred brush/paper.

Absolutely no visible text, pseudo-text, letters, numbers, labels, captions, subtitles, watermark, logo, UI, signature, speech bubbles, arrows, speed lines, motion trails, arcs, rays, ripples as graphic effects, comic emphasis marks, or decorative symbols. Do not make it photorealistic, cinematic, colorful, anime, manga, comic, polished illustration, detailed costume art, or realistic architecture.
```

### P009 v01

- 生成时间：2026-08-30 16:02:19 +08:00；原始生成图：`C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-f1f67b4c-54d0-42a0-8500-ba631090eafd.png`
- 原始图尺寸：1672×941，1,138,545 bytes，SHA-256 `C59E8AFF152C2FED3149935B49E52379ABD0799F3651750D5D9A3646C66C620C`。
- 候选归档：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P009_v01.png`；已复制归档，原始图保持不动，未覆盖正式 `board_P009.png`。
- 唯一连续性参考：不可变 `E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P008_v01.png`；该参考由主代理独立 QC 判定 PASS。
- 生成子代理说明：按主代理指令仅完成一次 ImageGen 调用与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 针对性要求：左上严格复现 B041 王弗左侧望向池水、尚未回答，苏轼右侧、丫鬟后景；后五格依次为王弗回望作安静解释、苏轼姿态收住认真朝向她、同轴私人回应视点苏轼静陈述、两人相向短静默、轻拉为稳定双人全身构图且丫鬟后景；人物左右不翻、距离稳定、不重复追问；保持真正极简火柴人、竹径简线、16:9、2×3、无文字/符号/额外肢体。
- 完整 Prompt：

```text
Use case: illustration-story
Asset type: production storyboard board for STEP 3, Panel P009.
Input image: Image 1 is the sole immutable continuity reference: the approved P008 v01 storyboard board. Use it only to preserve the strict minimal stick-figure blocking language, the quiet same-day bamboo-path setting, the stable C013/C014 screen axis, and the exact B041 end-state in the bottom-right cell. Do not copy the whole reference board into the new image.

Create exactly one complete black-and-white storyboard board for Panel P009 of a Northern Song historical film sequence. This is a director's rough blocking sheet, not final art, not a character sheet, and not six separate images.

TOP-LEFT ZERO-DURATION BOUNDARY — HIGHEST PRIORITY:
Reproduce P008 v01 bottom-right B041 exactly as a completed static state, without re-establishing or advancing it: Wang Fu stands on screen-left with head and torso briefly turned toward the pool-water direction beyond the bamboo, not yet answering; Su Shi stands on screen-right watching her; the maid remains a half-step behind Wang Fu in the rear. Preserve the bamboo-path geometry, left-right positions, distance, C014 axis, and three-person blocking. This anchor must not show Wang Fu turning back, explaining, Su Shi changing posture, repeated questioning, silence, or a camera pullback. It is a zero-duration continuity cell.

Canvas and grid: exact landscape 16:9. One clean board with exactly 2 rows by 3 columns, six equal rectangular cells, thin black dividers, reading order left-to-right across the top row then left-to-right across the bottom row. No title strip, extra cells, merged cells, nested boards, or unequal panels.

DRAWING LANGUAGE — STRICTLY MINIMAL:
Match Image 1's director blocking-sheet style: white paper, sparse black pencil/charcoal lines and tiny light-gray geometric blocks only. Every person is a faceless empty circle head, one single-line torso, and simple line-segment arms and legs. No facial marks, eyes, mouth, hair, topknot, anatomy, complete robe silhouette, clothing folds, realistic costume, shading, texture, crosshatching, polished illustration, or realistic people. Wang Fu and the maid are distinguished only by extremely few simple outline anchors: Wang Fu may have one tiny restrained hair/garment contour; the maid keeps one tiny light-gray torso block or short outer contour. Su Shi remains an undecorated stick figure. The bamboo path has only a few vertical bamboo lines and a simplified path line, with no detailed foliage. No color.

FORBIDDEN GRAPHIC MARKS — ABSOLUTE:
No arcs or curved marks around a head or body, no short emphasis strokes, no action lines, speed lines, motion trails, rays, sparkles, exclamation marks, question marks, comic symbols, reaction marks, halos, starbursts, arrows, speech bubbles, or decorative symbols in any cell. Show explanation, attention, private response, silence, and camera distance only through natural head angle, hand position, shoulder level, torso posture, and scale. No eyes, mouths, facial expression marks, or surprise lines.

SCENE, AXIS, AND CONTINUITY:
All cells remain on the same-day quiet bamboo path beside the waterside grounds. Keep the C013/C014 axis unflipped: Wang Fu remains screen-left and Su Shi remains screen-right in every two-shot; the maid remains behind Wang Fu, slightly farther back. A private response viewpoint may change framing but must not mirror left-right positions or reverse screen direction. Keep the distance between Wang Fu and Su Shi stable until the final gentle pullback. The pool direction is only a simple implied opening beyond the bamboo; use a few vertical bamboo lines and a simplified path line, no detailed landscape. There are no paper slips, writing props, labels, or hand props anywhere in this board. All dialogue is post-production only and must not appear as text.

SIX STATIC BEATS IN EXACT ORDER:
1. Top-left, boundary B041 / prior setup C014: exact completed state from P008 v01 bottom-right — Wang Fu screen-left has head and torso turned briefly toward the pool-water direction, not yet answering; Su Shi screen-right watches her; the maid remains half a step behind Wang Fu. No new action or transition.
2. Top-middle, B042 / setup C014: Wang Fu has turned her head and torso back toward Su Shi and gives a quiet, natural explanation through an attentive upright speaking posture and one restrained open hand if needed. She does not repeat a question. Keep Wang Fu screen-left, Su Shi screen-right, and the maid rear-left. No mouth, text, or speech marks.
3. Top-right, B043 / setup C014: Su Shi's relaxed posture gradually settles into a serious attentive stance facing Wang Fu; show a small, believable reduction of casual looseness through straighter torso and fixed head direction, without eyes or facial marks. Keep the same distance and unflipped axis. The maid remains behind Wang Fu.
4. Bottom-left, B044 / setup C015 private response viewpoint: cut to a closer private response framing while preserving screen direction — Su Shi remains screen-right, quietly states his response through a composed speaking posture and a subtle hand position; Wang Fu stays screen-left facing him, maid behind her. This is a response, not another question. Do not draw speech bubbles, letters, mouths, or gesture lines.
5. Bottom-middle, B045 / setup C015: both Wang Fu and Su Shi hold their mutual facing gaze in a short quiet silence. Their heads remain directed toward each other and their bodies stay still at the same distance; the maid remains a quiet rear presence. No new gesture, no repeated question, no reaction marks.
6. Bottom-right, B046 / setup C016: a gentle pullback settles into a stable full-body two-person composition on the bamboo path. Wang Fu remains screen-left and Su Shi screen-right at the same relative positions, both facing each other; the maid is still visible in the rear behind Wang Fu. Use a slightly wider but steady framing only, with no motion lines, no axis flip, and no new action.

BEAT LOGIC:
Wang Fu paused toward the pool before answering -> she turns back and quietly explains -> Su Shi's relaxed body settles into serious attention -> private same-axis response from Su Shi -> both hold a short mutual silence -> gentle pullback to a stable full-body two-shot with the maid in back. Do not repeat the question, do not add a second explanation turn, do not merge the pool and bamboo settings, and do not change screen-left/screen-right positions.

CHARACTER AND ANATOMY LOCK:
Every stick figure has exactly two arms and two legs. Wang Fu is one body at screen-left with the same minimal contour in every cell; the maid is one body half a step behind her with one tiny gray torso anchor; Su Shi is one body at screen-right. All gestures use only each character's existing arms. No ghost hands, detached limbs, duplicate characters, merged bodies, extra props, paper slips, or floating objects.

Absolutely no visible text, pseudo-text, letters, numbers, labels, captions, subtitles, watermark, logo, UI, signature, speech bubbles, arrows, speed lines, motion trails, arcs, rays, ripples as graphic effects, comic emphasis marks, or decorative symbols. Do not make it photorealistic, cinematic, colorful, anime, manga, comic, polished illustration, detailed costume art, or realistic architecture.
```

### P010 v01 promotion

- 独立 QC 结论：PASS（主代理确认，SHA-256 `92C57BC2068766607660B934FCF443D4FB428EBF23D7D4F0AD4C6189C15E7A07`）。
- 提升来源：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P010_v01.png`。
- 正式文件：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P010.png`。
- 提升后正式文件与候选逐字节一致；提升后 SHA-256 `92C57BC2068766607660B934FCF443D4FB428EBF23D7D4F0AD4C6189C15E7A07`。候选与原始生成图均保留。

### P011 v01

- 生成时间：2026-08-30 16:14:20 +08:00；原始生成图：`C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-30a7d0e6-b056-4bee-8929-0479e70f37ae.png`
- 原始图尺寸：1672×941，964,392 bytes，SHA-256 `FEAEFD7657A3100264B7231FF91B4E1FEBB0F59A9A751D1B022FBF690F34D5DE`。
- 候选归档：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P011_v01.png`；已复制归档，原始图保持不动，未覆盖正式 `board_P011.png`。
- 连续性参考：仅使用不可变 `E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P010_v01.png`；既有旧 P011 候选（含 v00）全部作废，不得作为参考或 QC 基准。
- 生成子代理说明：按主代理指令仅完成一次 ImageGen 调用与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 针对性要求：左上严格复现 B051 苏轼右侧手停唯一纸边、苏辙左侧持唯一毛笔、兄弟对视；后五格依次为苏辙放下并完全松手、自然放松轻笑作承诺、苏轼克制愣住转郑重、苏轼仅一手按住弟弟肩膀、近景仅两条前臂和两只叠手；墙上恰好两个人影、两盏烛火；保持极简火柴人/几何书房、16:9、2×3、无文字/伪字/漫画线/多手/重复毛笔纸张。
- 完整 Prompt：

```text
Use case: illustration-story
Asset type: production storyboard board for STEP 3, Panel P011.
Input image: Image 1 is the sole immutable continuity reference: the approved P010 v01 storyboard board. All previous P011 candidates are invalid and must not be used. Use Image 1 only to preserve the strict minimal stick-figure blocking language, the sparse Northern Song night study-room geometry, the Su Zhe/Su Shi screen axis, and the exact B051 end-state in the bottom-right cell. Do not copy any old P011 image or the whole reference board.

Create exactly one complete black-and-white storyboard board for Panel P011 of a Northern Song historical film sequence. This is a director's rough blocking sheet, not final art, not a character sheet, and not six separate images.

TOP-LEFT ZERO-DURATION BOUNDARY — HIGHEST PRIORITY:
Reproduce P010 v01 bottom-right B051 exactly as a completed static state, without re-establishing or advancing it: Su Shi is seated on screen-right with one hand stopped at the edge of the single blank paper on the low table; Su Zhe is seated opposite on screen-left and still holds the single brush; the brothers face each other across the table. Preserve the night-room window, low table, two candle flames, screen-left/screen-right positions, the one paper and one brush, and the exact hand/prop ownership. The anchor must not show the brush being placed down, Su Zhe relaxing, Su Shi becoming serious, touching a shoulder, a close-up, extra hands, or extra shadows. It is a zero-duration continuity cell.

Canvas and grid: exact landscape 16:9. One clean board with exactly 2 rows by 3 columns, six equal rectangular cells, thin black dividers, reading order left-to-right across the top row then left-to-right across the bottom row. No title strip, extra cells, merged cells, nested boards, or unequal panels.

DRAWING LANGUAGE — STRICTLY MINIMAL:
Match the director's rough blocking-sheet style: white paper, sparse black pencil/charcoal lines and tiny light-gray geometric blocks only. Every visible full person is a faceless empty circle head, one single-line torso, and simple line-segment arms and legs. No facial marks, eyes, mouth, hair, topknot, anatomy, complete robe silhouette, clothing folds, realistic costume, shading, texture, crosshatching, polished illustration, or realistic people. Distinguish Su Zhe and Su Shi only with the same two minimal cap/body anchors from P010: Su Zhe smaller/slimmer with one simple cap, Su Shi slightly broader/taller with the other simple cap. No detailed costume or face. The night-room geometry is only one simple window, one low table, and two small candle shapes/flames. No other furniture, architecture, props, or background detail. The final close-up may crop out heads and torsos as specified. No color.

FORBIDDEN GRAPHIC MARKS — ABSOLUTE:
No arcs or curved marks around a head or body, no short emphasis strokes, no action lines, speed lines, motion trails, rays, sparkles, exclamation marks, question marks, comic symbols, reaction marks, halos, starbursts, arrows, speech bubbles, or decorative symbols in any cell. Show release, relaxation, seriousness, touch, and hand overlap only by natural posture and actual simple contact. No eyes, mouths, written marks, pseudo-writing, or visualized dialogue. Do not use graphic lines to show laughter, surprise, impact, or emphasis.

SCENE, AXIS, AND PROP CONTINUITY:
The entire board remains in the same sparse Northern Song night study room. Su Zhe stays screen-left and Su Shi screen-right across the low table in B051–B055; do not flip the axis. There is exactly one blank paper on the table and exactly one simple brush. In B051 the brush is held by Su Zhe; in B052 he places that same brush on the table and fully releases it; in B053–B056 it remains the same single brush on/near Su Zhe's side and is never duplicated. The same single blank paper remains on the table, unreadable, with no marks. The two candles are the only light props. No extra people, maid, path, bamboo, paper, brush, or furniture enters the room. The final wall shows exactly two simple human shadows, one for each brother, and no other shadow.

SIX STATIC BEATS IN EXACT ORDER:
1. Top-left, boundary B051 / prior setup C020: exact completed state from P010 v01 bottom-right — Su Shi screen-right has one hand stopped at the edge of the one blank paper; Su Zhe screen-left still holds the one brush; both face each other across the low table. Keep all props and axis unchanged. No new action.
2. Top-middle, B052 / setup C021: Su Zhe has placed the one brush onto his side of the low table and has completely released it. Show the single brush lying on the table, with both of Su Zhe's hands clearly away from it; the one blank paper remains on the table. Su Shi's hand is no longer advancing and stays on his side. No second brush, no extra hands, no placement lines.
3. Top-right, B053 / setup C021: Su Zhe is naturally relaxed and gives a quiet light smile/承诺 through softened shoulders, an easy upright torso, and a slight calm head angle only. No eyes, mouth, facial marks, laughter marks, arcs, or comic signs. The single brush remains lying on the table and the single paper remains blank. Su Shi watches from screen-right.
4. Bottom-left, B054 / setup C021: cut to Su Shi's restrained reaction. He is momentarily still and slightly startled, then his posture turns serious and deliberate toward Su Zhe; convey this only with a controlled head angle and firmer torso, never a face or comic line. Su Zhe remains opposite, relaxed, with the one brush on the table and the one paper unchanged.
5. Bottom-middle, B055 / setup C022: Su Shi uses exactly one of his hands to gently press/hold Su Zhe's shoulder across the low table. The other Su Shi hand is completely uninvolved, relaxed at his own side or resting away from all props. Su Zhe remains seated and receives the touch; no extra arm, no second contact, no impact/action mark. Keep the one brush lying on Su Zhe's side and the single paper on the table, clearly separate from the shoulder touch.
6. Bottom-right, B056 / setup C022 close-up: show only the two brothers' two forearms and exactly two hands, cropped from the bodies; each brother contributes exactly one visible forearm and one visible hand, with the two hands clearly overlapping in one gentle shoulder/hand contact. Do not show heads, faces, torsos, extra arms, or any third hand. On the simple wall behind them cast exactly two human shadows, one per brother, and show exactly two small candle flames; no third shadow, no extra candle, no other prop. This is a quiet close-up, not an impact image and not a gesture diagram.

BEAT LOGIC:
Su Shi's hand stopped at the paper edge while Su Zhe holds the brush -> Su Zhe places and fully releases the brush -> Su Zhe relaxes and lightly smiles as a promise -> Su Shi's restrained reaction settles into seriousness -> Su Shi uses one hand to press his brother's shoulder -> close-up of exactly two forearms and two overlapping hands with exactly two wall shadows and two candle flames. Do not duplicate the old P011, do not change the axis, do not add a third hand, and do not turn the touch into a comic or forceful action.

CHARACTER, ANATOMY, AND PROP LOCK:
Every full stick figure has exactly two arms and two legs. Su Zhe is one slimmer body on screen-left with one minimal cap; Su Shi is one slightly broader/taller body on screen-right with the other minimal cap. B055 uses only one Su Shi hand for the shoulder contact; his other hand is not participating. B056 is cropped to exactly two forearms and exactly two hands total, one from each brother, overlapping clearly; no torso, head, or third limb is visible. There is exactly one paper and exactly one brush in B051–B056, both blank/unwritten and never copied. The wall has exactly two human shadows and the room has exactly two candle flames in B056. No ghost hands, detached limbs, duplicate characters, merged bodies, extra props, floating objects, or repeated brush/paper.

Absolutely no visible text, pseudo-text, letters, numbers, labels, captions, subtitles, watermark, logo, UI, signature, speech bubbles, arrows, speed lines, motion trails, arcs, rays, ripples as graphic effects, comic emphasis marks, or decorative symbols. Do not make it photorealistic, cinematic, colorful, anime, manga, comic, polished illustration, detailed costume art, or realistic architecture.
```

### P011 v01 promotion

- 独立 QC 结论：PASS（主代理确认，SHA-256 `FEAEFD7657A3100264B7231FF91B4E1FEBB0F59A9A751D1B022FBF690F34D5DE`）。
- 提升来源：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P011_v01.png`。
- 正式文件：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P011.png`。
- 提升后正式文件与候选逐字节一致；提升后 SHA-256 `FEAEFD7657A3100264B7231FF91B4E1FEBB0F59A9A751D1B022FBF690F34D5DE`。候选与原始生成图均保留。

### P012 v01

- 生成时间：2026-08-30 16:22:29 +08:00；原始生成图：`C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-508d05d3-27fd-48aa-82b4-c148f08fddc1.png`
- 原始图尺寸：1672×941，986,415 bytes，SHA-256 `CA57EB2D89C6F1EC8674E5A3DE64571481D6C3D02412218ED8D1759AD1211DEE`。
- 候选归档：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P012_v01.png`；已复制归档，原始图保持不动，未覆盖正式 `board_P012.png`。
- 唯一连续性参考：不可变 `E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P011_v01.png`；该参考由主代理独立 QC 判定 PASS。
- 生成子代理说明：按主代理指令仅完成一次 ImageGen 调用与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 针对性要求：左上严格复现 B056 两前臂两手叠合、两人影、两烛；上中硬切北宋写实宋式院落婚礼，苏轼/王弗与宾客拜堂且婚服仅极简轮廓；上右礼成起身；左下鞭炮燃放后仅细烟与散纸段；下中程夫人一手掩口咳、一手下垂，苏洵一手扶其手臂；右下同院落 jump cut 数月后为空院石桌；无时间文字，16:9、2×3、无文字/符号/多手。
- 完整 Prompt：

```text
Use case: illustration-story
Asset type: production storyboard board for STEP 3, Panel P012.
Input image: Image 1 is the sole immutable continuity reference: the approved P011 v01 storyboard board. Use it only to preserve the strict minimal stick-figure blocking language and the exact B056 end-state in the bottom-right cell. Do not copy any previous P012 image or the whole reference board into the new image.

Create exactly one complete black-and-white storyboard board for Panel P012 of a Northern Song historical film sequence. This is a director's rough blocking sheet, not final art, not a character sheet, and not six separate images.

TOP-LEFT ZERO-DURATION BOUNDARY — HIGHEST PRIORITY:
Reproduce P011 v01 bottom-right B056 exactly as a completed static state, without re-establishing or advancing it: a close-up showing exactly two brothers' forearms and exactly two hands overlapping, one hand from each brother; the simple wall behind them has exactly two human shadows and exactly two candle flames. No heads, torsos, third hand, third shadow, or extra candle is visible. Preserve the quiet night-study-room geometry and this exact two-hands/two-shadows/two-flames count. The anchor must not show the wedding courtyard, ceremony, firecrackers, cough, or time jump. It is a zero-duration continuity cell.

Canvas and grid: exact landscape 16:9. One clean board with exactly 2 rows by 3 columns, six equal rectangular cells, thin black dividers, reading order left-to-right across the top row then left-to-right across the bottom row. No title strip, extra cells, merged cells, nested boards, or unequal panels.

DRAWING LANGUAGE — STRICTLY MINIMAL:
Match the director's rough blocking-sheet style: white paper, sparse black pencil/charcoal lines and tiny light-gray geometric blocks only. Every full person is a faceless empty circle head, one single-line torso, and simple line-segment arms and legs. No facial marks, eyes, mouth, hair, topknot, anatomy, complete robe silhouette, clothing folds, realistic costume, shading, texture, crosshatching, polished illustration, or realistic people. Wedding clothing is represented only by minimal outline anchors: Su Shi may have one simple cap/shoulder contour and Wang Fu one tiny simple bridal head/shoulder contour; never draw ornate robes, Qing-style clothing, headdresses, veil detail, embroidery, or fabric folds. Guests and elders are plain stick figures with no faces. The courtyard uses only simple geometric gate/wall lines, ground line, hanging ribbon strips, and a stone table. No color.

FORBIDDEN GRAPHIC MARKS — ABSOLUTE:
No arcs or curved marks around a head or body, no short emphasis strokes, no action lines, speed lines, motion trails, rays, sparkles, exclamation marks, question marks, comic symbols, reaction marks, halos, starbursts, arrows, speech bubbles, or decorative symbols in any cell. Show ceremony, standing, coughing, support, and the later empty-yard state only through natural body positions and sparse props. Natural thin smoke in B059 is allowed only as a few wispy strokes rising directly from the spent firecracker string; it must not look like action lines or comic effects. No visualized dialogue or time label.

SCENE, CUT, AND PROP CONTINUITY:
The top-left is the P011 night-study close-up. At B057 hard cut to a same-day Northern Song family courtyard wedding in daylight; do not carry the night wall, candles, brothers' table, bamboo path, or paper/brush into the courtyard. The courtyard remains the same for B057–B060: simple gate/wall geometry, open ground, minimal hanging wedding ribbon strips, and later a stone table. The wedding ribbons, guests, and newlyweds must disappear only at the B061 jump cut. The phrase “数月后” is a post-production overlay and must not appear in this storyboard. No text or pseudo-text anywhere. The wedding board is historical Song-period blocking, explicitly not Qing dynasty visual styling.

SIX STATIC BEATS IN EXACT ORDER:
1. Top-left, boundary B056 / prior setup C022: exact completed state from P011 v01 bottom-right — close-up of exactly two forearms and two overlapping hands, exactly two wall shadows, exactly two candle flames; no heads, torsos, third hand, third shadow, or extra prop. No courtyard transition.
2. Top-middle, B057 / setup C023: hard cut to the Northern Song family courtyard wedding. Su Shi and Wang Fu, the two newlyweds, stand side by side or just before the guests and make a simple formal bow toward a small group of plain stick-figure guests. Use only a few simple hanging wedding ribbon strips and minimal courtyard gate/wall lines. Show Song-style simplicity, not Qing clothing. Newlyweds are distinguished only by their two tiny outline anchors; no faces, ornate costume, or decorative symbols.
3. Top-right, B058 / setup C023: the wedding ceremony is complete and the two newlyweds have risen to stand upright. Keep Su Shi and Wang Fu at the front with the sparse guests behind or opposite, the same courtyard and hanging ribbons, and no new gesture. Use only natural posture to show the completed礼成; no text, clapping marks, or symbols.
4. Bottom-left, B059 / setup C023: on the courtyard ground, one string of firecrackers has finished burning. Show only the spent string as a few simple connected ground segments, a few scattered paper fragments, and thin natural smoke rising directly from it. No explosion, sparks, starbursts, sound marks, action lines, flames, arrows, or comic effects. Keep the courtyard geometry; do not add a person or duplicate firecracker strings.
5. Bottom-middle, B060 / setup C023: Cheng Furen stands in the same courtyard and lightly covers her mouth with exactly one hand in a restrained cough posture; her other hand hangs down naturally. Su Xun stands beside her and gently supports her arm with exactly one of his hands; his other hand remains uninvolved and lowered. Make their relationship and single-point support clear through attached arms and close but natural spacing. No cough marks, facial marks, or extra hands. Keep the same simple courtyard, ribbons, and stone-table geometry.
6. Bottom-right, B061 / setup C024 jump cut within the same Clip: months later, the same courtyard is clean and empty. All wedding ribbons, guests, newlyweds, Cheng Furen, and Su Xun have disappeared; no person remains. Show only the quiet courtyard ground, simple gate/wall geometry, and one clear stone table. No time text, “数月后” label, calendar, debris from the wedding, or extra prop. This is a clean static empty-yard state after the jump cut.

BEAT LOGIC:
night-study two-hands/two-shadows/two-candles anchor -> hard cut to Song-style courtyard wedding bow -> newlyweds rise after ceremony -> spent firecracker string with only thin smoke and paper fragments -> Cheng Furen coughs while Su Xun supports one arm with one hand -> same courtyard months later is empty and clean with a stone table. Do not merge the night and courtyard settings, do not use Qing clothing, do not depict explosive effects, and do not show the time passage as on-image text.

CHARACTER, ANATOMY, AND PROP LOCK:
Every full stick figure has exactly two arms and two legs. In B057–B058 Su Shi and Wang Fu are the only newlyweds, with minimal distinct outline anchors; guests are separate plain stick figures. In B060 Cheng Furen uses one hand at her mouth and one lowered hand; Su Xun uses one hand to support her arm and one uninvolved lowered hand. No ghost hands, detached limbs, duplicate bodies, merged figures, or extra gestures. B059 has one and only one spent firecracker string, a few scattered paper fragments, and thin smoke only. B061 has no people and one clear stone table; all wedding/people props are gone. The B056 anchor alone has exactly two forearms, two hands, two wall shadows, and two candle flames.

Absolutely no visible text, pseudo-text, letters, numbers, labels, captions, subtitles, watermark, logo, UI, signature, speech bubbles, arrows, speed lines, motion trails, arcs, rays, comic emphasis marks, decorative symbols, Qing-style clothing, ornate costumes, or realistic architecture. Do not make it photorealistic, cinematic, colorful, anime, manga, comic, polished illustration, detailed costume art, or realistic people.
```

### P012 v02

- 生成时间：2026-08-30 16:27:39 +08:00；原始生成图：`C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-fda6f307-7a6a-4e4b-8c34-8ce49c320461.png`
- 原始图尺寸：1672×941，1,178,466 bytes，SHA-256 `5ABEB08C6A3344E61CB763C370419B709E8B8B709795BD1BB0A9DAD8A070C30F`。
- 候选归档：`E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P012_v02.png`；已复制归档，原始图保持不动，未覆盖正式 `board_P012.png`。
- 唯一连续性参考：不可变 `E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P011_v01.png`；仍以 P011 v01 为唯一上一板参考，P012 v01 不作为视觉参考。
- 生成子代理说明：按主代理指令仅完成一次 ImageGen 调用与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 修订根因：`TIME-JUMP-STATE-001`；仅强化 B061 末格时间跳切后的完全素净状态，保持 B056–B060 的既有语义不变。
- 针对性要求：右下 B061 为最高优先级清空边界——同一院落数月后，屋檐/横梁/门柱/背景零悬挂绸带、零花结、零灯笼、零宾客、零新人、零人物、零鞭炮纸、零烟、零婚礼残留，只保留裸露院墙/屋檐几何线、清楚石桌和普通地面；无人、无时间文字、无转场图形。
- 完整 Prompt：

```text
Use case: illustration-story
Asset type: production storyboard board for STEP 3, Panel P012 revision v02.
Input image: Image 1 is the sole immutable continuity reference: the approved P011 v01 storyboard board. Use P011 v01 as the only reference image. Do not use P012 v01 or any previous P012 candidate as a visual reference. Preserve the minimal black-and-white blocking language and the exact B056 night-study anchor.

Create exactly one complete black-and-white storyboard board for Panel P012, revision v02, of a Northern Song historical film sequence. This is a director's rough blocking sheet, not final art, not a character sheet, and not six separate images. Keep all previously approved P012 v01 beats B056–B060 unchanged in meaning; the revision is specifically to correct the final B061 time-jump state.

TOP-LEFT ZERO-DURATION BOUNDARY:
Reproduce P011 v01 bottom-right B056 exactly as a completed static state: a close-up showing exactly two brothers' forearms and exactly two hands overlapping, one hand from each brother; the simple wall behind them has exactly two human shadows and exactly two candle flames. No heads, torsos, third hand, third shadow, or extra candle. Preserve the quiet night-study-room geometry. This anchor must not show the wedding courtyard, ceremony, firecrackers, cough, or time jump.

FINAL CELL B061 — HIGHEST PRIORITY QC BOUNDARY:
The bottom-right cell must be a completely clean, empty version of the same family courtyard after a jump cut months later. It must contain absolutely no wedding decoration or human presence: zero hanging silk ribbons, zero ribbon bows, zero lanterns, zero guests, zero newlyweds, zero Cheng Furen, zero Su Xun, zero firecracker strings, zero spent firecracker paper fragments, zero smoke, zero wedding debris, zero people, zero shadows of people, and zero time text. Show only the bare courtyard wall/eaves as a few simple geometric lines, the roof edge or gate geometry without decorations, one clearly readable stone table, and ordinary clean ground. The final cell must look visibly and decisively different from the decorated wedding cells B057–B060. Do not let any wedding prop or ornament cross into B061. Do not add a calendar, title, caption, or “数月后” label. This is a static empty-yard state, not a dissolve or transition graphic.

Canvas and grid: exact landscape 16:9. One clean board with exactly 2 rows by 3 columns, six equal rectangular cells, thin black dividers, reading order left-to-right across the top row then left-to-right across the bottom row. No title strip, extra cells, merged cells, nested boards, or unequal panels.

DRAWING LANGUAGE — STRICTLY MINIMAL:
Match the director's rough blocking-sheet style: white paper, sparse black pencil/charcoal lines and tiny light-gray geometric blocks only. Every full person is a faceless empty circle head, one single-line torso, and simple line-segment arms and legs. No facial marks, eyes, mouth, hair, topknot, anatomy, complete robe silhouette, clothing folds, realistic costume, shading, texture, crosshatching, polished illustration, or realistic people. Wedding clothing in B057–B058 is represented only by minimal outline anchors: Su Shi may have one simple cap/shoulder contour and Wang Fu one tiny simple bridal head/shoulder contour; never ornate robes, Qing-style clothing, headdresses, veil detail, embroidery, or fabric folds. Guests and elders are plain stick figures. The courtyard uses sparse gate/wall, ground, minimal wedding ribbon strips in B057–B060, and stone-table geometry. B061 uses only the undecorated bare courtyard geometry and stone table. No color.

FORBIDDEN GRAPHIC MARKS — ABSOLUTE:
No arcs or curved marks around a head or body, no short emphasis strokes, no action lines, speed lines, motion trails, rays, sparks, starbursts, exclamation marks, question marks, comic symbols, reaction marks, halos, arrows, speech bubbles, or decorative symbols in any cell. Natural thin smoke in B059 is allowed only as a few wispy strokes directly above the spent firecracker string; it must not look like action lines or comic effects. B061 has no smoke of any kind. No visualized dialogue, no time label, and no transition effects.

SCENE, CUT, AND PROP CONTINUITY:
The top-left is the P011 night-study close-up. At B057 hard cut to a same-day Northern Song family courtyard wedding in daylight; do not carry the night wall, candles, brothers' table, bamboo path, or paper/brush into the courtyard. B057–B060 are the same simple courtyard wedding sequence and retain only the minimal wedding ribbon strips needed for the ceremony beats. At the B061 jump cut within the same Clip, remove every wedding item and every person. The final courtyard must be bare: no silk, bow, lantern, guest, bride, groom, elder, maid, firecracker fragment, smoke, or shadow. The phrase “数月后” is a post-production overlay and must not appear in this storyboard. No text or pseudo-text anywhere. The wedding styling is historical Northern Song, explicitly not Qing dynasty.

SIX STATIC BEATS IN EXACT ORDER:
1. Top-left, boundary B056 / prior setup C022: exact completed state from P011 v01 bottom-right — close-up of exactly two forearms and two overlapping hands, exactly two wall shadows, exactly two candle flames; no heads, torsos, third hand, third shadow, or extra prop. No courtyard transition.
2. Top-middle, B057 / setup C023: hard cut to the Northern Song family courtyard wedding. Su Shi and Wang Fu, the two newlyweds, stand before a small group of plain stick-figure guests and make a simple formal bow. Use only a few minimal hanging wedding ribbon strips and simple gate/wall lines. Show Song-style simplicity, not Qing clothing. Newlyweds have only tiny outline anchors; no faces or ornate costume.
3. Top-right, B058 / setup C023: the ceremony is complete and the two newlyweds have risen upright. Keep the same simple courtyard, the minimal wedding ribbon strips, and sparse guests. Use natural posture only to show礼成; no text, clapping marks, or symbols.
4. Bottom-left, B059 / setup C023: on the courtyard ground, one string of firecrackers has finished burning. Show only the spent string as a few simple connected ground segments, a few scattered paper fragments, and thin natural smoke rising directly from it. No explosion, sparks, starbursts, sound marks, action lines, flames, arrows, or comic effects. Keep any remaining courtyard ceremony geometry minimal; do not duplicate the firecracker string.
5. Bottom-middle, B060 / setup C023: Cheng Furen stands in the courtyard and lightly covers her mouth with exactly one hand in a restrained cough posture; her other hand hangs down. Su Xun stands beside her and gently supports her arm with exactly one of his hands; his other hand remains uninvolved and lowered. Make the one-point support clear through attached arms and natural spacing. No cough marks, facial marks, or extra hands. Keep only the simple courtyard and stone-table geometry; no extra props.
6. Bottom-right, B061 / setup C024 jump cut within the same Clip — FINAL EMPTY YARD, HIGHEST PRIORITY: months later, the same courtyard is entirely clean and empty. All wedding silk/ribbons/bows/lanterns, guests, newlyweds, Cheng Furen, Su Xun, firecracker string, paper fragments, smoke, people, and people-shadows are gone. No person is present. Show only bare undecorated courtyard wall/eaves/gate geometry, one clear stone table, and ordinary clean ground. No wedding trace, no debris, no text, no “数月后” label, no calendar, no transition graphic. The final cell must not resemble B057–B060's decorated wedding state.

BEAT LOGIC:
night-study two-hands/two-shadows/two-candles anchor -> hard cut to Song-style courtyard wedding bow -> newlyweds rise after ceremony -> spent firecracker string with only thin smoke and paper fragments -> Cheng Furen coughs while Su Xun supports one arm with one hand -> same courtyard months later is a completely bare, clean, unoccupied yard with a stone table. The only intended revision is the strong state separation at B061: wedding decorations and all people disappear entirely at the jump cut.

CHARACTER, ANATOMY, AND PROP LOCK:
Every full stick figure has exactly two arms and two legs. In B057–B058 Su Shi and Wang Fu are the only newlyweds, with minimal distinct outline anchors; guests are separate plain stick figures. In B060 Cheng Furen uses one hand at her mouth and one lowered hand; Su Xun uses one hand to support her arm and one uninvolved lowered hand. No ghost hands, detached limbs, duplicate bodies, merged figures, or extra gestures. B059 has one and only one spent firecracker string, a few scattered paper fragments, and thin smoke only. B061 has no people, no shadows, no wedding items, no firecracker debris, and one clear stone table; only the bare courtyard remains. The B056 anchor alone has exactly two forearms, two hands, two wall shadows, and two candle flames.

Absolutely no visible text, pseudo-text, letters, numbers, labels, captions, subtitles, watermark, logo, UI, signature, speech bubbles, arrows, speed lines, motion trails, arcs, rays, comic emphasis marks, decorative symbols, Qing-style clothing, ornate costumes, wedding decorations in B061, people in B061, firecracker debris in B061, smoke in B061, or realistic architecture. Do not make it photorealistic, cinematic, colorful, anime, manga, comic, polished illustration, detailed costume art, or realistic people.

### P012 v03

- 生成时间：2026-08-30 16:36:03 +08:00；原始生成图：C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-b0716bb1-da72-46e1-b88b-8fb89530a748.png
- 生成方式：一次完整画布 ImageGen 编辑；输入整板保持不变，禁止裁格、拼板或脚本修图。
- 原始图尺寸：1672×941，1,135,516 bytes，SHA-256 3C67647F7A6D599D9587BBFD7A10A8BFF7A76E4138A68C89E93824040BCD747A。
- 候选归档：E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P012_v03.png；已复制归档，原始图保持不动，未覆盖正式 board_P012.png。
- 唯一输入源：不可变 E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P012_v02.png；未引入其他视觉参考。
- 候选与原始图 SHA-256 一致：3C67647F7A6D599D9587BBFD7A10A8BFF7A76E4138A68C89E93824040BCD747A。
- 生成子代理说明：按主代理指令仅完成一次完整画布编辑与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 修订根因：TIME-JUMP-STATE-001；仅修订右下 B061 的时间跳切后清空状态，锁定并保留前五格。
- 针对性编辑边界：前五格 B056–B060 的 Beat、构图、人物、手部、道具、轴线、边框、分隔线和极简火柴人样式全部锁定；仅编辑第六格 B061，删除婚礼花结、绸带、垂挂装饰、灯笼、人物、宾客、新人、鞭炮纸、烟和一切婚礼残留；B061 只保留裸院墙、裸屋檐线、清楚石桌和普通地面，无人、无文字、无悬挂物。
- 完整编辑 Prompt（原样）：

    Edit this existing storyboard board in full-canvas mode. Use the supplied image as the sole reference source and output ONE complete board, not a crop or a partial panel. Preserve the exact landscape 16:9 canvas, the complete 2×3 six-cell grid, all outer borders and internal dividers. Do not crop, tile, splice, paste, reassemble, redraw, resize, or rearrange the board.

    HIGHEST PRIORITY: lock cells 1–5 completely. Preserve the top-left through bottom-middle cells exactly as they are in the supplied P012 v02 board: B056 close-up with exactly two forearms/two hands, two candle flames and two wall shadows; B057 wedding courtyard with the same minimal stick figures and simple Song-style hanging wedding ribbons; B058 the newlyweds rising after the ceremony; B059 the completed firecrackers with only the existing restrained smoke and scattered paper; B060 Cheng furen coughing with one hand near her mouth and the other down while Su Xun uses one hand to support her arm. Preserve every beat, composition, character placement, axis, hand/prop ownership, line weight, minimal black-and-white stick-figure style, and panel boundary in cells 1–5. Do not alter, clean up, or reinterpret any part of cells 1–5.

    ONLY EDIT the bottom-right sixth cell, B061. This is the same courtyard after several months, shown as a clean empty state. In the sixth cell delete every wedding remnant and every person: remove all hanging silk ribbons, fabric, flower knots, bows, lanterns, decorations, newlyweds, guests, elders, attendants, people and their shadows, firecracker strings, firecracker paper, smoke, ash, and debris. Leave ONLY a bare unadorned courtyard: simple naked wall geometry, a plain roof/eaves edge or gate-post geometric line, one clearly readable stone table, and clean ordinary ground. There must be no hanging object whatsoever. The sixth cell must contain no people and no time caption. Keep its cell border and divider unchanged.

    The entire board must remain a rough director's blocking sheet: true faceless stick figures with simple line bodies and minimal geometric environment, monochrome black ink on white, no realistic people, no costume detail, no textures, no shading, no photorealism, no cinematic rendering. No text, pseudo-text, letters, numbers, labels, captions, subtitles, watermark, logo, UI, signature, speech bubbles, arrows, speed lines, motion trails, arcs, rays, comic emphasis marks, or decorative symbols anywhere. Do not modify any cell except the bottom-right B061 cell.

### P012 v03 promotion

- 独立 QC 结论：PASS；按主控指令核验候选 SHA-256 3C67647F7A6D599D9587BBFD7A10A8BFF7A76E4138A68C89E93824040BCD747A 一致。
- 提升时间：2026-08-30 16:39:17 +08:00。
- 来源候选：E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P012_v03.png
- 正式板：E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P012.png
- 提升后正式板 SHA-256：3C67647F7A6D599D9587BBFD7A10A8BFF7A76E4138A68C89E93824040BCD747A；字节与候选一致。
- 提升前正式板 SHA-256：F0D38C36F0E646168DE49483F6925E33BDA406D88C27D83DB1D67882CA25DE5F。

### P013 v01

- 生成时间：2026-08-30 16:41:41 +08:00；原始生成图：C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-cd7de953-5770-433b-9a8e-26931147f1e3.png
- 原始图尺寸：1672×941，1,088,643 bytes，SHA-256 BFE4432BE976200E6F4940003670B6513B3A066E29F4C7E753C4F0E355CDFF85。
- 候选归档：E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P013_v01.png；已复制归档，原始图保持不动，未覆盖正式 board_P013.png。
- 唯一连续性参考：不可变 E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P012_v03.png；P012 v03 已提升为正式 board_P012.png。
- 候选与原始图 SHA-256 一致：BFE4432BE976200E6F4940003670B6513B3A066E29F4C7E753C4F0E355CDFF85。
- 生成子代理说明：按主代理指令仅完成一次 ImageGen 调用与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 针对性连续性要求：左上零时长复现 P012 v03 右下 B061 的数月后素净无人院落；B062–B066 只推进同一封空白信从苏洵手中到石桌，再到巢儿手中的连续动作；全程仅一封空白信，不显示任何文字。
- 完整 Prompt（原样）：

    Create exactly ONE complete black-and-white storyboard board for Panel P013, revision v01, using the supplied immutable P012 v03 board as the sole visual reference for canvas, 2×3 grid, courtyard geography, line weight, and continuity. This is a new panel sequence, not six separate images. Preserve the exact landscape 16:9 canvas, six equal rectangular cells in a 2 rows × 3 columns grid, thin black outer border and internal dividers, and left-to-right reading order. Do not crop, tile, splice, paste, merge, add a title strip, or create extra panels.

    The board must be a rough director's blocking sheet in true minimal stick-figure language: faceless empty circular heads, single-line torsos, simple line-segment limbs, sparse geometric courtyard lines, monochrome black ink on white. Use only tiny simple outline anchors to distinguish Su Xun, Su Shi, Su Zhe, and Chao'er by silhouette/scale/head or shoulder shape; no facial features, hair detail, robes, fabric folds, texture, shading, realism, or polished illustration. Keep the courtyard quiet and bare after the months-later jump: no wedding decorations, ribbons, bows, lanterns, guests, newlyweds, firecrackers, smoke, or debris in any P013 cell. A stone table is the only important prop. The letter must always be a single blank, unreadable sheet/envelope with no writing or pseudo-writing.

    EXACT SIX-CELL BEATS AND CONTINUITY:
    1. TOP-LEFT, zero-duration boundary B061 from P012 v03: reproduce the clean empty courtyard after several months. No person at all, no wedding trace, no hanging object, only bare wall/eaves or gate geometry, ordinary ground, and one clear stone table centered in the courtyard. This is a static continuity anchor, not a new event.
    2. TOP-MIDDLE, B062: same bare courtyard. Su Xun enters from the rear-right courtyard gate/door, moving into the yard with one and only one blank letter in one hand. Show a natural large step posture, but no motion lines or arrows. No other letter and no other person required in this cell.
    3. TOP-RIGHT, B063: same courtyard and same Su Xun. The same single blank letter has just been placed firmly on the stone table; show Su Xun's hand at the table/letter in a natural placing gesture. The table contains exactly one blank letter, no duplicate sheets, and nobody else holds a letter.
    4. BOTTOM-LEFT, B064: Su Xun and the three family members Su Shi, Su Zhe, and Chao'er are present around the stone table. Su Shi, Su Zhe, and Chao'er simultaneously turn their heads and upper bodies toward the one letter/table and toward Su Xun. The single blank letter remains on the table. No person holds any letter; no duplicated paper.
    5. BOTTOM-MIDDLE, B065: declaration viewpoint in the same bare courtyard. Su Xun faces the three listeners and uses one natural pointing arm toward the stone table's one blank letter. The other three do not hold paper. Keep all four bodies anatomically simple with exactly two arms each, no extra hands, no reaction marks, no speech text.
    6. BOTTOM-RIGHT, B066: Chao'er takes the same unique blank letter from the stone table and begins reading with head lowered. Show exactly one letter and exactly Chao'er's two hands holding that one sheet steadily; Su Xun, Su Shi, and Su Zhe remain present but hold nothing. Do not duplicate the letter or add a second sheet.

    Continuity and logic locks: P013 begins with the P012 v03 empty courtyard state; the same single letter travels from Su Xun's hand in B062 to the stone table in B063–B065, then into Chao'er's hands in B066. Do not invent a second letter, extra table, extra gate, or unexplained prop. Identity and positions should remain stable across the courtyard cells. All letter surfaces are blank and unreadable; the phrase “数月后” is a post-production overlay and must not appear in the board.

    Absolutely no visible text, pseudo-text, letters or characters written on the paper, numbers, labels, captions, subtitles, watermark, logo, UI, signature, speech bubbles, arrows, action lines, speed lines, motion trails, arcs, rays, sparkles, exclamation marks, question marks, comic symbols, or decorative marks. Do not make it photorealistic, colorful, cinematic, anime, manga, comic, Qing-style, or realistic costume art. Output only one complete rough 2×3 storyboard board.

### P013 v02

- 生成时间：2026-08-30 19:55:36 +08:00；原始生成图：C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-9318ea65-bf6b-4e8d-b785-5c972c917dc6.png
- 原始图尺寸：1672×941，933,699 bytes，SHA-256 0E40B9DBF309BA10D5DDC34805B03A0AF6AA5FE229166915E5B1093A523BFB21。
- 候选归档：E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P013_v02.png；已复制归档，原始图保持不动，未覆盖正式 board_P013.png。
- 唯一连续性参考：不可变 E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P012_v03.png；未使用 P013 v01 或其他图像作为视觉参考。
- 候选与原始图 SHA-256 一致：0E40B9DBF309BA10D5DDC34805B03A0AF6AA5FE229166915E5B1093A523BFB21。
- 生成子代理说明：按主代理指令仅完成一次 ImageGen 调用与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 修订根因：STYLE-MODALITY-001 及附加朝向问题；强化 P001 v05 式真正火柴人导演草图、矩形/直线院落，并锁定 B064 三人共同转向及 B066 巢儿低头双手持信阅读。
- 针对性要求：B061–B063 保持既定语义状态；B064 苏轼、苏辙、巢儿的圆头与躯干同向转向石桌唯一信件/右侧苏洵；B065 苏洵指向唯一信；B066 巢儿头部和上身明确向下俯，双手持同一信在胸前阅读，其他人空手；全板无文字、符号、多手、多信。
- 完整 Prompt（原样）：

    Create exactly ONE complete black-and-white storyboard board for Panel P013, revision v02. Use the supplied immutable P012 v03 image as the ONLY visual reference, solely for the exact landscape canvas, 2×3 grid, bare courtyard geography, and panel continuity. Do not use any other image reference and do not copy detailed costume art from the reference. This must be one complete six-cell board, not six separate images.

    STRICT DIRECTOR BLOCKING SHEET MODALITY:
    Make it look like P001 v05's rough director blocking sheet: white paper, sparse black lines, true faceless stick figures made only from blank circular heads, single-line torsos, and simple line-segment arms and legs. Identify Su Xun, Su Shi, Su Zhe, and Chao'er only with minimal cap shape, tiny head/shoulder anchor, or clear height difference. Absolutely no closed long robes, sleeve curves, robe hems, garment silhouettes, cuffs, clothing folds, hair, facial features, anatomy, shading, texture, hatching, polished illustration, or realistic people. The courtyard uses only a rectangular gate frame, two or three straight eaves lines, a ground line, and one simple geometric stone table. No roof-tile repetition, architectural detail, decoration, wedding remnants, firecrackers, smoke, or extra props. Monochrome only.

    Keep exact landscape 16:9, exactly six equal cells in a 2 rows × 3 columns grid, thin black outer border and dividers, no title strip, no extra cells, no text. Do not crop, tile, splice, or rearrange.

    CONTINUITY AND SIX BEATS:
    1. TOP-LEFT B061, zero-duration anchor: the same clean empty courtyard months later, with no people and no wedding trace. Only bare rectangular gate/wall/eaves geometry, ordinary ground, and one clear geometric stone table centered in the yard.
    2. TOP-MIDDLE B062: keep the same bare courtyard. Su Xun enters from the rear-right gate, carrying one and only one small blank unreadable letter in one hand. Use a natural large step posture, with no motion lines or arrows. No other person and no other paper in this cell.
    3. TOP-RIGHT B063: keep the same courtyard and same Su Xun. The same single blank letter is now placed on the stone table; show only one of Su Xun's hands making the natural placing gesture. The table has exactly one blank letter. No second sheet and no other person holding paper.
    Cells 1–3 must retain these already-correct B061–B063 semantic states while using the strict stick-figure modality above.
    4. BOTTOM-LEFT B064: show Su Xun at the right side of the stone table and the three family members Su Shi, Su Zhe, and Chao'er nearby. At this one static instant, all three family members' blank circular heads AND single-line torsos are clearly rotated toward the one letter on the stone table and toward Su Xun on the right, visibly sharing the same turning orientation. The one blank letter remains on the table. Nobody holds a letter. Do not show a sequential turn, reaction marks, or duplicate paper.
    5. BOTTOM-MIDDLE B065: declaration viewpoint in the same bare courtyard. Su Xun faces the three listeners and points with one natural line arm toward the one blank letter on the stone table. The other arm is uninvolved and all three listeners are empty-handed. Keep four simple stick bodies, exactly two arms per body, with no extra hands, no reaction marks, no speech text, and no comic marks.
    6. BOTTOM-RIGHT B066: Chao'er clearly lowers both head and upper torso toward the one blank letter and begins reading. Chao'er holds that same single sheet at chest height with exactly two clearly attached hands, one from each arm. Su Xun, Su Shi, and Su Zhe remain present but hold nothing. Only one blank letter exists in the whole cell; no duplicate paper. The reading pose must be conveyed by the downward head and torso angle, not facial details or motion marks.

    LOGIC LOCKS:
    The same single blank letter travels from Su Xun's hand in B062, to the stone table in B063–B065, then to Chao'er's two hands in B066. Do not invent a second letter, extra table, extra gate, or unexplained prop. Keep identity, side of frame, and courtyard axis stable. Every paper surface is entirely blank and unreadable; no writing or pseudo-writing. “数月后” is post-production only and must not appear.

    ABSOLUTE NEGATIVES:
    No visible text, pseudo-text, letters or characters drawn on paper, numbers, labels, captions, subtitles, watermark, logo, UI, signature, speech bubbles, arrows, arcs, speed lines, motion trails, rays, sparkles, exclamation marks, question marks, comic symbols, reaction marks, decorative marks, closed robes, sleeve curves, robe hems, garment detail, roof tiles, wedding decoration, realistic architecture, photorealism, color, anime, manga, comic, or cinematic final art. Output only one complete rough 2×3 storyboard board.

### P013 v03

- 生成时间：2026-08-30 20:00:52 +08:00；原始生成图：C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-d49f37df-eb4b-4425-8164-c42254ad450e.png
- 原始图尺寸：1672×941，892,610 bytes，SHA-256 3C1D19095CA25BE900C587BF48227D465DF4FCE3D52F62AA4F5B4A172149982D。
- 候选归档：E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P013_v03.png；已复制归档，原始图保持不动，未覆盖正式 board_P013.png。
- 唯一连续性参考：不可变 E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P012_v03.png；未使用 P013 v02 或其他图像作为视觉参考。
- 候选与原始图 SHA-256 一致：3C1D19095CA25BE900C587BF48227D465DF4FCE3D52F62AA4F5B4A172149982D。
- 生成子代理说明：按主代理指令仅完成一次 ImageGen 调用与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 修订根因：BEAT-POSE-READABILITY-001；保持 v02 已通过的单线火柴人、极简院落、唯一信件和 B061–B063/B065，强化 B064 全身共同右向与 B066 明确低头阅读。
- 针对性要求：B064 苏轼、苏辙、巢儿的脚、骨盆线、单线躯干、肩线、颈部和圆头全部向画面右侧石桌/苏洵旋转，三人同时右倾；B066 巢儿从髋部向前下方约 30 度俯身，圆头低于肩线靠近胸前较低处唯一信件，双手持信，苏轼/苏辙/苏洵直立空手。
- 完整 Prompt（原样）：

    Create exactly ONE complete black-and-white storyboard board for Panel P013, revision v03. Use the supplied immutable P012 v03 board as the ONLY visual reference, solely for the exact landscape canvas, 2×3 grid, bare courtyard geography, and panel continuity. Do not use any other image reference. This is one complete six-cell board, not six separate images.

    STRICT DIRECTOR BLOCKING SHEET MODALITY:
    Use the rough minimal director blocking-sheet look of P001 v05: white paper, sparse black lines, true faceless stick figures built only from blank circular heads, single-line torsos, simple line-segment arms and legs. Identify Su Xun, Su Shi, Su Zhe, and Chao'er only by tiny cap/shoulder anchor or height difference. No closed long robes, sleeve curves, robe hems, garment silhouettes, cuffs, clothing folds, hair, facial features, anatomy detail, shading, texture, hatching, polished illustration, or realistic people. Courtyard is only a rectangular gate frame, two or three straight eaves lines, a ground line, and one simple geometric stone table. No roof-tile repetition, architectural detail, wedding remnants, ribbons, bows, lanterns, firecrackers, smoke, debris, or extra props. Monochrome only.

    Exact landscape 16:9, exactly six equal cells in a 2 rows × 3 columns grid, thin black outer border and dividers, no title strip, no extra cells, no text. Do not crop, tile, splice, or rearrange.

    CONTINUITY AND SIX BEATS:
    1. TOP-LEFT B061, zero-duration anchor: clean empty courtyard months later, with no person and no wedding trace. Only bare rectangular gate/wall/eaves geometry, ordinary ground, and one clear geometric stone table centered in the yard.
    2. TOP-MIDDLE B062: same bare courtyard. Su Xun enters from the rear-right gate, carrying one and only one small blank unreadable letter in one hand. Natural large step posture, no motion lines or arrows. No other person and no other paper.
    3. TOP-RIGHT B063: same courtyard and same Su Xun. The same single blank letter is placed on the stone table; show one hand making the placing gesture. The table contains exactly one blank letter; no second sheet and no other person holding paper.
    B061–B063 must keep these already-correct semantic states and the same courtyard axis.
    4. BOTTOM-LEFT B064, one static instant: Su Xun stands at the RIGHT side of the stone table. Su Shi, Su Zhe, and Chao'er stand together on the other side. Make the three listeners' pose unambiguous: each of their feet, pelvis/hip line, single-line torso, shoulder line, neck/head and circular head are all rotated toward the RIGHT side of the picture, toward the stone table and Su Xun. Their bodies are in clear side profile or 3/4 profile, simultaneously leaning slightly to the right. The head direction must agree with the torso and pelvis; do not leave any listener front-facing. Their three shared body orientations must visibly express one simultaneous turn toward the single letter/table and Su Xun. The one blank letter remains on the table. Nobody holds paper. No sequential-turn depiction, arrows, gaze lines, reaction marks, or duplicate paper.
    5. BOTTOM-MIDDLE B065: declaration viewpoint in the same bare courtyard. Su Xun faces the three listeners and points with one natural line arm toward the one blank letter on the stone table. The other arm is uninvolved. All three listeners are empty-handed. Exactly two arms per body, no extra hands, no speech text or comic marks. Keep the same axis and side positions.
    6. BOTTOM-RIGHT B066, pose readability is highest priority: Chao'er stands beside the stone table and begins reading the same unique blank letter. Her upper torso must hinge forward from the hip and angle down toward the front by approximately 30 degrees. Her blank circular head must be visibly lower than her shoulder line and close to the single letter held lower in front of her chest. Show both arms descending naturally from the shoulders and exactly two attached hands holding that one sheet. The paper is at a lower chest/upper-abdomen level, not held high. Su Xun, Su Shi, and Su Zhe remain nearby standing upright, with straight vertical torsos and empty hands, creating a clear upright-versus-low-reading contrast. Only one blank letter exists in the cell; no duplicate paper, no extra hands. Convey the reading pose only through hip bend, lowered head, and hand placement, never facial details or motion marks.

    LOGIC LOCKS:
    The same single blank letter travels from Su Xun's hand in B062, to the stone table in B063–B065, then to Chao'er's two hands in B066. Do not invent a second letter, extra table, extra gate, or unexplained prop. Keep identity, side of frame, and courtyard axis stable. Every paper surface is entirely blank and unreadable; no writing or pseudo-writing. “数月后” is post-production only and must not appear.

    ABSOLUTE NEGATIVES:
    No visible text, pseudo-text, letters or characters drawn on paper, numbers, labels, captions, subtitles, watermark, logo, UI, signature, speech bubbles, arrows, gaze lines, action lines, speed lines, motion trails, arcs, rays, sparkles, exclamation marks, question marks, comic symbols, reaction marks, decorative marks, closed robes, sleeve curves, robe hems, garment detail, roof tiles, wedding decoration, realistic architecture, photorealism, color, anime, manga, comic, or cinematic final art. Output only one complete rough 2×3 storyboard board.

### P013 v04

- 生成时间：2026-08-30 20:08:59 +08:00；原始生成图：C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-03eac931-8c23-4b2e-81f9-e73f2cc48305.png
- 原始图尺寸：1672×941，1,064,010 bytes，SHA-256 8B6D89234839DF7046B3EF9801710CA5385DE78767905EC7AFD1410AAB9B542A。
- 候选归档：E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P013_v04.png；已复制归档，原始图保持不动，未覆盖正式 board_P013.png。
- 唯一连续性参考：不可变 E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P012_v03.png；未使用 P013 v03 或其他图像作为视觉参考。
- 候选与原始图 SHA-256 一致：8B6D89234839DF7046B3EF9801710CA5385DE78767905EC7AFD1410AAB9B542A。
- 生成子代理说明：按主代理指令仅完成一次 ImageGen 调用与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 修订根因：CHARACTER-ANATOMY-001；强化每人单一圆头、单一躯干、两臂两腿及巢儿无附加圆形/重影/第二头。
- 针对性要求：保持 v03 已通过的极简风格、B061–B063、B064 三人共同右转、B065 指向唯一信件、B066 巢儿俯身低头读信；巢儿仅以更矮身高和短直线帽檐/肩宽区分，B066 双手持唯一信，其他人空手。
- 完整 Prompt（原样）：

    Create exactly ONE complete black-and-white storyboard board for Panel P013, revision v04. Use the supplied immutable P012 v03 board as the ONLY visual reference, solely for the exact landscape canvas, 2×3 grid, bare courtyard geography, and panel continuity. Do not use any other image reference. This is one complete six-cell board, not six separate images.

    STRICT DIRECTOR BLOCKING SHEET MODALITY:
    Use a rough minimal director blocking-sheet style like P001 v05: white paper, sparse black lines, true faceless stick figures made only from one blank circular head connected to one single-line torso, with simple line-segment arms and legs. Each person in every cell must have exactly one and only one circular head, visibly attached to that person's single torso. HIGHEST ANATOMY LOCK: absolutely no extra small circles, round buns, circular hats, double rings, halo circles, head duplicates, ghost heads, floating circles, detached circles, or second heads around any character. This applies especially to Chao'er: she is identified only by shorter height and one short straight cap-brim or shoulder line, never by a circular head ornament. Identify Su Xun, Su Shi, and Su Zhe only by height or a tiny straight cap/shoulder anchor, never circles or anatomy detail. Every person has exactly two arms and exactly two legs, all attached naturally; no extra hands or limbs.

    No closed long robes, sleeve curves, robe hems, garment silhouettes, cuffs, clothing folds, hair, facial features, anatomy detail, shading, texture, hatching, polished illustration, or realistic people. Courtyard uses only a rectangular gate frame, two or three straight eaves lines, a ground line, and one simple geometric stone table. No roof-tile repetition, architectural detail, wedding remnants, ribbons, bows, lanterns, firecrackers, smoke, debris, or extra props. Monochrome only.

    Exact landscape 16:9, exactly six equal cells in a 2 rows × 3 columns grid, thin black outer border and dividers, no title strip, no extra cells, no text. Do not crop, tile, splice, or rearrange.

    CONTINUITY AND SIX BEATS:
    1. TOP-LEFT B061, zero-duration anchor: clean empty courtyard months later, with no person and no wedding trace. Only bare rectangular gate/wall/eaves geometry, ordinary ground, and one clear geometric stone table centered in the yard.
    2. TOP-MIDDLE B062: same bare courtyard. Su Xun enters from the rear-right gate, carrying one and only one small blank unreadable letter in one hand. Natural large step posture, no motion lines or arrows. No other person and no other paper.
    3. TOP-RIGHT B063: same courtyard and same Su Xun. The same single blank letter is placed on the stone table; show one hand making the placing gesture. The table contains exactly one blank letter; no second sheet and no other person holding paper.
    B061–B063 must retain these already-correct semantic states and the same courtyard axis.

    4. BOTTOM-LEFT B064, one static instant: Su Xun stands at the RIGHT side of the stone table. Su Shi, Su Zhe, and Chao'er stand together on the other side. All four people must each have exactly one attached blank circular head, one single-line torso, two arms, and two legs. The three listeners' feet, pelvis/hip line, torso, shoulder line, neck/head, and their single circular heads are all rotated toward the RIGHT side of the picture, toward the stone table and Su Xun. Their bodies are clear side profile or 3/4 profile and lean slightly right at the same instant. The one blank letter remains on the table. Nobody holds paper. No extra circles around any head, no head doubles, no sequential-turn depiction, arrows, gaze lines, reaction marks, or duplicate paper.
    5. BOTTOM-MIDDLE B065: declaration viewpoint in the same bare courtyard. Su Xun faces the three listeners and points with one natural line arm toward the one blank letter on the stone table. His other arm is uninvolved. Every character has one head only, two arms and two legs; all three listeners are empty-handed. No extra hands, round attachments, speech text or comic marks.
    6. BOTTOM-RIGHT B066, pose and anatomy lock: Chao'er stands beside the stone table and begins reading the same unique blank letter. Chao'er has exactly one circular head attached to one torso, no extra small circle, bun, ring, shadow-head, floating circle, or head ornament. Her upper torso hinges forward from the hip and angles down by approximately 30 degrees; her single circular head is visibly lower than her shoulder line and close to the one blank letter held lower in front of her chest. Her two attached arms end in exactly two hands holding that one sheet. Su Xun, Su Shi, and Su Zhe remain nearby upright and empty-handed; each also has exactly one head, one torso, two arms and two legs. The upright-versus-low-reading contrast must be clear. Only one blank letter exists in this cell; no duplicate paper, no extra hands or limbs.

    LOGIC LOCKS:
    The same single blank letter travels from Su Xun's hand in B062, to the stone table in B063–B065, then to Chao'er's two hands in B066. Do not invent a second letter, extra table, extra gate, or unexplained prop. Keep identity, side of frame, and courtyard axis stable. Every paper surface is entirely blank and unreadable; no writing or pseudo-writing. “数月后” is post-production only and must not appear.

    ABSOLUTE NEGATIVES:
    No visible text, pseudo-text, letters or characters drawn on paper, numbers, labels, captions, subtitles, watermark, logo, UI, signature, speech bubbles, arrows, gaze lines, action lines, speed lines, motion trails, arcs, rays, sparkles, exclamation marks, question marks, comic symbols, reaction marks, decorative marks, extra circles, round buns, circular ornaments, double heads, head ghosts, floating circles, second heads, extra limbs, closed robes, sleeve curves, robe hems, garment detail, roof tiles, wedding decoration, realistic architecture, photorealism, color, anime, manga, comic, or cinematic final art. Output only one complete rough 2×3 storyboard board.

### P013 v05

- 生成时间：2026-08-30 20:14:14 +08:00；原始生成图：C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-497aa7fa-e38c-4a96-a98c-50582bdbb544.png
- 生成方式：一次完整画布 ImageGen 编辑；输入整板保持不变，禁止裁格、拼板或脚本修图。
- 原始图尺寸：1672×941，972,871 bytes，SHA-256 8D8EF0E0B57EDB7140FF11FF9AFD9B27EA0C79A801AD20A5CC8B9F05AD8B535A。
- 候选归档：E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P013_v05.png；已复制归档，原始图保持不动，未覆盖正式 board_P013.png。
- 唯一输入源：不可变 E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P013_v04.png；未引入其他视觉参考。
- 候选与原始图 SHA-256 一致：8D8EF0E0B57EDB7140FF11FF9AFD9B27EA0C79A801AD20A5CC8B9F05AD8B535A。
- 生成子代理说明：按主代理指令仅完成一次完整画布编辑与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 修订根因：CHARACTER-ANATOMY-001 连续失败；只改右下 B066，删除左侧多出的第五名完整直立火柴人，保留前三格至前五格及 B066 的三名直立空手人物、巢儿前俯低头双手持唯一信。
- 针对性编辑边界：B066 最终恰好四人——苏洵、苏轼、苏辙三名直立空手，巢儿一人从髋部前俯低头双手持唯一信；删除多余人物的头、躯干、四肢，零残肢、零鬼影、零填补人物；B061–B065 和整板边框/分隔线锁定。
- 完整编辑 Prompt（原样）：

    Edit this existing complete storyboard board in full-canvas mode. Output ONE complete board at the same landscape 16:9 canvas with the same exact 2×3 six-cell grid. Do not crop, tile, splice, paste, reassemble, redraw, resize, or rearrange the board. Preserve the outer border, all internal dividers, and the complete composition.

    HIGHEST PRIORITY: lock cells 1–5 completely. Preserve the top-left through bottom-middle cells B061–B065 exactly as supplied: same bare courtyard, B061 empty-yard anchor, B062 Su Xun with one blank letter, B063 the same single letter on the stone table, B064 the three listeners turned right toward Su Xun/table, and B065 Su Xun pointing to the single letter. Preserve their figures, poses, line weight, geometry, props, and panel boundaries. Do not edit, clean up, or reinterpret any part of cells 1–5.

    In the bottom-right sixth cell B066, preserve the already-correct minimal stick-figure style, the bare courtyard, the stone table, the three intended upright empty-handed people, and Chao'er's forward-bent low-reading pose with both hands holding the same single blank letter. ONLY remove the stray fifth full upright stick figure on the LEFT side of B066: it is the extra isolated upright figure in the left-side cluster between the two intended left listeners and the bent reader. Erase that extra person's entire one circular head, single-line torso, both arms, and both legs completely, with zero residual limb fragments, ghost head, duplicate torso, shadow, or fill-in person. Do not remove the two intended left listeners, do not remove the intended far-right upright Su Xun, and do not remove or alter Chao'er.

    After the edit, B066 must contain exactly four people and only four: three upright, empty-handed figures—Su Xun, Su Shi, and Su Zhe—and one Chao'er figure bent forward from the hip, head visibly lower than the shoulder line, holding the single blank letter at lower chest/upper-abdomen level with exactly two attached hands. No other person, head, torso, arm, leg, shadow-person, or ghost remains. Keep exactly one blank unreadable letter; no duplicate paper and no text. Keep the B066 border/divider unchanged.

    The full board remains a rough black-and-white director blocking sheet: faceless circular heads, single-line torsos, line-segment limbs, sparse rectangular gate/straight eaves/geometric stone table, no closed robes or architectural detail. No text, pseudo-text, numbers, captions, watermark, logo, arrows, action lines, motion trails, comic marks, decorative symbols, color, photorealism, or cinematic rendering. This is a precise full-board edit with only the specified B066 deletion.

### P013 v05 promotion

- 独立 QC 结论：PASS；按主控指令核验候选 SHA-256 8D8EF0E0B57EDB7140FF11FF9AFD9B27EA0C79A801AD20A5CC8B9F05AD8B535A 一致。
- 提升时间：2026-08-30 20:19:06 +08:00。
- 来源候选：E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P013_v05.png
- 正式板：E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P013.png
- 提升后正式板 SHA-256：8D8EF0E0B57EDB7140FF11FF9AFD9B27EA0C79A801AD20A5CC8B9F05AD8B535A；字节与候选一致。
- 提升前正式板：不存在；本次为首次正式板提升。

### P015 v01 promotion

- 独立 QC 结论：PASS（两名独立 QC 一致）；按主控指令核验候选 SHA-256 F99572DE365336EAABE166736159CD4B7C45EF3BE47F1A1F95483D06AE117268 一致。
- 提升时间：2026-08-30 21:11:16 +08:00。
- 来源候选：E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P015_v01.png
- 正式板：E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P015.png
- 提升后正式板 SHA-256：F99572DE365336EAABE166736159CD4B7C45EF3BE47F1A1F95483D06AE117268；字节与候选一致。
- 提升前正式板：不存在；本次为首次正式板提升。

### P015 v01

- 生成时间：2026-08-30 21:05:19 +08:00；原始生成图：C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-48f508d6-7037-468f-ad6f-40744f2b481f.png
- 原始图尺寸：1672×941，1,101,413 bytes，SHA-256 F99572DE365336EAABE166736159CD4B7C45EF3BE47F1A1F95483D06AE117268。
- 候选归档：E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P015_v01.png；已复制归档，原始图保持不动，未覆盖正式 board_P015.png。
- 唯一连续性参考：不可变 E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P014_v05.png；P014 v05 已提升为正式 board_P014.png。
- 候选与原始图 SHA-256 一致：F99572DE365336EAABE166736159CD4B7C45EF3BE47F1A1F95483D06AE117268。
- 生成子代理说明：按主代理指令仅完成一次 ImageGen 调用与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 针对性连续性要求：P015 含三个 Setup（C029、C030、C031）与两个明确硬切；C029 为 B071–B074 同一院落群像，C030 为 B075 夕阳院中苏轼独处，C031 为 B076 廊下程夫人与三名青年背影；全板四人/单头双臂双腿约束及唯一空白信保持。
- 完整 Prompt（原样）：

    Create exactly ONE complete black-and-white storyboard board for Panel P015, revision v01, using the supplied immutable P014 v05 board as the ONLY visual reference for the P014 B071 anchor, character silhouettes, bare courtyard geography, and rough 2×3 board language. This is a new complete six-cell board, not six separate images and not a local edit. Do not use any other visual reference.

    Preserve exact landscape 16:9, exactly six equal rectangular cells in 2 rows × 3 columns, thin black outer border and internal dividers, left-to-right reading order, no title strip or extra panels. Do not crop, tile, splice, paste, merge, or rearrange.

    DIRECTOR BLOCKING-SHEET STYLE:
    True minimal faceless stick figures: one blank circular head attached to one simple line torso, two simple line arms, two simple line legs, sparse black lines on white. Every person has exactly one head, one torso, two arms, and two legs; no extra heads, circles, ghost limbs, duplicate bodies, or accidental fifth person. Identify Su Xun, Su Shi, Su Zhe, Chao'er, and Cheng Furen only by height, tiny straight cap/shoulder anchor, or silhouette. Chao'er is shorter; Cheng Furen is an older, slightly smaller figure with a minimal straight shoulder anchor. No facial features, eyes, mouth, hair, closed robes, sleeve curves, robe hems, clothing folds, shading, texture, hatching, polished illustration, realistic people, or detailed architecture. Courtyard and corridor use only rectangular gate/wall frames, two or three straight eaves lines, simple ground, sparse corridor posts, one low geometric sunset disk, a few simple cloud bands, and no decorative objects. Monochrome only.

    GLOBAL CONTINUITY:
    P015 contains three setups and exactly two hard cuts, represented through clear changes of location/time/camera without any cut symbol or text:
    - C029: B071–B074, one same-day bare courtyard medium group setup, stable axis and relationships.
    - C030: B075, hard cut to an evening courtyard with a solo north-facing Su Shi.
    - C031: B076, hard cut to a corridor with Cheng Furen and three young people's backs.
    The only letter in the whole panel is the same blank unreadable letter from P014 B071. It may be held by Chao'er in C029; never write on it and never duplicate it. “数月后” is post-production only and must not appear.

    EXACT SIX-CELL BEATS:
    1. TOP-LEFT B071 / C029 zero-duration anchor: reproduce P014 v05 bottom-right B071 exactly as a four-person bare-courtyard state. Su Xun, Su Shi, and Su Zhe are upright and empty-handed; Chao'er holds the unique blank letter in her LEFT hand, with her RIGHT elbow bent and right finger pointing to her own one blank circular head/face/nose area. She has not yet spoken. Keep exactly four people and one blank letter.
    2. TOP-MIDDLE B072 / C029: immediately continue the same courtyard group setup. Chao'er maintains the self-reference relationship and clearly asks in place; do not replay or redraw the hand-raising process. Her head/torso face the family and her right-hand self-pointing state may remain held as a static conversational pose; no extra gesture stages, arrows, or speech text. Su Xun, Su Shi, and Su Zhe remain clearly present, empty-handed except Chao'er still holding the same one letter.
    3. TOP-RIGHT B073 / same C029: keep the same courtyard medium group axis and all four people. Su Shi uses exactly one arm from slightly behind/side to loosely and comfortably rest around Chao'er's shoulder/upper shoulder line, conveying an easy supportive embrace. It must not touch or constrict her throat, neck front, or airway and must not look rough or violent. Su Shi's other arm is down/uninvolved. Chao'er's LEFT hand still holds the same single blank letter; her RIGHT hand naturally drops down. No extra hands, no crowding, no duplicated letter.
    4. BOTTOM-LEFT B074 / same C029: keep the same medium group setup, camera side, axis, and readable four-person relationship. Chao'er and Su Zhe show relaxed smiling energy only through eased torsos and slightly lifted heads, without facial features or reaction lines. Su Shi remains close but not crowded and uses no aggressive hold. Su Xun looks across the three young people and makes one natural hand signal indicating preparation to pack; exactly one arm gestures, the other is uninvolved. Chao'er may continue holding the same single blank letter in her left hand; nobody else holds paper. All four figures are clearly visible.
    5. BOTTOM-MIDDLE B075 / C030: unmistakable hard cut to a different setup and time—an evening courtyard with no group. Only Su Shi appears, alone in back or 3/4 view, facing north and looking toward the horizon; no other person. Convey sunset with one low circular sun disk near the horizon and a few simplified horizontal cloud bands. Keep the figure faceless, with no eye or facial detail, and use only natural upright/quiet posture. No letter, no extra prop, no text, and no transition graphic.
    6. BOTTOM-RIGHT B076 / C031: unmistakable second hard cut to a corridor/veranda. Cheng Furen is in the foreground or side foreground and lightly covers her mouth with exactly one hand in a restrained suppressed cough; her other arm hangs down. She is not bleeding, falling, collapsing, or surrounded by cough marks. In the background/outer direction, exactly three young people's backs—Su Shi, Su Zhe, and Chao'er—face outward/north and do not turn their heads. Their backs and head directions clearly point away from Cheng Furen; none looks back. Su Xun must not appear in this trio or anywhere in B076. Keep exactly these four people total, no extra elder, no extra person, and no duplicate letter.

    SETUP AND CONTINUITY LOCKS:
    B071–B074 must read as one stable C029 courtyard group setup: no camera flip, no location change, and no re-staging as unrelated shots. B075 must visibly cut from the group to the solo evening C030 shot through the new sun/sky and the absence of the group. B076 must visibly cut from C030 to a corridor C031 through the new posts/roofed passage and Cheng Furen's cough; the three young backs remain oriented outward without turning. Do not mix Su Xun into B076 or the three young backs. Keep character counts and one-letter ownership exact in every cell.

    ABSOLUTE NEGATIVES:
    No visible text, pseudo-text, letters or characters written on paper, numbers, labels, captions, subtitles, watermark, logo, UI, signature, speech bubbles, cut symbols, arrows, gaze lines, action lines, speed lines, motion trails, arcs, rays, sparkles, exclamation marks, question marks, comic symbols, cough marks, decorative marks, extra circles, second heads, extra limbs, fifth person, duplicate letter, blood, collapse, violent choking, closed robes, sleeve curves, robe hems, roof-tile repetition, wedding decoration, realistic architecture, photorealism, color, anime, manga, comic, or cinematic final art. Output only one complete rough 2×3 storyboard board.

### P014 v01

- 生成时间：2026-08-30 20:21:25 +08:00；原始生成图：C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-c11595a3-0eed-49e3-b651-b1ba56629465.png
- 原始图尺寸：1672×941，1,038,233 bytes，SHA-256 8CA2F625128BB31205EFB7883DBDE5A5FB1D5C9C192C96CD61B79B7E65C687BD。
- 候选归档：E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P014_v01.png；已复制归档，原始图保持不动，未覆盖正式 board_P014.png。
- 唯一连续性参考：不可变 E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P013_v05.png；P013 v05 已提升为正式 board_P013.png。
- 候选与原始图 SHA-256 一致：8CA2F625128BB31205EFB7883DBDE5A5FB1D5C9C192C96CD61B79B7E65C687BD。
- 生成子代理说明：按主代理指令仅完成一次 ImageGen 调用与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 针对性连续性要求：左上零时长复现 P013 v05 右下 B066 的四人状态；B067–B071 保持苏洵、苏轼、苏辙、巢儿四人关系、唯一空白信及极简火柴人院落逻辑；B071 巢儿左手持信、右手指向自身唯一圆头。
- 完整 Prompt（原样）：

    Create exactly ONE complete black-and-white storyboard board for Panel P014, revision v01, using the supplied immutable P013 v05 board as the ONLY visual reference for canvas, 2×3 grid, bare courtyard geography, stick-figure modality, and character continuity. This is one complete six-cell board, not six separate images. Preserve exact landscape 16:9, exactly six equal rectangular cells in a 2 rows × 3 columns grid, thin black outer border and internal dividers, and left-to-right reading order. Do not crop, tile, splice, paste, merge, add a title strip, or create extra panels.

    Use a rough director's blocking sheet like P001 v05: white paper, sparse black lines, true faceless stick figures made from one blank circular head attached to one single-line torso and simple line-segment arms and legs. Every person in every cell must have exactly one head, one torso, two arms, and two legs; no extra heads, circles, ghost limbs, duplicate bodies, or fifth person. Identify Su Xun, Su Shi, Su Zhe, and Chao'er only through height, tiny straight cap/shoulder anchor, or body scale. Chao'er is the shorter figure and never has a circular head ornament. No facial features, hair, closed robes, sleeve curves, robe hems, clothing folds, anatomy detail, shading, texture, hatching, polished illustration, or realistic people. Courtyard uses only a rectangular gate frame, two or three straight eaves lines, ordinary ground, and one simple geometric stone table. No wedding decoration, ribbons, bows, lanterns, firecrackers, smoke, debris, roof-tile repetition, or architectural detail. Monochrome only.

    CONTINUITY LOCK:
    The top-left must be a zero-duration static reproduction of P013 v05 bottom-right B066: exactly four people in the same bare courtyard—Su Xun, Su Shi, and Su Zhe upright and empty-handed; Chao'er forward-bent from the hip with head low and both hands holding one unique blank unreadable letter near lower chest/upper abdomen. The same single blank letter must remain the only paper prop through the sequence until B071. No text or pseudo-text may appear on it.

    EXACT SIX-CELL BEATS:
    1. TOP-LEFT, B066 boundary: exact completed B066 state described above. Exactly four figures; Chao'er bent low reading, both hands on one blank letter; three others upright and empty-handed. This is a static anchor, not a new event.
    2. TOP-MIDDLE, B067: same four people and same bare courtyard. Chao'er remains standing beside the table with both hands holding the same single blank letter and completes a full reading posture. Keep her head lowered naturally; no text on paper, no extra paper.
    3. TOP-RIGHT, B068: Su Shi and Su Zhe respond with a restrained upward lift of their heads and upper torsos, showing quiet encouragement or renewed energy only through natural body posture. Chao'er still holds the same single blank letter with both hands. Su Xun and all other figures remain in the same scene; no reaction lines, arrows, symbols, or extra limbs.
    4. BOTTOM-LEFT, B069: same bare courtyard and four-person relationship. Su Xun looks across the three young people—Su Shi, Su Zhe, and Chao'er—and makes one decisive sweeping hand gesture with exactly one arm. His other arm is uninvolved. The three young people remain distinct, empty-handed except Chao'er still holding the same one blank letter with both hands. No motion lines or comic emphasis; show decisiveness only through the natural arm and torso pose.
    5. BOTTOM-MIDDLE, B070: Su Xun faces the three young people and announces that they will go to the capital, conveyed only through clear facing/gestural blocking: one hand raised or extended in a calm declarative pose, three young people facing him. Keep all four people and the same axis; Chao'er may continue to hold the same single blank letter, but no one else holds paper. No dialogue text, speech bubble, or pseudo-writing.
    6. BOTTOM-RIGHT, B071: Chao'er reacts with a restrained startle while remaining one person with one head and one torso. Her LEFT hand continues to hold the same single blank letter; her RIGHT arm bends naturally so the right hand points toward the center of her own one blank circular head/face, clearly expressing “me?” without text, facial features, question marks, or comic marks. The other three—Su Xun, Su Shi, Su Zhe—remain present and empty-handed. Keep exactly four people, exactly one paper, exactly two hands on Chao'er total (left holding paper, right pointing), no extra hands or heads.

    LOGIC AND ANATOMY LOCKS:
    P014 starts from the exact P013 v05 B066 state. The unique blank letter stays with Chao'er from the reading beats through B071; never duplicate it or place another sheet on the table. Every full figure has one attached circular head, one torso, two arms, and two legs. No extra small circles, round buns, circular hats, head doubles, floating circles, ghost limbs, detached limbs, or fifth character in any cell. “数月后” is post-production only and must not appear.

    ABSOLUTE NEGATIVES:
    No visible text, pseudo-text, letters or characters written on paper, numbers, labels, captions, subtitles, watermark, logo, UI, signature, speech bubbles, arrows, gaze lines, action lines, speed lines, motion trails, arcs, rays, sparkles, exclamation marks, question marks, comic symbols, reaction marks, decorative marks, extra circles, second heads, extra limbs, closed robes, sleeve curves, robe hems, roof tiles, wedding decoration, realistic architecture, photorealism, color, anime, manga, comic, or cinematic final art. Output only one complete rough 2×3 storyboard board.

### P014 v02

- 生成时间：2026-08-30 20:30:02 +08:00；原始生成图：C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-b509af1b-ccb6-4cd7-a4b6-3a7b218dccd2.png
- 生成方式：一次完整画布 ImageGen 编辑；输入整板保持不变，禁止裁格、拼板或脚本修图。
- 原始图尺寸：1672×941，1,179,618 bytes，SHA-256 B7CD700709E4C294C6078BC54E4A30AB40D1EA45402BF933D44F95A5DABC6B3A。
- 候选归档：E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P014_v02.png；已复制归档，原始图保持不动，未覆盖正式 board_P014.png。
- 唯一输入源：已独立 QC 通过的不可变 E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P014_v01.png；未引入其他视觉参考。
- 候选与原始图 SHA-256 一致：B7CD700709E4C294C6078BC54E4A30AB40D1EA45402BF933D44F95A5DABC6B3A。
- 生成子代理说明：按主代理指令仅完成一次完整画布编辑与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 修订根因：BEAT-POSE-READABILITY-001；锁定 B066–B070 和四人/唯一空白信，只强化 B071 巢儿右手指向自身圆头中央的动作链。
- 针对性编辑边界：B071 巢儿左臂向下/向外持唯一空白信；右上臂抬至肩高、右肘明确弯曲、右前臂斜向自身圆头，右手一根简化指线末端接触圆头正中央（鼻子位置），与胸口留可见空隙；苏洵、苏轼、苏辙空手看她；每人一个头、两臂两腿，无漫画线箭头。
- 完整编辑 Prompt（原样）：

    Edit this existing complete storyboard board in full-canvas mode and output ONE complete board at the exact same landscape 16:9 canvas, exact 2×3 six-cell grid, outer border, and internal dividers. Do not crop, tile, splice, paste, reassemble, resize, or rearrange. Use the supplied P014 v01 board as the sole source.

    HIGHEST PRIORITY: lock the first five cells completely. Preserve top-left through bottom-middle B066, B067, B068, B069, and B070 exactly as supplied, including all four people, their poses, the bare courtyard, line weight, stone table, single blank letter, and panel boundaries. Do not alter, redraw, clean up, or reinterpret any part of those five cells.

    ONLY EDIT the bottom-right sixth cell B071 to make the “me?” pose physically unmistakable. Keep the same bare courtyard and exactly four people: Su Xun, Su Shi, and Su Zhe remain upright and empty-handed; Chao'er remains one person with one blank circular head, one torso, two arms, and two legs. Keep exactly one blank unreadable letter.

    B071 POSE LOCK — highest priority:
    Chao'er's LEFT arm must extend clearly downward and slightly outward to hold the same single blank letter at lower chest/waist level. Her RIGHT upper arm must be visibly raised to about shoulder height, with a clearly defined right elbow bent. Her right forearm must run diagonally inward and upward toward her own one blank circular head. The simplified single right index-finger line must have its endpoint visibly touching the exact center of her circular head/face at the nose position. There must be a clearly visible white gap between her right hand/forearm and her chest and neck; the hand must not stop at the chest, shoulder, collar, or side of the neck. The contact is head-center contact only. Do not add a face, nose mark, text, question mark, arrow, or comic reaction. The other three people look toward Chao'er and remain empty-handed. No fifth person, duplicate head, ghost limb, or extra hand.

    Keep the same rough black-and-white director blocking-sheet modality: one blank circular head per person, simple line torso, line-segment limbs, minimal geometric courtyard, no closed robes or architectural detail. Preserve the B071 cell border and all unchanged cells. No text, pseudo-text, symbols, arrows, action lines, motion lines, decorative marks, color, photorealism, or cinematic rendering. This is a precise full-board edit with only the specified B071 pose adjustment.

### P014 v03

- 生成时间：2026-08-30 20:36:43 +08:00；原始生成图：C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-b053cfb5-7f40-46fa-989a-a81ecf3b1a62.png
- 生成方式：一次完整画布 ImageGen 编辑；输入整板保持不变，禁止裁格、拼板或脚本修图。
- 原始图尺寸：1672×941，1,183,007 bytes，SHA-256 A830231DAD533E52F78B95AC993A502C16708897504EFEB27CA1A4899265E98A。
- 候选归档：E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P014_v03.png；已复制归档，原始图保持不动，未覆盖正式 board_P014.png。
- 唯一输入源：失败候选 E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P014_v02.png（P014 v02 QC 结论：FAIL）；本次仅将其作为完整画布编辑输入，未引入其他视觉参考。
- 候选与原始图 SHA-256 一致：A830231DAD533E52F78B95AC993A502C16708897504EFEB27CA1A4899265E98A。
- 生成子代理说明：按主代理指令仅完成一次完整画布编辑与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 修订根因：BEAT-POSE-READABILITY-001 连续失败；锁定 B066–B070 以及 B071 除右指尖外的全部状态，仅把右手食指线从圆头左缘延伸至圆头几何中心。
- 针对性编辑边界：B071 巢儿左手继续持唯一空白信；右上臂抬肘弯曲，右前臂斜向自身圆头，食指线穿过圆头轮廓少量距离并将端点落在圆头中心/鼻子位置；指线与胸口保持空隙；不新增手、人物、圆点、箭头或漫画线。
- 完整编辑 Prompt（原样）：

    Edit this existing complete storyboard board in full-canvas mode and output ONE complete board at the exact same landscape 16:9 canvas, exact 2×3 six-cell grid, outer border, and internal dividers. Do not crop, tile, splice, paste, reassemble, resize, or rearrange. Use the supplied P014 v02 board as the sole input source.

    HIGHEST PRIORITY: lock the first five cells completely. Preserve B066, B067, B068, B069, and B070 in the top-left through bottom-middle cells exactly as supplied, including all four people, poses, bare courtyard, stone table, single blank letter, line weight, borders, and dividers. Do not alter, clean up, or reinterpret any of those five cells.

    ONLY edit the bottom-right B071 cell. Preserve B071's exact four-person arrangement, bare courtyard, three upright empty-handed figures, Chao'er as one bent/standing figure, and one single blank unreadable letter. Preserve Chao'er's left hand holding that unique letter and her right upper arm already raised with a clear elbow bend.

    The sole B071 change: extend Chao'er's existing RIGHT index-finger line from its current endpoint at the left edge of her blank circular head, continuing it slightly rightward through the circular head outline by a small amount, so the fingertip endpoint is clearly located at the geometric center of the blank circular head/face, the nose position. The finger endpoint must visibly land in the center, not remain on the rim or side. Keep the right forearm diagonal toward the head and keep a clearly visible white gap between the right forearm/hand and Chao'er's chest and neck. Do not move the hand to the chest, shoulder, collar, or neck. This is one existing finger line extending to the head center only.

    Do not add a hand, finger beyond this one simplified line, person, head, circle, arrow, gaze line, question mark, comic mark, ghost limb, or duplicate letter. Keep exactly four people: Su Xun, Su Shi, Su Zhe upright and empty-handed, and Chao'er with left hand holding the single letter and right fingertip touching the center of her only circular head. Keep every person's anatomy simple: one head, one torso, two arms, two legs. Keep the B071 border and all other cells unchanged.

    The complete board remains a rough black-and-white director blocking sheet with sparse geometry, no text or pseudo-text, no realistic art, no color, no captions, no symbols, no motion lines, no arrows, and no decorative marks. This is a precise full-board edit with only the specified B071 fingertip extension.

### P014 v04

- 生成时间：2026-08-30 20:49:41 +08:00；原始生成图：C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-a3bd1bc4-edec-4f57-b9c6-e71ab75c4ccb.png
- 原始图尺寸：1672×941，1,046,634 bytes，SHA-256 3625CEB303508194FF0ACE77618E86D1A4F02F051A7B82DC499F6FD7438C72DF。
- 候选归档：E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P014_v04.png；已复制归档，原始图保持不动，未覆盖正式 board_P014.png。
- 唯一连续性参考：不可变 E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P013_v05.png；未使用 P014 v01–v03 作为整板视觉参考。
- 候选与原始图 SHA-256 一致：3625CEB303508194FF0ACE77618E86D1A4F02F051A7B82DC499F6FD7438C72DF。
- 生成子代理说明：按主代理指令仅完成一次全新整板 ImageGen 调用与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 修订根因：SHOT-BEAT-DIFFERENTIATION-001；以 P013 v05 为唯一上一板参考，从头生成完整 P014，区分 C027 medium close-up 与 C028 medium group shot。
- 针对性要求：B066 左上复现 P013 v05 右下四人状态；B067/B068 保持同一巢儿主导的正侧面 medium close-up，后景小人物只以姿态变化表现振奋；B069–B071 保持同一 medium group shot，四人关系稳定，B071 巢儿左手持信、右肘弯曲、右指指向脸/鼻部区域。
- 完整 Prompt（原样）：

    Create exactly ONE complete black-and-white storyboard board for Panel P014, revision v04, using the supplied immutable P013 v05 board as the ONLY visual reference for the P013 B066 anchor, bare courtyard geography, character silhouettes, line weight, and 2×3 board language. Do not use P014 v01, v02, or v03 as any visual reference. This is a new complete six-cell board, not six separate images and not a local edit.

    Preserve an exact landscape 16:9 canvas with exactly six equal rectangular cells in 2 rows × 3 columns, thin black outer border and internal dividers, left-to-right reading order, no title strip and no extra panels. Do not crop, tile, splice, paste, merge, or rearrange.

    DIRECTOR BLOCKING-SHEET STYLE:
    Use true minimal faceless stick figures: one blank circular head attached to one simple line torso, line-segment arms and legs, sparse black lines on white. Every person in every cell has exactly one head, one torso, two arms, and two legs. No extra heads, circles, ghost limbs, duplicate bodies, or fifth person. Identify Su Xun, Su Shi, Su Zhe, and Chao'er only by height, a tiny straight cap/shoulder anchor, or body scale. Chao'er is shorter and has no circular head ornament. No facial features, hair, closed robes, sleeve curves, robe hems, clothing folds, shading, texture, hatching, polished illustration, realistic people, or architectural detail. Courtyard uses only a rectangular gate frame, two or three straight eaves lines, a ground line, and one simple geometric stone table. No wedding decorations, ribbons, bows, lanterns, firecrackers, smoke, debris, roof-tile repetition, or extra props. Monochrome only.

    GLOBAL PROP/CHARACTER LOCK:
    There are exactly four characters throughout P014: Su Xun, Su Shi, Su Zhe, and Chao'er. There is exactly one small blank unreadable letter, never any writing or pseudo-writing. The letter starts in Chao'er's two hands at the B066 anchor and remains the same single letter in her hands through B070; in B071 her left hand still holds it while her right hand gestures. Nobody else holds paper. The phrase “数月后” is post-production only and must not appear.

    SHOT-BEAT DIFFERENTIATION AND EXACT CELLS:
    1. TOP-LEFT B066, zero-duration boundary from P013 v05: reproduce the P013 v05 bottom-right state as a four-person bare-courtyard anchor. Chao'er is forward-bent from the hip, head lower than shoulder line, both hands holding the one blank letter near lower chest/upper abdomen; Su Xun, Su Shi, and Su Zhe are upright and empty-handed. Keep the four-person relation and courtyard axis. This is a static anchor, not a new wide shot.
    2. TOP-MIDDLE B067 / C027: hard cut to a clearly different shot—a medium close-up in strict side profile of Chao'er as the dominant foreground subject. Chao'er occupies most of the cell height and width, with her single head and torso clearly readable; she keeps her head lowered and both hands hold the same one blank letter as she completes a full reading. Su Shi and Su Zhe appear only as much smaller figures in the rear background; Su Xun is only a small partial figure at the far edge/rear background. This is not a repeated wide group shot. Keep the same courtyard axis but use the close camera scale and side-facing composition.
    3. TOP-RIGHT B068 / same C027 shot: use exactly the same medium-close-up camera position, side profile, scale, foreground placement, and composition as B067—not a new wide shot and not a duplicate static frame. Chao'er remains the dominant foreground figure and continues holding the same single letter with both hands. In the small background, Su Shi and Su Zhe now clearly lift their heads and tilt/straighten their upper torsos toward Chao'er to show renewed energy; Su Xun remains at the edge/rear. Show the change only through natural posture, with no action lines, reaction marks, or symbols.
    4. BOTTOM-LEFT B069 / C028: clear cut back to a medium group shot in the same bare courtyard, showing all four characters at a readable shared scale. Su Xun faces the three young people—Su Shi, Su Zhe, and Chao'er—and makes one decisive hand-sweeping gesture with exactly one arm. Chao'er continues to hold the same single blank letter with both hands; Su Shi and Su Zhe are empty-handed. Use the group framing to clearly show the family relationship; no close-up composition.
    5. BOTTOM-MIDDLE B070 / same C028: keep exactly the same medium group-shot camera position, scale, axis, and four-person arrangement as B069. Su Xun completes the calm declaration that they will go to the capital, conveyed only by facing and one clear raised/extended hand; the three young people face him. Chao'er still holds the same one blank letter; the other two young men are empty-handed. No new camera scale, no extra person, and no speech text.
    6. BOTTOM-RIGHT B071 / same C028: keep the same medium group-shot camera position, scale, axis, and four-person arrangement as B069–B070. Chao'er holds the same single blank letter in her LEFT hand. Her RIGHT elbow is raised and clearly bent; her right forearm points inward and her simplified right finger points clearly toward her own face/nose area on her one blank circular head, semantically expressing “me?” without needing mathematical center contact. Her right hand must not point to her chest or neck. Su Xun, Su Shi, and Su Zhe remain empty-handed and look toward Chao'er. Exactly four people, exactly one letter, exactly one head per person.

    CONTINUITY CHECKS TO EMBODY:
    B066 establishes four figures and the letter in Chao'er's hands. B067/B068 are the same C027 close-up with Chao'er dominant foreground and the younger men small behind. B069/B070/B071 are the same C028 medium group-shot family arrangement. Keep shot size, side positions, and axis stable within each setup while making the C027-to-C028 cut unmistakable. Do not turn B067/B068 into repeated wide group compositions.

    ABSOLUTE NEGATIVES:
    No visible text, pseudo-text, letters or characters written on the paper, numbers, labels, captions, subtitles, watermark, logo, UI, signature, speech bubbles, arrows, gaze lines, action lines, speed lines, motion trails, arcs, rays, sparkles, exclamation marks, question marks, comic symbols, reaction marks, decorative marks, extra circles, second heads, extra limbs, fifth person, duplicate letter, closed robes, sleeve curves, robe hems, roof tiles, wedding decoration, realistic architecture, photorealism, color, anime, manga, comic, or cinematic final art. Output only one complete rough 2×3 storyboard board.

### P014 v05

- 生成时间：2026-08-30 20:57:29 +08:00；原始生成图：C:\Users\Administrator\.codex\generated_images\01a05175-708d-78d2-9938-4f6510d6d655\exec-4991af46-83cb-4482-8341-46fd591a2199.png
- 生成方式：一次完整画布 ImageGen 编辑；输入整板保持不变，禁止裁格、拼板或脚本修图。
- 原始图尺寸：1672×941，1,048,065 bytes，SHA-256 1F8C891EE89733F66FD578B5AF71B49F4C3BD770B2F3D9B671BF741DCB10F3A7。
- 候选归档：E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P014_v05.png；已复制归档，原始图保持不动，未覆盖正式 board_P014.png。
- 唯一输入源：不可变失败候选 E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P014_v04.png；本次仅作为完整画布编辑输入，未引入其他视觉参考。
- 候选与原始图 SHA-256 一致：1F8C891EE89733F66FD578B5AF71B49F4C3BD770B2F3D9B671BF741DCB10F3A7。
- 生成子代理说明：按主代理指令仅完成一次完整画布编辑与归档；本条不包含候选视觉 PASS/FAIL 判定，等待主代理独立 QC。
- 修订根因：SHOT-BEAT-DIFFERENTIATION-001；锁定 B066、B067、B069、B070、B071 及 B068 巢儿/苏洵状态，只增强 B068 后景苏轼、苏辙的同步可读反应。
- 针对性编辑边界：B068 保持与 B067 同一 C027 medium close-up 机位、轴线、尺度、前景巢儿和后景苏洵；仅使后景苏轼、苏辙两人明显抬头、躯干向巢儿前倾约 20 度、肩线/脚向巢儿旋转；可一人自然抬手至胸前但不新增肢体或漫画线。
- 完整编辑 Prompt（原样）：

    Edit this existing complete storyboard board in full-canvas mode and output ONE complete board at the exact same landscape 16:9 canvas, exact 2×3 six-cell grid, outer border, and internal dividers. Do not crop, tile, splice, paste, reassemble, resize, or rearrange the board. Use P014 v04 as the sole input image.

    HIGHEST PRIORITY: lock cells 1, 2, 4, 5, and 6 completely. Preserve B066 (top-left), B067 (top-middle), B069 (bottom-left), B070 (bottom-middle), and B071 (bottom-right) exactly as supplied, including their four people, one blank letter, poses, bare courtyard, line weight, shot framing, borders, and dividers. Do not alter, redraw, or reinterpret those five cells.

    In the top-right third cell B068 only, preserve the same C027 medium close-up as B067: same camera position, same side axis, same scale, same foreground/background composition, same dominant Chao'er position and the same framing. Chao'er must remain the large foreground figure, head and torso in the same position, still holding the single blank letter with both hands; do not change her pose, hands, letter, or size. Preserve Su Xun's small rear/edge background figure and do not change him.

    ONLY change the two rear-background figures representing Su Shi and Su Zhe. Their change must be visually obvious, not a tiny pixel shift: both of their blank circular heads rise clearly upward, both single-line torsos tilt or lean forward toward foreground Chao'er by approximately 20 degrees, and both shoulder lines and feet rotate toward Chao'er. The two figures must visibly look more energized and attentive through this synchronized natural posture. Keep them small in the rear background and keep the same camera scale; do not turn the cell into a wide group shot. One of the two may raise one natural hand to chest height, but never add a limb or duplicate hand. All three rear figures remain distinct and anatomically simple.

    After the edit B068 must still contain exactly four people total: one large foreground Chao'er with exactly one head, one torso, two arms, two legs, and both hands on exactly one blank unreadable letter; three small background figures, including unchanged Su Xun and the two clearly lifted/leaning Su Shi and Su Zhe. No additional person, head, hand, limb, letter, circle, reaction mark, or shadow-person. No arrows or comic lines. Preserve B068's cell border and the complete rest of the board byte-for-byte in intent.

    Maintain the rough monochrome director blocking-sheet style: blank circular heads, single-line torsos, line-segment limbs, sparse straight courtyard geometry, no closed robes, no texture, no realistic art. No text, pseudo-text, symbols, motion lines, arrows, decorative marks, color, or photorealism. This is a precise full-board edit with only B068 rear-figure pose adjustment.

### P014 v05 promotion

- 独立 QC 结论：PASS（两名独立 QC 一致）；按主控指令核验候选 SHA-256 1F8C891EE89733F66FD578B5AF71B49F4C3BD770B2F3D9B671BF741DCB10F3A7 一致。
- 提升时间：2026-08-30 21:02:42 +08:00。
- 来源候选：E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\candidates\board_P014_v05.png
- 正式板：E:\ideaProjects\zero-to-story\.short-drama\一蓑烟雨\zts\chapter_03\assets\boards\board_P014.png
- 提升后正式板 SHA-256：1F8C891EE89733F66FD578B5AF71B49F4C3BD770B2F3D9B671BF741DCB10F3A7；字节与候选一致。
- 提升前正式板：不存在；本次为首次正式板提升。
```
