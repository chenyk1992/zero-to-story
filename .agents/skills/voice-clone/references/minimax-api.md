# MiniMax 本地音色克隆接口

本地适配器固定使用 MiniMax 官方的两段式流程：

## 1. 上传主参考音频

```text
POST {base_url}/v1/files/upload
Authorization: Bearer $MINIMAX_API_KEY
Content-Type: multipart/form-data

purpose=voice_clone
file=@<clone-audio>
```

响应中的 `file.file_id` 是下一步请求的 `file_id`。主音频支持 mp3、m4a、wav，时长 10 秒至 5 分钟，大小不超过 20 MB。

## 2. 可选上传示例音频

如果要增强相似度和稳定性，再次调用同一个上传接口，但把 `purpose` 设置为 `prompt_audio`。示例音频必须小于 8 秒且不超过 20 MB，得到的 `file_id` 放到 `clone_prompt.prompt_audio`，其逐字稿放到 `clone_prompt.prompt_text`。

## 3. 执行克隆

```json
{
  "file_id": 123456789,
  "voice_id": "lfo_example_20260818",
  "text": "已确认的试听文本",
  "model": "speech-2.8-hd",
  "need_noise_reduction": false,
  "need_volume_normalization": false,
  "aigc_watermark": false
}
```

请求地址为 `POST {base_url}/v1/voice_clone`，请求头为 Bearer API key 和 `application/json`。`text` 与 `model` 可以一起省略以跳过试听；如果传入 `text`，长度不超过 1000 字符，试听按语音合成规则计费。

可选字段：

- `language_boost`：例如 `Chinese`、`Chinese,Yue` 或 `auto`。
- `text_validation`：参考音频的已知逐字稿，最多 200 字符。
- `accuracy`：配合 `text_validation` 的 ASR 相似度阈值，范围 0–1，默认 0.7。
- `clone_prompt`：同时包含 `prompt_audio` 和 `prompt_text`。

`voice_id` 必须为 8–256 个字符，以英文字母开头，允许字母、数字、`-`、`_`，末字符不能为 `-` 或 `_`，且不能与已有音色重复。脚本在未指定时生成以 `lfo_` 开头的唯一 ID。

成功响应重点关注：

- `base_resp.status_code` 是否为 0。
- `demo_audio`：请求了 `text` 和 `model` 时返回试听链接。
- `input_sensitive` / `input_sensitive_type`：输入音频风控结果。
- `extra_info`：试听生成时的音频和计费信息。

## 官方文档

- [上传复刻音频](https://platform.minimaxi.com/docs/api-reference/voice-cloning-uploadcloneaudio)
- [上传示例音频](https://platform.minimaxi.com/docs/api-reference/voice-cloning-uploadprompt)
- [音色快速复刻](https://platform.minimaxi.com/docs/api-reference/voice-cloning-clone)
- [音色快速复刻指南](https://platform.minimaxi.com/docs/guides/speech-voice-clone)

