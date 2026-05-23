import type { Metadata } from "next";
import Link from "next/link";
import { ChefHat, MessageSquareText, Server, Utensils } from "lucide-react";

import "./globals.css";

export const metadata: Metadata = {
  title: "What To Eat",
  description: "Graph RAG recipe assistant",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <div className="appShell">
          <aside className="sidebar">
            <Link className="brand" href="/chat" aria-label="What To Eat">
              <ChefHat size={24} />
              <span>What To Eat</span>
            </Link>
            <nav className="nav">
              <Link href="/chat">
                <MessageSquareText size={18} />
                <span>问答</span>
              </Link>
              <Link href="/recipes">
                <Utensils size={18} />
                <span>菜谱</span>
              </Link>
              <Link href="/status">
                <Server size={18} />
                <span>状态</span>
              </Link>
            </nav>
          </aside>
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}
