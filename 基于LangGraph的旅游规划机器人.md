# 基于LangGraph的旅游规划机器人

## 项目简介

本项目是一个基于大语言模型（LLM）和LangGraph框架的智能旅游规划助手。它可以根据用户的需求，自动为用户规划旅游行程，包括景点推荐、路线规划、交通查询、餐饮和住宿建议等。用户只需输入自己的旅游需求，机器人会一步步引导并生成详细的旅游计划。

## 主要功能
- **目的地智能推荐**：根据用户输入，智能识别并推荐合适的旅游城市或景点。
- **景点信息查询**：自动抓取并整理目的地的热门景点、简介、开放时间、游玩建议等。
- **路线与交通规划**：根据景点地理位置，自动规划合理的每日游玩路线，并查询交通方式、距离和耗时。
- **周边餐饮与住宿推荐**：结合每日行程，推荐附近的餐厅和酒店。
- **信息保存与历史管理**：支持保存当前规划结果，方便后续查阅。

## 目录结构说明

```
├── agents/           # 智能体相关代码，负责决策和调用工具
├── graph/            # 状态流转与LangGraph工作流定义
├── models/           # 大语言模型工厂与模型管理
├── prompts/          # 提示词模板，定义AI的行为规范
├── states/           # 状态管理，定义对话和数据流转结构
├── tools/            # 具体功能工具，如景点、交通、周边、地图等
├── utils/            # 辅助工具函数
├── webrun.py         # Web界面启动入口（Gradio）
├── requirements.txt  # 依赖库列表
├── README.md         # 项目说明文档
├── travle.png        # 项目相关图片
├── WorkFlow.png      # 工作流程图
```

## 依赖安装

1. 安装Python 3.10及以上版本。
2. 安装依赖库：
   ```bash
   pip install -r requirements.txt
   ```
3. 配置环境变量（如需使用高德地图API等服务，需在根目录下创建`.env`文件，填写API KEY等信息）。

## 启动方法

直接运行Web界面：
```bash
python webrun.py
```
启动后会自动打开Gradio网页界面，用户可直接输入需求与机器人对话。

## 流程架构图

![基于LangGraph的旅游攻略机器人](/Users/yuejunzhang/Downloads/基于LangGraph的旅游攻略机器人.png)

## 主要模块与工具说明

### agents/
- `agents.py`：定义了Agent（智能体）和AsyncAgent（异步智能体），负责与大语言模型交互和决策。

### graph/
- `graph.py`：定义了整个对话和任务的流程图，描述了各个节点（如Agent、工具调用）之间的流转关系。

### models/
- `factory.py`：封装了大语言模型的创建逻辑，目前支持OpenAI GPT系列。

### prompts/
- `main.py`：存放AI提示词模板，规范AI的行为和输出格式。

### states/
- `state.py`：定义了对话状态的数据结构（如PublicState），用于在各节点间传递消息。

### tools/
- `attractions.py`：景点信息抓取与整理工具。
- `locations.py`：地理坐标查询工具。
- `nearby.py`：周边餐饮、住宿等POI查询工具。
- `save.py`：信息保存工具。
- `static_map.py`：静态地图图片获取工具。
- `transportation.py`：交通路线规划工具。
- `web_search.py`：网络搜索工具，辅助补全信息。

### utils/
- `helper.py`：常用辅助函数，如获取当前时间等。

### webrun.py
- Gradio Web界面入口，集成了对话、调试信息展示等。

## 主要API/工具参数与返回值说明

### 1. 景点信息查询（tools/attractions.py）
- **函数**：`get_attractions_information(destination: str) -> dict`
- **参数**：
  - `destination`：目的地名称（如"长沙"），必须是具体城市或村镇名。
- **返回**：
  - `overview`：目的地简介
  - `scenic_list`：景点列表（含名称、简介、开放时间等）

### 2. 路线规划（tools/transportation.py）
- **函数**：`route_planning(origin: str, destination: str, origin_city_code: str, dest_city_code: str) -> dict`
- **参数**：
  - `origin`：出发点经纬度（如"113.129362,29.371356"）
  - `destination`：目的地经纬度
  - `origin_city_code`：出发城市代码
  - `dest_city_code`：目的地城市代码
- **返回**：
  - `origin`、`destination`、`walking_distance`、`taxi_cost`、`public_transport_options_list`（公交方案列表）

### 3. 周边POI查询（tools/nearby.py）
- **函数**：`search_nearby_poi(location: str, city: str, types: str, keyword: str, radius: int, offset: int, page: int)`
- **参数**：
  - `location`：中心点经纬度
  - `city`：城市代码
  - `types`：POI类型（如"中餐厅|酒店"）
  - `keyword`：关键词
  - `radius`：查询半径（米）
  - `offset`：每页数量
  - `page`：页码
- **返回**：
  - `pois`：POI列表（含名称、类型、地址、距离、评分、价格等）

### 4. 信息保存（tools/save.py）
- **函数**：`save_info_and_clear_history(infomation_to_save: str) -> Tuple[str, str]`
- **参数**：
  - `infomation_to_save`：需要保存的信息
- **返回**：
  - `content`：保存结果提示
  - `artifact`：实际保存的信息

## 常见问题与改进建议
- 若遇到API KEY失效、网络不通等问题，请检查.env配置和网络环境。
- 若需支持更多城市或景点，可扩展相关工具模块。
- 欢迎提出建议和反馈，帮助我们不断完善机器人功能！

---

> 本项目适合初学者及零基础用户，界面友好，操作简单。只需输入"我想去哪里玩"，机器人就能帮你搞定一切旅游规划！ 


























