# 工具使用

从项目根调用项目 Python 3.12（优先 `.venv/Scripts/python.exe`）。脚本只用标准库及已有 FFmpeg/ffprobe，可用 `LFO_FFMPEG/LFO_FFPROBE` 指定可执行文件。不安装依赖。所有写操作拒绝覆盖，输出父目录必须已经存在。生产产物位于对应项目 `outputs/<run_id>/`；测试用系统临时目录，不用真实 workspace。

以下示例的 `<...>` 是调用者提供的真实路径/ID，不能直接照填。`audio_tools.py --help` 和各子命令 `--help` 显示参数。

## 草稿与工作流

```powershell
python .agents/skills/qwen3-tts/scripts/audio_tools.py validate .agents/skills/qwen3-tts/assets/voice-design.json
python .agents/skills/qwen3-tts/scripts/preflight.py --mode design --comfy-root <ComfyUI目录> --schema-output <本次object-info.json>
python .agents/skills/qwen3-tts/scripts/audio_tools.py workflow <草稿.json> --schema <本次object-info.json> --output <workflow.json>
```

`eric-smoke.json` 仍可直接校验。Base 模板有意留空参考来源、授权和转写，首次 `validate` 应失败；补齐后才能执行准备。它不是已经可生成的示例。`workflow` 的 schema 必须来自本次服务；离线源码 schema 仅用于测试，不能作为实时预检替代。

Base 工作流还要求 `--uploaded-reference <正式执行器已上传的Comfy文件名>`，工具只验证 LoadAudio 枚举并建图，不上传。正式 Canvas 执行器以 MCP 上传成功回执和源文件未变化作为提交条件；离线准备成功本身不证明服务器上该文件内容相同。保存节点使用本机已核对的 SaveAudio FLAC；节点变更时会失败，应按实际新 schema 更新。

## 验证、登记与单次变速

正式 Canvas 运行已经保存 `original.flac`、`speech.flac` 和 `speech.flac.json`；以下 `register` / `deliver` 命令仅供另有来源的原始音频做离线后期，不要对 Canvas 交付文件再次变速。

```powershell
python .agents/skills/qwen3-tts/scripts/audio_tools.py probe <音频.flac>
python .agents/skills/qwen3-tts/scripts/audio_tools.py register <生成时配置.json> <实际原始.flac> --request-id <实际来源请求ID> --output <raw.json>
python .agents/skills/qwen3-tts/scripts/audio_tools.py deliver <raw.json> --output <delivery.flac>
```

`register` 不创建运行，也不能证明外部请求 ID 真伪；ID 必须来自正式执行回执。原始文件需经来源核对，不能把另一个变速工具的文件冒充原始。`deliver` 输出 FLAC 和 `delivery.flac.json`，包含实测元数据与哈希，听审默认 `INCONCLUSIVE`。无 `--tempo` 时使用配置的倍率（缺省 1.2）；`--tempo 1.0` 保留原速，`--tempo 1.1` 等单次覆盖。工具范围为 0.5–2.0，超出显式报错而不截断。

再改倍率时仍从同一个 raw.json 输出到新文件，不能拿 delivery 的 JSON 当原始记录。工具给派生 FLAC 写入来源哈希和倍率标签；拒绝将带此标签的文件重新登记为原始。失败后保留已有文件以供核实，不自动删除或重试。

## 保存角色音色，生成新台词草稿

```powershell
python .agents/skills/qwen3-tts/scripts/audio_tools.py profile <Canvas运行目录/speech.flac.json> --name <角色名> --transcript <实际参考转写> --authorization <已核实来源及允许用途> --output <voice.json>
```

没有实际听审时只保存待验收配置。对实际交付文件听审并核对转写后，新增 `--listened-and-verified`，保存到另一个新配置文件；这个参数是对已做人工检查的声明，不执行自动听审，不凭台词文本或 ASR 使用。然后：

```powershell
python .agents/skills/qwen3-tts/scripts/audio_tools.py clone-draft <已接受voice.json> --text <新台词> --language Chinese --output <clone.json>
```

工具重新核对参考哈希，拷贝已接受参考信息，生成 Base 草稿。`clone-draft` 不合成、不上传、不生成缓存 embedding。参考使用设计声音的真实交付文件；新台词经 Base 合成后的原始输出才执行一次 1.2 倍派生。文件移动后更新引用并重新核对哈希，JSON 不内嵌音频。
