"use client";

import Link from "next/link";
import { SendHorizontal } from "lucide-react";
import { FormEvent, useState } from "react";

import { ChatResponse, Source, chat } from "@/lib/api";

type Message = {
  role: "user" | "assistant";
  content: string;
};

export function ChatWorkspace() {
  const [query, setQuery] = useState("推荐几个简单的素菜");
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "告诉我你想吃什么、手边有什么食材，或者直接问某道菜怎么做。" },
  ]);
  const [sources, setSources] = useState<Source[]>([]);
  const [strategy, setStrategy] = useState<string>("hybrid");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || loading) return;
    setLoading(true);
    setError(null);
    setMessages((items) => [...items, { role: "user", content: trimmed }]);
    setQuery("");
    try {
      const response: ChatResponse = await chat(trimmed);
      setStrategy(response.strategy);
      setSources(response.sources);
      setMessages((items) => [...items, { role: "assistant", content: response.answer }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "请求失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chatGrid">
      <section className="panel chatPanel">
        <div className="messages">
          {messages.map((message, index) => (
            <div className={`message ${message.role}`} key={`${message.role}-${index}`}>
              {message.content}
            </div>
          ))}
          {error ? <div className="message assistant errorText">{error}</div> : null}
        </div>
        <form className="composer" onSubmit={onSubmit}>
          <textarea
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="例如：我有鸡蛋和土豆，能做什么？"
          />
          <button className="iconButton" type="submit" disabled={loading} title="发送">
            <SendHorizontal size={20} />
          </button>
        </form>
      </section>

      <aside className="sideStack">
        <section className="panel contentBlock">
          <h2>检索策略</h2>
          <div className="meta">
            <span className="tag">{strategy}</span>
            <span className="tag">{loading ? "生成中" : "就绪"}</span>
          </div>
        </section>
        <section className="panel contentBlock">
          <h2>引用菜谱</h2>
          <div className="sourceList">
            {sources.length ? (
              sources.map((source) => (
                <Link className="sourceCard" href={`/recipes/${source.recipe_id}`} key={source.recipe_id}>
                  <h3>{source.recipe_name}</h3>
                  <div className="meta">
                    <span>{source.category}</span>
                    <span>{source.difficulty}</span>
                  </div>
                </Link>
              ))
            ) : (
              <p className="empty">回答后会显示匹配到的菜谱来源。</p>
            )}
          </div>
        </section>
      </aside>
    </div>
  );
}
