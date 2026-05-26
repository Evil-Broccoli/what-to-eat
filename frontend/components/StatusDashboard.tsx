"use client";

import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { IndexStatus, RebuildResponse, apiGet, rebuildIndex } from "@/lib/api";

export function StatusDashboard() {
  const [status, setStatus] = useState<IndexStatus | null>(null);
  const [result, setResult] = useState<RebuildResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [rebuilding, setRebuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadStatus() {
    setLoading(true);
    setError(null);
    try {
      setStatus(await apiGet<IndexStatus>("/index/status"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法连接后端");
    } finally {
      setLoading(false);
    }
  }

  async function onRebuild() {
    setRebuilding(true);
    setError(null);
    setResult(null);
    try {
      const rebuildResult = await rebuildIndex();
      setResult(rebuildResult);
      setStatus(rebuildResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : "索引重建失败");
    } finally {
      setRebuilding(false);
    }
  }

  useEffect(() => {
    void loadStatus();
  }, []);

  return (
    <>
      <section className="panel statusToolbar">
        <div>
          <h2>索引维护</h2>
          <p>重建会重新读取本地 Markdown 菜谱，并在外部服务可用时同步 Neo4j 与 Milvus。</p>
        </div>
        <button className="primaryButton" type="button" onClick={onRebuild} disabled={loading || rebuilding}>
          <RefreshCw size={18} />
          {rebuilding ? "重建中" : "重建索引"}
        </button>
      </section>

      {error ? <p className="errorText">{error}</p> : null}
      {result ? (
        <section className="panel contentBlock">
          <h2>最近重建结果</h2>
          <p>{result.message}</p>
          {result.failed_sources.length ? (
            <div className="failedSources">
              {result.failed_sources.map((source) => (
                <span className="tag" key={source}>
                  {source}
                </span>
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="statusGrid">
        <StatusCard title="Neo4j" value={status?.neo4j ? "已连接" : "未连接，使用 Markdown 兜底"} />
        <StatusCard title="Milvus" value={status?.milvus ? "已连接" : "未连接，使用本地检索兜底"} />
        <StatusCard title="菜谱数量" value={loading ? "读取中" : String(status?.recipe_count ?? "-")} />
        <StatusCard title="文本块数量" value={loading ? "读取中" : String(status?.chunk_count ?? "-")} />
        <StatusCard title="最近重建" value={status?.last_build ? new Date(status.last_build).toLocaleString() : "暂无"} />
      </section>
    </>
  );
}

function StatusCard({ title, value }: { title: string; value: string }) {
  return (
    <div className="statusCard">
      <h3>{title}</h3>
      <p>{value}</p>
    </div>
  );
}
