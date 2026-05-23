# what-to-eat

一个菜谱 Graph RAG Web 应用。当前版本将原命令行 RAG 改造成前后端分离架构：

- 后端：FastAPI，提供问答、菜谱浏览、索引状态和重建接口。
- 前端：Next.js，提供菜谱问答、菜谱列表、菜谱详情和系统状态页面。
- 数据层：Neo4j + Milvus 通过 Docker Compose 本地运行。
- 数据源：继续复用 `cook/` 目录下的 Markdown 菜谱库。

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
