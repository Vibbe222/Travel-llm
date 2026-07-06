# 基于 LangGraph 的旅游规划机器人

## 项目简介

本项目是一个基于 LangGraph 和大语言模型的智能旅游规划助手。系统会根据用户输入的旅行需求，识别目的地、采集景点信息、生成每日行程、校验交通可行性，并补充餐饮和住宿建议。

项目当前同时保留两种界面：

- FastAPI + Vue 单页前端：当前主要体验入口；
- Gradio 页面：保留原演示入口。

## 当前核心能力

- **意图识别与目的地判断**：识别用户是否提出新规划、修改规划或确认规划。
- **目的地缺失澄清**：未识别出明确目的地时，立即反问用户，不继续调用重工具。
- **前置计划摘要**：识别出目的地后，流式输出“任务 / 回顾 / 分析 / 计划”。
- **景点信息抓取**：优先使用 Selenium 抓取马蜂窝景点信息。
- **搜索降级**：景点主数据源失败时，可降级到 Tavily 或 DuckDuckGo Web 搜索。
- **路线与交通规划**：基于高德地图进行坐标查询、周边 POI 和公共交通路线规划。
- **餐饮与住宿推荐**：根据最后一个景点附近 POI 补充推荐。
- **流式前端体验**：展示进度、工具调用、错误、降级提示和最终行程。
- **会话管理**：支持新建会话、本地历史会话和 Markdown 导出。
- **缓存与持久化**：支持 Redis TTL 缓存和 LangGraph checkpoint。

## 目录结构说明

```text
├── agents/                 # 阶段执行器
├── api/                    # FastAPI 服务入口
├── graph/                  # LangGraph 图、节点和路由
├── models/                 # 模型工厂
├── prompts/                # 分阶段提示词
├── states/                 # 状态定义
├── templates/              # Vue 单页前端
├── tests/                  # 自动化测试
├── tools/                  # 景点、搜索、地图、交通等工具
├── utils/                  # Redis 缓存与辅助函数
├── chat_service.py         # 流式事件转换与聊天服务
├── run_fastapi.py          # FastAPI 启动入口
├── webrun.py               # Gradio 启动入口
├── settings.py             # 统一配置
└── requirements.txt
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

填写 `.env`：

```env
DASHSCOPE_API_KEY=your_dashscope_api_key
AMAP_API_KEY=your_amap_api_key
WEB_SEARCH_PROVIDER=tavily
TAVILY_API_KEY=your_tavily_api_key
```

启动 FastAPI 前端：

```powershell
.\.venv\Scripts\python.exe run_fastapi.py
```

访问：

```text
http://127.0.0.1:8000/
```

启动 Gradio：

```powershell
.\.venv\Scripts\python.exe webrun.py
```

## LangGraph 工作流

当前主流程：

```text
intent_router
  -> clarification_responder
  -> attraction_collector
  -> itinerary_planner
  -> transport_validator
  -> poi_enricher
  -> final_responder
```

路由说明：

- 如果用户确认已有方案，则直接进入 `final_responder`；
- 如果未识别出目的地，则进入 `clarification_responder` 并结束；
- 如果识别出目的地，则进入景点采集和后续规划流程。

## 流式反馈设计

前端通过 `/chat/stream` 接收 NDJSON 事件。

主要事件：

| 事件 | 说明 |
|---|---|
| `progress` | 用户可见进度 |
| `chunk` | 助手回复文本片段 |
| `tool_start` | 工具开始调用 |
| `tool_end` | 工具调用完成 |
| `degradation` | 降级提示 |
| `tool_error` | 工具错误 |
| `error` | 后端异常 |
| `done` | 本轮完成 |

前置计划摘要会以多条 `chunk` 流式输出：

```text
任务：用户明确想去福州游玩3天，需要获取福州的景点信息。
回顾：用户描述了本次旅行需求，目的地已明确为“福州”。
分析：需要先获取福州的景点信息，包括景点简介、开放时间和预计游玩时间等。
计划：调用“景点搜索工具”获取福州的景点列表。
```

## 工具说明

### 景点工具

文件：

```text
tools/attractions.py
```

能力：

- 使用 Selenium 打开马蜂窝搜索页；
- 找到目的地攻略页；
- 抓取景点列表；
- 进入景点详情页提取简介、开放时间和建议游玩时长。

返回结构：

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

文件：

```text
tools/web_search.py
```

支持 provider：

- `duckduckgo`
- `tavily`

推荐本地演示使用：

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

调试详情仍会保留工具名、阶段、错误类型和原始返回摘要。

## Redis 能力

Redis 用于：

- 外部工具查询 TTL 缓存；
- LangGraph checkpoint 持久化。

Redis 不可用时：

- 缓存自动 miss；
- checkpoint 回退内存；
- 主流程不受影响。

## 配置说明

主要配置位于 `settings.py`，从 `.env` 读取：

| 配置 | 说明 |
|---|---|
| `MODEL_NAME` | 模型名称 |
| `DASHSCOPE_API_KEY` | 百炼模型 API key |
| `AMAP_API_KEY` | 高德地图 API key |
| `WEB_SEARCH_PROVIDER` | `duckduckgo` 或 `tavily` |
| `TAVILY_API_KEY` | Tavily API key |
| `CACHE_ENABLED` | 是否启用缓存 |
| `REDIS_URL` | Redis 地址 |
| `REDIS_CHECKPOINT_ENABLED` | 是否启用 Redis checkpoint |
| `REQUIRE_API_KEYS` | 是否要求访问本项目后端时鉴权 |

## 测试

运行：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

当前测试覆盖：

- settings 配置校验；
- API smoke；
- LangGraph 路由；
- Redis 缓存和 checkpoint；
- 流式事件；
- Tavily / DuckDuckGo 搜索；
- 景点、坐标、周边、路线工具。

## 常见问题

### 为什么 DuckDuckGo 搜索不可用？

DuckDuckGo 非官方搜索入口可能返回：

```text
202 Ratelimit
```

建议使用 Tavily。

### 为什么会降级到 Web 搜索？

景点主数据源依赖 Selenium + Chrome WebDriver。如果 Chrome 启动失败、页面结构变化或抓取不到景点列表，系统会使用 Web 搜索作为 fallback。

### 为什么 Edge 和 Chrome 页面不一样？

通常是浏览器缓存旧 HTML。使用 `Ctrl + F5` 或无痕窗口重新打开 `http://127.0.0.1:8000/`。

## 安全注意事项

- `.env` 不要提交到 Git；
- `.env.example` 只能放占位符；
- 如果 API key 已经出现在截图、聊天或日志里，建议去对应平台轮换。
