from fastapi import FastAPI

app = FastAPI(title="释文 DocRelease")


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}
