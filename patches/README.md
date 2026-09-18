# GPT-SoVITS 补丁

`third_party/gpt-sovits`（上游 RVC-Boss/GPT-SoVITS @ 48b1a01）不入库，对它的修改以 patch 形式保存在这里。换机器 clone 上游后：

```powershell
cd third_party/gpt-sovits
git apply --ignore-whitespace ../../patches/gpt-sovits-single-gpu-train.patch
git apply --ignore-whitespace ../../patches/gpt-sovits-webui-endfield.patch
```

## gpt-sovits-single-gpu-train.patch

单卡 Windows 训练修复。上游默认走 DDP，单卡时 `dist.init_process_group` / `net_g.module` 会炸：

- `s1_train.py`：`devices=1, strategy="auto"`
- `s2_train.py`：只有 `n_gpus > 1` 才初始化进程组与 DDP，加载预训练权重时按 `hasattr(net, "module")` 判断
- `s2_train.py`：DataLoader 的 worker 数/pin_memory 改由环境变量 `GSV_NUM_WORKERS`（默认 5）、`GSV_PIN_MEMORY`（默认 1）控制；16GB 主机上 5 worker + pinned memory 会在首个 step 触发 "CUDA unknown error"，Studio 后端固定传 2 / 0
- `AR/data/bucket_sampler.py`：`dist.is_initialized()` 代替 `torch.cuda.is_available()` 判断是否分布式

## gpt-sovits-webui-endfield.patch

推理页 `GPT_SoVITS/inference_webui.py`（端口 9872）三处增强：

1. **长参考音频切分**：折叠区块，上传 >10s 音频 → `Slicer` 按静音切成 ≤10s 片段 → FunASR 逐段识别 → 每段渲染成内嵌 `<audio>` 播放器 + 文本 + 文件名。片段存在 `output/ref_slices/<原名>/<原名>_segNNN.wav`。
2. **识别参考文本**：参考文本框旁加按钮，对上传的参考音频跑 ASR 回填。
3. **终末地视觉风格** `ENDFIELD_CSS`：纸色 `#e8e8e2` / 面板 `#f2f2ec` / 墨色 `#101110`，信号黄 `#fff500` 只用于主按钮、焦点、选区，全直角，标题左侧墨色竖条。

## 未做成 patch 的本地配置

`GPT_SoVITS/configs/tts_infer.yaml` 的 `custom` 段被改成绝对路径指向 `GPT_weights_v2/typhoea-e20.ckpt` 和 `SoVITS_weights_v2/typhoea_e20_s5000.pth`，让推理页启动即加载微调模型。这是机器相关配置，不入 patch，换机器手动改。
