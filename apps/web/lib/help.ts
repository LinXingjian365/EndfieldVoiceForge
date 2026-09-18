/** 所有参数的新手说明。key 用在 <Field help="..."> 里做悬浮提示,同时渲染成 /guide 页。 */

export interface HelpEntry {
  /** 一句话:这个东西是什么 */
  what: string;
  /** 调大 / 调小会怎样 */
  effect?: string;
  /** 建议值 */
  tip?: string;
}

export const HELP = {
  /* ---------- 合成:采样 ---------- */
  top_k: {
    what: "每一步生成时,只从概率最高的前 k 个候选里挑。",
    effect: "小 → 更稳、更像参考音频,但可能呆板;大 → 更多变化,可能出怪音。",
    tip: "15 是默认。读不稳、有杂音时降到 5–10;想要更自然的语气可试 20–30。",
  },
  top_p: {
    what: "核采样。把候选按概率从高到低累加,累加到 p 就截断,只从这些里挑。",
    effect: "1.0 = 不截断;越小候选越少、越保守。",
    tip: "一般保持 1.0,让 top_k 起作用就够。念错字多时可降到 0.8。",
  },
  temperature: {
    what: "随机性温度。控制候选概率分布的“平”与“尖”。",
    effect: "低(0.3–0.7)→ 语调平稳、复读性强;高(>1)→ 情绪起伏大但容易崩坏、拖音。",
    tip: "默认 1.0。台词是叙述句用 0.6–0.8;感叹、撒娇类可 1.0–1.2。",
  },
  speed_factor: {
    what: "语速倍率,直接对生成音频做时间伸缩。",
    effect: "1.0 原速;0.8 慢 20%;1.2 快 20%。",
    tip: "提弗洛斯原声偏慢,0.9–1.0 最自然;超过 1.3 会有金属感。",
  },
  repetition_penalty: {
    what: "重复惩罚。已经生成过的语义 token 再出现时概率被压低。",
    effect: "越大越不容易复读、拖长音;太大会吞字。",
    tip: "默认 1.35。出现“啊啊啊”复读或尾音无限拖长时调到 1.5;吞字则降到 1.2。",
  },
  seed: {
    what: "随机种子。同样的文本 + 参考 + 参数 + seed,结果完全一样。",
    effect: "-1 = 每次随机。填固定数字可复现某次满意的结果。",
    tip: "调参数对比时固定 seed(比如 1234),否则分不清是参数还是运气的差别。",
  },
  text_split_method: {
    what: "长文本怎么切成一句句去合成。模型一次只能处理几十个字,太长会崩。",
    effect: "“按标点切”最稳;“不切”只适合一句话;“凑50字一切”适合长段落。",
    tip: "默认“按标点切”。台词有很多逗号导致断句太碎时,换成“凑四句一切”。",
  },
  text_lang: {
    what: "要合成文本的语种。决定怎么把文字转成音素。",
    tip: "中文台词选“中文”;中英混杂选“中文”也行(模型会按拼音+英文处理);“自动”会多一步检测,稍慢。",
  },
  prompt_lang: {
    what: "参考音频里说的是什么语言。",
    tip: "和参考音频实际内容一致即可,提弗洛斯的都是中文。",
  },
  prompt_text: {
    what: "参考音频里说的那句话的文字。模型靠它把“声音”和“文字”对上,学会这个人怎么发音。",
    effect: "写错会导致音色偏、语调怪。",
    tip: "用「识别参考文本」自动填,再人工校对标点。参考音频 3–10 秒、干净无杂音最好。",
  },
  ref_audio: {
    what: "参考音频。模型模仿它的音色、语气、语速。",
    effect: "换一条不同情绪的参考,合成出来的情绪就会跟着变。",
    tip: "想要撒娇语气就挑一条撒娇的台词做参考;想要严肃就挑严肃的。数据集里都是可用的。",
  },
  /* ---------- 合成:高级 ---------- */
  fragment_interval: {
    what: "切分后的句子之间插入多长的静音(秒)。",
    tip: "0.3 自然;对话感要紧凑用 0.15;念旁白用 0.5。",
  },
  batch_size: {
    what: "一次并行合成多少句。",
    effect: "大 → 快但吃显存;6 GB 显卡建议 1–4。",
    tip: "只合成一两句时无所谓;长文本可开 4 提速。",
  },
  batch_threshold: {
    what: "并行分批时,句子长度相差多少以内才放进同一批。",
    tip: "默认 0.75,一般不用动。",
  },
  parallel_infer: {
    what: "多句并行推理。关掉就一句一句串行。",
    tip: "开着更快。出现显存不足时关掉。",
  },
  split_bucket: {
    what: "把长度相近的句子分到一个桶里一起算,减少 padding 浪费。",
    tip: "保持开启。",
  },
  sample_steps: {
    what: "v3/v4 版本扩散模型的去噪步数。v2 无效。",
    effect: "步数多 → 音质细腻但慢。",
    tip: "v2 模型忽略此项。",
  },
  super_sampling: {
    what: "v3 版本把 24k 音频超采样到 48k。v2 无效。",
    tip: "v2 模型忽略此项。",
  },
  gpt_weight: {
    what: "GPT 权重(.ckpt):负责“文字 → 语义 token”,决定语调、停顿、情感节奏。",
    tip: "epoch 越大越像训练集的说话方式,但过大会过拟合(只会训练集里的语气)。e15–e20 之间挑。",
  },
  sovits_weight: {
    what: "SoVITS 权重(.pth):负责“语义 token → 波形”,决定音色本身。",
    tip: "和 GPT 权重独立选;用模型页 A/B 试听比对 e12 / e16 / e20 / e22。",
  },
  /* ---------- 训练 ---------- */
  exp: {
    what: "实验名。所有中间产物和权重都以它命名(logs/<exp>/、<exp>-eN.ckpt)。",
    tip: "一个角色一个名字,如 typhoea。改名 = 从头开始新实验。",
  },
  version: {
    what: "GPT-SoVITS 模型版本。v2 最成熟;v2Pro/v2ProPlus 多一个说话人向量;v3/v4 用扩散模型音质更好但吃显存。",
    tip: "6 GB 显卡用 v2。其他版本需要先下载对应预训练权重。",
  },
  format_1a: { what: "文本 → 音素 + BERT 特征。读 .list 里的台词文本。", tip: "改了台词文本要重跑。" },
  format_1b: { what: "音频 → HuBERT 语义特征,并重采样到 32 kHz。", tip: "最慢的一步,改了音频要重跑。" },
  format_1sv: { what: "提取说话人向量(仅 v2Pro/v2ProPlus 需要)。" },
  format_1c: { what: "HuBERT 特征 → 离散语义 token。依赖 1b。" },
  s2_epochs: {
    what: "SoVITS 训练总轮数。一轮 = 把全部训练音频过一遍。",
    effect: "少 → 音色不像;多 → 过拟合(只会训练集那几句的发音)。",
    tip: "254 条数据 8–20 轮足够。已有 e20 时填 22 就是再训 2 轮(续训)。填的数小于等于已训轮数会立刻结束。",
  },
  s1_epochs: {
    what: "GPT 训练总轮数。",
    tip: "GPT 更容易过拟合,15 轮左右,再多语调会僵。",
  },
  train_batch: {
    what: "每步同时训练几条音频。",
    effect: "大 → 稳但吃显存。",
    tip: "6 GB 显卡只能 1。",
  },
  save_every: { what: "每几轮保存一个权重文件。", tip: "1 = 每轮都存,方便 A/B 挑最佳;磁盘每个 SoVITS 权重 81 MB、GPT 150 MB。" },
  text_low_lr_rate: {
    what: "文本编码器的学习率相对系数。文本部分已经在预训练里学好了,压低它避免被小数据集带偏。",
    tip: "默认 0.4,不用动。",
  },
  grad_ckpt: { what: "梯度检查点:用重算换显存。", tip: "6 GB 必开,会慢 20%。" },
  resume: {
    what: "从 logs/<exp>/logs_s2_v2/ 里最新的 G/D 检查点继续训。关掉则删掉它们从预训练重新开始。",
    tip: "正常保持开启。想换 batch/学习率重头训才关。",
  },
  if_dpo: { what: "GPT 用 DPO 偏好训练,理论上更少复读,但显存翻倍。", tip: "6 GB 关掉。" },
  lora_rank: { what: "v3/v4 的 LoRA 秩。越大可训练参数越多。", tip: "v2 无效。" },
  /* ---------- RVC ---------- */
  rvc_what: {
    what: "RVC(检索式声音转换):输入任意人声音频,把音色换成提弗洛斯,内容、节奏、情绪原样保留。GPT-SoVITS 只能念文字,呻吟、喘息、受击这类非语言人声要靠 RVC。",
    tip: "找一段情绪、节奏你满意的人声(自己录也行),工具页「RVC 音色转换」上传即可。",
  },
  rvc_index_rate: {
    what: "检索强度。RVC 会在训练集特征库里找最像的片段替换进来,这个值是替换比例。",
    effect: "0 = 不检索,完全靠模型;1 = 最大程度贴训练集音色,但输入内容会被“拉”向训练集,可能失真。",
    tip: "语音 0.5–0.75;呻吟喘息这种训练集里没有的声音用 0.2–0.4,否则会被强行拉成说话声。",
  },
  rvc_pitch: {
    what: "整体变调,半音为单位。",
    effect: "+12 = 高一个八度。男声转女声通常 +12,女→女 0。",
    tip: "输入本来就是女声就填 0;男声源填 +8 到 +12。",
  },
  rvc_protect: {
    what: "保护清辅音和气息声不被变调污染。",
    effect: "0.5 = 关闭保护;越小保护越强但可能损失一点音色相似度。",
    tip: "默认 0.33。喘息声很多时可降到 0.2 保留气声。",
  },
  rvc_rms: {
    what: "音量包络混合。0 = 完全沿用输入音量起伏;1 = 完全用模型输出的音量。",
    tip: "呻吟喘息保留原音量起伏更自然,用 0.2–0.5。",
  },
  rvc_f0_method: {
    what: "音高提取算法。rmvpe 最准最抗噪;pm 快但粗糙。",
    tip: "一律 rmvpe。",
  },
  rvc_total_epoch: {
    what: "RVC 训练总轮数。DeepSeek 之前只跑到 e20 / 200 就停了。",
    effect: "RVC 通常 50–100 轮基本可用,200 轮更稳。每轮约 2 分钟。",
    tip: "填 100 就是从 e20 继续再训 80 轮(约 3 小时)。训练期间显卡被占用,不能合成。",
  },
  rvc_save_every: { what: "每几轮存一次检查点并导出小模型到 assets/weights/。", tip: "10。" },
  rvc_index: {
    what: "faiss 特征索引。把训练集的 HuBERT 特征建成可检索的库,index_rate > 0 时用到。",
    tip: "训练完新轮数不需要重建(索引只依赖训练集特征,不依赖模型)。",
  },
  /* ---------- 工具 ---------- */
  uvr5: { what: "人声/伴奏分离。从带 BGM 的音频里抠出干声。", tip: "HP5 更适合去伴奏,HP2 保留更多人声细节。" },
  slice_threshold: { what: "低于此分贝算静音,用来找切点。", tip: "-34 默认;背景噪音大时调到 -40 以下。" },
  slice_min_length: { what: "切出来的片段至少多长(毫秒)。", tip: "训练用 4000–10000。" },
  slice_min_interval: { what: "两个切点之间的最小静音时长(毫秒)。", tip: "300。" },
  slice_max_sil_kept: { what: "每个片段首尾最多保留多少静音(毫秒)。", tip: "500。" },
  denoise: { what: "基于 FRCRN 的降噪。对轻微底噪有效,重噪会损伤音质。", tip: "先试 float16;结果发闷换 float32。" },
  asr_backend: { what: "语音识别引擎。Fun-ASR 中文更准;Faster Whisper 多语种。", tip: "中文用 Fun-ASR。" },
} satisfies Record<string, HelpEntry>;

export type HelpKey = keyof typeof HELP;

/** /guide 页的章节组织 */
export const GUIDE_SECTIONS: { title: string; en: string; intro: string; keys: HelpKey[] }[] = [
  {
    title: "五分钟上手",
    en: "QUICKSTART",
    intro: "合成页 → 左侧参考音频默认已填 → 中间输入要说的话 → 右下「生成语音」。听到结果后再回来看参数。",
    keys: ["ref_audio", "prompt_text", "text_lang", "text_split_method"],
  },
  {
    title: "采样参数",
    en: "SAMPLING",
    intro: "这些决定“同一句话怎么说”。先动 temperature 和 top_k,其他保持默认。",
    keys: ["top_k", "top_p", "temperature", "speed_factor", "repetition_penalty", "seed"],
  },
  {
    title: "高级参数",
    en: "ADVANCED",
    intro: "一般不用碰。显存不够或长文本时才调。",
    keys: ["fragment_interval", "batch_size", "batch_threshold", "parallel_infer", "split_bucket", "sample_steps", "super_sampling"],
  },
  {
    title: "权重(模型文件)",
    en: "WEIGHTS",
    intro: "GPT-SoVITS 是两个模型配合:GPT 管“怎么说”,SoVITS 管“什么声音”。",
    keys: ["gpt_weight", "sovits_weight"],
  },
  {
    title: "训练",
    en: "TRAINING",
    intro: "顺序:格式化 1a→1b→1c(一次即可) → SoVITS(s2) → GPT(s1)。6 GB 显卡训练前引擎会自动卸载,主机内存要留 4 GB 以上。",
    keys: ["exp", "version", "format_1a", "format_1b", "format_1sv", "format_1c", "s2_epochs", "s1_epochs", "train_batch", "save_every", "text_low_lr_rate", "grad_ckpt", "resume", "if_dpo", "lora_rank"],
  },
  {
    title: "RVC 音色转换(呻吟 / 喘息 / 非语言人声)",
    en: "RVC",
    intro: "TTS 只会念字。要“非语言人声”有两条路:直接用游戏原声(解包里 97% 就是这类音效,零失真);或者拿任意一段人声用 RVC 换成提弗洛斯音色。",
    keys: ["rvc_what", "rvc_index_rate", "rvc_pitch", "rvc_protect", "rvc_rms", "rvc_f0_method", "rvc_total_epoch", "rvc_save_every", "rvc_index"],
  },
  {
    title: "工具",
    en: "TOOLS",
    intro: "给新数据做预处理用。已有的提弗洛斯数据集不需要再过这些。",
    keys: ["uvr5", "slice_threshold", "slice_min_length", "slice_min_interval", "slice_max_sil_kept", "denoise", "asr_backend"],
  },
];
