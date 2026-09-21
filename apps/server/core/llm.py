"""云端 LLM / embedding 客户端（OpenAI 兼容协议）。

只用标准库 urllib，避免给 server 的 venv 增加依赖。
配置从 config.py 读（可用 .env / 环境变量覆盖），见 config.py 注释。

支持所有 OpenAI 兼容的接口：OpenAI / DeepSeek / Qwen(DashScope 兼容模式)
/ SiliconFlow / Moonshot / GLM 等。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from . import paths


class LlmError(RuntimeError):
    pass


def llm_enabled() -> bool:
    return bool(paths.LLM_API_KEY) and bool(paths.LLM_BASE_URL)


def embed_enabled() -> bool:
    return bool(paths.EMBED_API_KEY) and bool(paths.EMBED_BASE_URL)


def _post(url: str, api_key: str, payload: dict, timeout: float = 60.0) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            detail = ""
        raise LlmError(f"HTTP {e.code}: {detail[:500]}") from e
    except urllib.error.URLError as e:
        raise LlmError(f"network error: {e.reason}") from e


def _anthropic_url(base_url: str) -> str:
    """Anthropic Messages 端点：base_url 视为 origin（如 https://anyrouter.top），拼 /v1/messages。

    兼容用户把 base_url 直接填成 .../v1 的情况（自动去重 /v1）。
    """
    b = base_url.rstrip("/")
    if b.endswith("/v1"):
        b = b[:-3]
    return b + "/v1/messages"


def _post_anthropic(url: str, api_key: str, payload: dict, timeout: float = 120.0) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("x-api-key", api_key)
    req.add_header("anthropic-version", "2023-06-01")
    if paths.LLM_ANTHROPIC_BETA:
        req.add_header("anthropic-beta", paths.LLM_ANTHROPIC_BETA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            detail = ""
        raise LlmError(f"HTTP {e.code}: {detail[:500]}") from e
    except urllib.error.URLError as e:
        raise LlmError(f"network error: {e.reason}") from e


def anthropic_chat(messages: list[dict], temperature: float = 0.8, max_tokens: int = 512) -> str:
    """Anthropic Messages 原生协议：system 单独提出，其余 user/assistant 交替传入。"""
    system = ""
    msgs: list[dict] = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            system = content
        elif role in ("user", "assistant"):
            msgs.append({"role": role, "content": content})
    if not msgs:
        msgs = [{"role": "user", "content": ""}]

    url = _anthropic_url(paths.LLM_BASE_URL)
    payload: dict = {"model": paths.LLM_MODEL, "max_tokens": max_tokens, "messages": msgs}
    if system:
        payload["system"] = system
    if temperature > 0:
        payload["temperature"] = temperature

    out = _post_anthropic(url, paths.LLM_API_KEY, payload)
    try:
        return out["content"][0]["text"].strip()
    except (KeyError, IndexError, TypeError) as e:
        raise LlmError(f"unexpected anthropic response: {str(out)[:300]}") from e


def chat(messages: list[dict], temperature: float = 0.8, max_tokens: int = 512) -> str:
    """messages: [{"role": "system"|"user"|"assistant", "content": str}, ...] -> 回复文本。

    按 ENDFIELD_LLM_API_FORMAT 选择协议：openai（默认，Chat Completions）或 anthropic（Messages 原生）。
    """
    if not llm_enabled():
        raise LlmError("LLM 未配置：请在项目根目录 .env 里设置 ENDFIELD_LLM_API_KEY / ENDFIELD_LLM_BASE_URL")
    if (paths.LLM_API_FORMAT or "openai") == "anthropic":
        return anthropic_chat(messages, temperature, max_tokens)

    url = paths.LLM_BASE_URL.rstrip("/") + "/chat/completions"
    payload = {
        "model": paths.LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    out = _post(url, paths.LLM_API_KEY, payload)
    try:
        return out["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as e:
        raise LlmError(f"unexpected chat response: {str(out)[:300]}") from e


def _stream_openai(messages: list[dict], temperature: float, max_tokens: int):
    url = paths.LLM_BASE_URL.rstrip("/") + "/chat/completions"
    payload = {"model": paths.LLM_MODEL, "messages": messages, "temperature": temperature, "max_tokens": max_tokens, "stream": True}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {paths.LLM_API_KEY}")
    try:
        resp = urllib.request.urlopen(req, timeout=120)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise LlmError(f"HTTP {e.code}: {detail[:500]}") from e
    except urllib.error.URLError as e:
        raise LlmError(f"network error: {e.reason}") from e
    with resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
                delta = chunk["choices"][0]["delta"].get("content")
            except (ValueError, KeyError, IndexError, TypeError):
                continue
            if delta:
                yield delta


def _stream_anthropic(messages: list[dict], temperature: float, max_tokens: int):
    system = ""
    msgs: list[dict] = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            system = content
        elif role in ("user", "assistant"):
            msgs.append({"role": role, "content": content})
    if not msgs:
        msgs = [{"role": "user", "content": ""}]

    url = _anthropic_url(paths.LLM_BASE_URL)
    payload: dict = {"model": paths.LLM_MODEL, "max_tokens": max_tokens, "messages": msgs, "stream": True}
    if system:
        payload["system"] = system
    if temperature > 0:
        payload["temperature"] = temperature
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("x-api-key", paths.LLM_API_KEY)
    req.add_header("anthropic-version", "2023-06-01")
    if paths.LLM_ANTHROPIC_BETA:
        req.add_header("anthropic-beta", paths.LLM_ANTHROPIC_BETA)
    try:
        resp = urllib.request.urlopen(req, timeout=120)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise LlmError(f"HTTP {e.code}: {detail[:500]}") from e
    except urllib.error.URLError as e:
        raise LlmError(f"network error: {e.reason}") from e
    with resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            try:
                chunk = json.loads(data_str)
            except ValueError:
                continue
            if chunk.get("type") == "content_block_delta":
                text = chunk.get("delta", {}).get("text")
                if text:
                    yield text


def chat_stream(messages: list[dict], temperature: float = 0.8, max_tokens: int = 512):
    """流式生成回复，逐段 yield 文本。按 ENDFIELD_LLM_API_FORMAT 选择协议。"""
    if not llm_enabled():
        raise LlmError("LLM 未配置：请在项目根目录 .env 里设置 ENDFIELD_LLM_API_KEY / ENDFIELD_LLM_BASE_URL")
    if (paths.LLM_API_FORMAT or "openai") == "anthropic":
        yield from _stream_anthropic(messages, temperature, max_tokens)
    else:
        yield from _stream_openai(messages, temperature, max_tokens)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量向量化。返回与 texts 等长的 float 向量列表。"""
    if not texts:
        return []
    if not embed_enabled():
        raise LlmError("embedding 未配置：请在项目根目录 .env 里设置 ENDFIELD_EMBED_API_KEY / ENDFIELD_EMBED_BASE_URL")
    url = paths.EMBED_BASE_URL.rstrip("/") + "/embeddings"
    payload = {"model": paths.EMBED_MODEL, "input": texts}
    out = _post(url, paths.EMBED_API_KEY, payload)
    try:
        data = out["data"]
        data.sort(key=lambda x: x.get("index", 0))
        return [item["embedding"] for item in data]
    except (KeyError, TypeError) as e:
        raise LlmError(f"unexpected embedding response: {str(out)[:300]}") from e


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
