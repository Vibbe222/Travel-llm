# 第七阶段补充优化方案：Tavily 搜索替换

## 1. 优化原因

当前项目原有 `web_search` 工具使用 `duckduckgo_search` 包访问 DuckDuckGo 的 lite/html 搜索入口。

本地测试时出现稳定限流：

```text
https://lite.duckduckgo.com/lite/ 202 Ratelimit
https://html.duckduckgo.com/html 202 Ratelimit
```

这说明当前运行环境被 DuckDuckGo 搜索入口限制，导致 `web_search` 返回：

```json
{
  "success": false,
  "error": {
    "message": "web_search_timeout",
    "detail": "https://lite.duckduckgo.com/lite/ 202 Ratelimit",
    "retryable": true
  }
}
```

影响范围：

- 独立 `web_search` 工具不可稳定使用；
- 景点主数据源失败时，`web_search_fallback` 可能继续失败；
- 降级链路不够可靠；
- 本地演示时容易出现“主工具失败后备用搜索也失败”的情况。

因此需要将搜索能力从非官方 DuckDuckGo 网页抓取，升级为稳定的正式搜索 API。

## 2. 选择 Tavily 的原因

Tavily 是面向 AI agent、RAG 和 LLM 应用的搜索 API，适合当前旅游规划项目。

选择原因：

- 有正式 API，不依赖网页抓取；
- 返回结构稳定；
- 结果包含标题、URL、内容摘要和相关性分数；
- 适合给 LLM 提供简短、干净的检索结果；
- 免费开发额度可满足本地测试和演示；
- 限流规则明确，Development key 的 Search API 限流为 100 RPM；
- 可替代当前 `web_search` 工具，并保持项目内部返回协议不变。

## 3. 本次改动目标

本次 Tavily 升级目标：

1. 保留现有 `web_search` 工具名和调用方式；
2. 保留现有工具统一返回结构；
3. 新增 `WEB_SEARCH_PROVIDER` 配置；
4. 支持 `duckduckgo` 和 `tavily` 两种 provider；
5. 默认仍使用 `duckduckgo`，避免没有 Tavily key 时破坏本地运行；
6. 配置 `WEB_SEARCH_PROVIDER=tavily` 后使用 Tavily Search API；
7. Tavily 返回结果映射成当前项目已有字段；
8. 补充缺 key、限流、成功映射等测试。

## 4. 配置变更

新增 `.env.example` 配置：

```env
# Web search provider: duckduckgo or tavily.
WEB_SEARCH_PROVIDER=duckduckgo
TAVILY_API_KEY=your_tavily_api_key
```

启用 Tavily 时，本地 `.env` 应配置：

```env
WEB_SEARCH_PROVIDER=tavily
TAVILY_API_KEY=your_tavily_api_key
```

说明：

- `WEB_SEARCH_PROVIDER=duckduckgo`：使用旧 DuckDuckGo 实现；
- `WEB_SEARCH_PROVIDER=tavily`：使用 Tavily Search API；
- `TAVILY_API_KEY` 不应提交到 Git；
- `.env` 已在 `.gitignore` 中忽略。

## 5. Settings 改动

`settings.py` 新增：

```python
VALID_WEB_SEARCH_PROVIDERS = {"duckduckgo", "tavily"}
```

`Settings` 新增字段：

```python
web_search_provider: str
tavily_api_key: str
```

校验逻辑：

```text
WEB_SEARCH_PROVIDER 必须是 duckduckgo 或 tavily
```

默认值：

```text
WEB_SEARCH_PROVIDER=duckduckgo
```

这样可以保证没有配置 Tavily key 时，项目仍按原方式运行。

## 6. 工具实现改动

修改文件：

- `tools/web_search.py`

新增常量：

```python
TAVILY_SEARCH_URL = "https://api.tavily.com/search"
```

新增 provider 分发：

```text
WEB_SEARCH_PROVIDER=tavily
  -> _search_with_tavily(...)

WEB_SEARCH_PROVIDER=duckduckgo
  -> _search_with_duckduckgo(...)
```

缓存 key 中加入 provider：

```text
provider + keywords + max_results
```

这样可以避免 Tavily 和 DuckDuckGo 使用同一个缓存 key，造成不同来源结果互相污染。

## 7. Tavily 返回结构映射

Tavily 原始结果字段：

```json
{
  "title": "福州旅游攻略",
  "url": "https://example.test/fuzhou",
  "content": "三坊七巷和西湖公园推荐。",
  "score": 0.9
}
```

映射为项目已有结构：

```json
{
  "title": "福州旅游攻略",
  "href": "https://example.test/fuzhou",
  "body": "三坊七巷和西湖公园推荐。",
  "score": 0.9
}
```

最终工具返回：

```json
{
  "success": true,
  "data": {
    "source": "tavily",
    "fallback_used": false,
    "results": [
      {
        "title": "福州旅游攻略",
        "href": "https://example.test/fuzhou",
        "body": "三坊七巷和西湖公园推荐。",
        "score": 0.9
      }
    ]
  },
  "error": null
}
```

这样 `get_attractions_information` 的 `web_search_fallback` 不需要改调用协议。

## 8. 错误处理

新增 Tavily 错误码：

| 错误码 | 含义 | retryable |
|---|---|---|
| `missing_tavily_api_key` | 缺少 `TAVILY_API_KEY` | false |
| `tavily_auth_failed` | API key 无效或无权限 | false |
| `tavily_rate_limited` | Tavily 限流 | true |
| `tavily_invalid_response` | Tavily 响应结构不符合预期 | false |
| `tavily_search_timeout` | Tavily 请求超时或连接失败 | true |
| `tavily_search_failed` | 其他 Tavily 搜索失败 | false |

DuckDuckGo 原错误码继续保留：

- `web_search_empty`
- `web_search_timeout`
- `web_search_failed`

## 9. 当前测试结果

新增和更新测试：

- `tests/test_tools_web_search.py`
- `tests/test_settings.py`

覆盖内容：

1. DuckDuckGo provider 原成功逻辑；
2. DuckDuckGo 空结果；
3. DuckDuckGo 网络超时；
4. Tavily 成功结果映射；
5. Tavily 缺少 API key；
6. Tavily 429 限流；
7. settings 默认 provider；
8. settings 拒绝未知 provider；
9. `.env.example` 包含 Tavily 配置。

测试命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_tools_web_search.py tests\test_settings.py
```

结果：

```text
12 passed
```

完整测试：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

结果：

```text
78 passed
```

## 10. 启用步骤

1. 获取 Tavily API key。

2. 修改本地 `.env`：

```env
WEB_SEARCH_PROVIDER=tavily
TAVILY_API_KEY=your_tavily_api_key
```

3. 重启 FastAPI：

```powershell
.\.venv\Scripts\python.exe run_fastapi.py
```

4. 测试 `web_search`：

```powershell
.\.venv\Scripts\python.exe -c "from tools import web_search; import json; print(json.dumps(web_search.invoke({'keywords':'福州 旅游 景点','max_results':3}), ensure_ascii=False, indent=2))"
```

预期：

```json
{
  "success": true,
  "data": {
    "source": "tavily",
    "fallback_used": false,
    "results": []
  },
  "error": null
}
```

## 11. 安全注意事项

Tavily API key 属于敏感信息。

注意：

- 不要写入 `.env.example`；
- 不要提交到 Git；
- 不要打印到日志；
- 不要展示在前端；
- 如果 key 已经暴露在聊天、截图或日志里，建议去 Tavily 控制台轮换。

## 12. 后续建议

后续可以继续优化：

1. 将 Tavily 设为默认 provider；
2. 实现 provider fallback：

```text
Tavily -> DuckDuckGo
```

3. Tavily 429 时增加短冷却，避免重复请求；
4. 在前端降级提示中明确显示搜索 provider；
5. 给 Tavily 搜索结果增加 Redis TTL 缓存命中提示；
6. 支持 Tavily `include_answer` 或 `include_raw_content`，用于更强的攻略摘要场景。
