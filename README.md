# EndfieldVoiceForge

《明日方舟：终末地》角色语音克隆实验工程。当前目标角色：**提弗洛斯**（`chr_0034_typhoea`）。

从官方解包语音里定位角色人声、构建带台词文本的训练集，然后用 GPT-SoVITS 微调 / IndexTTS 零样本 / RVC 音色转换三条路线做对比。

> 仅用于个人学习。解包素材与克隆模型不公开分发，仓库只含脚本与说明。

## 现状（2026-09-18）

| 路线 | 状态 | 效果 / 备注 |
|---|---|---|
| **GPT-SoVITS v2 微调** | 已训 20 epoch，可推理 | 目前最可用。`outputs/gsv_typhoea_ft.wav` 为样例 |
| IndexTTS-2.5 零样本 | 跑通 | RTX 3060 6GB 上 RTF≈87（3s 音频要 270s），只能试听 |
| RVC v2 音色转换 | 已训至 step 5320 | 未做推理验证 |

训练集：254 条提弗洛斯中文台词，共 23.6 分钟，全部带官方台词文本（来自 ASR + `AudioDialog` 校对）。

## 目录

```
EndfieldVoiceForge/
├── config.py                 所有路径集中在这里；依赖同级的 EndfieldUnpacker
├── pipeline/                 数据管线（按序号执行）
│   ├── 01_measure_externals.py   解密 PCK externals 区，量每条 wem 时长并缓存
│   ├── 02_select_speech.py       按台词时长找最近邻 wem，解码并量 F0 / 有声比
│   ├── 03_extract_train.py       按 F0 180-350Hz 等条件筛出训练集 wav
│   ├── 04_postprocess_list.py    规范 ASR 输出的 .list 为训练格式
│   ├── build_ref.py              抠指定台词拼零样本参考音频
│   └── export_vad.py             （早期路线）全量 wem + Silero VAD 筛人声，已弃用
├── gsv_train.py / gsv_infer.py   GPT-SoVITS v2 训练 / 推理编排
├── rvc_train.py                  RVC 训练编排
├── indextts_clone.py             IndexTTS 零样本克隆
├── third_party/   (gitignore)   gpt-sovits@48b1a01、RVC@81eed5e、index-tts@ee40fa7 各自 clone + venv + 权重
├── datasets/      (gitignore)   typhoea_train/（wav）、typhoea_train_asr/typhoea.list、cache/
└── outputs/       (gitignore)   生成音频
```

## 环境

- Windows 11，RTX 3060 Laptop 6GB
- `third_party/index-tts/.venv`：Python 3.11 + torch 2.8 cu128，**同时给 GPT-SoVITS 用**
- `third_party/RVC/.venv`：Python 3.12 + torch 2.7 cu128
- 外部依赖：同级目录的 [EndfieldUnpacker](https://github.com/LinXingjian365/EndfieldUnpacker)（AKPK 解密逻辑、`DecryptOutput/`、vgmstream）。路径不同时设环境变量 `ENDFIELD_UNPACKER_DIR`

third_party 与 datasets 不进 git，换机器需按上面版本重新 clone 引擎、跑一遍 pipeline。

## 用法

```powershell
# 数据管线（需 EndfieldUnpacker 已解包出 DecryptOutput/Audio 与 TableCfg_json）
python pipeline/01_measure_externals.py
python pipeline/02_select_speech.py
python pipeline/03_extract_train.py
# 用 GPT-SoVITS WebUI 的 ASR 工具对 datasets/typhoea_train 打标 -> typhoea_train.list，然后
python pipeline/04_postprocess_list.py

# GPT-SoVITS 微调 + 推理
third_party/index-tts/.venv/Scripts/python.exe gsv_train.py preprocess
third_party/index-tts/.venv/Scripts/python.exe gsv_train.py s1
third_party/index-tts/.venv/Scripts/python.exe gsv_train.py s2
third_party/index-tts/.venv/Scripts/python.exe gsv_infer.py

# RVC
python rvc_train.py all

# IndexTTS 零样本
third_party/index-tts/.venv/Scripts/python.exe indextts_clone.py
```

## 关键发现（详见 [LESSONS.md](LESSONS.md)）

- 正式版 VFS 里语音和音效混在一起，`AudioDialog.json` 的 key 只有 6% 能用 FNV-1 反查到 wem 名，**不能靠哈希定位**
- 真正可用的定位方式：中文语音流 `default_chinese_stream.pck` 的 **externals 区** + `wavDuration` 最近邻匹配 + F0 过滤
- 全量 wem 里 97% 是环境音，任何"时长匹配"都必须先过 VAD 或 F0 检查
