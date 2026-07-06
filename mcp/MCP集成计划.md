# Travel_llm MCP 集成计划

## 目标

在不破坏现有 LangGraph 主流程的前提下，为 Travel_llm 增加 MCP 能力展示。第一阶段先提供一个独立的 stdio MCP Server，把现有旅游工具通过标准 MCP Tool 暴露出去；第二阶段再考虑让项目内部 Agent 可选地通过 MCP 调用这些工具。

核心目标：

- 体现项目支持 Model Context Protocol。
- 保留当前本地 LangChain Tool 调用链路，避免一次性重构带来风险。
- 优先封装通用、稳定、可复用的旅游工具。
- 将 Selenium 这类重依赖工具逐步隔离到独立 MCP 进程中。

## 推荐范围

第一阶段建议暴露 3 个 MCP 工具：

| MCP 工具名 | 包装的现有工具 | 当前文件 | 作用 |
|---|---|---|---|
| `travel_get_attractions` | `get_attractions_information` | `tools/attractions.py` | 根据目的地获取景点概览、推荐景点、开放时间和游玩时长 |
| `travel_geocode` | `get_location_coordinate` | `tools/locations.py` | 根据地点名和城市获取经纬度坐标 |
| `travel_search_nearby` | `search_nearby_poi` | `tools/nearby.py` | 根据坐标查询周边餐饮、酒店等 POI |

暂不建议暴露：

- `save_info_and_clear_history`：它和当前会话状态强相关，不适合作为通用 MCP 工具。
- LangGraph 节点内部逻辑：这些属于流程编排层，不应该直接作为 MCP 工具暴露。
- 最终回复生成工具：它依赖完整状态，不是独立外部能力。

## 阶段一：新增 stdio MCP Server

新增文件建议：

```text
mcp/
├─ MCP集成计划.md
└─ travel_server.py
```

`travel_server.py` 的职责：

- 创建一个名为 `travel-llm` 的 MCP Server。
- 将现有 LangChain Tool 包装成 MCP Tool。
- 保持返回结构不变，继续使用项目当前的 `success/data/error` 格式。
- 通过 stdio 运行，方便本地 MCP Host 或 Inspector 调试。

建议接口形态：

```python
travel_get_attractions(destination: str) -> dict
travel_geocode(location: str, city: str = "") -> dict
travel_search_nearby(
    location: str,
    city: str = "",
    types: str = "中餐厅",
    radius: int = 3000,
    offset: int = 5,
    page: int = 1,
) -> dict
```

运行方式示例：

```powershell
.\.venv\Scripts\python.exe mcp\travel_server.py
```

注意事项：

- stdio MCP Server 的 `stdout` 只能输出 MCP 协议消息。
- 普通日志应输出到 `stderr` 或日志文件。
- 不要在 MCP Server 启动时打印调试文本。
- 工具内部可以继续复用现有 Redis 缓存、降级和错误返回逻辑。

## 阶段二：增加 MCP ToolBundle 适配层

新增文件建议：

```text
tools/
└─ mcp_adapter.py
```

目标是在不改动节点业务逻辑的情况下，让 `graph/nodes.py` 可以选择工具后端：

- `local`：当前默认方式，直接调用本地 LangChain Tool。
- `mcp`：通过 MCP Client 调用 `mcp/travel_server.py`。

建议配置项：

```env
TOOL_BACKEND=local
MCP_TRAVEL_SERVER_COMMAND=.\.venv\Scripts\python.exe
MCP_TRAVEL_SERVER_ARGS=mcp\travel_server.py
```

建议保留当前 `ToolBundle`，新增 `McpToolBundle`，两者对外暴露相同属性：

```python
web_search
attractions
location
route
nearby
```

这样 `AttractionCollectorNode`、`TransportValidatorNode`、`PoiEnricherNode` 不需要大改，只需要在构建节点时选择不同 bundle。

## 阶段三：完善演示与文档

README 可以增加一节：

- MCP 能力说明。
- stdio MCP Server 启动方式。
- MCP 工具列表。
- 与本地工具模式的区别。

演示重点：

1. MCP Host 发现 `travel_get_attractions`、`travel_geocode`、`travel_search_nearby`。
2. 手动调用 `travel_get_attractions("福州")` 获取景点。
3. 调用 `travel_geocode("三坊七巷", "福州")` 获取坐标。
4. 调用 `travel_search_nearby(...)` 查询周边餐饮或酒店。
5. 说明主 Agent 仍可使用本地工具，MCP 是可插拔能力。

## 风险与控制

| 风险 | 影响 | 控制方式 |
|---|---|---|
| Selenium 工具启动慢 | MCP 调用耗时较长 | 保留缓存，必要时提高 MCP 客户端超时 |
| stdio 输出被日志污染 | MCP 协议解析失败 | 禁止向 stdout 打印普通日志 |
| 环境变量缺失 | 高德或搜索工具失败 | 沿用现有 `success=False` 错误结构 |
| 一次性迁移范围过大 | 影响主流程稳定性 | 先只新增 MCP Server，不改 LangGraph |
| MCP 返回结构和前端事件不一致 | 降级提示失效 | 保持 `success/data/error` 返回格式不变 |

## 验收标准

阶段一完成标准：

- `mcp/travel_server.py` 可以独立启动。
- MCP Inspector 或支持 MCP 的 Host 可以发现 3 个工具。
- 3 个 MCP 工具能成功调用现有工具函数。
- 工具返回结构和原本 LangChain Tool 返回结构一致。
- 不影响当前 FastAPI、LangGraph 和测试。

阶段二完成标准：

- 可以通过配置选择 `TOOL_BACKEND=local` 或 `TOOL_BACKEND=mcp`。
- 本地模式保持原行为。
- MCP 模式下核心流程可以完成至少一次旅游规划。
- 工具失败时仍能进入现有降级和错误展示链路。

## 推荐实施顺序

1. 新增 `mcp/travel_server.py`，只包装 3 个工具。
2. 补充 `requirements.txt` 中 MCP SDK 依赖。
3. 使用 MCP Inspector 做手动验证。
4. 增加最小 smoke test，验证 MCP Server 能导入且工具函数存在。
5. 再设计 `McpToolBundle`，不要第一阶段就改主流程。

## 结论

当前项目最适合采用“先旁路、后接入”的 MCP 集成方式。先把旅游工具作为 stdio MCP Server 暴露出去，能清晰展示 MCP 能力；等 MCP Server 稳定后，再考虑让 Travel_llm 自身通过 MCP 后端调用工具。这样既能体现协议化工具能力，也能降低对现有 LangGraph 流程的影响。
