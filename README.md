# what-to-eat

一个菜谱 Graph RAG Web 应用。当前版本将原命令行 RAG 改造成前后端分离架构：

- 后端：FastAPI，提供问答、菜谱浏览、索引状态和重建接口。
- 前端：Next.js，提供菜谱问答、菜谱列表、菜谱详情和系统状态页面。
- 数据层：Neo4j + Milvus 通过 Docker Compose 本地运行。
- 数据源：继续复用 `cook/` 目录下的 Markdown 菜谱库。
- 模型：LLM 和 Embedding 都通过 OpenAI-compatible API 配置，便于服务器部署。

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

5. 启动前端：

```bash
cd frontend
npm install
npm run dev
```

访问 `http://localhost:3000`。

## API

- `GET /api/health`
- `POST /api/chat`
- `POST /api/chat/stream`
- `GET /api/recipes`
- `GET /api/recipes/{id}`
- `GET /api/index/status`
- `POST /api/index/rebuild`

Neo4j 或 Milvus 未启动时，后端会使用 Markdown 本地检索兜底，方便先验证 Web 链路。
