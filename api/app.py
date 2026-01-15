from fastapi import FastAPI

api = FastAPI()

@api.get("/health")
async def health():
    return {"status": "ok"}
