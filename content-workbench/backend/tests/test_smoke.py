async def test_app_starts(client):
    response = await client.get("/docs")
    assert response.status_code == 200
