# 旅游规划机器人

一个基于 LangGraph 的旅游规划机器人示例项目，提供 Gradio Web 界面，结合通义千问、高德地图 API、网页搜索和景点抓取能力生成旅游规划结果。

## 功能概览

- 基于 LangGraph 组织 Agent 与工具调用流程
- 使用通义千问 `deepseek-v4-flash` 生成旅游规划回复
- 支持地点经纬度查询
- 支持周边 POI 搜索
- 支持公交路线规划
- 支持网页搜索
- 支持景点信息抓取
- 提供 Gradio 聊天界面和调试信息面板

## 项目结构

```text
旅游规划机器人/
├─ agents/          # Agent 定义
├─ graph/           # LangGraph 流程编排
├─ models/          # 模型工厂
├─ prompts/         # 提示词模板
├─ states/          # 状态定义
├─ tools/           # 外部工具能力
├─ utils/           # 辅助函数
├─ requirements.txt # 项目依赖列表
└─ webrun.py        # Web 启动入口
```

## 运行环境

- Python 3.10 或 3.11
- Windows PowerShell
- 本机已安装 Google Chrome
- 可访问阿里云百炼和高德地图相关接口

## 安装步骤

建议先进入项目根目录再执行命令：

```powershell
cd "E:\BaiduNetdiskDownload\AI\langGraph_day01-day05\旅游规划机器人"
```

创建并激活虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
```

### 方式一：直接安装仓库依赖

如果你的目标是先把项目跑起来，最省事的是直接安装：

```powershell
pip install -r requirements.txt
```

### 方式二：先安装核心依赖

如果你想先最小化安装，可以先装这一组：

```powershell
pip install beautifulsoup4 duckduckgo_search fastapi gradio langchain-core langchain-openai langgraph langgraph-prebuilt pydantic python-dotenv requests selenium uvicorn
```

上述命令仅列出项目直接使用的依赖，其余传递依赖会由 `pip` 自动安装。

## 环境变量

项目运行前至少需要准备以下环境变量：

- `DASHSCOPE_API_KEY`
- `AMAP_API_KEY`

推荐在项目根目录创建 `.env` 文件：

```env
DASHSCOPE_API_KEY=your_dashscope_key
AMAP_API_KEY=your_amap_key
```

说明：

- `DASHSCOPE_API_KEY` 用于通过阿里云百炼 OpenAI 兼容接口调用通义千问
- `AMAP_API_KEY` 用于调用高德地图地理编码、周边搜索和路线规划接口

## 启动项目

在项目根目录执行：

```powershell
python .\webrun.py
```

当前默认模型为 `deepseek-v4-flash`。

## 模型说明

当前项目默认使用阿里云百炼的 OpenAI 兼容接口访问通义千问：

- 模型名：`deepseek-v4-flash`
- Base URL：`https://dashscope.aliyuncs.com/compatible-mode/v1`

模型创建逻辑位于：

- [models/qwen_factory.py](E:\BaiduNetdiskDownload\AI\langGraph_day01-day05\旅游规划机器人\models\qwen_factory.py)

原有的 OpenAI 工厂文件保留，但默认运行链路不再使用。

## 工具能力说明

当前项目主要接入了以下工具：

- `web_search`：DuckDuckGo 搜索
- `get_location_coordinate`：地点转经纬度
- `search_nearby_poi`：周边地点搜索
- `route_planning`：公交路线规划
- `get_attractions_information`：景点信息抓取
- `save_info_and_clear_history`：保存信息并清理历史

其中：

- 高德相关工具依赖 `AMAP_API_KEY`
- 景点抓取工具依赖 Selenium 和本机 Chrome

## 常见问题

### 1. 编辑器里提示未解析的引用

例如：

- `from prompts.main import agent_prompt_template`
- `from states.state import PublicState`
- `from tools import *`

这类导入要求 Python 把当前项目目录当成模块搜索根目录。建议：

1. IDE 直接打开本项目目录，而不是更上一级目录
2. 运行时从项目根目录执行 `python .\webrun.py`
3. 解释器切换到项目虚拟环境 `.venv\Scripts\python.exe`

有些情况下编辑器会报红线，但运行 `webrun.py` 仍然可以成功。

### 2. 缺少环境变量

如果出现和通义千问或高德 API 相关的报错，先检查 `.env` 中是否正确配置了：

- `DASHSCOPE_API_KEY`
- `AMAP_API_KEY`

### 3. Selenium / Chrome 启动失败

`tools/attractions.py` 使用了 `webdriver.Chrome(...)`。如果这里报错，请检查：

- 本机是否安装 Chrome
- Selenium 版本是否可正常驱动本机 Chrome
- 当前网络和浏览器环境是否允许抓取目标页面

### 4. 从上一级目录运行导致找不到模块

如果报错类似：

```text
ModuleNotFoundError: No module named 'prompts'
```

通常是因为运行目录不对。请切换到项目根目录后再启动：

```powershell
cd "E:\BaiduNetdiskDownload\AI\langGraph_day01-day05\旅游规划机器人"
python .\webrun.py
```

## 备注

- `requirements.txt` 只保留项目源码直接使用的依赖
- 间接依赖由 `pip` 根据固定版本自动解析安装

## 面试准备材料

如果你想基于这个项目准备面试，仓库中新增了一组可直接使用的材料：

- [面试材料总览](E:\BaiduNetdiskDownload\AI\langGraph_day01-day05\旅游规划机器人\docs\interview-prep\README.md)
- [项目讲稿](E:\BaiduNetdiskDownload\AI\langGraph_day01-day05\旅游规划机器人\docs\interview-prep\project-walkthrough.md)
- [高频追问题库](E:\BaiduNetdiskDownload\AI\langGraph_day01-day05\旅游规划机器人\docs\interview-prep\mock-qa.md)
- [7 天训练清单](E:\BaiduNetdiskDownload\AI\langGraph_day01-day05\旅游规划机器人\docs\interview-prep\7-day-plan.md)
