import { StatusDashboard } from "@/components/StatusDashboard";

export default function StatusPage() {
  return (
    <>
      <header className="pageHeader">
        <div>
          <h1 className="pageTitle">系统状态</h1>
          <p className="pageLead">检查后端服务、图数据库、向量数据库和当前索引规模。</p>
        </div>
      </header>
      <StatusDashboard />
    </>
  );
}
