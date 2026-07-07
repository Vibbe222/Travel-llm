"""FastAPI 用户版入口。

该入口复用同一套聊天后端接口，但首页返回用户版页面，避免展示工具调用、
降级提示和调试详情。原有 `api.main:app` 保持不变，继续作为开发调试版。
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from chat_service import DEFAULT_MODEL_NAME, build_config, create_session, iter_chat_event_lines
from settings import get_settings

BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_FILE = BASE_DIR / "templates" / "index_user.html"

app = FastAPI(title="Travel Planner API User")
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    thread_id: str
    message: str
    model_name: str = DEFAULT_MODEL_NAME

    model_config = {"protected_namespaces": ()}


@app.get("/")
async def index():
    return FileResponse(INDEX_FILE)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/sessions")
async def create_chat_session():
    session = create_session()
    return {"thread_id": session["thread_id"]}


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    config = build_config(thread_id=request.thread_id)
    return StreamingResponse(
        iter_chat_event_lines(
            user_message=request.message,
            config=config,
            model_name=request.model_name,
        ),
        media_type="application/x-ndjson",
    )
