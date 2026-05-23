import { ChatWorkspace } from "@/components/ChatWorkspace";

export default function ChatPage() {
  return (
    <>
      <header className="pageHeader">
        <div>
          <h1 className="pageTitle">菜谱问答</h1>
          <p className="pageLead">基于本地菜谱库、图谱关系和向量检索回答吃什么、怎么做、有什么替代选择。</p>
        </div>
      </header>
      <ChatWorkspace />
    </>
  );
}
