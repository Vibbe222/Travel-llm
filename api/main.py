"""FastAPI 服务入口。

这个文件负责创建整个 Web 应用对象 `app`，并定义前端会访问的 HTTP 接口。
如果把整个项目想成一家餐厅，这个文件就像前台：外部请求先到这里，
再由这里决定返回页面、创建会话，或把聊天请求转交给后面的业务逻辑。
"""

from pathlib import Path

# `FastAPI` 用来创建 Web 应用实例。
# `CORSMiddleware` 用来处理“跨域”问题，方便前端页面从别的地址访问这里的接口。
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# `FileResponse` 适合直接返回文件，比如 HTML 页面。
# `StreamingResponse` 适合流式输出内容，比如聊天时边生成边返回。
from fastapi.responses import FileResponse, StreamingResponse

# `BaseModel` 用来定义请求体的数据结构，FastAPI 会自动按这个结构做校验。
from pydantic import BaseModel

from chat_service import DEFAULT_MODEL_NAME, build_config, create_session, iter_chat_event_lines
from settings import get_settings

# `BASE_DIR` 是项目根目录，`INDEX_FILE` 指向首页 HTML 文件。
# 这样不管从哪里启动程序，都能稳定找到 `templates/index.html`。
BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_FILE = BASE_DIR / "templates" / "index.html"

# `app` 是整个 FastAPI 应用的核心对象。
# 后面定义的接口、文档、配置，都会挂在这个对象上。
app = FastAPI(title="Travel Planner API")
settings = get_settings()

# 这里添加跨域中间件。
# 允许来源从 settings.CORS_ORIGINS 读取：
# - 本地开发默认允许 localhost / 127.0.0.1 常见端口
# - 生产环境禁止使用通配符 "*"
# - 允许任意 HTTP 方法
# - 允许任意请求头
# 具体配置请参考 .env.example。
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    # `POST /chat/stream` 这个接口期望收到的 JSON 请求体结构。
    # 当前一次聊天请求，前端至少要传下面 3 个字段。

    # 会话 id。用来告诉后端“这条消息属于哪一轮对话”。
    thread_id: str
    # 用户这次输入的聊天内容。
    message: str
    # 可选模型名；如果前端不传，就使用项目里默认的模型。
    model_name: str = DEFAULT_MODEL_NAME

    # Pydantic 有一些默认保留字段前缀保护机制。
    # 这里将其放宽，避免字段命名时受到额外限制。
    model_config = {"protected_namespaces": ()}


@app.get("/")
async def index():
    # 首页接口：直接把本地的 HTML 文件返回给浏览器。
    # 用户在浏览器打开服务根地址时，通常看到的就是这个页面。
    return FileResponse(INDEX_FILE)


@app.get("/health")
async def health():
    # 健康检查接口。
    # 常用于快速确认服务是否成功启动、是否还能正常响应请求。
    return {"status": "ok"}


@app.post("/sessions")
async def create_chat_session():
    # 创建新会话接口。
    # 前端通常会先调用它，拿到一个新的 `thread_id`，
    # 之后再把这个 id 带到聊天请求里，表示后续消息属于同一个会话。
    session = create_session()
    return {"thread_id": session["thread_id"]}


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    # 聊天流式接口。
    # 它接收前端发来的消息，然后把后端生成过程“边算边发”地返回给前端，
    # 而不是等完整答案全部生成完再一次性返回。
    config = build_config(thread_id=request.thread_id)
    return StreamingResponse(
        # `iter_chat_event_lines(...)` 会持续产出一行一行的 JSON 文本。
        # 每一行代表一个独立事件，例如：
        # - 模型生成了一个文本片段
        # - 某个工具开始调用
        # - 某个工具调用结束
        # 前端可以一边读取，一边实时更新界面。
        iter_chat_event_lines(
            user_message=request.message,
            config=config,
            model_name=request.model_name,
        ),
        # `application/x-ndjson` 表示返回的是“按行分隔的 JSON”。
        # NDJSON = Newline Delimited JSON。
        # 也就是说，响应体不是一个大 JSON 数组，而是很多行独立 JSON，
        # 前端读到一行就可以立刻解析一行，非常适合聊天流式场景。
        media_type="application/x-ndjson",
    )
