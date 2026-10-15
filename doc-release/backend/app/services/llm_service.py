"""LLM 业务化改写：分块 → 并发调用 → JSON 修复 → 合并与降级。"""

import asyncio
import json
import re

from app.config import settings
from app.prompts.docrelease_v1 import PROMPT_VERSION, SYSTEM_PROMPT_TEMPLATE, build_user_prompt
from app.services import glossary as glossary_svc
from app.services.errors import RunCancelled
from app.services.xingyu_api import generate_by_xingyu

_FEATURE_DEFAULTS: dict = {
    "tag": "技术重构", "risk": "中", "breaking": False, "title": "",
    "biz": "", "tech": "", "visible": "无", "scope": "", "acceptance": "",
    "action": "无需操作", "role": "研发", "paths": [],
}


def extract_json(text: str) -> dict:
    """从模型输出提取 JSON：剥离 code fence → 从首个 { 起做括号配平截取。"""
    t = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", t, re.S)
    if fence:
        t = fence.group(1)
    start = t.find("{")
    if start == -1:
        raise ValueError("输出中没有 JSON 对象")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(t)):
        ch = t[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(t[start:i + 1])
    raise ValueError("JSON 括号不配平")


def validate_payload(data) -> None:
    """校验 LLM 输出结构：features 必须为对象数组且每项含非空 title。"""
    if not isinstance(data, dict):
        raise ValueError("输出不是 JSON 对象")
    features = data.get("features")
    if not isinstance(features, list):
        raise ValueError("features 必须是数组")
    for f in features:
        if not isinstance(f, dict):
            raise ValueError("features 元素必须是对象")
        if not str(f.get("title") or "").strip():
            raise ValueError("功能点缺少非空 title")
    if data.get("highlights") is not None and not isinstance(data.get("highlights"), list):
        raise ValueError("highlights 必须是数组")


def build_chunks(changeset: dict, max_files: int = 8, max_lines: int = 600) -> list[dict]:
    """按模块聚类分块；单块超限时按文件继续拆（同名追加序号）。"""
    files_by_path = {f["path"]: f for f in changeset["files"]}
    chunks: list[dict] = []
    for module in changeset["modules"]:
        group = [files_by_path[p] for p in module["files"] if p in files_by_path]
        current: list[dict] = []
        current_lines = 0
        for f in group:
            cost = max(len(f.get("lines", [])), 1)
            if current and (len(current) >= max_files or current_lines + cost > max_lines):
                chunks.append({"name": module["name"], "files": current})
                current, current_lines = [], 0
            current.append(f)
            current_lines += cost
        if current:
            chunks.append({"name": module["name"], "files": current})

    counts: dict[str, int] = {}
    for c in chunks:
        counts[c["name"]] = counts.get(c["name"], 0) + 1
    seen: dict[str, int] = {}
    for c in chunks:
        if counts[c["name"]] > 1:
            seen[c["name"]] = seen.get(c["name"], 0) + 1
            c["name"] = f"{c['name']}·{seen[c['name']]}"
    return chunks


async def _chat(system_prompt: str, user_prompt: str) -> str:
    if settings.llm_provider == "deepseek":
        return await _chat_deepseek(system_prompt, user_prompt)
    return await generate_by_xingyu(system_prompt, user_prompt)


async def _chat_deepseek(system_prompt: str, user_prompt: str) -> str:
    if not settings.deepseek_api_key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY")
    import httpx

    async with httpx.AsyncClient(timeout=settings.llm_timeout) as client:
        resp = await client.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
            json={
                "model": "deepseek-chat",
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def _rewrite_chunk(chunk: dict, sem: asyncio.Semaphore, system_prompt: str,
                         cancel_check=None) -> dict:
    user_prompt = build_user_prompt(chunk)
    async with sem:
        last_error = ""
        for attempt in (1, 2):
            # 取消检查须在每次 LLM 调用前执行，避免已取消的任务继续等待并发配额
            if cancel_check is not None and cancel_check():
                raise RunCancelled("运行已取消")
            try:
                prompt = user_prompt
                if attempt == 2:
                    prompt += "\n\n注意：只输出 JSON 对象本身，不要任何解释文字。"
                text = await _chat(system_prompt, prompt)
                data = extract_json(text)
                validate_payload(data)
                return {"ok": True, "chunk": chunk, "data": data, "output": text}
            except RunCancelled:
                raise  # 取消不是失败，不得进入重试
            except Exception as exc:  # noqa: BLE001 —— 解析/请求失败均重试一次
                last_error = str(exc)
        return {"ok": False, "chunk": chunk, "error": last_error or "未知错误"}


async def rewrite_changes(changeset: dict, cancel_check=None) -> dict:
    """把变更集改写为功能点结构；取消在分块启动前与每次 LLM 调用前生效。"""
    chunks = build_chunks(changeset)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(glossary=glossary_svc.build_glossary_prompt_section())
    sem = asyncio.Semaphore(max(1, settings.llm_max_concurrency))
    tasks = []
    for c in chunks:
        if cancel_check is not None and cancel_check():
            raise RunCancelled("运行已取消")
        tasks.append(asyncio.create_task(_rewrite_chunk(c, sem, system_prompt, cancel_check)))
    try:
        results = await asyncio.gather(*tasks)
    except RunCancelled:
        # 单块取消即整体取消：终止其余分块并等待退出，避免任务悬挂
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    return merge_results(results, changeset)


def _fill_feature_defaults(f: dict) -> dict:
    out = dict(_FEATURE_DEFAULTS)
    if isinstance(f, dict):
        out.update({k: v for k, v in f.items() if k in _FEATURE_DEFAULTS})
    out["title"] = str(out.get("title") or "").strip()
    if not isinstance(out.get("paths"), list):
        out["paths"] = []
    return out


def _degraded_feature(chunk: dict, error: str) -> dict:
    return _fill_feature_defaults({
        "tag": "技术重构", "risk": "中",
        "title": f"{chunk['name']} 变更待人工确认",
        "biz": "该模块的变更未能自动生成业务描述，请在发布前人工确认影响面。",
        "tech": "LLM 改写失败：" + (error or "")[:120],
        "visible": "待确认", "scope": chunk["name"],
        "acceptance": "人工核对 diff 与符号变更",
        "action": "人工确认该模块变更内容",
        "paths": [f["path"] for f in chunk["files"]][:8],
    })


def merge_results(results: list[dict], changeset: dict) -> dict:
    features: list[dict] = []
    seen_titles: set[str] = set()
    highlights: list[str] = []
    low_confidence: list[str] = []
    confidences: list[float] = []
    input_chars = output_chars = 0
    ok_count = 0
    chunk_logs: list[dict] = []

    for r in results:
        chunk = r["chunk"]
        if not r["ok"]:
            error = r.get("error", "")
            features.append(_degraded_feature(chunk, error))
            low_confidence.append(f"{chunk['name']}：LLM 改写失败（{error[:80]}）")
            chunk_logs.append({"chunk": chunk["name"], "ok": False, "error": error[:200]})
            continue
        ok_count += 1
        data = r["data"]
        for raw in data.get("features") or []:
            f = _fill_feature_defaults(raw)
            if not f["title"] or f["title"] in seen_titles:
                continue
            seen_titles.add(f["title"])
            features.append(f)
        for h in data.get("highlights") or []:
            h = str(h).strip()
            if h and h not in highlights:
                highlights.append(h)
        conf = data.get("confidence")
        if isinstance(conf, (int, float)):
            confidences.append(float(conf))
        input_chars += len(build_user_prompt(chunk))
        output_chars += len(r.get("output") or "")
        chunk_logs.append({"chunk": chunk["name"], "ok": True,
                           "features": len(data.get("features") or [])})

    for sig in changeset.get("contract_signals", []):
        text = f"契约变更：{sig['message']}"
        if text not in highlights:
            highlights.append(text)

    glossary_hits = len(glossary_svc.match_terms(
        " ".join(f"{f['title']} {f['biz']} {f['tech']}" for f in features)))

    all_failed = ok_count == 0
    model = ("deepseek-chat" if settings.llm_provider == "deepseek"
             else f"xingyu:{settings.robot_code}")
    return {
        "ok": not all_failed,
        "all_failed": all_failed,
        "features": features,
        "highlights": highlights,
        "lowConfidence": low_confidence,
        "chunk_logs": chunk_logs,
        "llm": {
            "provider": settings.llm_provider,
            "model": model,
            "prompt": PROMPT_VERSION,
            "confidence": round(sum(confidences) / len(confidences), 2) if confidences else 0.0,
            "inputChars": input_chars,
            "outputChars": output_chars,
            "glossaryHits": glossary_hits,
            "lowConfidence": low_confidence,
        },
    }
