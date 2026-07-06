# 旅游规划机器人

基于 LangGraph 的多阶段旅游规划 Agent。项目把原始的单 Agent 工具调用流程，改造成更可控的旅游规划工作流：先识别需求和目的地，再采集景点、生成行程、校验交通、补充餐饮住宿，最后整理成用户可读的 Markdown 方案。

当前默认入口是 FastAPI + Vue 单页前端，原 Gradio 演示入口仍保留。

## 功能概览

- LangGraph 多节点流程编排，节点职责清晰，便于测试和扩展。
- 阿里云百炼 OpenAI 兼容接口，默认模型为 `deepseek-v4-flash`。
- FastAPI 流式接口，使用 NDJSON 输出进度、文本、工具状态、错误和降级提示。
- Vue 单页前端，支持停止生成、新建会话、本地历史、Markdown 导出和工具调试面板。
- 景点数据优先抓取马蜂窝，失败时可降级到 Web 搜索。
- Web 搜索支持 DuckDuckGo 和 Tavily，可通过环境变量切换。
- 高德地图工具支持地理编码、周边 POI、公共交通路线规划。
- Redis 可选，用于工具 TTL 缓存和 LangGraph checkpoint 持久化。
- pytest 覆盖配置、API、图路由、流式事件、缓存、checkpoint 和各工具成功/失败路径。

## 项目结构

```text
Travel_llm/
├─ agents/                  # 阶段执行器与 LLM 调用封装
├─ api/                     # FastAPI 服务入口
├─ graph/                   # LangGraph 图、节点、路由和 checkpoint
├─ mcp/                     # MCP 集成规划文档
├─ models/                  # 模型工厂
├─ prompts/                 # 分阶段提示词
├─ states/                  # LangGraph 状态定义
├─ templates/               # FastAPI 单页前端
├─ tests/                   # 自动化测试
├─ tools/                   # 景点、地图、搜索、交通等工具
├─ utils/                   # Redis 缓存与辅助函数
├─ 多阶段详细优化/          # 分阶段技术方案、验收文档和降级说明
├─ chat_service.py          # 流式事件整理与聊天服务
├─ run_fastapi.py           # FastAPI 启动入口
├─ webrun.py                # Gradio 启动入口
├─ settings.py              # 统一配置读取与校验
├─ requirements.txt         # Python 依赖
└─ README.md
```

更多文件说明见 `文件说明.md`。

## 运行环境

- Python 3.11
- Windows PowerShell
- Google Chrome，用于 Selenium 景点抓取
- 可访问阿里云百炼和高德地图
- 可选：Tavily API key，用于替代 DuckDuckGo 搜索
- 可选：本地 Redis，用于缓存和 checkpoint 持久化

## 快速开始

```powershell
cd "E:\py_project\Travel_llm"
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

编辑 `.env`，至少填写：

```env
DASHSCOPE_API_KEY=your_dashscope_api_key
AMAP_API_KEY=your_amap_api_key
```

启动 FastAPI + Vue 前端：

```powershell
.\.venv\Scripts\python.exe run_fastapi.py
```

访问：

```text
http://127.0.0.1:8000/
```

启动原 Gradio 演示入口：

```powershell
.\.venv\Scripts\python.exe webrun.py
```

## 环境变量

`.env.example` 包含完整配置示例。常用配置如下：

```env
APP_ENV=development
MODEL_NAME=deepseek-v4-flash
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_API_KEY=your_dashscope_api_key
AMAP_API_KEY=your_amap_api_key

REQUEST_TIMEOUT_SECONDS=12
MAX_RETRIES=2
CACHE_ENABLED=true
CACHE_TTL_SECONDS=86400

WEB_SEARCH_PROVIDER=duckduckgo
TAVILY_API_KEY=your_tavily_api_key

REDIS_URL=redis://127.0.0.1:6379/0
REDIS_KEY_PREFIX=travel_llm
REDIS_CHECKPOINT_ENABLED=true
REDIS_CHECKPOINT_TTL_SECONDS=604800

LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000
CORS_ALLOW_CREDENTIALS=true
REQUIRE_API_KEYS=false
```

说明：

- `DASHSCOPE_API_KEY`：模型调用使用。
- `AMAP_API_KEY`：高德地理编码、周边 POI 和路线规划使用。
- `WEB_SEARCH_PROVIDER`：可选 `duckduckgo` 或 `tavily`。
- `TAVILY_API_KEY`：当 `WEB_SEARCH_PROVIDER=tavily` 时必须配置。
- `REQUIRE_API_KEYS`：开启后会在启动配置校验中要求 `DASHSCOPE_API_KEY` 和 `AMAP_API_KEY` 非空；当前代码未实现请求头鉴权中间件。
- `APP_ENV=production` 时不要使用通配符 `*` 作为 CORS 来源。

不要提交真实 `.env`。`.gitignore` 已忽略 `.env` 和 `.env.*`，但保留 `.env.example`。

## API 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/` | 返回单页前端 |
| `GET` | `/health` | 健康检查 |
| `POST` | `/sessions` | 创建会话，返回 `thread_id` |
| `POST` | `/chat/stream` | 聊天流式接口，返回 NDJSON |

`POST /chat/stream` 请求体：

```json
{
  "thread_id": "2026_06_28 181805",
  "message": "福州三天两晚，轻松一点",
  "model_name": "deepseek-v4-flash"
}
```

流式事件类型：

| 事件 | 说明 |
|---|---|
| `progress` | 阶段进度 |
| `chunk` | 用户可见文本片段 |
| `tool_start` | 工具开始调用 |
| `tool_end` | 工具调用结束 |
| `tool_error` | 工具失败，包含用户可读错误和调试信息 |
| `degradation` | fallback、缓存旧数据或部分字段缺失等降级提示 |
| `error` | 后端异常 |
| `done` | 本轮完成 |

## 工作流说明

当前主流程：

```text
intent_router
  -> clarification_responder
  -> END

intent_router
  -> attraction_collector
  -> itinerary_planner
  -> transport_validator
  -> itinerary_planner 或 poi_enricher
  -> final_responder
  -> END
```

关键行为：

- 未识别出明确目的地时，直接返回澄清问题，不继续调用景点、地图等重工具。
- 识别出目的地后，会先向用户输出前置计划摘要，再继续执行景点采集和规划。
- 交通校验发现明显问题时，会有限次数重排行程。
- 最终回复只输出用户可读内容，内部 JSON 和 Prompt 不暴露给前端。

前置计划摘要示例：

```text
任务：用户明确想去福州游玩3天，需要获取福州的景点信息。
回顾：用户描述了本次旅行需求，目的地已明确为“福州”。
分析：需要先获取福州的景点信息，包括景点简介、开放时间和预计游玩时间等。
计划：调用“景点搜索工具”获取福州的景点列表。
```

## 工具能力

| 工具 | 文件 | 说明 |
|---|---|---|
| `get_attractions_information` | `tools/attractions.py` | 使用 Selenium 抓取马蜂窝景点信息，失败时可降级到 Web 搜索 |
| `web_search` | `tools/web_search.py` | Tavily 或 DuckDuckGo 搜索 |
| `get_location_coordinate` | `tools/locations.py` | 高德地理编码 |
| `search_nearby_poi` | `tools/nearby.py` | 高德周边 POI |
| `route_planning` | `tools/transportation.py` | 高德公共交通路线 |
| `save_info_and_clear_history` | `tools/save.py` | 保存工具返回的重要信息 |
| `static_map.get_location_coordinate` | `tools/static_map.py` | 生成静态地图图片 |

工具统一返回：

```json
{
  "success": true,
  "data": {},
  "error": null
}
```

失败时：

```json
{
  "success": false,
  "data": null,
  "error": {
    "message": "error_code",
    "detail": "详细信息",
    "retryable": true
  }
}
```

景点缓存策略：

- 只缓存 `source == "mafengwo"` 的成功结果。
- `web_search_fallback` 不缓存，避免一次降级长期污染结果。

## Redis 缓存与 Checkpoint

Redis 用于两类能力：

- 工具 TTL 缓存，减少重复外部查询。
- LangGraph checkpoint 持久化，支持会话状态恢复。

Redis 不可用时：

- 工具缓存自动退化为 miss。
- checkpointer 回退到内存。
- 主流程继续运行。

## 前端能力

FastAPI 首页返回 `templates/index.html`，主要能力包括：

- 新建会话
- 停止生成
- 本地历史会话
- 导出当前会话
- 导出历史会话
- 当前生成过程展示
- 工具调用调试面板
- 降级提示独立展示
- 错误信息分层展示
- 移动端单列布局

本地历史目前保存在浏览器 `localStorage`，key 为：

```text
travelPlannerSessions:v1
```

## 测试

运行完整测试：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

按模块运行示例：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_api_smoke.py
.\.venv\Scripts\python.exe -m pytest tests\test_streaming_and_prompts.py
.\.venv\Scripts\python.exe -m pytest tests\test_tools_attractions.py
```

当前测试覆盖：

- API smoke
- settings 校验
- Redis cache/checkpoint
- LangGraph 工作流和路由
- 流式事件、前置摘要和降级提示
- 工具成功、失败、超时、限流和 fallback 路径
- Tavily / DuckDuckGo Web 搜索 provider

## 文档索引

| 文档 | 说明 |
|---|---|
| `文件说明.md` | 项目目录和主要文件说明 |
| `修改内容说明.md` | 从原项目到当前项目的改造说明 |
| `基于LangGraph的旅游规划机器人.md` | 项目介绍文档 |
| `项目总体优化建议.md` | 总体优化建议 |
| `项目优化计划.md` | 分阶段优化计划 |
| `多阶段详细优化/` | 各阶段技术方案、验收文档和 fallback 降级说明 |
| `mcp/MCP集成计划.md` | MCP stdio server 和后续工具后端适配计划 |

注意：当前 `mcp/` 目录只有集成计划文档，MCP Server 尚未接入主流程。

## 常见问题

### DuckDuckGo 限流

如果 `web_search` 返回：

```text
web_search_timeout
202 Ratelimit
```

建议切换到 Tavily：

```env
WEB_SEARCH_PROVIDER=tavily
TAVILY_API_KEY=your_tavily_api_key
```

### Selenium / Chrome 启动失败

景点抓取依赖本机 Chrome 和 Selenium WebDriver。如果失败：

- 检查 Chrome 是否安装。
- 检查 Selenium 是否能驱动当前 Chrome。
- 检查目标网页是否可访问。
- 查看前端降级提示和工具调试日志。

### Redis 没启动

Redis 是可选依赖。没启动时缓存和 checkpoint 会降级，但主流程仍可运行。需要持久化会话或减少重复外部查询时，再启动 Redis。

### 缓存导致结果不符合预期

可清理 Redis 中对应工具缓存后重试。景点 fallback 结果当前不会写入长期缓存。

