# 智扫通 · 扫地机器人智能客服

> 基于 DeepSeek + LangGraph ReAct 架构的扫地/扫拖机器人专业 AI 客服系统，支持工具调用、RAG 知识库检索、流式输出与持久化多轮记忆。

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-1.0-green)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)
![Vue](https://img.shields.io/badge/Vue-3.x-42b883)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 演示

![系统界面预览](docs/preview.png)

> 左侧侧边栏展示可咨询的问题类型；中间主区域实时呈现 Agent 推理过程（工具调用 + 工具结果）与最终回答，支持 Markdown 渲染。

---

## 功能特性

- **ReAct 自主推理**：Agent 按照「思考 → 工具调用 → 观察 → 再思考」循环自主决策，无需人工干预
- **RAG 知识库**：覆盖故障排查、维护保养、选购指南、使用咨询四大领域，支持 TXT / PDF 多格式文档
- **实时天气联动**：自动获取用户所在城市天气与湿度，判断是否适合当天使用扫拖机器人
- **持久化多轮记忆**：基于 LangGraph `AsyncSqliteSaver` 将完整对话状态持久化，服务重启后上下文自动恢复
- **跨会话用户画像**：每轮对话摘要自动存档，Agent 可在后续对话中主动调取历史记录提供个性化服务
- **推理过程可视化**：前端实时展示每步工具调用名称、入参与返回结果，支持展开 / 收起
- **流式输出**：SSE 协议逐 Token 推送，响应即时，无需等待完整回答
- **用户系统**：注册 / 登录 / JWT 鉴权，多用户数据完全隔离

---

## 技术架构

```
┌─────────────────────────────────────────────────────┐
│                    前端 Vue 3                         │
│         SSE 流式接收 · Markdown 渲染 · JWT 鉴权       │
└────────────────────┬────────────────────────────────┘
                     │ HTTP / SSE
┌────────────────────▼────────────────────────────────┐
│               FastAPI 后端服务                        │
│        /chat/stream · /auth · /chat/clear            │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│              LangGraph ReAct Agent                   │
│                                                      │
│  ┌──────────────┐    ┌──────────────────────────┐   │
│  │  DeepSeek    │    │      工具集（7个）          │   │
│  │  V4 Pro      │◄──►│  RAG / 天气 / 定位 /      │   │
│  │  LLM         │    │  用户记录 / 历史查询        │   │
│  └──────────────┘    └──────────────────────────┘   │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │         AsyncSqliteSaver Checkpoint          │    │
│  │         （完整对话状态持久化）                  │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│                  数据层                               │
│  FAISS 向量索引 · app.db · user_records.db ·         │
│  checkpoints.sqlite                                  │
└─────────────────────────────────────────────────────┘
```

---

## 技术栈

| 分类 | 技术 |
|---|---|
| Agent 框架 | LangGraph 1.0 · LangChain 1.0 |
| 大语言模型 | DeepSeek V4 Pro |
| Embedding | 阿里云 DashScope `text-embedding-v3` |
| 向量数据库 | FAISS（MMR 检索策略）|
| 后端框架 | FastAPI · Uvicorn |
| 持久化记忆 | LangGraph `AsyncSqliteSaver` · aiosqlite |
| 鉴权 | JWT（python-jose · bcrypt）|
| 外部 API | 高德地图（天气 · IP 定位）|
| 前端框架 | Vue 3 · Vite |
| Markdown 渲染 | marked |
| 通信协议 | REST + SSE |

---

## 项目结构

```
swap_robot_care/
├── agent/
│   ├── agent_react.py          # ReactAgent：create_agent + checkpointer
│   └── tool/
│       ├── tools.py            # 7 个工具函数
│       └── midlleware.py       # MonitorMiddleware（sync + async 双路）
├── backend/
│   ├── server.py               # FastAPI 服务 · SSE 接口 · lifespan 管理
│   ├── auth.py                 # 注册 / 登录 / JWT
│   └── database.py             # 用户表初始化
├── model/
│   ├── init_llm.py             # LLM 初始化（DeepSeek / Qwen Embedding）
│   └── loadenv_utils.py        # .env 加载
├── rag/
│   ├── rag_service.py          # 文档加载 · FAISS 构建 · RAG Chain
│   └── faiss/                  # 持久化向量索引（git ignored）
├── frontend/
│   └── src/App.vue             # Vue 3 单页应用
├── prompt/
│   ├── agent_system_prompt.txt # Agent 系统提示词
│   └── rag.txt                 # RAG 知识提炼提示词
├── data/
│   ├── 扫地机器人100问2.txt
│   ├── 扫拖一体机器人100问.txt
│   ├── 故障排除.txt
│   ├── 维护保养.txt
│   └── 选购指南.txt
└── main.py                     # CLI 调试入口
```

---

## 快速开始

### 前置要求

- Python 3.10+
- Node.js 18+
- DeepSeek API Key（或兼容 OpenAI 接口的代理）
- 阿里云 DashScope API Key
- 高德地图 API Key

### 1. 克隆项目

```bash
git clone https://github.com/your-username/swap-robot-care.git
cd swap-robot-care
```

### 2. 安装后端依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

在 `model/` 目录下创建 `.env` 文件：

```env
DEEPSEEK_APIKEY=your_deepseek_api_key
DEEPSEEK_BASEURL=https://your-deepseek-endpoint/v1
DASHSCOPE_APIKEY=your_dashscope_api_key
DASHSCOPE_BASEURL=https://dashscope.aliyuncs.com/compatible-mode/v1
GAODE_APIKEY=your_gaode_api_key
Unsplash_Access_Key=your_unsplash_access_key
```

### 4. 构建知识库向量索引

首次运行需要构建 FAISS 索引（约需 1-2 分钟）：

```bash
python rag/rag_service.py
```

### 5. 启动后端服务

```bash
python backend/server.py
# 服务运行在 http://localhost:8000
```

### 6. 启动前端

```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

### CLI 调试模式（无需前端）

```bash
python main.py
```

---

## 设计亮点

**结构化分块策略**

针对 QA 问答、故障条目、维保列表、选购指南、PDF 五类文档各自实现定制化 chunk 逻辑，避免通用 splitter 在问答对中间截断导致语义丢失。

**双层 Memory 架构**

| 层次 | 实现 | 解决的问题 |
|---|---|---|
| 消息级 | `AsyncSqliteSaver` Checkpoint | 同一会话跨请求、服务重启后恢复 |
| 摘要级 | `save_user_record` + `get_user_history` | 跨会话用户画像、长期行为记忆 |

**同步 / 异步双路 Middleware**

`MonitorMiddleware` 同时实现 `wrap_tool_call` / `awrap_tool_call` 和 `before_model` / `abefore_model`，CLI（`stream`）与 Web（`astream`）场景共用同一套监控逻辑。

**SSE 健壮解析**

前端使用 `buffer + \n\n` 分帧解析 SSE 事件，解决网络 chunk 边界截断导致 JSON 解析失败、推理过程偶发丢失的问题。

---

## 许可证

[MIT License](LICENSE)
