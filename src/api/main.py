from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router

app = FastAPI(title="ClauseWise API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/")
def hello():
    return {"message": "Welcome to ClauseWise API"}

@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
