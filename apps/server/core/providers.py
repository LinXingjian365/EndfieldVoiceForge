"""主流 LLM / embedding 提供商预设（OpenAI 兼容协议）。

借鉴 cc-switch 的思路：预填常用大厂模型，支持自定义提供商，支持从上游拉取模型列表。
这里的 base_url / models 都是「预填常用值」，模型名随时间会变，用户在设置页可点「拉取模型列表」刷新。
"""
from __future__ import annotations

PROVIDERS: list[dict] = [
    {
        "id": "siliconflow",
        "name": "硅基流动 SiliconFlow",
        "base_url": "https://api.siliconflow.cn/v1",
        "models": [
            "deepseek-ai/DeepSeek-V3",
            "deepseek-ai/DeepSeek-R1",
            "Qwen/Qwen2.5-72B-Instruct",
            "Qwen/Qwen2.5-14B-Instruct",
            "Qwen/Qwen2.5-7B-Instruct",
        ],
        "embeds": ["BAAI/bge-m3", "BAAI/bge-large-zh-v1.5"],
        "default_model": "Qwen/Qwen2.5-7B-Instruct",
        "default_embed": "BAAI/bge-m3",
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "models": [
            "openai/gpt-4o",
            "anthropic/claude-sonnet-4-5",
            "google/gemini-2.5-flash",
            "deepseek/deepseek-chat-v3-0324",
        ],
        "embeds": [],
        "default_model": "anthropic/claude-sonnet-4-5",
        "default_embed": "",
    },
    {
        "id": "deepseek",
        "name": "DeepSeek 深度求索",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "embeds": [],
        "default_model": "deepseek-chat",
        "default_embed": "",
    },
    {
        "id": "qwen",
        "name": "阿里云百炼 DashScope",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-max", "qwen-plus", "qwen-turbo", "qwen-flash"],
        "embeds": ["text-embedding-v3", "text-embedding-v2"],
        "default_model": "qwen-plus",
        "default_embed": "text-embedding-v3",
    },
    {
        "id": "glm",
        "name": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": ["glm-4-plus", "glm-4-air", "glm-4-flash"],
        "embeds": ["embedding-3", "embedding-2"],
        "default_model": "glm-4-flash",
        "default_embed": "embedding-2",
    },
    {
        "id": "moonshot",
        "name": "月之暗面 Kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "embeds": [],
        "default_model": "moonshot-v1-8k",
        "default_embed": "",
    },
    {
        "id": "minimax",
        "name": "MiniMax",
        "base_url": "https://api.minimax.chat/v1",
        "models": ["MiniMax-Text-01", "abab6.5s-chat"],
        "embeds": [],
        "default_model": "MiniMax-Text-01",
        "default_embed": "",
    },
    {
        "id": "stepfun",
        "name": "阶跃星辰 StepFun",
        "base_url": "https://api.stepfun.com/v1",
        "models": ["step-2-16k", "step-1-8k"],
        "embeds": ["embedding-2"],
        "default_model": "step-1-8k",
        "default_embed": "",
    },
    {
        "id": "yi",
        "name": "零一万物 Yi",
        "base_url": "https://api.lingyiwanwu.com/v1",
        "models": ["yi-large", "yi-medium"],
        "embeds": [],
        "default_model": "yi-large",
        "default_embed": "",
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini"],
        "embeds": ["text-embedding-3-small", "text-embedding-3-large"],
        "default_model": "gpt-4o-mini",
        "default_embed": "text-embedding-3-small",
    },
]


def find(base_url: str) -> dict | None:
    for p in PROVIDERS:
        if p["base_url"].rstrip("/") == (base_url or "").rstrip("/"):
            return p
    return None


# 每个提供商的图标色 + 短名（设置页图标 chips 用，借鉴 cc-switch 的 ProviderIcon）
_META = {
    "siliconflow": ("#f97316", "SiliconFlow"),
    "openrouter": ("#94a3b8", "OpenRouter"),
    "deepseek": ("#4d6bfe", "DeepSeek"),
    "qwen": ("#7c3aed", "通义千问"),
    "glm": ("#2563eb", "智谱 GLM"),
    "moonshot": ("#a78bfa", "Kimi"),
    "minimax": ("#f43f5e", "MiniMax"),
    "stepfun": ("#0ea5e9", "阶跃"),
    "yi": ("#14b8a6", "零一万物"),
    "openai": ("#10a37f", "OpenAI"),
}

for _p in PROVIDERS:
    _color, _short = _META.get(_p["id"], ("#888888", _p["name"]))
    _p["color"] = _color
    _p["short"] = _short
    _p.setdefault("format", "openai")
