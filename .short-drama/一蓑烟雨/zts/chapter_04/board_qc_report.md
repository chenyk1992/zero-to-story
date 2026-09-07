# STEP 3 既有黑白分镜板 QC 与资产路由报告

## 结论

- 项目：一蓑烟雨 / 第四章·出川
- 历史 QC 范围：P001–P020，共 20 张完整 2×3 黑白分镜板
- 当前资产路由：只有 P001/P005/P012/P015 四张板作为 R2V `runtime_input`；其余 16 张板为 `planning_only`
- 当前 STEP 3 状态：四张必需板与 P018/P020 两张 FL2V 目标尾帧均通过内部 QC，用户已确认并进入 STEP 4
- STEP 4：尚未进入；未生成 H3 提示词、Prompt Manifest 或 LFO 执行包

20 张正式板均通过当时的 `G/S/T/M/B/P` 技术与目视门禁；P002–P020 的左上边界锚点均已按上一板右下末态复核。该结论只证明既有文件可用，不代表它们全部应作为视频模型参考。正式板与对应通过候选逐字节一致，失败候选和超时/预检记录均保留。

## 运行时用途分类

| 分类 | 资产 | 规则 |
|---|---|---|
| R2V `runtime_input` | `board.P001`、`board.P005`、`board.P012`、`board.P015` | 可按蓝图槽位交给 H3/LFO |
| `planning_only` | 其余 16 张 `board.Pxxx` | 只供导演审阅和历史追溯，不进入 H3/LFO |
| 已生成待确认 FL2V 尾帧 | `keyframe.P018.last`、`keyframe.P020.last` | 与各自上一 Clip 真实尾帧成对，不附加分镜板；单帧文件记录见下表 |

## 单帧尾帧 QC

| Asset key | 文件 | 尺寸 / 像素 | SHA-256 | 目视结论 |
|---|---|---|---|---|
| `keyframe.P018.last` | `assets/keyframes/keyframe_P018_last_v01.png` | 941×1672 / rgb24 | `7008AF1EC595F5091B7D4939D4C6450B53E8186BE28F29E3BF5AB13703CFDCC3` | PASS：空堂只留兄弟；左右角色、两盏桌灯、空纸、苏轼右手悬笔明确；单画面无文字/网格 |
| `keyframe.P020.last` | `assets/keyframes/keyframe_P020_last_v01.png` | 941×1672 / rgb24 | `ACC74F1B7BD3B0BCDC82EC382F7A75E071B8692402823C9CFEAF707AC5ABFB8D` | PASS：苏轼左灯亮、苏辙右灯熄灭；左灯投出长影与悬笔意象；无鼓点图形、淡出或文字 |

## 正式板完整性

- 正式板数量：20/20，缺失：0
- 网格：每张均为一张完整画布、2 行 × 3 列、六格等大；未使用裁切、拼接或六张单图替代
- 颜色：正式文件均为 `rgb24` 的黑/白/中性灰分镜线稿；未见彩色、文字、伪文字、水印或声音符号
- 尺寸：P001–P016 为 1672×941；P017–P020 为 1672×940（均保持约 16:9 完整画布，未后处理拉伸或裁切）
- 正式板与通过候选字节一致：20/20
- 正式板 SHA-256 重复：0

## 正式板与通过候选

| Panel | 正式板（相对本章目录） | 通过候选 | 尺寸 | SHA-256 | 尝试 / 重试 |
|---|---|---|---|---|---:|
| P001 | `assets/boards/board_P001.png` | `candidates/board_P001_v05.png` | 1672×941 | `CFBA12DAD8AD10428E90D106BD897BF040FBAC8E99ABC339AA02911A7211A155` | 5 / 4 |
| P002 | `assets/boards/board_P002.png` | `candidates/board_P002_v01.png` | 1672×941 | `50BBD15962797D00F4E145C8CE45ED58EAD43B7DBF9F41DB05B8A2E3B946DEE7` | 1 / 0 |
| P003 | `assets/boards/board_P003.png` | `candidates/board_P003_v01.png` | 1672×941 | `182A7A9A8284E7A7F5187429105F6C080CAAA6BC3B47A6D20430E04BF8558294` | 1 / 0 |
| P004 | `assets/boards/board_P004.png` | `candidates/board_P004_v03.png` | 1672×941 | `72C7C49F29F1209AD5D3E830A61C4787936C7AB232490138BB93FA781D59030B` | 3 / 2 |
| P005 | `assets/boards/board_P005.png` | `candidates/board_P005_v02.png` | 1672×941 | `D406FC198DCD3D24EE5B80F3F2E10912FA08DB754AD72A1ABE1014C41B485209` | 2 / 1 |
| P006 | `assets/boards/board_P006.png` | `candidates/board_P006_v02.png` | 1672×941 | `E9187103CA705C337AE6806758F1AD08E2EA36D77696F39730D0DAB5CECB6729` | 2 / 1 |
| P007 | `assets/boards/board_P007.png` | `candidates/board_P007_v01.png` | 1672×941 | `758BCE3546B29C7697974CCB66D9A98F41D1E44855D7934857E6D90B9B7A0428` | 1 / 0 |
| P008 | `assets/boards/board_P008.png` | `candidates/board_P008_v01.png` | 1672×941 | `5AD23715E6DE6E2F3A2871D8575259B81D29A75AFD5B280E7CB216FF827CBDFC` | 1 / 0* |
| P009 | `assets/boards/board_P009.png` | `candidates/board_P009_v01.png` | 1672×941 | `8AAE7A29CBD476E85BFFFF9B5F4DF496EEEF21A71C720EC11BDE15CFAF190E58` | 1 / 0 |
| P010 | `assets/boards/board_P010.png` | `candidates/board_P010_v01.png` | 1672×941 | `725D6F87216FF63AB988C3983CF1B0B9606AEAB39E2E7041E3AB850F146D45D7` | 1 / 0 |
| P011 | `assets/boards/board_P011.png` | `candidates/board_P011_v01.png` | 1672×941 | `C1905725637A04EF8A3175A4F8C63A675A2BE7C2187EB9665C63CA9BA3B1D5F5` | 1 / 0 |
| P012 | `assets/boards/board_P012.png` | `candidates/board_P012_v01.png` | 1672×941 | `6B388DBAD265596FFF77BC1C7A797D07C14258D65EBBEF5C005735C35D90D728` | 1 / 0* |
| P013 | `assets/boards/board_P013.png` | `candidates/board_P013_v01.png` | 1672×941 | `F7F5F3BA63C385C898A4827B9D7885A8B4362AC16B825E182C9341DE962C926F` | 1 / 0 |
| P014 | `assets/boards/board_P014.png` | `candidates/board_P014_v01.png` | 1672×941 | `80AACE830D6F66562D9E8C57FCE176F07BEFCCAAA5F354983570F568A28A647E` | 1 / 0 |
| P015 | `assets/boards/board_P015.png` | `candidates/board_P015_v02.png` | 1672×941 | `A976E1449C7B28419C907CCB3E7AB4EC31EEF3721C383C7262AEF493D26D0806` | 2 / 1** |
| P016 | `assets/boards/board_P016.png` | `candidates/board_P016_v03.png` | 1672×941 | `897029BCBF1125C6563091B0E6A794A52989924103772BB7282A68E7DB55B461` | 3 / 2** |
| P017 | `assets/boards/board_P017.png` | `candidates/board_P017_v01.png` | 1672×940 | `A32A4F6DF3DE3EFD6058076F7F58179B3E618BC54248CC9E94AE26250D433F1D` | 1 / 0* |
| P018 | `assets/boards/board_P018.png` | `candidates/board_P018_v03.png` | 1672×940 | `437BA50BCBB775EB7D743B180344780DD7D999781EAA1B1062B1EE09914D0B2A` | 3 / 2 |
| P019 | `assets/boards/board_P019.png` | `candidates/board_P019_v03.png` | 1672×940 | `B709D7D08D5401BFAAA221249E12FCCF331B675CE0FE102FB8D4FB8FBD1315BE` | 3 / 2** |
| P020 | `assets/boards/board_P020.png` | `candidates/board_P020_v01.png` | 1672×940 | `F619A692BDD03EEB6D8E39CC8D0D9D522998DC7FED9908F8FFDBC3C7A9956B58` | 1 / 0 |

`*` 该 Panel 另有一次调用因等待过久或路径预检失败而没有生成文件；无空候选被计入版本号。  
`**` 该 Panel 的早期超时任务没有文件；候选版本号只对应实际归档的图像。

## 目视 QC 摘要

| 范围 | 结果 |
|---|---|
| P001–P004 | 山道到驿站的父子四人轴线、脚伤、扁担/书箱和饭桌关系连贯；P001 v05、P004 v03 解决风格与人物数量问题。 |
| P005–P011 | 驿站吃饭、伙计退场、父亲转郑重、苏辙追问到四人沉静；饭碗、桌位、两盏灯和空白纸笔无文字。 |
| P012–P014 | 城门日景硬切、城内纵深、巢儿左/苏轼右并肩、唯一引荐信取出并回怀；城门招牌均为空白。 |
| P015–P017 | 夜客栈硬切、兄弟左前与举子甲乙右后稳定；慎言后苏轼转向苏辙，再由苏辙低头收笔墨。 |
| P018–P020 | 满座到深夜空场时间切；两灯入场、笔悬空、兄弟相向；P020 右灯熄灭、左灯与悬笔影保留，更鼓不画入板面。 |

## 用户确认闸门

历史上曾按用户“依次生成全部”指令完成 P001–P020 并进行板级内部 QC；本次用户已确认改用选择性资产路由，因此不再要求逐张确认全部 20 张板。用户已通过“进入 STEP4”确认四张 R2V 必需板、新生成的 P018/P020 目标尾帧及其资产用途；`planning_only` 板不传入 `$h3-prompt-writing`、H3 或 LFO。当前 H3 提示词与 manifest 已生成，尚未创建或执行 LFO 执行包。
