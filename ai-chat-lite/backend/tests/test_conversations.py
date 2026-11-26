from tests.test_auth import _register_and_login


async def _auth_headers(client, username="alice"):
    token = await _register_and_login(client, username)
    return {"Authorization": f"Bearer {token}"}


async def test_create_and_list_conversations(client):
    headers = await _auth_headers(client)
    resp = await client.post("/api/conversations", headers=headers)
    assert resp.status_code == 201
    cid = resp.json()["id"]
    assert resp.json()["title"] == "新对话"

    resp = await client.get("/api/conversations", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert [c["id"] for c in items] == [cid]
    assert items[0]["running"] is False


async def test_conversation_isolation_404(client):
    alice = await _auth_headers(client, "alice")
    bob = await _auth_headers(client, "bob")
    cid = (await client.post("/api/conversations", headers=alice)).json()["id"]
    assert (await client.get(f"/api/conversations/{cid}/messages", headers=bob)).status_code == 404
    assert (await client.delete(f"/api/conversations/{cid}", headers=bob)).status_code == 404


async def test_delete_cascades_messages(client):
    from sqlalchemy import select

    from app.database import async_session_factory
    from app.models.message import Message

    headers = await _auth_headers(client)
    cid = (await client.post("/api/conversations", headers=headers)).json()["id"]
    async with async_session_factory() as db:
        db.add(Message(conversation_id=cid, role="user", content="hi", status="done"))
        await db.commit()
    assert (await client.delete(f"/api/conversations/{cid}", headers=headers)).status_code == 204
    async with async_session_factory() as db:
        assert (await db.scalar(select(Message).where(Message.conversation_id == cid))) is None


async def test_conversations_listed_newest_first(client):
    headers = await _auth_headers(client)
    first = (await client.post("/api/conversations", headers=headers)).json()["id"]
    second = (await client.post("/api/conversations", headers=headers)).json()["id"]
    items = (await client.get("/api/conversations", headers=headers)).json()["items"]
    assert [c["id"] for c in items] == [second, first]
