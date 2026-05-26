"use client";

import Link from "next/link";
import { RotateCcw, SendHorizontal } from "lucide-react";
import { FormEvent, useState } from "react";

import { Source, streamChat } from "@/lib/api";

type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
};

const initialMessage: Message = {
  id: 1,
  role: "assistant",
  content: "告诉我你想吃什么、手边有什么食材，或者直接问某道菜怎么做。",
};

export function ChatWorkspace() {
  const [query, setQuery] = useState("推荐几个简单的素菜");
  const [messages, setMessages] = useState<Message[]>([initialMessage]);
  const [sources, setSources] = useState<Source[]>([]);
  const [strategy, setStrategy] = useState<string>("hybrid");
  const [loading, setLoading] = useState(false);
  const [activeAssistantId, setActiveAssistantId] = useState<number | null>(null);
  const [lastQuery, setLastQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submitQuery(text: string) {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    const userId = Date.now();
    const assistantId = userId + 1;
    let receivedToken = false;

    setLoading(true);
    setActiveAssistantId(assistantId);
    setLastQuery(trimmed);
    setError(null);
    setSources([]);
    setMessages((items) => [
      ...items,
      { id: userId, role: "user", content: trimmed },
      { id: assistantId, role: "assistant", content: "" },
    ]);
    setQuery("");

    try {
      await streamChat(trimmed, {
        onMeta: (meta) => {
          setStrategy(meta.strategy);
          setSources(meta.sources);
        },
        onToken: (content) => {
          if (!content) return;
          receivedToken = true;
          setMessages((items) =>
            items.map((message) =>
              message.id === assistantId ? { ...message, content: message.content + content } : message,
            ),
          );
        },
        onError: (message) => {
          setError(message);
          setMessages((items) =>
            items.map((item) =>
              item.id === assistantId && !item.content ? { ...item, content: message } : item,
            ),
          );
        },
      });

      if (!receivedToken) {
        setMessages((items) =>
          items.map((item) =>
            item.id === assistantId && !item.content
              ? { ...item, content: "没有收到生成内容，请稍后重试。" }
              : item,
          ),
        );
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "请求失败";
      setError(message);
      setMessages((items) =>
        items.map((item) => (item.id === assistantId ? { ...item, content: message } : item)),
      );
    } finally {
      setLoading(false);
      setActiveAssistantId(null);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void submitQuery(query);
  }

  function retryLastQuery() {
    if (lastQuery) {
      void submitQuery(lastQuery);
    }
  }

  return (
    <div className="chatGrid">
      <section className="panel chatPanel">
        <div className="messages">
          {messages.map((message) => (
            <div className={`message ${message.role}`} key={message.id}>
              {message.content || (message.id === activeAssistantId ? "正在生成..." : "")}
            </div>
          ))}
          {error ? (
            <div className="message assistant errorText">
              <span>{error}</span>
              {lastQuery ? (
                <button className="textButton" type="button" onClick={retryLastQuery} disabled={loading}>
                  <RotateCcw size={16} />
                  重试
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
        <form className="composer" onSubmit={onSubmit}>
          <textarea
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="例如：我有鸡蛋和土豆，能做什么？"
          />
          <button className="iconButton" type="submit" disabled={loading} title="发送" aria-label="发送">
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
