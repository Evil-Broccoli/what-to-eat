# what-to-eat

一个菜谱 Graph RAG Web 应用。

- 后端：FastAPI，提供问答、菜谱浏览、索引状态和重建接口。
- 前端：Next.js，提供菜谱问答、菜谱列表、菜谱详情和系统状态页面。
- 数据层：Neo4j + Milvus，通过 Docker Compose 运行。
- 数据源：食谱来自 https://github.com/Anduin2017/HowToCook 。
- 模型：LLM 和 Embedding 通过 OpenAI-compatible API 配置。

## 本地开发

1. 复制环境变量模板：

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env.local
```

本地开发时，后端通常直接运行在宿主机，因此 `.env` 保持以下默认值即可：

```bash
NEO4J_URI=bolt://localhost:7687
MILVUS_HOST=localhost
NEXT_PUBLIC_API_BASE_URL=/api
INTERNAL_API_BASE_URL=http://127.0.0.1:8000/api
```

2. 启动数据服务：

```bash
docker compose --env-file .env -f infra/docker-compose.yml up -d neo4j milvus
```

3. 启动后端：

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

4. 启动前端：

```bash
cd frontend
npm install
npm run dev
```

访问 `http://localhost:3000`。

## 单机 Docker Compose 部署

服务器上只需要 Docker 和 Docker Compose。首次部署：

```bash
cp .env.example .env
```

编辑 `.env`，至少填写模型配置：

```bash
OPENAI_API_KEY=你的 LLM API Key
OPENAI_BASE_URL=https://兼容 OpenAI 协议的服务地址/v1
OPENAI_MODEL=gpt-4o-mini

EMBEDDING_API_KEY=你的 Embedding API Key
EMBEDDING_BASE_URL=https://兼容 OpenAI 协议的服务地址/v1
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536
```

如果 `EMBEDDING_API_KEY` 或 `EMBEDDING_BASE_URL` 留空，后端会分别复用 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`。更换 embedding 模型或维度后，必须重新重建索引。

启动完整服务：

```bash
docker compose --env-file .env -f infra/docker-compose.yml up -d --build
```

检查容器：

```bash
docker compose --env-file .env -f infra/docker-compose.yml ps
```

检查后端健康状态：

```bash
curl http://localhost:8000/api/health
```

访问：

- 前端：`http://localhost:3000`
- 后端 API：`http://localhost:8000/api`
- Neo4j Browser：`http://localhost:7474`
- MinIO Console：`http://localhost:9001`

## 索引重建与演示验收

启动服务后，先重建一次索引：

1. 打开 `http://localhost:3000/status`。
2. 点击“重建索引”。
3. 等待页面显示最近重建结果。
4. 打开 `http://localhost:3000/chat`。
5. 输入“推荐几个简单素菜”。
6. 确认回答流式出现，右侧显示检索策略、引用菜谱、匹配原因和标签。

也可以在后端容器中手动执行：

```bash
docker compose --env-file .env -f infra/docker-compose.yml exec backend python scripts/rebuild_index.py
```

## API

- `GET /api/health`
- `POST /api/chat`
- `POST /api/chat/stream`
- `GET /api/recipes`
- `GET /api/recipes/{id}`
- `GET /api/index/status`
- `POST /api/index/rebuild`

## 常见故障

- **Milvus 未连接**：问答会退回本地 Markdown 检索。确认 `milvus`、`etcd`、`minio` 容器已启动。
- **Neo4j 未连接**：图谱同步和图遍历会使用本地 Markdown 兜底，基础问答仍可演示。
- **LLM API Key 未配置**：系统会基于检索结果生成模板回答。
- **Embedding 维度不一致**：确认 `EMBEDDING_MODEL` 和 `EMBEDDING_DIMENSION` 匹配，然后重新重建索引。
- **前端无法访问后端**：Docker 部署默认使用同源 `/api`，由 Next.js 代理到 `backend:8000`；本地开发时确认 `INTERNAL_API_BASE_URL=http://127.0.0.1:8000/api`。
- **修改前端 API 地址后不生效**：`NEXT_PUBLIC_API_BASE_URL` 会进入前端构建产物，修改后需要重新执行 `docker compose --env-file .env -f infra/docker-compose.yml up -d --build frontend`。
