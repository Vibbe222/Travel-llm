# 旅游规划机器人

基于 LangGraph 的旅游规划机器人示例项目。项目使用多节点工作流组织意图识别、景点采集、行程生成、交通校验、周边推荐和最终回复，并提供 FastAPI + Vue 单页前端与原有 Gradio 演示入口。

## 功能概览

- 基于 LangGraph 编排多阶段旅游规划流程
- 使用阿里云百炼 OpenAI 兼容接口调用 `deepseek-v4-flash`
- 支持用户可见的流式进度反馈和前置计划摘要
- 支持停止生成、新建会话、本地历史会话和 Markdown 导出
- 支持工具调用调试面板、错误分层展示和降级提示
- 支持马蜂窝景点抓取，失败时可降级到 Web 搜索
- 支持 Tavily 或 DuckDuckGo Web 搜索 provider
- 支持高德地图坐标查询、周边 POI 和公共交通路线规划
- 支持 Redis TTL 缓存和 LangGraph checkpoint 持久化

## 项目结构

```text
Travel_llm/
├─ agents/                 # 阶段执行器与 LLM 调用封装
├─ api/                    # FastAPI 服务入口
├─ graph/                  # LangGraph 图、路由和 checkpoint
├─ models/                 # 模型工厂
├─ prompts/                # 分阶段提示词
├─ states/                 # LangGraph 状态定义
├─ templates/              # FastAPI 单页前端
├─ tests/                  # 自动化测试
├─ tools/                  # 景点、地图、搜索、交通等工具
├─ utils/                  # Redis 缓存与辅助函数
├─ chat_service.py         # 流式事件整理与聊天服务
├─ run_fastapi.py          # FastAPI 启动入口
├─ webrun.py               # Gradio 启动入口
├─ settings.py             # 统一配置读取与校验
└─ requirements.txt
```

## 运行环境

- Python 3.11
- Windows PowerShell
- Google Chrome
- 可访问阿里云百炼、高德地图、Tavily 或 DuckDuckGo
- 可选：本地 Redis，用于缓存和会话 checkpoint

## 安装

```powershell
cd "E:\py_project\Travel_llm"
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 环境变量

复制 `.env.example` 为 `.env`，并填写真实 key：

```powershell
Copy-Item .env.example .env
```

核心配置：

```env
APP_ENV=development
MODEL_NAME=deepseek-v4-flash
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_API_KEY=your_dashscope_api_key
AMAP_API_KEY=your_amap_api_key

WEB_SEARCH_PROVIDER=tavily
TAVILY_API_KEY=your_tavily_api_key

REDIS_URL=redis://127.0.0.1:6379/0
REDIS_KEY_PREFIX=travel_llm
```

说明：

- `DASHSCOPE_API_KEY`：模型调用使用。
- `AMAP_API_KEY`：高德地理编码、周边 POI、路线规划使用。
- `WEB_SEARCH_PROVIDER`：可选 `duckduckgo` 或 `tavily`。
- `TAVILY_API_KEY`：当 `WEB_SEARCH_PROVIDER=tavily` 时必须配置。
- `REQUIRE_API_KEYS`：控制访问本项目后端接口时是否要求鉴权，不是第三方服务 key。

不要把真实 `.env` 提交到 Git。

## 启动方式

### FastAPI + Vue 前端

```powershell
.\.venv\Scripts\python.exe run_fastapi.py
```

访问：

```text
http://127.0.0.1:8000/
```

常用接口：

- `GET /health`
- `POST /sessions`
- `POST /chat/stream`

`/chat/stream` 使用 NDJSON 流式返回，事件包括：

- `progress`
- `chunk`
- `tool_start`
- `tool_end`
- `tool_error`
- `degradation`
- `error`
- `done`

### Gradio 演示入口

```powershell
.\.venv\Scripts\python.exe webrun.py
```

Gradio 入口保留用于兼容原演示方式。

## 工作流说明

当前 LangGraph 流程：

```text
intent_router
  -> clarification_responder 或 attraction_collector
  -> itinerary_planner
  -> transport_validator
  -> poi_enricher
  -> final_responder
```

关键行为：

- 识别出目的地后，后端会先流式输出前置计划摘要。
- 未识别出明确目的地时，会立即反问用户，不继续调用景点搜索等重工具。
- 最终行程继续追加到同一条助手消息中。

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
| `get_attractions_information` | `tools/attractions.py` | 使用 Selenium 抓取马蜂窝景点信息 |
| `web_search` | `tools/web_search.py` | Tavily 或 DuckDuckGo 搜索 |
| `get_location_coordinate` | `tools/locations.py` | 高德地理编码 |
| `search_nearby_poi` | `tools/nearby.py` | 高德周边 POI |
| `route_planning` | `tools/transportation.py` | 高德公共交通路线 |
| `save_info_and_clear_history` | `tools/save.py` | 保存工具返回的重要信息 |
| `static_map.get_location_coordinate` | `tools/static_map.py` | 生成静态地图图片 |

景点工具缓存策略：

- 只缓存 `source == "mafengwo"` 的成功结果；
- `web_search_fallback` 不缓存，避免一次降级长期污染结果。

## 降级与错误展示

当前前端会分层展示：

- 用户可读错误
- 调试详情
- 工具原始返回

发生 fallback、缓存旧数据、工具失败或不完整数据时，会显示降级提示：

```text
降级提示
出问题的组件：景点主数据源抓取组件（get_attractions_information / Selenium）
原因：Chrome WebDriver 启动或页面抓取失败，已改用网页搜索结果。
影响：景点详情、开放时间或停留时长可能不如主数据源完整。
可信度：中等
```

## Redis 缓存与 checkpoint

Redis 用于两类能力：

- 工具 TTL 缓存；
- LangGraph checkpoint 持久化。

Redis 不可用时：

- 工具缓存自动退化为 miss；
- checkpointer 回退到内存；
- 主流程继续运行。

## 测试

运行完整测试：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

当前覆盖内容包括：

- API smoke
- settings 校验
- Redis cache/checkpoint
- LangGraph 工作流
- 流式事件与前置摘要
- 各工具成功和失败路径
- Tavily / DuckDuckGo Web 搜索 provider

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

- 检查 Chrome 是否安装；
- 检查 Selenium 是否能驱动当前 Chrome；
- 检查目标网页是否可访问；
- 查看前端降级提示和工具调试日志。

### 前端页面还是旧样式

浏览器可能缓存了旧 HTML。使用：

```text
Ctrl + F5
```

或无痕窗口重新打开：

```text
http://127.0.0.1:8000/
```

### 缓存导致结果不符合预期

可清理 Redis 中对应工具缓存后重试。景点 fallback 结果当前不会再写入长期缓存。

## 安全提示

- 不要提交 `.env`。
- 不要把 `DASHSCOPE_API_KEY`、`AMAP_API_KEY`、`TAVILY_API_KEY` 写入文档或前端。
- 如果 key 已经暴露在聊天、截图或日志中，建议去对应平台轮换。
