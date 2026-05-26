# what-to-eat

一个菜谱 Graph RAG Web 应用。

- 后端：FastAPI，提供问答、菜谱浏览、索引状态和重建接口。
- 前端：Next.js，提供菜谱问答、菜谱列表、菜谱详情和系统状态页面。
- 数据层：Neo4j + Milvus 通过 Docker Compose 本地运行。
- 数据源：食谱来自 https://github.com/Anduin2017/HowToCook 。
- 模型：LLM 和 Embedding 通过 OpenAI-compatible API 配置。

## 本地启动

1. 启动数据库：

```bash
docker compose -f infra/docker-compose.yml up -d
```

2. 配置环境变量：

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env.local
```

关键模型配置：

```bash
OPENAI_API_KEY=你的 LLM API Key
OPENAI_BASE_URL=https://兼容 OpenAI 协议的服务地址/v1
OPENAI_MODEL=gpt-4o-mini

EMBEDDING_API_KEY=你的 Embedding API Key
EMBEDDING_BASE_URL=https://兼容 OpenAI 协议的服务地址/v1
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536
```

如果 `EMBEDDING_API_KEY` 或 `EMBEDDING_BASE_URL` 留空，后端会分别复用 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`。更换 embedding 模型或维度后，需要重新执行索引重建。

3. 启动后端：

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

4. 重建图谱和向量索引：

```bash
cd backend
python scripts/rebuild_index.py
```

也可以先启动前端后，在 `http://localhost:3000/status` 点击“重建索引”。状态页会显示 Neo4j、Milvus、LLM、Embedding 的配置/连接情况，以及当前是否使用本地兜底。

5. 启动前端：

```bash
cd frontend
npm install
npm run dev
```

访问 `http://localhost:3000`。

## 本地演示检查

1. 打开 `http://localhost:3000/status`，确认后端状态可以读取。
2. 点击“重建索引”，等待页面显示最近重建结果。
3. 打开 `http://localhost:3000/chat`，输入“推荐几个简单的素菜”。
4. 确认回答会流式出现，并在右侧显示检索策略和引用菜谱。

如果 Milvus 未启动，系统会退回本地 Markdown 检索；如果 Neo4j 未启动，图谱同步会跳过但不影响基础问答演示。
如果未配置 `OPENAI_API_KEY`，问答仍会基于检索结果生成模板回答；配置 LLM 后会自动走流式模型输出。

## API

- `GET /api/health`
- `POST /api/chat`
- `POST /api/chat/stream`
- `GET /api/recipes`
- `GET /api/recipes/{id}`
- `GET /api/index/status`
- `POST /api/index/rebuild`

Neo4j 或 Milvus 未启动时，后端会使用 Markdown 本地检索兜底，方便先验证 Web 链路。
