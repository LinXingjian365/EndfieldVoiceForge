# 经验总结

从 2026-09-17 深夜到 09-18 下午，DeepSeek（Trae）花了约 17 小时把这条链路跑通。中间走了不少弯路，记下来避免重蹈。

## 一、模型选型

对比过 IndexTTS / Chatterbox / tts-studio / Voice-Pro / abogen，结论：

- **IndexTTS**：中文最强、零样本、Apache 2.0。但 IndexTTS-2.5 在 6GB 显卡上 RTF≈87，s2mel 阶段 25 步扩散占了 220 秒。做试听可以，做批量或微调不现实。
- **GPT-SoVITS v2**：最终选它微调。6GB 显存 batch_size=1 + grad_ckpt 能跑，s1+s2 各 20 epoch 约 1 小时。推理秒级。
- Chatterbox 英文为主，tts-studio / Voice-Pro 是套壳，abogen 不能克隆，直接排除。

**教训**：选型时要先看本机显存能不能跑推理，指标再好也没用。

## 二、语音定位（最耗时的部分）

### 走过的弯路

1. **哈希反查**：假设 `AudioDialog.json` 的 key 是 wem 文件名的 FNV-1。实测只有 30/514 命中，FNV-1a、全路径、小写都试过，都不行。key 与 Wwise ShortID 的关系至今未完全解开。
2. **全量 wem 时长匹配**：从 8 个 PCK 里解出 56262 个 wem，按 `wavDuration` 匹配。结果 81 条"高置信"全是环境音——正式版把语音和音效合并进了 `Main/default_stream_*.pck`，时长恰好相同的 SFX 太多。
3. **VAD 过滤**：加 Silero VAD 后筛到 29 条真人声，但只覆盖 484 条台词的 6%，因为 Wwise 编码后帧对齐导致大多数 wem 时长与 `wavDuration` 对不上。

### 最终可用的路线

`DecryptOutput/Audio/PCK/Windows/Chinese/default_chinese_stream.pck` 的 **externals 区**才是纯语音流：

1. 解密 PCK 头 → 解析 externals 表（entry 含 low/high/blk/size/offset）→ 每条 wem 用 vgmstream `-m` 量精确时长，缓存到 `ext_durations.json`（28277 条）
2. 对提弗洛斯每条台词（`voType` 0/4/5）找最近邻，delta<0.01s 的解码
3. 用 librosa pyin 量 F0 中位数和有声比，**F0 180-350Hz + voiced≥0.30** 过滤掉男声/环境音
4. 得到 254 条，23.6 分钟，再用 GPT-SoVITS 自带 ASR 打标

**教训**：
- 先查语言分流的 PCK，别一上来就全量解包
- 时长匹配必须配合 F0/VAD 二次确认，且要用 vgmstream 量真实时长而不是信 header
- `voType` 含义：0=角色语音（干员台词）、4=剧情对白、5=无线电，2 是战斗短语音噪声多

## 三、环境与工具

- Trae 沙箱会拦截 HTTPS 下载（SSL 日志写入 `C:\ssl_key\sslog.log` 失败），HuggingFace 模型下载反复失败。**改走 ModelScope 镜像**，并把 `USE_MODELSCOPE=true`、`MODELSCOPE_CACHE` 指到项目内。
- IndexTTS 的 venv（Py3.11 + torch 2.8）可以直接复用给 GPT-SoVITS，不用再建一套。RVC 需要 Py3.12 单独 venv。
- GPT-SoVITS s1 训练前要清空 `logs_s1_v2/ckpt/`，否则残留 checkpoint 触发 `weights_only` 反序列化失败。
- GPT-SoVITS 的 `1-get-text.py` 等预处理脚本输出带 `-0` 后缀的分片文件，单卡时要手动改名合并。
- RVC 必须用 `-m train.preprocess` 模块方式运行，否则 `sys.path[0]=train/` 会把包名解析成 `train.py`。
- venv 搬家：uv 建的 venv 移动后 `python.exe` 仍可用，但要改 `site-packages/*.pth` 里的绝对路径（editable install 和 users.pth）。

## 四、工程方面

- DeepSeek 把 90 多个 `_diag_*.py` 试错脚本全堆在 EndfieldUnpacker 根目录，只有 3 个进了 git。本仓库只保留了链路上真正用到的 6 个管线脚本 + 3 个训练/推理脚本。
- 所有路径原来硬编码 `a:\Hypergryph Launcher\...\EndfieldUnpacker`，现在统一走 `config.py`。

## 五、下一步

- [ ] 试听 `outputs/gsv_typhoea_ft.wav`，判断 e20 是否过拟合；GPT_weights_v2 / SoVITS_weights_v2 下每个 epoch 都有存档，可以对比 e8 / e12 / e16
- [ ] gsv_infer.py 的参考音频换几条不同情绪的台词看稳定性
- [ ] RVC G_5320.pth 做一次推理验证，看能否作为 GPT-SoVITS 输出的后处理
- [ ] 把 `voType=5`（无线电）加进训练集会不会拉低音质（无线电有滤波效果）
- [ ] 考虑 GPT-SoVITS v2ProPlus / v4 版本（目录已建但权重未下）
