# 来源与适配范围

技能：news-explainer-video · 版本1.3.1 · 整合日期2026-10-21。

## 用户提供的材料

`article-video-studio-0.3.1.zip`，SHA-256：`92701f58930dbfe204d2242bc6c9cff3fc4ef3a065557bd7dad7c113c46123d5`。

已研究包内中文主文件、meta.yaml及视觉方向、研究脚本、验证用例参考。整合其事实/宣称区分、语义与镜头映射、素材状态、真实配音定时、代表段审片、局部恢复与三层验证方法。按本次用户请求收窄为“链接到资讯视觉视频”，明确Opus 5.5主创和可选H3，并采用可直接推进的默认规格。

原包没有独立LICENSE文件；本适配不将原包整体重新标成MIT，不原样分发该包全部文件、旧检查器或历史版本。此来源说明不是对第三方材料权利的额外授权。

## 公开仓库

- 仓库：https://github.com/threeaus/creator-style-kit
- 固定提交：`6aeb1ba22913dbc75b3dea0f9e131cfa78422504`
- 取得日期：2026-10-21。
- 本包附带该提交的18个 `styles/<id>/style.yaml`，内容原样保留，放在 `references/styles/`；校验值见 [upstream-manifest.json](upstream-manifest.json)。
- 仓库许可为MIT，原版权及全文保留在 [creator-style-kit-MIT.txt](../licenses/creator-style-kit-MIT.txt)，适用于上述上游文件与相关衍生部分。
- 选风格与节奏方法依据仓库SKILL.md、STYLES.md、REFERENCE.md进行独立平台适配；没有复制作者机器路径、品牌身份限制或强制安装流程。

没有捆绑HyperFrames、GSAP、音效、字体、示例视频或sound-layer。token里提及的第三方名称/文件不是已授权下载资源，也不是本包能直接执行的接口。样张数字不作为资讯证据。

## 本次新增与验证边界

新增Design模型实际选择与证据记录、链接提取失败处理、语义图形设计规则、中性数据比较、18套风格迁移、按需H3底片与准确后期叠字、工程/画布真实交付状态。Design适配也参考本机huashu-motion-design的能力发现、项目资源、画布播放与工程入口经验，重新编写为本技能独立流程，不依赖该技能或引擎。

Opus 5.5与H3是用户指定的模型名称。此包未验证当前账户的模型可用性、实际API标识或生成参数；执行时读取真实平台能力。本次包结构、链接、配置与来源校验不等于在Design生成过成片。回归情境是后续验证材料，不是已完成的测试报告。

1.1.0 根据实际成片反馈，将原始媒体盘点、看片选段、正文主视觉、原片时间映射和避免图文轮播加入主流程。此次修改只验证技能结构与流程一致性，不代表新版已在 Design 重跑成片。

1.3.1 按平台版本规则调整技能包结构：新增英文默认运行文件 SKILL.md 与中文 SKILL.cn.md，frontmatter 只保留 name、description、trigger-words，版本号移入 meta.yaml；meta.yaml 按当前字段与字数范围重写；移除非平台的 agents/openai.yaml。工作流、护栏与风格配置未改动。
