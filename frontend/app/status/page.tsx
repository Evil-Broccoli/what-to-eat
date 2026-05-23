import { IndexStatus, apiGet } from "@/lib/api";

export default async function StatusPage() {
  let status: IndexStatus | null = null;
  let error: string | null = null;
  try {
    status = await apiGet<IndexStatus>("/index/status");
  } catch (err) {
    error = err instanceof Error ? err.message : "无法连接后端";
  }

  return (
    <>
      <header className="pageHeader">
        <div>
          <h1 className="pageTitle">系统状态</h1>
          <p className="pageLead">检查后端服务、图数据库、向量数据库和当前索引规模。</p>
        </div>
      </header>
      {error ? <p className="errorText">{error}</p> : null}
      <section className="statusGrid">
        <div className="statusCard">
          <h3>Neo4j</h3>
          <p>{status?.neo4j ? "已连接" : "未连接，使用 Markdown 兜底"}</p>
        </div>
        <div className="statusCard">
          <h3>Milvus</h3>
          <p>{status?.milvus ? "已连接" : "未连接，使用本地检索兜底"}</p>
        </div>
        <div className="statusCard">
          <h3>菜谱数量</h3>
          <p>{status?.recipe_count ?? "-"}</p>
        </div>
        <div className="statusCard">
          <h3>文本块数量</h3>
          <p>{status?.chunk_count ?? "-"}</p>
        </div>
      </section>
    </>
  );
}
