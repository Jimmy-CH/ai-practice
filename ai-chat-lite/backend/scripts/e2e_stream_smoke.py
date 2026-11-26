"""端到端冒烟：对着真实运行的 uvicorn + scripts/fake_upstream.py 验证流式链路。

前置：
    终端 A: python -m uvicorn scripts.fake_upstream:app --port 8011
    终端 B: 设 DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL=http://127.0.0.1:8011 后启动 app.main:app
运行：
    python scripts/e2e_stream_smoke.py            # 默认 http://127.0.0.1:8000
    $env:SMOKE_BASE_URL="http://127.0.0.1:8010"; python scripts/e2e_stream_smoke.py

覆盖：健康检查与静态资源、注册登录、完整流式、断线续传、运行中停止、上游错误、并发保护、越权与级联删除。
"""
import json
import os
import sys
import time
import uuid

import httpx

BASE = os.getenv("SMOKE_BASE_URL", "http://127.0.0.1:8000")


def parse(lines):
    """把 SSE 行迭代器解析成 (event, data) 事件。"""
    event, data = "message", []
    for line in lines:
        line = line.rstrip("\r")
        if line == "":
            if data:
                yield event, json.loads("\n".join(data))
            event, data = "message", []
        elif line.startswith(":"):
            continue
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].lstrip())
    if data:
        yield event, json.loads("\n".join(data))


def check(label, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {label} {detail}")
    if not ok:
        sys.exit(1)


c = httpx.Client(base_url=BASE, timeout=30)

# ---------- 基础链路 ----------
check("health", c.get("/api/health").json() == {"status": "ok"})
index = c.get("/")
check("index", index.status_code == 200 and 'id="auth-view"' in index.text)
for path in ("/app.js", "/markdown.js", "/styles.css"):
    check(f"static {path}", c.get(path).status_code == 200)

user = f"smoke_{uuid.uuid4().hex[:8]}"
check(
    "register",
    c.post("/api/auth/register", json={"username": user, "password": "smoke-pass-123"}).status_code == 201,
)
token = c.post("/api/auth/login", json={"username": user, "password": "smoke-pass-123"}).json()["access_token"]
c.headers["Authorization"] = f"Bearer {token}"
check("me", c.get("/api/users/me").json()["username"] == user)
check("unauthorized", httpx.get(f"{BASE}/api/users/me").status_code == 401)


def new_conv():
    return c.post("/api/conversations").json()["id"]


def send(cid, text):
    resp = c.post(f"/api/conversations/{cid}/messages", json={"content": text})
    return resp.status_code, resp.json()


# ---------- 场景 1：完整流式 ----------
cid = new_conv()
status, sent = send(cid, "你好")
check("send created", status == 201 and sent["assistant_message"]["status"] == "streaming", str(status))
mid = sent["assistant_message"]["id"]
check("auto title", c.get("/api/conversations").json()["items"][0]["title"] == "你好")

started = time.time()
stamps, events = [], []
with c.stream("GET", f"/api/messages/{mid}/stream?resume_from=-1") as resp:
    check("stream headers", resp.headers["content-type"].startswith("text/event-stream"))
    for event, data in parse(resp.iter_lines()):
        stamps.append(round(time.time() - started, 2))
        events.append(event)
        if event in ("done", "error"):
            final = data
            break
check("deltas streamed", events.count("delta") >= 5, f"n={events.count('delta')} stamps={stamps[:3]}")
check("progressively streamed", stamps[1] - stamps[0] > 0.03, f"gap={round(stamps[1] - stamps[0], 3)}s")
check("final done", final["status"] == "done", final["status"])
msgs = c.get(f"/api/conversations/{cid}/messages").json()["items"]
check("db persisted", msgs[-1]["status"] == "done" and msgs[-1]["content"] == final["content"])
check("conversation running=false", c.get("/api/conversations").json()["items"][0]["running"] is False)

# ---------- 场景 2：读一半断线，再 resume_from 续传 ----------
cid = new_conv()
_, sent = send(cid, "再讲一次")
mid = sent["assistant_message"]["id"]
seen = 0
last_seq = -1
with c.stream("GET", f"/api/messages/{mid}/stream?resume_from=-1") as resp:
    for event, data in parse(resp.iter_lines()):
        if event == "delta":
            seen += 1
            last_seq = data["seq"]
        if seen == 3:
            break  # 模拟前端断开
check("disconnect saw deltas", seen == 3 and last_seq == 2, f"last_seq={last_seq}")

time.sleep(0.6)  # 断开期间后台任务继续消费上游
resumed = []
with c.stream("GET", f"/api/messages/{mid}/stream?resume_from={last_seq}") as resp:
    for event, data in parse(resp.iter_lines()):
        if event == "delta":
            resumed.append(data["seq"])
        if event in ("done", "error"):
            final = data
            break
check(
    "resume continues",
    resumed[0] == last_seq + 1 and final["status"] == "done",
    f"first={resumed[0]} total={len(resumed)} status={final['status']}",
)
check("resume out of range 400", c.get(f"/api/messages/{mid}/stream?resume_from=999").status_code == 400)

# ---------- 场景 3：运行中停止 ----------
cid = new_conv()
_, sent = send(cid, "长一点")
mid = sent["assistant_message"]["id"]
partial = []
with c.stream("GET", f"/api/messages/{mid}/stream?resume_from=-1") as resp:
    gen = parse(resp.iter_lines())
    for event, data in gen:
        if event == "delta":
            partial.append(data["content"])
        if len(partial) == 3:
            break
    mid_stream = c.get(f"/api/conversations/{cid}/messages").json()["items"][-1]
    check("mid-stream db status", mid_stream["status"] == "streaming", mid_stream["status"])
    stop = c.post(f"/api/messages/{mid}/stop").json()
    check("stop status", stop["status"] == "stopped", stop["status"])
    for event, data in gen:
        if event in ("done", "error"):
            final = data
            break
check("stopped final", final["status"] == "stopped", final["status"])
check("partial persisted", final["content"].startswith("".join(partial)), f"content={final['content']!r}")
msgs = c.get(f"/api/conversations/{cid}/messages").json()["items"]
check("db stopped", msgs[-1]["status"] == "stopped")

# 已停止的会话再次订阅：回放缓冲的 delta，再补终止事件（会话在 TTL 内保留）
events = []
with c.stream("GET", f"/api/messages/{mid}/stream?resume_from=-1") as resp:
    for event, data in parse(resp.iter_lines()):
        events.append(event)
        if event in ("done", "error"):
            final = data
            break
check("stopped replay", events.count("delta") > 0 and events[-1] == "done" and final["status"] == "stopped", str(events))

# ---------- 场景 4：上游错误（需要假上游配合） ----------
cid = new_conv()
_, sent = send(cid, "SIMULATE_HTTP_ERROR 触发 502")
mid = sent["assistant_message"]["id"]
with c.stream("GET", f"/api/messages/{mid}/stream?resume_from=-1") as resp:
    for event, data in parse(resp.iter_lines()):
        if event in ("done", "error"):
            final = data
            break
check("error event", final.get("code") == "upstream_http", str(final))
msgs = c.get(f"/api/conversations/{cid}/messages").json()["items"]
check("failed persisted", msgs[-1]["status"] == "failed" and "502" in (msgs[-1]["error"] or ""))

# ---------- 场景 5：并发保护与越权 ----------
cid = new_conv()
send(cid, "占位")
status, _ = send(cid, "再发一条")
check("409 concurrent", status == 409, str(status))
last_mid = c.get(f"/api/conversations/{cid}/messages").json()["items"][-1]["id"]
c.post(f"/api/messages/{last_mid}/stop")
check("foreign 404", c.get("/api/conversations/999999/messages").status_code == 404)
check("delete 204", c.delete(f"/api/conversations/{cid}").status_code == 204)
check("cascade", c.get(f"/api/conversations/{cid}/messages").status_code == 404)

print("\nALL SMOKE CHECKS PASSED")
