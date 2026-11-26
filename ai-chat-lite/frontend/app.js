// AI Chat Lite 原生前端：fetch + ReadableStream 解析 SSE，无框架、无构建链。
const TOKEN_KEY = "ai-chat-lite-token";
const MAX_RETRIES = 3;
const RETRY_BASE_MS = 1000;
const INACTIVITY_MS = 60000;

const els = {
  authView: document.getElementById("auth-view"),
  appView: document.getElementById("app-view"),
  authForm: document.getElementById("auth-form"),
  authHint: document.getElementById("auth-hint"),
  authSubmit: document.getElementById("auth-submit"),
  authToggle: document.getElementById("auth-toggle"),
  authError: document.getElementById("auth-error"),
  username: document.getElementById("username"),
  password: document.getElementById("password"),
  list: document.getElementById("conversation-list"),
  newChat: document.getElementById("new-chat"),
  currentUser: document.getElementById("current-user"),
  logout: document.getElementById("logout"),
  chatTitle: document.getElementById("chat-title"),
  chatStatus: document.getElementById("chat-status"),
  messageList: document.getElementById("message-list"),
  composer: document.getElementById("composer"),
  input: document.getElementById("input"),
  send: document.getElementById("send"),
  stop: document.getElementById("stop"),
  chatError: document.getElementById("chat-error"),
};

const state = {
  token: localStorage.getItem(TOKEN_KEY) || "",
  authMode: "login",
  conversations: [],
  currentId: null,
  messages: [],
  stream: null,
};

const pendingText = new Map();
let rafId = null;
let stickToBottom = true;

// ---------------- 基础请求 ----------------

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body) headers["Content-Type"] = "application/json";
  if (state.token) headers["Authorization"] = `Bearer ${state.token}`;

  const resp = await fetch(path, { ...options, headers });
  if (resp.status === 401) {
    logout("登录已失效，请重新登录");
    throw new Error("登录已失效");
  }
  if (!resp.ok) {
    let detail = `请求失败（${resp.status}）`;
    try {
      const data = await resp.json();
      if (typeof data.detail === "string") detail = data.detail;
    } catch (_) {
      /* 响应不是 JSON 时保留默认提示 */
    }
    throw new Error(detail);
  }
  if (resp.status === 204) return null;
  return resp.json();
}

function showError(el, message) {
  el.textContent = message;
  el.hidden = !message;
}

function setStatus(text) {
  els.chatStatus.textContent = text || "";
}

// ---------------- 认证 ----------------

function setAuthMode(mode) {
  state.authMode = mode;
  const isLogin = mode === "login";
  els.authHint.textContent = isLogin ? "登录后开始多轮流式对话" : "注册新账号后自动登录";
  els.authSubmit.textContent = isLogin ? "登录" : "注册";
  els.authToggle.textContent = isLogin ? "没有账号？去注册" : "已有账号？去登录";
  els.password.autocomplete = isLogin ? "current-password" : "new-password";
  showError(els.authError, "");
}

function showApp() {
  els.authView.hidden = true;
  els.appView.hidden = false;
}

function showAuth() {
  els.appView.hidden = true;
  els.authView.hidden = false;
  els.username.focus();
}

async function handleAuthSubmit(event) {
  event.preventDefault();
  const username = els.username.value.trim();
  const password = els.password.value;
  showError(els.authError, "");
  els.authSubmit.disabled = true;

  try {
    if (state.authMode === "register") {
      await api("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
    }
    const data = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    state.token = data.access_token;
    localStorage.setItem(TOKEN_KEY, state.token);
    els.authForm.reset();
    await bootstrap();
  } catch (err) {
    showError(els.authError, err.message);
  } finally {
    els.authSubmit.disabled = false;
  }
}

function logout(message) {
  detachStream();
  state.token = "";
  state.conversations = [];
  state.currentId = null;
  state.messages = [];
  localStorage.removeItem(TOKEN_KEY);
  els.currentUser.textContent = "";
  els.list.innerHTML = "";
  els.messageList.innerHTML = "";
  els.chatTitle.textContent = "新对话";
  setStatus("");
  showAuth();
  if (message) showError(els.authError, message);
}

async function bootstrap() {
  const me = await api("/api/users/me");
  els.currentUser.textContent = me.username;
  showApp();
  await refreshConversations();
  if (state.conversations.length > 0) {
    await selectConversation(state.conversations[0].id);
  } else {
    showEmptyState();
  }
}

// ---------------- 会话列表 ----------------

async function refreshConversations() {
  const data = await api("/api/conversations");
  state.conversations = data.items;
  renderConversations();
  const current = state.conversations.find((c) => c.id === state.currentId);
  if (current) els.chatTitle.textContent = current.title;
}

function renderConversations() {
  els.list.innerHTML = "";
  for (const conv of state.conversations) {
    const li = document.createElement("li");
    li.className = "conv-item" + (conv.id === state.currentId ? " active" : "");
    li.dataset.id = String(conv.id);

    const title = document.createElement("span");
    title.className = "conv-title";
    title.textContent = conv.title;
    title.title = conv.title;

    li.appendChild(title);

    if (conv.running) {
      const dot = document.createElement("span");
      dot.className = "conv-dot";
      dot.title = "生成中";
      li.appendChild(dot);
    }

    const del = document.createElement("button");
    del.type = "button";
    del.className = "conv-delete";
    del.textContent = "×";
    del.title = "删除会话";
    del.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteConversation(conv.id);
    });
    li.appendChild(del);

    li.addEventListener("click", () => selectConversation(conv.id));
    els.list.appendChild(li);
  }
}

async function createConversation() {
  detachStream();
  setComposerBusy(false);
  try {
    const conv = await api("/api/conversations", { method: "POST" });
    state.conversations.unshift(conv);
    state.currentId = conv.id;
    state.messages = [];
    els.chatTitle.textContent = conv.title;
    renderMessages();
    renderConversations();
    els.input.focus();
  } catch (err) {
    showError(els.chatError, err.message);
  }
}

async function deleteConversation(id) {
  if (!window.confirm("删除后无法恢复，确定删除该会话吗？")) return;
  try {
    await api(`/api/conversations/${id}`, { method: "DELETE" });
    if (state.currentId === id) {
      detachStream();
      state.currentId = null;
      state.messages = [];
      els.chatTitle.textContent = "新对话";
      showEmptyState();
    }
    await refreshConversations();
    if (!state.currentId && state.conversations.length > 0) {
      await selectConversation(state.conversations[0].id);
    }
  } catch (err) {
    showError(els.chatError, err.message);
  }
}

async function selectConversation(id) {
  if (state.currentId === id && state.stream) return;
  detachStream();
  setComposerBusy(false);
  state.currentId = id;
  const conv = state.conversations.find((c) => c.id === id);
  if (conv) els.chatTitle.textContent = conv.title;
  renderConversations();

  try {
    const data = await api(`/api/conversations/${id}/messages`);
    state.messages = data.items;
    renderMessages();

    const last = state.messages[state.messages.length - 1];
    if (last && last.role === "assistant" && last.status === "streaming") {
      // 运行中消息以服务端 buffer 为权威：清空本地部分内容后从头订阅
      last.content = "";
      const el = document.querySelector(`.msg[data-id="${last.id}"] .bubble`);
      if (el) el.textContent = "";
      openStream(last.id, -1);
    }
  } catch (err) {
    showError(els.chatError, err.message);
  }
}

// ---------------- 消息渲染 ----------------

function showEmptyState() {
  els.messageList.innerHTML =
    '<div class="empty-state"><p>新建一个对话，开始提问。</p>' +
    '<p class="muted">Enter 发送，Shift+Enter 换行</p></div>';
}

function statusText(msg) {
  if (msg.role !== "assistant") return "";
  if (msg.status === "stopped") return "已停止";
  if (msg.status === "failed") return msg.error ? `生成失败：${msg.error}` : "生成失败";
  return "";
}

function buildMessageEl(msg) {
  const article = document.createElement("article");
  article.className = `msg msg-${msg.role}` + (msg.status === "failed" ? " msg-error" : "");
  article.dataset.id = String(msg.id);

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  applyBubbleContent(bubble, msg);

  const meta = document.createElement("div");
  meta.className = "msg-meta";
  const text = statusText(msg);
  if (text) {
    const span = document.createElement("span");
    span.textContent = text;
    meta.appendChild(span);
  }

  article.append(bubble, meta);
  return article;
}

function applyBubbleContent(bubble, msg) {
  if (msg.role === "assistant" && msg.status !== "streaming" && msg.content) {
    bubble.innerHTML = window.renderMarkdown(msg.content);
  } else {
    bubble.textContent = msg.content || "";
  }
}

function renderMessages() {
  els.messageList.innerHTML = "";
  if (state.messages.length === 0) {
    showEmptyState();
    return;
  }
  for (const msg of state.messages) {
    els.messageList.appendChild(buildMessageEl(msg));
  }
  scrollToBottom(true);
}

function updateMessageEl(msg) {
  const old = document.querySelector(`.msg[data-id="${msg.id}"]`);
  const fresh = buildMessageEl(msg);
  if (old) old.replaceWith(fresh);
  else els.messageList.appendChild(fresh);
}

// ---------------- 发送与流式订阅 ----------------

async function sendMessage(text) {
  const content = text.trim();
  if (!content || state.stream) return;

  if (!state.currentId) {
    await createConversation();
    if (!state.currentId) return;
  }

  showError(els.chatError, "");
  els.send.disabled = true;

  try {
    const data = await api(`/api/conversations/${state.currentId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    });
    els.input.value = "";
    els.input.style.height = "";
    state.messages.push(data.user_message, data.assistant_message);
    renderMessages();
    stickToBottom = true;
    els.chatTitle.textContent = state.conversations.find((c) => c.id === state.currentId)?.title || els.chatTitle.textContent;
    openStream(data.assistant_message.id, -1);
    refreshConversations().catch(() => {});
  } catch (err) {
    els.send.disabled = false;
    showError(els.chatError, err.message);
  }
}

function parseSSEBlock(block) {
  let event = "message";
  const dataLines = [];
  for (const raw of block.split("\n")) {
    if (!raw || raw.startsWith(":")) continue;
    if (raw.startsWith("event:")) event = raw.slice(6).trim();
    else if (raw.startsWith("data:")) dataLines.push(raw.slice(5).replace(/^ /, ""));
  }
  if (dataLines.length === 0) return null;
  try {
    return { event, data: JSON.parse(dataLines.join("\n")) };
  } catch (_) {
    return null;
  }
}

function detachStream() {
  const stream = state.stream;
  if (!stream) return;
  stream.ended = true;
  clearTimeout(stream.watchdog);
  stream.ctrl.abort();
  state.stream = null;
}

function endStream(stream) {
  if (!stream) return;
  stream.ended = true;
  clearTimeout(stream.watchdog);
  stream.ctrl.abort();
  if (state.stream === stream) state.stream = null;
}

function setComposerBusy(busy) {
  els.send.disabled = busy;
  els.stop.hidden = !busy;
  els.stop.disabled = false;
  setStatus(busy ? "生成中…" : "");
}

async function openStream(mid, resumeFrom = -1, retries = 0) {
  detachStream();
  const ctrl = new AbortController();
  const stream = { mid, lastSeq: resumeFrom, retries, ctrl, ended: false, watchdog: null };
  state.stream = stream;
  setComposerBusy(true);

  try {
    const res = await fetch(`/api/messages/${mid}/stream?resume_from=${resumeFrom}`, {
      headers: state.token ? { Authorization: `Bearer ${state.token}` } : {},
      signal: ctrl.signal,
    });
    if (res.status === 401) {
      logout("登录已失效，请重新登录");
      return;
    }
    if (!res.ok) throw new Error(`订阅失败（${res.status}）`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    const armWatchdog = () => {
      clearTimeout(stream.watchdog);
      stream.watchdog = setTimeout(() => ctrl.abort(), INACTIVITY_MS);
    };
    armWatchdog();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      armWatchdog();
      buffer += decoder.decode(value, { stream: true });

      let index;
      while ((index = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, index);
        buffer = buffer.slice(index + 2);
        const evt = parseSSEBlock(block);
        if (evt) handleStreamEvent(evt);
        if (stream.ended) return;
      }
    }

    if (!stream.ended) {
      await reconnect(stream);
    }
  } catch (err) {
    if (!stream.ended) await reconnect(stream);
  }
}

async function reconnect(stream) {
  if (state.stream !== stream) return;
  const attempt = stream.retries + 1;
  const mid = stream.mid;
  const lastSeq = stream.lastSeq;
  endStream(stream);

  if (attempt > MAX_RETRIES) {
    failMessage(mid, "连接中断，请刷新页面或重新发送");
    setComposerBusy(false);
    return;
  }

  const delay = RETRY_BASE_MS * 2 ** (attempt - 1);
  setStatus(`连接中断，${delay / 1000}s 后重连（${attempt}/${MAX_RETRIES}）`);
  await new Promise((resolve) => setTimeout(resolve, delay));
  if (!state.token || state.currentId === null) return;
  openStream(mid, lastSeq, attempt);
}

function handleStreamEvent(evt) {
  const stream = state.stream;
  if (!stream) return;

  if (evt.event === "delta") {
    stream.lastSeq = evt.data.seq;
    appendDelta(stream.mid, evt.data.content);
    return;
  }
  if (evt.event === "done") {
    finalizeMessage(stream.mid, evt.data.status, evt.data.content);
    endStream(stream);
    setComposerBusy(false);
    return;
  }
  if (evt.event === "error") {
    failMessage(stream.mid, evt.data.message || "生成失败");
    endStream(stream);
    setComposerBusy(false);
  }
}

function appendDelta(mid, text) {
  const msg = state.messages.find((m) => m.id === mid);
  if (!msg) return;
  msg.content += text;
  pendingText.set(mid, msg.content);
  if (rafId === null) rafId = requestAnimationFrame(flushPendingText);
}

function flushPendingText() {
  rafId = null;
  for (const [mid, content] of pendingText) {
    const bubble = document.querySelector(`.msg[data-id="${mid}"] .bubble`);
    if (bubble) bubble.textContent = content;
  }
  pendingText.clear();
  scrollToBottom(false);
}

function finalizeMessage(mid, status, content) {
  const msg = state.messages.find((m) => m.id === mid);
  if (!msg) return;
  if (typeof content === "string" && content.length > 0) msg.content = content;
  msg.status = status || "done";
  msg.error = null;
  pendingText.delete(mid);
  updateMessageEl(msg);
  scrollToBottom(false);
  refreshConversations().catch(() => {});
}

function failMessage(mid, message) {
  const msg = state.messages.find((m) => m.id === mid);
  if (!msg) return;
  msg.status = "failed";
  msg.error = message;
  pendingText.delete(mid);
  updateMessageEl(msg);
  scrollToBottom(false);
  refreshConversations().catch(() => {});
}

async function stopGeneration() {
  const stream = state.stream;
  if (!stream) return;
  const mid = stream.mid;
  els.stop.disabled = true;
  try {
    const data = await api(`/api/messages/${mid}/stop`, { method: "POST" });
    finalizeMessage(mid, data.status || "stopped", null);
  } catch (err) {
    showError(els.chatError, err.message);
  } finally {
    endStream(stream);
    setComposerBusy(false);
    els.stop.disabled = false;
  }
}

// ---------------- 滚动与输入 ----------------

function scrollToBottom(force) {
  if (!force && !stickToBottom) return;
  els.messageList.scrollTop = els.messageList.scrollHeight;
}

els.messageList.addEventListener("scroll", () => {
  const distance = els.messageList.scrollHeight - els.messageList.scrollTop - els.messageList.clientHeight;
  stickToBottom = distance < 80;
});

els.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    els.composer.requestSubmit();
  }
});

els.input.addEventListener("input", () => {
  els.input.style.height = "auto";
  els.input.style.height = `${Math.min(els.input.scrollHeight, 180)}px`;
});

// ---------------- 事件绑定与启动 ----------------

els.authForm.addEventListener("submit", handleAuthSubmit);
els.authToggle.addEventListener("click", () => setAuthMode(state.authMode === "login" ? "register" : "login"));
els.newChat.addEventListener("click", createConversation);
els.logout.addEventListener("click", () => logout());
els.stop.addEventListener("click", stopGeneration);
els.composer.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(els.input.value);
});

setInterval(() => {
  if (state.token && document.visibilityState === "visible") {
    refreshConversations().catch(() => {});
  }
}, 8000);

if (state.token) {
  bootstrap().catch(() => logout("登录已失效，请重新登录"));
} else {
  showAuth();
}
setAuthMode("login");
