import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from app.config import settings
from app.core.sse import format_event
from app.database import async_session_factory, utcnow
from app.models.conversation import Conversation
from app.models.message import Message
from app.services import llm_client

SESSION_TTL_SECONDS = 600


@dataclass
class StreamSession:
    """一次生成任务的内存状态。

    status 必须与 messages.status 同一套词表（streaming / done / stopped / failed），
    因为 _flush 会把它直接写库；前端靠 "streaming" 判断刷新后要不要重订阅，
    启动恢复靠 "streaming" 收殓遗留消息。
    """

    message_id: int
    conversation_id: int
    owner_id: int
    status: str = "streaming"
    parts: list[str] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    waiters: set[asyncio.Event] = field(default_factory=set)
    finalized: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task | None = None
    finished_at: float | None = None
    last_flush: float = 0.0
    unflushed: int = 0

    @property
    def content(self) -> str:
        return "".join(self.parts)

    @property
    def last_seq(self) -> int:
        return len(self.parts) - 1


class StreamManager:
    def __init__(self) -> None:
        self._sessions: dict[int, StreamSession] = {}
        self._cleanup_tasks: set[asyncio.Task] = set()

    def get(self, message_id: int) -> StreamSession | None:
        return self._sessions.get(message_id)

    def has_running(self, conversation_id: int) -> bool:
        return any(
            s.conversation_id == conversation_id and s.status == "streaming"
            for s in self._sessions.values()
        )

    def start(self, message_id: int, conversation_id: int, owner_id: int, prompt: list[dict]) -> StreamSession:
        session = StreamSession(message_id=message_id, conversation_id=conversation_id, owner_id=owner_id)
        self._sessions[message_id] = session
        session.task = asyncio.create_task(self._run(session, prompt))
        return session

    async def stop(self, message_id: int) -> StreamSession | None:
        session = self._sessions.get(message_id)
        if session is None:
            return None
        await self._cancel(session)
        return session

    async def cancel_conversation(self, conversation_id: int) -> None:
        for session in list(self._sessions.values()):
            if session.conversation_id == conversation_id and session.status == "streaming":
                await self._cancel(session)

    async def _cancel(self, session: StreamSession) -> None:
        if session.status != "streaming" or session.task is None:
            return
        session.task.cancel()
        try:
            await asyncio.wait_for(session.task, timeout=5)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

    async def subscribe(self, session: StreamSession, resume_from: int = -1) -> AsyncIterator[str]:
        cursor = max(resume_from, -1)
        waiter = asyncio.Event()
        session.waiters.add(waiter)
        try:
            while True:
                for seq in range(cursor + 1, len(session.parts)):
                    yield format_event("delta", {"seq": seq, "content": session.parts[seq]}, event_id=seq)
                cursor = max(cursor, len(session.parts) - 1)
                if session.status != "streaming":
                    # 等 finally 中的强制落库完成，保证客户端收到终止事件时 DB 已是最新
                    try:
                        await asyncio.wait_for(session.finalized.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        pass
                    yield self._terminal_event(session)
                    return
                try:
                    await asyncio.wait_for(waiter.wait(), timeout=settings.HEARTBEAT_SECONDS)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                waiter.clear()
        finally:
            session.waiters.discard(waiter)

    def _terminal_event(self, session: StreamSession) -> str:
        if session.status == "failed":
            return format_event(
                "error",
                {
                    "message_id": session.message_id,
                    "status": "failed",
                    "code": session.error_code or "internal",
                    "message": session.error_message or "生成失败",
                },
            )
        return format_event(
            "done",
            {"message_id": session.message_id, "status": session.status, "content": session.content},
        )

    async def _run(self, session: StreamSession, prompt: list[dict]) -> None:
        try:
            async with asyncio.timeout(settings.STREAM_TIMEOUT_SECONDS):
                async for delta in llm_client.stream_chat(prompt):
                    session.parts.append(delta)
                    session.unflushed += 1
                    await self._maybe_flush(session)
                    self._notify(session)
            session.status = "done"
        except asyncio.TimeoutError:
            session.status = "failed"
            session.error_code = "timeout"
            session.error_message = f"生成超时（{settings.STREAM_TIMEOUT_SECONDS}s）"
        except asyncio.CancelledError:
            # 用户主动停止：取消只投递一次，此处吞掉以保证 finally 能完成落库
            session.status = "stopped"
        except llm_client.UpstreamError as exc:
            session.status = "failed"
            session.error_code = exc.code
            session.error_message = exc.message
        except Exception as exc:  # 兜底：任何异常都转成 error 事件，不向前端泄漏堆栈
            session.status = "failed"
            session.error_code = "internal"
            session.error_message = f"{type(exc).__name__}: {exc}"
        finally:
            await self._flush(session, final=True)
            session.finished_at = time.monotonic()
            session.finalized.set()
            self._notify(session)
            self._track(asyncio.create_task(self._cleanup_later(session)))

    async def _maybe_flush(self, session: StreamSession) -> None:
        if session.unflushed >= 20 or time.monotonic() - session.last_flush >= settings.FLUSH_INTERVAL_SECONDS:
            await self._flush(session)

    async def _flush(self, session: StreamSession, final: bool = False) -> None:
        try:
            async with async_session_factory() as db:
                msg = await db.get(Message, session.message_id)
                if msg is None:
                    return
                msg.content = session.content
                msg.status = session.status
                msg.error = session.error_message if session.status == "failed" else None
                msg.updated_at = utcnow()
                if final:
                    conv = await db.get(Conversation, session.conversation_id)
                    if conv is not None:
                        conv.updated_at = utcnow()
                await db.commit()
        finally:
            session.last_flush = time.monotonic()
            session.unflushed = 0

    def _notify(self, session: StreamSession) -> None:
        for waiter in list(session.waiters):
            waiter.set()

    async def _cleanup_later(self, session: StreamSession) -> None:
        await asyncio.sleep(SESSION_TTL_SECONDS)
        if self._sessions.get(session.message_id) is session:
            self._sessions.pop(session.message_id, None)

    def _track(self, task: asyncio.Task) -> None:
        self._cleanup_tasks.add(task)
        task.add_done_callback(self._cleanup_tasks.discard)

    def shutdown(self) -> None:
        for session in self._sessions.values():
            if session.task is not None and not session.task.done():
                session.task.cancel()
        self._sessions.clear()
        for task in list(self._cleanup_tasks):
            task.cancel()
        self._cleanup_tasks.clear()

    async def ashutdown(self) -> None:
        tasks = [s.task for s in self._sessions.values() if s.task is not None and not s.task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._sessions.clear()
        cleanup = list(self._cleanup_tasks)
        for task in cleanup:
            task.cancel()
        if cleanup:
            await asyncio.gather(*cleanup, return_exceptions=True)
        self._cleanup_tasks.clear()

    def reset(self) -> None:
        self.shutdown()


manager = StreamManager()
