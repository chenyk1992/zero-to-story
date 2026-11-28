# 运行、渲染和交付

## 创建项目与检查依赖

按项目工作区规范，在 `workspace/projects/<project_id>/` 下建立源码、媒体、音频、临时帧和成片（`final/`）目录；`.agents/skills/retro-collage-motion-film/` 安装目录只读使用。先运行：

```sh
node .agents/skills/retro-collage-motion-film/scripts/doctor.cjs workspace/projects/<project_id>
```

渲染需要Node、`@napi-rs/canvas`和FFmpeg/FFprobe，输出`"ready": true`才可继续。

- **缺少`@napi-rs/canvas`**：环境允许安装时，在项目目录（`workspace/projects/<project_id>`）执行`npm install @napi-rs/canvas`；脚本会自动从传入的项目目录、当前工作目录或环境变量 `CANVAS_MODULE` 解析该模块。不能安装时明确报告缺少该模块。
- **缺少FFmpeg/FFprobe**：用`FFMPEG`、`FFPROBE`指向环境中已核实的可执行文件；本机 PATH 中已配置的 `ffmpeg` / `ffprobe` 会自动被识别。
- 不硬编码本机缓存路径；缺少依赖时报告具体缺口，不索要参考视频。

## 时间轴和媒体契约

渲染脚本只支持有限的DOM/Canvas接口，不是任意HTML引擎。源码`film.html`应满足：

- `<canvas width="W" height="H">`写明尺寸；动画代码放在单个`<script>`中。
- 提供`window.CONFIG = {duration, fps}`、可选的`window.ready`（Promise），以及确定性的`window.seek(t)`；`seek`不能依赖之前渲染过的帧。
- 图像清单命名为`<源码文件名>-assets.json`，形如`{"id": "media/xxx.png"}`，路径相对源码；渲染时以`window.PRELOADED_ASSETS`传入已加载图像。
- 渲染模式下`window.RENDER_MODE`为真，不播放音频。
- 必须提供`window.TEXT_SPECS = [{role, font, text}]`，登记画面上出现的每段文字及其实际字体字符串，例如`{role:'主句', font:"900 150px 'Songti SC'", text:'踩出自己的路'}`。写成单独一段字面量数组，字形检查脚本会直接读取它。

## 字体与缺字检查

- 渲染器只能使用它实际注册到的字体。系统里看得到的字体不一定能被渲染器找到（例如部分 macOS 上的苹方），找不到时会被替换成只含部分字的字体，同一句里有的字正常、有的字缺失。
- 项目根目录下的`fonts/`文件夹（.ttf/.otf/.ttc）会在检查和渲染前自动注册。需要稳定的跨机器效果、或系统缺少某种语言的字体时，放入开源可商用字体，例如 Noto Sans/Serif SC、TC、JP、KR，并在来源记录中写明许可。
- 素材准备阶段运行：

```sh
node .agents/skills/retro-collage-motion-film/scripts/check-glyphs.cjs workspace/projects/<project_id>/film.html workspace/projects/<project_id>/type-specimen.png
```

  输出缺字清单，并生成字体样张图；缺字的字符用红框标出。样张与素材一起交给用户确认。退出码为1表示有缺字。
- `render-native.cjs`在渲染前会再次逐字检查，发现缺字直接停止，避免渲染出带豆腐块的成片。

文字与几何保持代码可编辑，固定随机种子。纸纹、噪点等大量细小笔画的静态纹理，应在`ready`阶段用`document.createElement('canvas')`（设置宽高后）预渲染一次，每帧只绘制这张图；每帧重画上千条细线可能导致抗锯齿结果不稳定，无法通过乱序跳帧检查。清单只包含实际使用的媒体；音频单独管理。改时长或画幅时同步更新所有时间点并重新排版，不能只改画布宽高。

## 渲染与混音

```sh
node .agents/skills/retro-collage-motion-film/scripts/render-native.cjs workspace/projects/<project_id>/film.html workspace/projects/<project_id>/render
```

生成静音`film-preview.mp4`和`render-report.json`，并自动做乱序跳帧一致性检查。再把项目音轨合成进成片（输出至 `workspace/projects/<project_id>/final/`），例如：

```sh
ffmpeg -y -i workspace/projects/<project_id>/render/film-preview.mp4 -i workspace/projects/<project_id>/audio/score.wav -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 256k -ar 48000 -t <duration-seconds> -movflags +faststart workspace/projects/<project_id>/final/final.mp4
```

命令为参数示意，使用真实路径，不覆盖用户已接受的旧版本。旁路音轨不能证明成片有声音，要检查最终MP4的音频流和时长。

配乐优先使用项目画布音乐节点或实际可调用且授权允许的音乐工具，记录真实来源；拿到音轨后实测节拍位置再对齐切点。没有音乐工具时，为项目编写专用的程序合成配乐与动作音效，并在交付中注明是程序合成。

## 成片检查与如实交付

- 核对宽高、帧率、总帧数、时长、音视频流与完整解码；乱序跳帧应与顺序渲染一致。
- 检查每个重要入场、峰值、落稳、交接和离场，尤其共享物体在镜头边界的位置与速度；不要只看静态终态，转场前后都要抽帧。
- 检查文案完整、`TEXT_SPECS`与画面文字一致且逐字检查通过、无旧主题残留，标题、品牌与底栏不被遮挡；非拉丁字形和新字号要重新验证。
- 实际试听与数值检测分开记录；接触表或正常音频流不能证明听感合格。
- 交付MP4、源码、所用素材及来源、音频与卡点表、简要检查结果。需回填项目画布时通过 `canvas-workspace` 导入并核对节点。

平台缺少不可替代的执行能力时，交付可执行项目并写明阻塞项，完成其余可做的工作；不能把源码或计划称为成片。
