# EndfieldVoiceForge 情感调控与场景预设系统 · 技术设计文档

> 目标：为 TTS → RVC 全链路增加可复用的情感/语气调控能力（旁白、俏皮、惊讶、疑惑、生气等场景预设 + 强度调节 + 自定义），面向《明日方舟：终末地》角色提弗洛斯的语音克隆工作台。
>
> 版本：v2.0　初版 2026-05-26 / 更新 2026-09-21（新增：2026 引擎格局更新、硬件分层与显卡升级路线、能力注册式插件架构、终极多引擎管线）
> 约束：全部模型本地离线运行；当前 GPU 6GB VRAM / RAM 16GB（RTX 3060），架构需面向未来 12–24GB 升级平滑扩展；不影响现有 RVC 训练流程。

---

## 1. 调研结论

### 1.1 技术路线对比

| 方案 | 情感控制方式 | 音色克隆 | 显存 | 许可证 | 结论 |
|---|---|---|---|---|---|
| **IndexTTS 2.5（B站）** | 4 种：跟随参考 / 独立情感参考音频 + alpha / 8 维情感向量 / 自然语言文本（Qwen3-0.6B 微调） | 零样本，强 | 官方 8GB，**实测 6GB 可跑（自动 low_vram 分段）** |  Apache-2.0（代码） | **主力，本地已下载完整权重** |
| GPT-SoVITS（现有） | 仅靠参考音频隐式传递，无显式控制；支持多参考音频 | 微调后最稳 | ~4GB | MIT | 保留，P0 借多参考做粗粒度情绪 |
| CosyVoice 2/3（阿里） | instruct 自然语言（"用开心的语气说"）、流式 150ms、方言 | 零样本 | ~6GB | Apache-2.0 | 备选，暂不引入 |
| ChatTTS | `[oral_0-9][laugh_0-2][break_0-7]` 口语/笑声/停顿标记 | 不做克隆，须套 RVC | ~4GB | AGPL（需注意） | 仅借鉴标记思路 |
| PROEMO（论文） | 情感类别 × 强度两级、全局 + 词级韵律 | — | — | 学术 | 预设 + 强度滑块的理论依据 |
| RVC | **不创造情感，只保留源语音的语调/哭笑/怒气**（F0 与内容特征分离） | — | 2–6GB | MIT | 情感在 TTS 注入，RVC 只做参数适配 |

### 1.2 IndexTTS 2.5 四种情感模式（官方 API 实测核实）

来源：[index-tts 官方仓库](https://github.com/index-tts/index-tts)、[IndexTTS2 论文 arXiv:2506.21619](https://arxiv.org/abs/2506.21619)、[2.5 技术报告](https://index-tts.github.io/index-tts2-5.github.io/)、[DeepWiki 情感控制配方](https://deepwiki.com/tabortao/index-tts2/13.2-emotion-control-recipes)、[PyPI](https://pypi.org/project/indextts2-inference/)。

| 模式 | 参数 | 用途 |
|---|---|---|
| 0 跟随音色参考 | 不传情感参数 | 情绪交给参考音频 |
| 1 独立情感参考 | `emo_audio_prompt` + `emo_alpha`（0.0–1.6，>1 放大） | **音色用 A、情绪用 B**（提弗洛斯战斗语音做情绪源） |
| 2 八维向量 | `emo_vector=[happy,angry,sad,afraid,disgusted,melancholic,surprised,calm]`，`emo_alpha` 0–1 | 按钮/滑块精确控制 |
| 3 自然语言描述 | `use_emo_text=True, emo_text="…"`；init 时必须 `use_qwen_emo=True`；官方建议 alpha≤0.6 | 疑惑、嘲讽、俏皮等 8 维覆盖不到的复杂语气 |

已核实的关键行为（[infer_v2_5.py](file:///A:/Hypergryph%20Launcher/games/Arknights%20Endfield/EndfieldVoiceForge/third_party/index-tts/indextts/infer_v2_5.py)）：

- 8 维顺序：**[高兴, 愤怒, 悲伤, 恐惧, 反感, 低落, 惊讶, 自然]**；向量总和官方归一化上限 **0.8**（超出自动等比缩放），且内置 bias 对易出怪声的情感降权。
- `use_emo_text` 或 `emo_vector` 非空时，`emo_audio_prompt` 会被强制忽略（三者互斥，优先级：文本 > 向量 > 音频参考）。
- 2.5 构造参数为 **`use_bf16=True`**（非 fp16），`infer()` **必传 `lang`**（"ZH"/"EN"/"JA"/"KO"）。
- 2.5 内置 **low_vram 自动模式**：检测到总显存 <10GB 时，长文本（>40 字）自动按标点切 40 字分段合成并按 `interval_silence` 毫秒停顿拼接。
- `infer()` 返回 `(sr, wav_numpy)`；不传 `output_path` 时直接返回音频，采样率 **22050Hz**。
- 音色参考音频最长自动截取 15 秒（GPT-SoVITS 要求 3–10 秒，两引擎校验不同）。

### 1.3 本地资产盘点（可直接利用）

- **完整权重已就位**：[third_party/index-tts/checkpoints](file:///A:/Hypergryph%20Launcher/games/Arknights%20Endfield/EndfieldVoiceForge/third_party/index-tts/checkpoints)（config.yaml 标 `version: 2.5`，含 gpt.pth、s2mel.pth、codec、bigvgan、情感矩阵 feat2.pt、Qwen 情感模型 `qwen0.6bemo4-merge/`）。
- **已验证可跑的最小脚本**：[indextts_clone.py](file:///A:/Hypergryph%20Launcher/games/Arknights%20Endfield/EndfieldVoiceForge/indextts_clone.py)，实例化参数 `use_bf16=True, use_cuda_kernel=False, use_torch_compile=False`，服务主 venv 即 `third_party/index-tts/.venv`，可在 FastAPI 进程内直接 import。
- **提弗洛斯本人情绪语料**：干净训练集 254 条（dialog 215 / **combat 32 战斗强情绪** / commvo 7），位于 `datasets/typhoea_train_clean/`，是天然的情绪参考音频库（emolib）候选。
- 现有引擎抽象已有锁、懒加载、`unload()`、`set_device()` 与 busy 状态（[tts_engine.py](file:///A:/Hypergryph%20Launcher/games/Arknights%20Endfield/EndfieldVoiceForge/apps/server/core/tts_engine.py)），可扩展为多引擎。

已知实测性能（[indextts_clone.py](file:///A:/Hypergryph%20Launcher/games/Arknights%20Endfield/EndfieldVoiceForge/indextts_clone.py) 注释）：6GB 卡上 RTF 一度 ≈87（3 秒音频 270 秒，疑似首次冷启动/未走满 GPU）。**P1 首先复核 GPU 占用与稳态 RTF**，合成一律走异步 job，不走同步 HTTP。

### 1.4 2026-09 引擎格局更新（v2.0 重新调研）

四个月过去，开源 TTS 迭代很快。核实结论：**IndexTTS 2.5 仍是官方最新开源版（GitHub 最新 release v2.5.0，2026-08-13，无 v3），本地权重不过时**；但出现了两个值得纳入路线图的新对手：

| 引擎（截至 2026-09） | 参数/体积 | 最低显存 | 情感控制 | 克隆 | 许可证 | 对本项目的意义 |
|---|---|---|---|---|---|---|
| **IndexTTS 2.5**（现有） | ~2GB 权重 + Qwen0.6B | 6GB（low_vram） | 8 维向量 + 情绪参考 + 文本描述 | 零样本 | Apache-2.0 | **中文情感主力，不动** |
| **CosyVoice 3**（阿里，权重 Fun-CosyVoice3-0.5B-2512，2025-12） | 0.5B，bf16 仅 2.1GB / int4 约 1.2GB | **官方称 FP16 4GB 起** | instruct 标签：happy/excited/sad/angry/**whispers/laughs**/calm/surprised/serious；9 语言 + 18 中文方言；150ms 流式；24kHz | 3 秒零样本，可注册音色 | Apache-2.0 | **升级后首选第二引擎**：补上 IndexTTS 没有的"笑场/耳语/严肃"标签与流式；4GB 体量未来可与 RVC 共驻 |
| **Qwen3-TTS**（2026-01） | 0.6B / 1.7B，2.5–4.5GB | 4–6GB | 情感 + 声音设计（voice design） | 短参考克隆 | Apache-2.0 | 轻量候选，实测后再定，P4+ 观察 |
| ZONOS2（Zyphra，2026-06） | MoE 8B 总参/900M 激活，**权重 15.3GB** | 官方 Linux+CUDA；8GB 需手调 KV cache，Windows 折腾 | 情感控制、44.1kHz、34 语言 | 高相似度 | Apache-2.0 | 24GB 档玩具，Windows/6GB 不现实 |
| Higgs TTS 3 4B（Boson，2026-07） | 4B / 9.3GB | ~12GB | 行内情感/风格/韵律/**音效**控制、102 语言、对话 | 零样本 | **研究非商用** | 能力最强但许可证排除，个人研究可试 |
| Breeze TTS 2（2026-08） | 3B / ~7.7GB | 12GB 起步 | 行内语音事件、中英双语 | 克隆+声音设计 | **研究非商用** | 同上，排除生产链路 |
| Orpheus TTS | 3.5GB | 4GB | 笑/叹气/犹豫等副语言标签最丰富 | 克隆 | Apache-2.0 | **仅英文**，不适用中文角色 |
| F5-TTS / Fish Speech 1.6 | 0.33B / 0.5B | 4GB | 无显式情感 / 弱 | 强 | **CC-BY-NC(-SA)** | 非商用授权，不进入正式链路 |

关键判断：

1. **中文情感 TTS 没有换引擎的必要**——IndexTTS 2.5 仍是中文情感可控性最完整的开源方案（8 维向量 + 音色情感解耦是独家），且权重就在本地。
2. **CosyVoice 3 是唯一值得新增的引擎**：① 4GB FP16 能跑，升级显卡后可与 IndexTTS/RVC 共驻；② `laughs`/`whispers` 标签正好补上 IndexTTS 八维之外的非语言情绪（笑场、耳语、严肃命令）；③ 流式 150ms 为以后实时对话（项目已有 chat 页）铺路；④ Apache-2.0 无授权风险；⑤ 官方 Docker 镜像支持 RTX 50 系与 Windows（WSL2）。
3. **许可证红线**：Higgs/Breeze/F5/Fish 均为非商用许可，只可个人研究对比，正式管线只用 Apache-2.0/MIT 的引擎（IndexTTS、CosyVoice、GSV、RVC、Qwen3-TTS）。
4. 引擎半年一代，**架构必须做成"插件 + 能力声明"而不是写死 IndexTTS**（见第 12 节）——这是本次方案升级最重要的决策。

---

## 2. 总体架构

```
前端 synth 页
  引擎开关 [GPT-SoVITS | IndexTTS2.5]
  情感场景 chips（旁白/俏皮/惊讶/疑惑/生气…）+ 强度滑块
  高级区：跟随参考 | 情绪参考音频 | 8维向量 | 文本描述
  文本框：支持行内（情绪）台词 标记
        │  POST /tts（engine + emotion 结构）
        ▼
后端推理路由
  ├─ EmotionSpec 解析/归一化（core/emotion.py）
  ├─ 行内标记切句 → 逐句 spec → 逐句合成 → 停顿拼接（P3）
  ├─ 引擎管理器（互斥单例，6GB 显存只允许一个 TTS 引擎驻留）
  │    ├─ GSvEngine（现有 tts_engine.py，包一层）
  │    └─ IndexTtsEngine（新增，进程内 import，qwen 按需加载）
  └─ RVC 转换前自动换出 TTS 显存；RVC 按预设情绪档调参（protect/index_rate…）
        ▼
  library 入库（记录 engine/emotion/preset 元数据，便于回溯 A/B）
```

设计原则（吸取既往多智能体情绪漂移教训）：

1. **统一 EmotionSpec**：全链路只有一套情绪枚举与一个数据结构，UI / API / 预设 / 入库元数据一一对应，冻结 8 维顺序。
2. **显式优先**：用户显式选择 > 预设 > 默认；不做纯关键词猜测。
3. **预设是配方而不是硬编码**：JSON 可增改，用户可另存自定义预设。
4. **引擎与情绪解耦**：EmotionSpec 不绑定引擎；GSV 引擎降级执行（只认 ref 模式），IndexTTS 全功能。

---

## 3. 核心数据模型（`core/emotion.py`，新增）

```python
from typing import Literal
from pydantic import BaseModel, Field

EMO_DIMS = ("happy", "angry", "sad", "afraid",
            "disgusted", "melancholic", "surprised", "calm")
# 中文展示顺序固定：高兴/愤怒/悲伤/恐惧/反感/低落/惊讶/自然
EMO_SUM_MAX = 0.8  # IndexTTS 官方硬约束

EmoMode = Literal["follow", "ref", "vector", "text"]

class EmotionParams(BaseModel):
    preset: str | None = None              # 预设 id，如 "playful"
    mode: EmoMode = "follow"
    intensity: float = Field(1.0, ge=0.0, le=1.6)  # 全局强度，乘到 alpha 上
    vector: list[float] | None = None      # 长度 8，与 EMO_DIMS 同序
    alpha: float | None = None             # 覆盖强度（高级用户）
    emo_text: str | None = None            # mode=text 的自然语言
    emo_ref: str | None = None             # mode=ref 的情绪参考音频（项目相对路径）

class EmotionSpec(BaseModel):              # 预设文件的完整配方
    id: str
    label: str
    scene: str                             # 场景分组：旁白/日常/战斗/情绪
    mode: EmoMode
    vector: list[float] = [0]*8
    alpha: float = 1.0
    emo_text: str | None = None
    emo_ref: str | None = None
    duration_factor: float = 1.0           # 2.5 语速：>1 慢，<1 快
    interval_silence: int = 200            # 句间停顿 ms
    rvc: dict = Field(default_factory=lambda: {
        "pitch": 0, "index_rate": 0.75, "protect": 0.33,
        "rms_mix_rate": 1.0, "filter_radius": 3, "f0_method": "rmvpe",
    })
    description: str = ""
```

解析流程：`preset → 取 EmotionSpec → EmotionParams 覆盖单字段 → intensity 乘 alpha → 向量裁剪负值/按 0.8 归一化 → 产出引擎无关的最终 spec`。

**行内标记语法（P3）**：每行 `（预设id 或中文标签）台词`，例：

```
（平静）罗德岛的各位，今天辛苦了。
（俏皮）哼哼，没想到吧~
（惊讶）等等，那是什么？！
（生气）谁允许你们擅自行动的！
```

解析器把全文切成 `[{spec: calm, text: …}, {spec: playful, text: …}]`，逐句合成后用 `interval_silence` 静音拼接；无标记行用全局预设。中文全角（）与英文半角 () 都支持，标签支持 id 与中文别名表。

---

## 4. 场景预设库（v1，17 个）

预设文件：`assets/emotion/presets.json`（随仓库分发，可被用户预设覆盖）。向量顺序统一为 `[高兴,愤怒,悲伤,恐惧,反感,低落,惊讶,自然]`，均已控制总和 ≤0.8。

| id | 标签 | 场景 | 模式 | 向量 / 文本要点 | alpha | 语速 | RVC 档 |
|---|---|---|---|---|---|---|---|
| `narration` | 旁白 | 旁白 | vector | `[0,0,0,0,0,.05,0,.6]` | 0.9 | ×1.05 慢 | normal |
| `calm` | 平静 | 日常 | vector | `[0,0,0,0,0,0,0,.7]` | 1.0 | 1.0 | normal |
| `playful` | 俏皮 | 日常 | **text** | "俏皮、恶作剧感，尾音轻快上扬，带一点小得意的笑意" | 0.6 | ×0.95 快 | normal |
| `happy` | 开心 | 情绪 | vector | `[.65,0,0,0,0,0,.15,.1]` | 1.0 | 0.97 | normal |
| `surprised` | 惊讶 | 情绪 | vector | `[.1,0,0,0,0,0,.7,.05]` | 1.1 | ×0.92 快 | strong |
| `doubt` | 疑惑 | 情绪 | **text** | "疑惑不解，尾音上扬像在反问，句中有不确定的停顿" | 0.6 | 1.0 | normal |
| `angry` | 生气 | 情绪 | vector | `[0,.75,0,0,0,0,.05,0]` | 1.1 | 0.97 | strong |
| `shout_combat` | 战斗怒吼 | 战斗 | **ref** | emo_ref=combat 战斗样本，叠加 `[0,.6,0,0,0,0,.1,0]` | 1.2 | 0.95 | strong |
| `sad` | 悲伤 | 情绪 | vector | `[0,0,.65,0,0,.2,0,.05]` | 1.0 | ×1.08 慢 | soft |
| `afraid` | 恐惧 | 情绪 | vector | `[0,0,.1,.65,0,0,.15,0]` | 1.1 | 1.0 | soft |
| `disgusted` | 厌恶 | 情绪 | vector | `[0,0,0,0,.65,0,0,.05]` | 1.0 | 1.0 | strong |
| `melancholic` | 忧郁 | 情绪 | vector | `[0,0,.15,0,0,.6,0,.1]` | 0.9 | 1.08 | soft |
| `gentle` | 温柔安慰 | 日常 | vector | `[.15,0,.05,0,0,.1,0,.45]` | 0.8 | 1.06 | soft |
| `serious` | 严肃命令 | 战斗 | **text** | "严肃、沉稳、不容置疑，咬字有力" | 0.6 | 1.0 | normal |
| `sarcastic` | 嘲讽 | 日常 | **text** | "带着讥讽和冷笑，拖长尾音，漫不经心" | 0.6 | 1.0 | normal |
| `shy` | 害羞 | 日常 | **text** | "害羞，声音变轻，带羞涩的笑意和小停顿" | 0.6 | 1.02 | soft |
| `custom` | 自定义 | 高级 | text/vector | 完全由用户输入 | — | — | normal |

RVC 三档参数（情感经 RVC 透传，只防伪影、不创造情绪）：

- **normal**：pitch 0 / index_rate 0.75 / protect 0.33 / filter_radius 3 / rmvpe
- **strong**（怒、喊、惊讶等高动态）：index_rate **0.4**（降低检索伪影/带入训练集噪声）、protect **0.4**（保护气声/清辅音）、rms_mix_rate 0.9
- **soft**（悲伤、温柔、恐惧等气声）：index_rate 0.6、protect **0.42**、rms_mix_rate 0.8

依据：[RVC inference settings](https://docs.aihub.gg/rvc/resources/inference-settings/)（protect 保护清辅音 0–0.5；index_rate 过高引入伪影），与本项目电流声排查结论一致（强情绪干声更易触发 rmvpe 毛刺）。

---

## 5. 后端设计

### 5.1 文件改动清单

| 文件 | 动作 | 说明 |
|---|---|---|
| `apps/server/core/emotion.py` | 新增 | EmotionSpec/Params、预设加载、归一化、行内标记解析、中文别名表 |
| `apps/server/core/indextts_engine.py` | 新增 | IndexTTS 2.5 适配器（进程内 import，参照 [indextts_clone.py](file:///A:/Hypergryph%20Launcher/games/Arknights%20Endfield/EndfieldVoiceForge/indextts_clone.py) 的环境变量与实例化） |
| `apps/server/core/engines.py` | 新增 | 引擎管理器：GSV / IndexTTS 互斥单例、active 切换时自动 unload、与 RVC job 的显存互斥 |
| `apps/server/core/tts_engine.py` | 改造 | 抽出统一接口 `load/unload/synthesize/describe/busy`，成为 GSV 引擎实现；现有调用方改走 engines 管理器 |
| `apps/server/core/emolib.py` | 新增（P2） | 情绪参考库扫描、候选打分（f0 均值/方差、RMS 能量、时长）、读写 `assets/emolib/index.json` |
| `apps/server/routers/inference.py` | 改造 | TtsRequest 增加 engine/emotion 字段；参考音频时长校验按引擎分支；合成改异步 job（IndexTTS） |
| `apps/server/routers/emotion.py` | 新增 | 预设/情绪库/试听见下文 API |
| `apps/server/main.py` | 改造 | 注册 emotion 路由 |
| `apps/server/routers/rvc.py` | 改造 | convert 入参接受整段 rvc 情绪档（已可覆盖现有字段）；job 启动前调 `engines.suspend_for_rvc()` 换出 TTS |
| `assets/emotion/presets.json` | 新增 | 第 4 节预设表 |
| `assets/emolib/{typhoea/*.wav,index.json}` | 新增（P2） | 情绪参考音频库 |

### 5.2 IndexTtsEngine 适配器要点

```python
# 伪代码，仅示意关键约束
class IndexTtsEngine:
    def __init__(self):
        self.model = None; self.profile = None  # "lite"(无qwen) | "full"(qwen)
        self.busy = False

    def load(self, profile: str):
        # 1) 必须在 import 前设置环境变量（与 indextts_clone.py 完全一致）：
        #    USE_MODELSCOPE=true、USERPROFILE/HOME=INDEXTTS_DIR、
        #    MODELSCOPE_CACHE、HF_HUB_CACHE；sys.path.insert(0, INDEXTTS_DIR)
        # 2) IndexTTS2(cfg_path=…/checkpoints/config.yaml, model_dir=…/checkpoints,
        #    use_bf16=True, use_cuda_kernel=False, use_torch_compile=False,
        #    use_qwen_emo=(profile=="full"))
        # 3) profile 切换（vector/ref ↔ text）= 卸载后重新构造（qwen 只在构造期加载）
```

`synthesize(spec, text, spk_ref, out_path)` 参数映射：

| 统一层 | IndexTTS 2.5 |
|---|---|
| lang（zh/en/ja/ko） | 必传，大写："ZH"/"EN"/"JA"/"KO" |
| mode=follow | 不传 emo_* |
| mode=vector | `emo_vector=归一化后向量, emo_alpha=clamp(alpha,0,1)` |
| mode=ref | `emo_audio_prompt=emo_ref, emo_alpha=clamp(alpha,0,1.6)` |
| mode=text | `use_emo_text=True, emo_text=…, emo_alpha=min(alpha,0.6)` |
| duration_factor | 同名透传 |
| 输出 | `output_path=None` 拿 `(22050, np)`，服务端自己存 wav |

显存策略：

- 引擎管理器只允许一个 TTS 引擎驻留；切换 = 旧引擎 `del + gc + torch.cuda.empty_cache()`（复用现有 `_free_locked`）。
- **RVC convert job 启动前**：管理器 `suspend_for_rvc()` 无条件换出 TTS（6GB 卡两者无法共存）；RVC 结束后下一次合成懒加载。状态面板显示当前驻留引擎。
- 训练 job 运行中沿用现有逻辑（TTS 走 CPU）；IndexTTS CPU 极慢，训练期间前端对该引擎返回 409 + 明确提示。
- qwen0.6b（约 1.2GB）按需：lite profile 支持向量/参考模式；用户首次用文本模式时前端提示"需加载情感语言模型"，确认后重建为 full profile。

### 5.3 API 变更

**POST /tts 扩展**（向后兼容，新字段全可选）：

```jsonc
{
  "engine": "indextts2",          // 默认 "gsv"，保持旧行为
  "character": "typhoea",
  "text": "（俏皮）哼哼，没想到吧~",
  "ref_audio_path": "…",          // 音色参考；IndexTTS 允许 ≤15s
  "prompt_text": "",              // IndexTTS 忽略
  "parse_inline": true,           // P3：解析行内（情绪）标记
  "emotion": {
    "preset": "playful",
    "mode": "text",               // 可省略，缺省取预设
    "intensity": 1.0,
    "vector": null, "alpha": null,
    "emo_text": null, "emo_ref": null
  },
  "save": true
}
```

- engine=gsv 时的降级：仅 `follow/ref` 有效——ref 模式把 emo_ref 作为主参考或追加进 `aux_ref_audio_paths`（P0 即用此机制）；vector/text 返回 400 并提示切换引擎。
- 入库 library 元数据增加 `engine`、`emotion`（解析后的最终 spec 快照）、`preset`，用于效果回溯。
- IndexTTS 合成走 job 体系（kind=`tts:indextts2`，复用 [jobs.py](file:///A:/Hypergryph%20Launcher/games/Arknights%20Endfield/EndfieldVoiceForge/apps/server/core/jobs.py) 日志/SSE），接口返回 `job_id`；GSV 维持现有同步返回。

**新增路由 routers/emotion.py**：

| 方法 路径 | 作用 |
|---|---|
| GET /emotion/presets | 预设列表（含标签/场景/模式，供前端渲染 chips） |
| GET /emotion/presets/{id} | 单个预设完整配方 |
| POST /emotion/resolve | 调试用：传入 emotion+text，返回解析归一化后的最终 spec（开发/前端预览强度） |
| GET /emolib?emotion=angry | 情绪参考库列表（路径/时长/f0/能量/标签） |
| POST /emolib/candidates | P2：从 datasets/typhoea_train_clean 计算候选并打分（不落库） |
| POST /emolib/entries | P2：确认入条目（复制/登记到 assets/emolib） |
| GET /emolib/{id}/audio | 试听（或复用现有 files 静态服务） |

### 5.4 与 RVC 的衔接

- 22050Hz 单声道 wav 直接喂现有 RVC convert（RVC 内部 load_audio 重采样，无需额外处理；与现有 GSV 32000Hz 输出路径相同）。
- 预设 rvc 档随合成元数据保存；synth 页点"RVC 精修"时自动填入该档（用户仍可手动覆盖）。

---

## 6. 前端设计（apps/web）

| 文件 | 改动 |
|---|---|
| `lib/api.ts` | `TtsParams` 增 `engine`/`emotion`/`parse_inline`；新增 `EmotionSpec`、`EmotionPreset` 类型与预设/情绪库接口 |
| `lib/emotion.ts`（新） | 8 维中英文 label、模式中文、场景分组、chips 排序、强度 → alpha 换算 |
| `app/synth/page.tsx` | 引擎切换；情感区；行内标记插入 |
| `components/emotion/emotion-panel.tsx`（新） | 情感主控件 |
| `components/emotion/vector-editor.tsx`（新） | 8 维滑条（含总和 0.8 归一化提示） |
| `components/emotion/emo-ref-picker.tsx`（新，P2） | 情绪参考下拉+试听（复用 audio/waveform） |
| `app/tools/page.tsx` 或 data 页（P2） | emolib 候选试听/打标管理页 |

情感区交互（自上而下）：

1. **场景 chips 横排**：按 旁白/日常/情绪/战斗 分组，点选套用预设；选中态高亮。
2. **强度滑块**：0–1.6（默认取预设 alpha），实时显示"温和/标准/强烈"。
3. **模式 Tab**（高级折叠）：跟随参考 / 情绪参考音频 / 八维向量（雷达图或 8 滑条）/ 文本描述（多行输入 + 常用语快捷插入）。
4. **行内标记**：文本框工具栏加"插入情绪标记"下拉，在光标处插入 `（俏皮）`；开关"逐句解析"。
5. 引擎切换 GSV↔IndexTTS2.5 时，vector/text 控件在 GSV 下置灰并提示"需 IndexTTS 引擎"。
6. 合成结果卡片展示预设名 + 强度，写入库，便于 A/B 对比。

---

## 7. 实施计划与验收标准

### P0 · GSV 情绪参考预设（约 0.5 天，零下载零风险）
- 落地 `core/emotion.py` + presets.json（仅 ref/follow 子集）、GET /emotion/presets、前端 chips + 强度。
- 从现有 254 干净样本手挑 ~10 条情绪参考（含 combat）填入预设 emo_ref；GSV 合成时切换主参考/多参考。
- **验收**：同一句台词切换"平静/生气/开心"三档，能听出明显语气差异且不破音。

### P1 · IndexTTS 2.5 引擎接线 + 向量/文本情感（1.5–2 天，核心）
- indextts_engine + engines 管理器 + 显存互斥（含 RVC 前换出）；POST /tts 扩展；异步 job。
- 第一步：**复核稳态 RTF 与显存峰值**（任务管理器/nvidia-smi 记录，确认 bf16 走 GPU；若 RTF 仍异常高，排查是否落 CPU）。
- 全 17 预设、模式 Tab、强度滑块；qwen lite/full profile 懒加载。
- **验收**：① 疑惑/俏皮（text）、生气/惊讶（vector）、战斗怒吼（ref）三类各 3 句，盲听语气可辨；② 引擎切换/RVC 精修全程无 OOM；③ 合成入库带情感元数据。

### P2 · emolib 情绪参考库（约 1 天）
- 候选打分脚本（f0 均值/方差 + RMS + 时长，combat 优先）、管理页试听打标、ref 模式全量接通。
- **验收**：每个强情绪标签（怒/喊/惊讶）≥3 条经人工确认的提弗洛斯本人参考；战斗怒吼预设音色/情绪均为角色本人。

### P3 · 行内情绪标记 + 多句拼接（约 1 天）
- 解析器、逐句合成、静音拼接、前端插入工具；长文本旁白自动利用 low_vram 分段。
- **验收**：4 行混合情绪剧本一次合成，句间情绪切换明显、音色一致、无爆音。

### 横向 · 效果评测（每阶段）
- 固定 10 句评测句（陈述/反问/感叹/命令/安慰），每预设出样，构建 A/B 盲听表（情绪可辨度 1–5、音色像角色 1–5、自然度 1–5）。
- 客观指标辅助：f0 均值/音域、能量动态、频谱平坦度（沿用 outputs/rvc_verify 的方法）。

---

## 8. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| 6GB 显存 OOM（qwen + GPT + vocoder 同驻，或与 RVC 并存） | 合成/转换崩溃 | 引擎互斥单例 + RVC 前强制换出；qwen 仅 text 模式懒加载；2.5 low_vram 自动分段；bf16；`use_cuda_kernel=False` 已验证 |
| IndexTTS RTF 异常高（曾测 ≈87） | 不可用 | P1 首查 GPU 占用（可能冷启动/误落 CPU）；合成异步 job + 进度日志；长句分段；必要时接受"精修用 IndexTTS，量产用 GSV"双引擎分工 |
| IndexTTS 零样本音色不如微调 GSV 像角色 | 音色漂移 | 双引擎并存按效果选用；最终统一经 RVC 收敛音色；P2 用角色本人 emo_ref 增强一致性 |
| 8 维无"疑惑/俏皮/嘲讽/严肃" | 预设表达不了 | 这些一律走 text 模式（Qwen T2E），alpha≤0.6 |
| 文本模式情感被 alpha 放大后出怪声 | 质量差 | text 模式硬限 alpha≤0.6（官方建议）；向量靠 0.8 归一化与官方 bias 兜底 |
| 强情绪经 RVC 出电流/毛刺 | 成品劣化 | strong 档 index_rate↓/protect↑/filter_radius=3；沿用已验证的"干声入 RVC"管线，禁止带 BGM 参考 |
| 路径/编码（中文路径、环境变量） | 加载失败 | 严格复刻 indextts_clone.py 的 sys.path 与 ModelScope 环境变量；Windows 路径统一 abs |
| 情感体系多套导致前后端不一致 | 维护灾难 | EMO_DIMS 顺序冻结、单一 EmotionSpec、预设单一数据源（后端 JSON，前端拉取不硬编码） |

## 9. 未来可选扩展（不在本期）

- CosyVoice 3 作为第三个引擎（instruct/方言/流式），抽象层已预留。
- ChatTTS 风格非语言填充音（笑声、停顿、hmm）作为文本后处理标记。
- 角色级"情绪画像"：从 emolib 统计该角色天然 f0/能量范围，预设按角色自动缩放。
- 情感强度与时长的词级控制（PROEMO 路线）。

## 10. 面向硬件升级的分层方案与显卡建议

核心思想：**系统启动时自动探测 VRAM，选择"硬件档位（tier）"，引擎管理器按档位决定驻留/换出策略**；同一套代码从 6GB 到 24GB 行为自动升级，换显卡只改配置不改架构。

### 10.1 硬件档位与引擎驻留矩阵

| 档位 | 显存 | TTS 驻留策略 | 与 RVC 关系 | 情感能力 | 体验 |
|---|---|---|---|---|---|
| **T0 当前** | 6GB | 任一时刻仅 1 个 TTS 引擎；IndexTTS low_vram 分段；qwen 按需加载 | RVC job 前强制换出 TTS；训练时 TTS 走 CPU（IndexTTS 返回 409 提示） | 全 17 预设（慢） | 单句精修可用，批量慢 |
| **T1 甜点** | 12GB | IndexTTS2.5（full profile 常驻）**或** GSV；CosyVoice3 FP16（4GB）可与 RVC 推理共驻 | TTS 与 RVC 串行但无需卸载（分段加载省 30s+/次） | 17 预设 + 笑场/耳语标签；短文本近实时 | **推荐升级目标** |
| **T2 舒适** | 16GB | IndexTTS2.5 + CosyVoice3 **双引擎常驻**（合计约 7–9GB） | RVC 推理常驻（2GB）共存；训练期间 TTS 仍可 GPU 推理 | 多引擎自动路由（见第 12 节）；流式 | 剧本批量生成、实时预览 |
| **T3 豪华** | 24GB+ | 再加 Qwen3-TTS-1.7B；GSV+IndexTTS+CV3 全驻 | 训练 + 三引擎推理互不干扰 | Best-of-N 多引擎各出一版自动盲听排序；可试 ZONOS2/Higgs（非商用） | 研究级工作台 |

档位探测：启动读 `torch.cuda.get_device_properties(...).total_memory`（IndexTTS 2.5 自身也是这样判 low_vram 的），写入状态接口；前端在引擎区显示当前档位与可共存引擎。用户可手动覆盖（防止显存被其他程序占用时误判）。

### 10.2 显卡选购建议（2026-09，中国大陆行情）

本工作负载的特殊性：**不吃算力，吃显存**——RVC 训练 6GB 就能跑，瓶颈是多引擎共驻与 RTF；且 GSV/RVC/IndexTTS/CosyVoice 全系 CUDA 生态，**只推荐 N 卡**（AMD 在 Windows 上 ROCm 支持差，ZONOS2 等新模型更是官方 Linux+CUDA）。内存建议同步升到 **32GB**（多 venv + 音频缓冲 + 未来 LLM 情绪导演）。

| 选择 | 型号 | 理由 | 参考价位 |
|---|---|---|---|
| **首选性价比** | **RTX 5060 Ti 16GB**（注意认准 16GB 版，另有 8GB 版别买错） | Blackwell、GDDR7 448GB/s、180W 不用换电源（600W）、16GB 一步到位到 T2 档；第五代 Tensor Core 支持 FP4 | ¥3000–3500 |
| 二手性价比 | RTX 3090 24GB | 24GB 直接 T3 档，训练/多引擎无敌；缺点 350W 功耗、需好电源与机箱散热、无保修 | ¥5000–6000（二手） |
| 均衡新机 | RTX 5070 Ti 16GB（256bit/896GB/s） | 比 5060Ti 带宽翻倍，RTF 更低，长文本/批量更爽；16GB 与 T2 档持平 | ¥6000–6800 |
| 不建议 | RTX 5070 12GB / 5060 8GB / 任何 8GB 卡 | 12GB 只到 T1，8GB 相对现在提升有限；一步到 16GB 最划算 | — |
| 未来旗舰 | RTX 5090 32GB（或等更新代际） | T3 满配，ZONOS2/Higgs 随便玩；价格是 5060Ti 的 5 倍以上，边际收益对本项目不高 | ¥20000+ |

**结论：¥3000 档的 RTX 5060 Ti 16GB 是本项目最优点**——从 T0 跳到 T2，双引擎常驻 + RVC 共存 + 笑场耳语标签 + 近实时 RTF，电源机箱都不用换。不必追旗舰：情感 TTS 的模型都很小（0.5–2B），32GB 显存对这套链路是浪费。

### 10.3 升级前后的行为对照（无需改代码的部分）

- T0 已实现的引擎互斥/懒加载/换出逻辑在 T1–T3 自动退化为"免换出"，代码路径不变。
- 预设 JSON、EmotionSpec、前端 UI 与显卡档位完全无关，升级零迁移成本。
- 唯一新增：T1 起安装 CosyVoice3 适配器（P4），T2 起开启自动路由。

## 11. 能力注册式引擎插件架构（v2.0 核心升级）

### 11.1 为什么必须这样做

v1 设计是"双引擎开关"，2026 年的现实是引擎半年一代（四个月内已新增 ZONOS2/Higgs3/Breeze2/Qwen3-TTS/CosyVoice3 五个）。把情感参数写死成 IndexTTS 的 8 维向量，等于每接一个引擎都要重写前后端。改为：

```
EmotionSpec（引擎无关的统一语义）
        │  CapabilityRegistry：查询每个引擎"能做什么、怎么做"
        ▼
EngineAdapter.compile(spec) → 该引擎自己的原生调用
  GsvAdapter       ：capabilities={ref, follow}
  IndexTtsAdapter  ：capabilities={vector8, ref, text, alpha0_1_6, duration}
  CosyVoice3Adapter：capabilities={tags[happy..whispers,laughs], instruct_text, stream, dialect}
  （未来）Qwen3TtsAdapter / ZonosAdapter …
```

### 11.2 引擎能力声明（静态注册表）

```python
class EngineCaps(BaseModel):
    id: str                       # "indextts2.5"
    license_ok: bool              # 仅 Apache/MIT 进生产
    vram_fp16_gb: float           # 4.0
    modes: list[EmoMode]          # 支持的统一模式
    extra_events: list[str]       # ["laugh","whisper","sigh"] 非语言事件
    streaming: bool
    languages: list[str]
    voice_ref_seconds: tuple      # (3, 15)
    pitch_control: bool
    output_sr: int

# 路由规则（按句子执行）：
# 1) spec 含非语言事件(laugh/whisper) 且引擎支持 → CosyVoice3
# 2) mode=vector8 → IndexTTS（唯一支持）
# 3) mode=text 且中文复杂语气 → IndexTTS(Qwen)；严肃/笑场/耳语 → CosyVoice3
# 4) 用户显式锁定引擎时不路由
# 5) 当前档位显存不足 → 按优先级换出或降级，并在 UI 明示
```

EmotionSpec 增加两个引擎无关字段：`events: list[{"type":"laugh|whisper|sigh|pause","at":"句首|句中|句尾","strength":0-1}]`。预设里"俏皮"可带 `laugh@尾`，"温柔安慰"可带 `whisper`——事件由支持的引擎实现，不支持的引擎降级为纯语气（比如 IndexTTS 用文本描述模拟"笑着说"）。

### 11.3 适配器接口（所有引擎实现同一接口）

```python
class TtsEngineAdapter(Protocol):
    caps: EngineCaps
    def load(self, profile, device) -> None: ...
    def unload(self) -> None: ...
    def synthesize(self, job: SynthJob) -> AudioResult: ...   # 引擎自行 compile spec
    def supports(self, spec: EmotionSpec) -> float: ...       # 返回 0-1 可胜任度，供路由器打分
```

P1 只实现 GSV/IndexTTS 两个适配器，但**接口按此协议一次定好**；P4 加 CosyVoice3 只新增一个文件 + 一条注册，不动路由/预设/前端逻辑。

## 12. 终极形态：LLM「情绪导演」+ 多引擎分工 + 评测闭环

分阶段全部完成后的"最最优"管线（复用项目已有的 [llm.py](file:///A:/Hypergryph%20Launcher/games/Arknights%20Endfield/EndfieldVoiceForge/apps/server/core/llm.py) / [chat 页](file:///A:/Hypergryph%20Launcher/games/Arknights%20Endfield/EndfieldVoiceForge/apps/web/app/chat/page.tsx)）：

```
剧本/台词原文
   │ ① 情绪导演（LLM，可本地 Qwen 也可云端，沿用现有 provider 配置）
   │   逐句输出：{文本, 预设, 强度, 事件[laugh/whisper], 停顿ms, 备注}
   ▼
② 引擎路由器（能力注册 + 硬件档位）逐句分派：
   生气(向量) → IndexTTS2.5 ｜ 笑场/耳语 → CosyVoice3 ｜ 音色基准句 → GSV
   ▼
③ 逐句干声 → 统一响度/采样率 → 句间停顿拼接
   ▼
④ RVC 按情绪档过一遍锁死提弗洛斯音色（强情绪 strong 档防伪影）
   ▼
⑤ Best-of-N：关键句每引擎出 2–3 版（不同 seed），客观指标(f0/能量/平坦度)
   + 前端 A/B 盲听打分，分数回写 library，形成预设调优闭环
```

这一形态回答了"最最优"：**不靠单一神模型，而靠统一语义层把各模型的长板拼起来**——IndexTTS 的中文八维情感、CosyVoice3 的笑场耳语与流式、GSV 微调音色的"像本人"、RVC 的最终音色锁定，各司其职；LLM 只当导演不当配音。硬件到位（T2）后全程自动，6GB 时降级为手动选引擎的单机模式，产出质量标准不变，只是慢与需手动。

## 13. 修订后的路线图

| 阶段 | 内容 | 硬件要求 | 变化（相对 v1） |
|---|---|---|---|
| P0 | GSV 情绪参考预设，先听到差异 | 6GB | 不变 |
| P1 | IndexTTS2.5 适配器 + 统一适配器接口（11.3 一次定好）+ 17 预设 | 6GB | 接口升级为插件协议，为 P4 铺路 |
| P2 | emolib 情绪参考库（combat 怒吼等本人情绪源） | 6GB | 不变 |
| P3 | 行内情绪标记 + 逐句拼接 | 6GB | 不变 |
| **P4** | **CosyVoice3 适配器**：Docker/WSL2 部署、笑声/耳语/严肃标签、事件字段、T1 档与 RVC 共驻 | 建议 ≥12GB（4bit 可在 6GB 试跑，不保证） | **新增** |
| P5 | 档位自动探测 + 多引擎路由器 + 双引擎常驻 | 16GB（T2） | **新增** |
| P6 | LLM 情绪导演 + Best-of-N 盲听闭环 + 流式实时对话 | 16GB+ | **新增** |

## 14. 参考资料

- IndexTTS 仓库：https://github.com/index-tts/index-tts
- IndexTTS2 论文：https://arxiv.org/abs/2506.21619 ；2.5 报告：https://index-tts.github.io/index-tts2-5.github.io/
- 情感控制 API 配方：https://deepwiki.com/tabortao/index-tts2/13.2-emotion-control-recipes ；https://pypi.org/project/indextts2-inference/
- CosyVoice：https://github.com/FunAudioLLM/CosyVoice
- ChatTTS：https://github.com/2noise/ChatTTS
- PROEMO（情感强度可控 TTS）：https://arxiv.org/pdf/2501.06276
- RVC 推理参数（protect/index_rate）：https://docs.aihub.gg/rvc/resources/inference-settings/
- CosyVoice 3 论文（arXiv 2505.17589）：https://arxiv.org/abs/2505.17589 ；仓库：https://github.com/FunAudioLLM/CosyVoice ；本地部署与 4GB FP16 要求可参考社区 Docker API：https://github.com/hsiang-han/CosyVoice3-API
- ZONOS2（Apache-2.0，8B MoE）：https://www.zyphra.com/our-work/zonos2
- Qwen3-TTS：https://github.com/QwenLM/Qwen3-TTS
- 2026 自托管 TTS 横评：https://offlinetts.com/blog/self-hosted-tts-guide-2026/ ；Windows 六模型实测：https://rarebuildsoftware.com/blog/best-open-source-voice-cloning-2026
