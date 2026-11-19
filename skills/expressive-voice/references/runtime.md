# 本地生成

自带脚本使用 Apple Silicon 上的 mlx-audio Qwen3-TTS 接口。运行前核对芯片、Python 与可用存储。以下为项目验证过的依赖版本。

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r SKILL_DIR/requirements.txt
```

`SKILL_DIR` 表示安装后的技能目录。把示例 JSON 复制到实际项目，再编辑其中的声音与台词。模型可填写本地目录，或有权访问的 Hugging Face 模型 ID；远程 ID 首次加载会下载权重，先说明所需下载并遵守当前环境网络权限。已有本地模型优先复用。

项目使用过的模型 ID 为 `mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-4bit` 和 `mlx-community/Qwen3-TTS-12Hz-1.7B-Base-4bit`。设计新声音时使用实际可获得的 MLX VoiceDesign 模型目录，不能把 CustomVoice 目录当作 VoiceDesign。

```bash
.venv/bin/python SKILL_DIR/scripts/synthesize.py voice-job.json --validate-only
.venv/bin/python SKILL_DIR/scripts/synthesize.py voice-job.json --out project-audio/take-01
```

输出目录须为新目录，避免覆盖已经听审的结果。每句完成即原子写入 manifest；中断后先查看已有记录，补录时以新任务文件仅列出需要补录的句子。

## 三种角色定义

`custom` 使用 `speaker` 与 `direction`。`design` 使用 `voice_description` 和 `direction`。这两种模式可在每行填写 `delivery`，补充这句的表演意图。0.6B CustomVoice 不支持这里依赖的情绪指令，应选支持指令的 1.7B 版本。

`clone` 配置示例中，参考路径相对于任务 JSON。

```json
{
  "roles": {
    "student": {
      "mode": "clone",
      "model": "models/qwen-base",
      "reference_audio": "references/student.wav",
      "reference_text": "与参考音频逐字对应的完整文本。"
    }
  },
  "lines": [
    {"id": "answer-01", "role": "student", "text": "我明白了！"}
  ]
}
```

本地模型路径相对任务文件解析；带 `models/`、`./`、`../` 前缀的路径必须真实存在，避免拼错后误当远程模型下载。其他 `owner/model` 形态可作为远程模型 ID。

参考 WAV 由脚本转为单声道、按模型采样率重采样。支持整数 PCM 和浮点 WAV，样本必须有限、可听且未损坏。参考文字须准确。带音乐、混响、多人串话的参考可能污染输出。

## 参数与记录

每句默认一个候选，可在任务中设置 `candidates` 为 1–3。增加候选数需符合当前任务的预算与用户期望。常用起点为 temperature 0.66、top_p 0.88。`seed` 默认 227，各句和候选产生稳定派生种子。`max_tokens` 可显式设置，句子较长时应检查是否截断。

`text` 是展示原文，`spoken_text` 是可选发音输入。记录保存两者。`delivery` 只传给支持表演指令的 custom/design 路径；clone 配置了表演指令会报错，避免静默失效。

manifest 记录模型、参数、参考哈希、原始与整理音频、时长和待听审状态。原始 WAV 保留完整生成结果。整理仅做首尾静音裁剪、最多 3dB 的峰值增益与短边缘淡入淡出，保留句内节奏。音量的最终混音在整段听审后处理。

其他系统可采用官方 Qwen3-TTS 的 PyTorch 后端，须按其当前文档另行配置与验证。本技能自带脚本的执行验证范围为 Apple Silicon。

本次封装已实际执行 CustomVoice 与 Base 的短句生成，并通过音频整理与配置回归测试。VoiceDesign 路径已核对接口，但尚未加载该模型实测。执行成功只证明流程可运行，情绪与音色仍须逐句听审。
