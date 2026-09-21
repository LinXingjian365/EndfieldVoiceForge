"""运行时配置：读写项目根目录 .env，改完即生效（无需重启 server）。

覆盖：LLM / embedding 的 base_url、api_key、model。
GET 返回脱敏后的 key（masked），POST 写入 .env 并同步到当前进程。
"""
from __future__ import annotations

import json
import os
import time
import uuid
import urllib.error
import urllib.request

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core import paths
from ..core import log
from ..core import providers

router = APIRouter(prefix="/config", tags=["config"])

_ENV_FILE = os.path.join(paths.ROOT, ".env")

# 请求字段 -> 环境变量名
_FIELD_TO_ENV = {
    "llm_base_url": "ENDFIELD_LLM_BASE_URL",
    "llm_api_key": "ENDFIELD_LLM_API_KEY",
    "llm_model": "ENDFIELD_LLM_MODEL",
    "llm_api_format": "ENDFIELD_LLM_API_FORMAT",
    "embed_base_url": "ENDFIELD_EMBED_BASE_URL",
    "embed_api_key": "ENDFIELD_EMBED_API_KEY",
    "embed_model": "ENDFIELD_EMBED_MODEL",
}

class ConfigUpdate(BaseModel):
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_api_format: str | None = None
    embed_base_url: str | None = None
    embed_api_key: str | None = None
    embed_model: str | None = None


def _mask(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}****{key[-4:]}"


def _snapshot() -> dict:
    return {
        "llm_base_url": paths.LLM_BASE_URL,
        "llm_api_key": _mask(paths.LLM_API_KEY),
        "llm_has_key": bool(paths.LLM_API_KEY),
        "llm_model": paths.LLM_MODEL,
        "llm_api_format": paths.LLM_API_FORMAT,
        "embed_base_url": paths.EMBED_BASE_URL,
        "embed_api_key": _mask(paths.EMBED_API_KEY),
        "embed_has_key": bool(paths.EMBED_API_KEY),
        "embed_model": paths.EMBED_MODEL,
        "env_file": _ENV_FILE,
    }


def _write_env(updates: dict[str, str]) -> None:
    """把 updates 写回 .env，保留注释与未知键。"""
    lines = []
    if os.path.isfile(_ENV_FILE):
        with open(_ENV_FILE, encoding="utf-8") as f:
            lines = f.read().splitlines()

    remaining = dict(updates)
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            out.append(line)
            continue
        k = line.split("=", 1)[0].strip()
        if k in remaining:
            out.append(f"{k}={remaining.pop(k)}")
        else:
            out.append(line)
    for k, v in remaining.items():
        out.append(f"{k}={v}")

    with open(_ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def _recompute() -> None:
    """按 config.py 的回退逻辑重算 paths 属性（embedding 未单独配置时回退到 LLM）。"""
    paths.LLM_BASE_URL = os.environ.get("ENDFIELD_LLM_BASE_URL", "")
    paths.LLM_API_KEY = os.environ.get("ENDFIELD_LLM_API_KEY", "")
    paths.LLM_MODEL = os.environ.get("ENDFIELD_LLM_MODEL", "")
    paths.LLM_API_FORMAT = os.environ.get("ENDFIELD_LLM_API_FORMAT", "openai").lower()
    paths.LLM_ANTHROPIC_BETA = os.environ.get("ENDFIELD_LLM_ANTHROPIC_BETA", "context-1m-2025-08-07")
    paths.EMBED_BASE_URL = os.environ.get("ENDFIELD_EMBED_BASE_URL", "") or paths.LLM_BASE_URL
    paths.EMBED_API_KEY = os.environ.get("ENDFIELD_EMBED_API_KEY", "") or paths.LLM_API_KEY
    paths.EMBED_MODEL = os.environ.get("ENDFIELD_EMBED_MODEL", "")


@router.get("")
def get_config():
    return _snapshot()


@router.post("")
def update_config(upd: ConfigUpdate):
    changes = upd.model_dump(exclude_none=True)
    if not changes:
        return _snapshot()

    # 1. 写回 .env
    env_updates = {_FIELD_TO_ENV[k]: v for k, v in changes.items()}
    _write_env(env_updates)

    # 2. 热更新当前进程
    for env_name, value in env_updates.items():
        os.environ[env_name] = value
    _recompute()

    # 记录变更（脱敏：不写 key）
    safe_fields = [k for k in changes if "key" not in k]
    log.info("配置已更新", fields=safe_fields)

    # 3. embedding 模型可能变了，重建检索向量（下次请求会重新向量化）
    from ..core import rag

    rag.reload()

    return _snapshot()


@router.get("/test")
def test_connection(base_url: str, api_key: str = "", format: str = "openai"):
    """连通测试：拉 /models 测可达性 + 延迟，返回 ok / latency_ms。"""
    if not base_url:
        return {"ok": False, "error": "缺少接口地址"}
    key = api_key or paths.LLM_API_KEY
    t0 = time.time()
    try:
        if format == "anthropic":
            b = base_url.rstrip("/")
            if b.endswith("/v1"):
                b = b[:-3]
            url = b + "/v1/models"
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/json")
            req.add_header("x-api-key", key)
            req.add_header("anthropic-version", "2023-06-01")
        else:
            url = base_url.rstrip("/") + "/models"
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/json")
            if key:
                req.add_header("Authorization", f"Bearer {key}")
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
        return {"ok": True, "status": status, "latency_ms": int((time.time() - t0) * 1000)}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "error": f"HTTP {e.code}", "latency_ms": int((time.time() - t0) * 1000)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "latency_ms": int((time.time() - t0) * 1000)}


@router.get("/providers")
def list_providers():
    """返回主流提供商预设（预填 base_url + 常用模型），供设置页一键填充。"""
    return {"providers": providers.PROVIDERS}


@router.get("/models")
def list_models(base_url: str, api_key: str = "", format: str = "openai"):
    """从上游拉取模型列表。openai 走 {base}/models，anthropic 走 {base}/v1/models。"""
    if not base_url:
        return {"models": []}
    key = api_key or paths.LLM_API_KEY
    if format == "anthropic":
        b = base_url.rstrip("/")
        if b.endswith("/v1"):
            b = b[:-3]
        url = b + "/v1/models"
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/json")
        req.add_header("x-api-key", key)
        req.add_header("anthropic-version", "2023-06-01")
    else:
        url = base_url.rstrip("/") + "/models"
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/json")
        if key:
            req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, ValueError, OSError) as e:
        return {"models": [], "error": f"拉取失败：{e}"}
    ids = sorted({m.get("id") for m in data.get("data", []) if isinstance(m, dict) and m.get("id")})
    return {"models": ids}


# ---- 保存的供应商（借鉴 cc-switch：多供应商管理 + 一键切换）----
_SAVED_FILE = os.path.join(paths.OUTPUTS_DIR, "saved_providers.json")


def _host(url: str) -> str:
    try:
        from urllib.parse import urlparse

        return urlparse(url).hostname or url
    except Exception:  # noqa: BLE001
        return url


def _load_saved() -> list[dict]:
    if not os.path.isfile(_SAVED_FILE):
        return []
    try:
        with open(_SAVED_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _dump_saved(items: list[dict]) -> None:
    with open(_SAVED_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


class SavedProvider(BaseModel):
    name: str = ""
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    format: str = "openai"
    color: str = "#888888"


@router.get("/saved")
def list_saved():
    return {"providers": _load_saved()}


@router.post("/saved")
def save_provider(p: SavedProvider):
    items = _load_saved()
    item = p.model_dump()
    item["id"] = uuid.uuid4().hex[:8]
    items.append(item)
    _dump_saved(items)
    log.info("已保存供应商", name=p.name or _host(p.base_url), model=p.model)
    return {"providers": items}


@router.delete("/saved/{pid}")
def delete_provider(pid: str):
    items = [p for p in _load_saved() if p.get("id") != pid]
    _dump_saved(items)
    return {"providers": items}


@router.post("/saved/{pid}/activate")
def activate_provider(pid: str):
    p = next((x for x in _load_saved() if x.get("id") == pid), None)
    if not p:
        raise HTTPException(404, "provider not found")
    env_updates = {
        "ENDFIELD_LLM_BASE_URL": p.get("base_url", ""),
        "ENDFIELD_LLM_MODEL": p.get("model", ""),
        "ENDFIELD_LLM_API_FORMAT": p.get("format", "openai"),
    }
    if p.get("api_key"):
        env_updates["ENDFIELD_LLM_API_KEY"] = p["api_key"]
    _write_env(env_updates)
    for k, v in env_updates.items():
        os.environ[k] = v
    _recompute()
    log.info("已切换供应商", name=p.get("name"), model=p.get("model"))
    return _snapshot()
