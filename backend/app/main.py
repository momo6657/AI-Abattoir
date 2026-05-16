from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import models, agents, conversations, games

app = FastAPI(title="AI Abattoir", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(models.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")
app.include_router(games.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}
