from typing import Protocol
import uuid


class PublisherAdapter(Protocol):
    async def publish(self, asset) -> str: ...
    async def status(self, task_id: str) -> str: ...


class MockPublisher:
    async def publish(self, asset) -> str:
        return uuid.uuid4().hex

    async def status(self, task_id: str) -> str:
        return "completed"


ADAPTERS: dict[str, PublisherAdapter] = {"mock": MockPublisher()}
