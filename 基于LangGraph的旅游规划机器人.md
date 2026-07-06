# 基于 LangGraph 的旅游规划机器人

更新时间：2026-06-30

## 项目简介

本项目是一个基于 LangGraph、FastAPI 和大语言模型的智能旅游规划助手。系统会根据用户输入的旅行需求，识别目的地和约束，采集景点信息，生成每日行程，校验交通可行性，并补充餐饮和住宿建议。

项目当前推荐入口是 FastAPI + Vue 单页前端。Gradio 页面仍保留为遗留演示入口，但当前工程化能力、流式事件、降级提示和会话管理主要围绕 FastAPI 入口维护。

## 当前结论

| 模块 | 当前状态 |
|---|---|
| LangGraph 主流程 | 已迁移到结构化 `TravelPlannerState` 和多节点图。 |
| 工具层 | 已统一 `success/data/error` 返回结构，并加入超时、重试、错误包装和日志。 |
| Prompt | 已拆分为意图、澄清、规划、校验、最终回复等阶段 Prompt。 |
| 配置 | 已通过 `settings.py` 统一读取模型、API key、超时、CORS、缓存、Redis 和搜索 provider。 |
| 缓存与会话 | 已支持 Redis TTL 缓存和 Redis-backed checkpoint，Redis 不可用时自动降级。 |
| 前端 | 已支持停止生成、新建会话、历史会话、Markdown 导出、工具面板、进度和降级提示。 |
| 测试 | 已建立测试体系，但最近一次全量 pytest 为 `76 passed / 3 failed`，仍需修复配置和 Tavily 相关失败。 |
| 部署 | 本地运行入口完整，生产级 Dockerfile 和部署说明仍待补充。 |

## 当前核心能力

- **意图识别与约束提取**：识别新规划、修改规划、确认方案等意图，并提取天数、偏好、预算、餐饮和住宿需求。
- **目的地处理**：能识别用户输入中的目的地；未识别出明确目的地时，当前主流程直接反问用户，不继续调用重工具。
- **前置计划摘要**：识别出目的地后，流式输出“任务 / 回顾 / 分析 / 计划”，让用户快速知道系统准备做什么。
- **景点信息采集**：优先使用 Selenium 抓取马蜂窝景点信息，并补全景点坐标。
- **搜索降级**：景点主数据源失败时，可降级到 Tavily 或 DuckDuckGo Web 搜索。
- **行程规划**：基于景点、用户约束和阶段 Prompt 生成每日行程。
- **交通校验**：基于高德地图路线规划检查景点间交通，并在距离异常时触发重排行程。
- **餐饮与住宿推荐**：根据最后一个景点附近 POI 补充餐饮和住宿建议。
- **流式前端体验**：展示进度、文本片段、工具调用、错误、降级提示和最终行程。
- **会话管理**：支持新建会话、浏览器本地历史会话和 Markdown 导出。
- **缓存与持久化**：支持 Redis TTL 缓存和 LangGraph checkpoint；Redis 不可用时主流程继续运行。

## 目录结构说明

```text
├── agents/                 # 阶段执行器，封装 LLM 调用和 JSON fallback
├── api/                    # FastAPI 服务入口
├── graph/                  # LangGraph 图、节点和路由
├── models/                 # 模型工厂
├── prompts/                # 分阶段提示词
├── states/                 # TravelPlannerState 状态定义
├── templates/              # Vue 单页前端
├── tests/                  # 自动化测试
├── tools/                  # 景点、搜索、地图、交通等工具
├── utils/                  # Redis 缓存与辅助函数
├── chat_service.py         # 流式事件转换与聊天服务
├── run_fastapi.py          # FastAPI 启动入口
├── webrun.py               # Gradio 遗留演示入口
├── settings.py             # 统一配置读取与校验
└── requirements.txt        # Python 依赖
```

## 快速启动

安装依赖：

```powershell
cd "E:\py_project\Travel_llm"
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

复制配置：

```powershell
Copy-Item .env.example .env
```

填写 `.env` 中的关键配置：

```env
APP_ENV=development
MODEL_NAME=deepseek-v4-flash
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_API_KEY=your_dashscope_api_key
AMAP_API_KEY=your_amap_api_key
WEB_SEARCH_PROVIDER=duckduckgo
TAVILY_API_KEY=your_tavily_api_key
REDIS_URL=redis://127.0.0.1:6379/0
```

启动 FastAPI 前端：

```powershell
.\.venv\Scripts\python.exe run_fastapi.py
```

访问：

```text
http://127.0.0.1:8000/
```

启动 Gradio 遗留演示入口：

```powershell
.\.venv\Scripts\python.exe webrun.py
```

## LangGraph 工作流

当前主图在 `graph/graph.py` 中创建，状态类型为 `TravelPlannerState`。

主流程：

```text
START
  -> intent_router
  -> clarification_responder        # 未识别出目的地时直接反问并结束
  -> attraction_collector           # 已有目的地时采集景点
  -> itinerary_planner              # 生成每日行程
  -> transport_validator            # 校验交通，必要时最多重排一次
  -> poi_enricher                   # 补充餐饮和住宿
  -> final_responder
  -> END
```

补充说明：

- `destination_clarifier` 节点已经实现，并能基于搜索候选目的地，但当前主路由未实际进入该节点；现在线上主行为是目的地缺失时直接进入 `clarification_responder`。
- 如果用户确认已有方案，且状态里已有 `daily_plan`，路由会直接进入 `final_responder`。
- 如果交通校验发现距离异常，`transport_validator` 会设置 `needs_replan`，并在限定次数内回到 `itinerary_planner`。

## 状态结构

`states/state.py` 中的 `TravelPlannerState` 当前包含：

| 字段 | 说明 |
|---|---|
| `messages` | LangGraph 对话消息。 |
| `intent_type` | 新规划、修改、确认等意图。 |
| `selected_destination` | 当前识别出的目的地。 |
| `user_constraints` | 天数、风格、预算、餐饮、住宿等约束。 |
| `candidate_destinations` | 候选目的地，当前主要用于预留澄清节点。 |
| `attractions` | 景点结构化结果。 |
| `daily_plan` | 每日行程。 |
| `transport_segments` | 交通校验结果。 |
| `meal_options` | 餐饮推荐。 |
| `hotel_options` | 住宿推荐。 |
| `validation_issues` | 工具失败、数据不完整、交通异常等校验提示。 |
| `final_status` | 当前流程状态。 |
| `needs_clarification` | 是否需要用户补充目的地。 |
| `needs_replan` | 是否需要重排行程。 |
| `replan_attempts` | 已重排次数。 |

## 流式反馈设计

前端通过 `/chat/stream` 接收 NDJSON 事件。每一行都是一个独立 JSON 事件，便于前端边读边渲染。

主要事件：

| 事件 | 说明 |
|---|---|
| `progress` | 用户可见进度，例如“正在识别旅行需求”“正在获取景点信息”。 |
| `chunk` | 助手回复文本片段。 |
| `tool_start` | 工具开始调用。 |
| `tool_end` | 工具调用完成。 |
| `degradation` | 降级提示，例如 fallback、缓存旧数据、部分结果不完整。 |
| `tool_error` | 工具错误。 |
| `error` | 后端异常。 |
| `done` | 本轮完成。 |

前置计划摘要会以 `chunk` 流式输出，示例：

```text
任务：用户明确想去福州游玩3天，需要获取福州的景点信息。
回顾：用户描述了本次旅行需求，目的地已明确为“福州”。
分析：需要先获取福州的景点信息，包括景点简介、开放时间和预计游玩时间等。
计划：调用“景点搜索工具”获取福州的景点列表。
```

## 工具说明

### 统一返回结构

工具成功时：

```json
{
  "success": true,
  "data": {},
  "error": null
}
```

工具失败时：

```json
{
  "success": false,
  "data": null,
  "error": {
    "message": "error_code",
    "detail": "错误详情",
    "retryable": false
  }
}
```

### 景点工具

文件：`tools/attractions.py`

能力：

- 使用 Selenium 打开马蜂窝搜索页；
- 找到目的地攻略页；
- 抓取景点列表；
- 进入景点详情页提取简介、开放时间和建议游玩时长；
- 失败时降级到 Web 搜索结果。

返回示例：

```json
{
  "success": true,
  "data": {
    "source": "mafengwo",
    "fallback_used": false,
    "warnings": [],
    "overview": "...",
    "scenic_list": []
  },
  "error": null
}
```

缓存策略：

- 只缓存 `source == "mafengwo"` 的成功结果；
- 不缓存 `web_search_fallback`，避免一次降级污染后续结果。

### Web 搜索工具

文件：`tools/web_search.py`

支持 provider：

- `duckduckgo`
- `tavily`

默认配置来自 `settings.py` 和 `.env.example`，当前默认是 `duckduckgo`。如果本地 DuckDuckGo 受限或频繁触发 rate limit，可以切换到 Tavily：

```env
WEB_SEARCH_PROVIDER=tavily
TAVILY_API_KEY=your_tavily_api_key
```

Tavily 字段映射：

| Tavily | 项目字段 |
|---|---|
| `title` | `title` |
| `url` | `href` |
| `content` | `body` |
| `score` | `score` |

### 高德地图工具

文件：

- `tools/locations.py`
- `tools/nearby.py`
- `tools/transportation.py`

能力：

- 地点转坐标；
- 周边餐饮、住宿 POI；
- 公共交通路线规划。

依赖：

```env
AMAP_API_KEY=your_amap_api_key
```

## 降级提示

当工具使用 fallback、数据不完整、缓存旧数据或工具失败时，前端会展示降级提示。

示例：

```text
降级提示
出问题的组件：景点主数据源抓取组件（get_attractions_information / Selenium）
原因：Chrome WebDriver 启动或页面抓取失败，已改用网页搜索结果。
影响：景点详情、开放时间或停留时长可能不如主数据源完整。
可信度：中等
```

调试详情会保留工具名、阶段、错误类型和原始返回摘要，但不应暴露 Prompt、中间推理或 API 密钥。

## Redis 能力

Redis 用于两类能力：

- 外部工具查询 TTL 缓存；
- LangGraph checkpoint 持久化。

已接入缓存的查询包括：

- 地点坐标；
- 景点信息；
- 周边 POI；
- 交通路线；
- Web 搜索结果。

Redis 不可用时：

- 缓存自动 miss；
- checkpointer 回退内存；
- 主流程不受影响。

当前 Redis-backed checkpointer 是项目内轻量适配器，适合本地演示和轻量持久化。生产化时建议评估官方 Redis/Postgres checkpointer。

## 配置说明

主要配置位于 `settings.py`，从 `.env` 读取：

| 配置 | 说明 |
|---|---|
| `APP_ENV` | `development`、`testing` 或 `production`。 |
| `MODEL_NAME` | 模型名称，默认 `deepseek-v4-flash`。 |
| `DASHSCOPE_BASE_URL` | DashScope OpenAI 兼容接口地址。 |
| `DASHSCOPE_API_KEY` | 百炼模型 API key。 |
| `AMAP_API_KEY` | 高德地图 API key。 |
| `REQUEST_TIMEOUT_SECONDS` | 外部请求超时时间。 |
| `MAX_RETRIES` | 外部请求最大重试次数。 |
| `WEB_SEARCH_PROVIDER` | `duckduckgo` 或 `tavily`。 |
| `TAVILY_API_KEY` | Tavily API key。 |
| `CACHE_ENABLED` | 是否启用 Redis 查询缓存。 |
| `CACHE_TTL_SECONDS` | 查询缓存 TTL。 |
| `REDIS_URL` | Redis 地址。 |
| `REDIS_KEY_PREFIX` | Redis key 前缀。 |
| `REDIS_CHECKPOINT_ENABLED` | 是否启用 Redis checkpoint。 |
| `REDIS_CHECKPOINT_TTL_SECONDS` | checkpoint TTL。 |
| `LOG_LEVEL` | 日志级别。 |
| `CORS_ORIGINS` | 允许访问后端的前端来源。 |
| `CORS_ALLOW_CREDENTIALS` | CORS 是否允许 credentials。 |
| `REQUIRE_API_KEYS` | 是否要求关键 API key 必须存在。 |

注意：生产环境不允许 `CORS_ORIGINS` 使用 `*`。`REQUIRE_API_KEYS` 为 true 时，启动配置会校验 `DASHSCOPE_API_KEY` 和 `AMAP_API_KEY`。

## 测试

运行：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

当前测试覆盖：

- settings 配置校验；
- API smoke；
- LangGraph 路由和工作流；
- Redis 缓存和 checkpoint；
- 流式事件和 Prompt fallback；
- Tavily / DuckDuckGo 搜索；
- 景点、坐标、周边、路线工具。

最近一次全量测试结果：

```text
79 collected
76 passed
3 failed
```

当前失败项集中在配置和 Tavily 搜索口径不一致：

| 测试 | 当前问题 |
|---|---|
| `tests/test_settings.py::test_settings_defaults_are_development_safe` | 测试期望默认搜索 provider 是 `duckduckgo`，但当前运行环境实际读到 `tavily`。 |
| `tests/test_settings.py::test_settings_requires_api_keys_in_production` | 测试期望生产环境缺少 key 会抛错，但当前配置没有触发该错误。 |
| `tests/test_tools_web_search.py::test_web_search_tavily_requires_api_key` | 测试期望缺少 Tavily key 返回 `missing_tavily_api_key`，当前实际进入 Tavily 请求并返回超时。 |

因此当前结论是：测试体系已建立，但全量测试还没有稳定变绿。下一步应优先统一 `.env`、`.env.example`、`settings.py` 和测试中的默认 provider / key 校验策略。

## 常见问题

### 为什么 DuckDuckGo 搜索不可用？

DuckDuckGo 非官方搜索入口可能返回 rate limit 或连接异常。遇到这种情况可以切换到 Tavily：

```env
WEB_SEARCH_PROVIDER=tavily
TAVILY_API_KEY=your_tavily_api_key
```

### 为什么会降级到 Web 搜索？

景点主数据源依赖 Selenium + Chrome WebDriver。如果 Chrome 启动失败、页面结构变化或抓取不到景点列表，系统会使用 Web 搜索作为 fallback。

### 为什么 Redis 没启动也能运行？

Redis 缓存和 checkpoint 都有降级逻辑。Redis 不可用时，工具查询等同于无缓存，LangGraph checkpoint 回退到内存，服务仍可启动和对话。

### 为什么浏览器看到旧页面？

通常是浏览器缓存旧 HTML。使用 `Ctrl + F5` 或无痕窗口重新打开 `http://127.0.0.1:8000/`。

## 安全注意事项

- `.env` 不要提交到 Git；
- `.env.example` 只能放占位符；
- 不要把 `DASHSCOPE_API_KEY`、`AMAP_API_KEY`、`TAVILY_API_KEY` 写入文档、前端代码或日志；
- 如果 API key 已经出现在截图、聊天或日志里，建议去对应平台轮换；
- 生产环境应显式配置 `CORS_ORIGINS`，不要使用通配符。

## 后续待办

1. 修复当前 3 个失败测试，让全量 pytest 变绿。
2. 统一 Tavily / DuckDuckGo 默认 provider 和 API key 校验口径。
3. 给 `api/main.py` 的 `ChatRequest` 增加 Pydantic 字段长度和格式约束。
4. 同步更新 `docs/interview-prep/` 中仍描述旧 `InMemorySaver` 或旧路径的内容。
5. 补 Dockerfile、生产启动命令、日志目录和部署说明。
6. 评估官方 Redis/Postgres checkpointer，替换当前轻量 Redis-backed 适配器。
