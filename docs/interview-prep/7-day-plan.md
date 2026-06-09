# 旅游规划机器人 7 天面试训练清单

## Day 1: 讲清主链路

目标：

- 能脱稿讲完整个项目
- 能口述主执行链路

任务：

- 通读 [project-walkthrough.md](E:/BaiduNetdiskDownload/AI/langGraph_day01-day05/旅游规划机器人/docs/interview-prep/project-walkthrough.md) 前 3 节
- 对着代码口述一遍 `前端/Gradio -> chat_service -> graph -> agent -> tools -> 流式返回`
- 自己录 2-3 分钟项目介绍，听一遍是否有卡壳

验收标准：

- 不看稿也能讲出 6 个核心模块
- 能说明为什么这里不是单次 function call

## Day 2: 讲清工具层

目标：

- 搞清 6 个核心工具做什么
- 说清输入、输出和失败方式

任务：

- 逐个复盘 `web_search`、`get_location_coordinate`、`search_nearby_poi`
- 再复盘 `route_planning`、`get_attractions_information`、`save_info_and_clear_history`
- 给每个工具写一句“面试版解释”

验收标准：

- 面试官随便点一个工具，你能在 30 秒内讲清职责
- 至少说出 3 个外部依赖风险

## Day 3: 补齐 LangGraph 八股

目标：

- 项目和基础知识能串起来

任务：

- 通读 [mock-qa.md](E:/BaiduNetdiskDownload/AI/langGraph_day01-day05/旅游规划机器人/docs/interview-prep/mock-qa.md) 中架构类、状态类、流式类问题
- 重点背熟 6 题：
  - 为什么用 LangGraph
  - LangChain 和 LangGraph 区别
  - Tool calling 机制
  - 状态为什么只存 `messages`
  - `thread_id` 的作用
  - 流式输出链路

验收标准：

- 这 6 题每题都能讲 1 分钟
- 回答里都能引用本项目具体实现

## Day 4: 练设计取舍和重构

目标：

- 不只会讲“怎么做”，还会讲“为什么这样做”

任务：

- 通读 [project-walkthrough.md](E:/BaiduNetdiskDownload/AI/langGraph_day01-day05/旅游规划机器人/docs/interview-prep/project-walkthrough.md) 第 4、5 节
- 把 6 个缺点和对应改进方案写成卡片
- 练习回答：
  - 如果上生产你先改什么
  - 为什么当前实现更像 demo
  - 如果重构你会怎么拆节点和状态

验收标准：

- 任意一个缺点都能接上对应改法
- 说改法时不会只停留在“优化一下”

## Day 5: 做一轮项目深挖模拟

目标：

- 适应连续追问

任务：

- 用 [mock-qa.md](E:/BaiduNetdiskDownload/AI/langGraph_day01-day05/旅游规划机器人/docs/interview-prep/mock-qa.md) 做 30 分钟模拟
- 覆盖这几个方向：
  - 架构
  - Agent 决策
  - 工具失败
  - 记忆和状态
  - 稳定性
  - 生产化改造

验收标准：

- 连续 10 个问题不明显慌乱
- 至少 80% 的回答能落到真实代码

## Day 6: 做一轮“八股 + 项目”混合模拟

目标：

- 训练从基础题切回项目的能力

任务：

- 自己或找朋友混着问：
  - Python 异步
  - FastAPI 流式响应
  - Agent 和 function calling
  - 状态管理
  - 系统设计
- 每道题都尽量落回这个项目

验收标准：

- 不会把八股答成纯概念
- 至少能把一半题目和当前项目绑定

## Day 7: 只背最值钱的内容

目标：

- 保证上场时记得住

任务：

- 只复习这 5 类内容：
  - 2-3 分钟项目介绍
  - 3 个亮点
  - 5 个缺点
  - 5 个改进点
  - 10 个高频追问

验收标准：

- 任何时候都能快速进入讲稿
- 不会出现“知道代码做了什么，但不知道怎么说”

## 最后一天上场前速查

- 主链路：输入 -> 服务层 -> Graph -> Agent/Tools -> 流式返回
- 核心价值：多工具 Agent 编排，不是单次问答
- 最大短板：内存记忆、工具不统一、抓取不稳定、prompt 过重
- 最佳加分项：主动讲改进方案，而不是等面试官指出问题
