"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { delJson, getJson } from "@/lib/api";
import { mdToHtml } from "@/lib/md";

interface Conversation {
  id: string;
  title: string;
  point_id: string | null;
  created_at: string;
  updated_at: string;
  msg_count: number;
}
interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  related_point_ids: string[];
  truncated: boolean;
  created_at: string;
}

export default function HistoryPage() {
  const [items, setItems] = useState<Conversation[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [error, setError] = useState("");

  function load() {
    getJson<{ items: Conversation[] }>("/api/assistant/conversations?limit=50")
      .then((d) => setItems(d.items))
      .catch((e) => setError(String(e)));
  }

  useEffect(load, []);

  async function open(cid: string) {
    if (active === cid) {
      setActive(null);
      return;
    }
    const data = await getJson<{ messages: Message[] }>(`/api/assistant/conversations/${cid}`);
    setActive(cid);
    setMessages(data.messages);
  }

  async function remove(cid: string) {
    if (!window.confirm("删除这个会话？不可恢复。")) return;
    await delJson(`/api/assistant/conversations/${cid}`);
    if (active === cid) setActive(null);
    load();
  }

  return (
    <>
      <nav className="control-bar">
        <b style={{ fontSize: 14 }}>问答历史</b>
        <span className="spacer" />
        <Link className="ghost" href="/study?view=study&sid=812" style={{ textDecoration: "none" }}>回到学习</Link>
      </nav>
      <div className="content">
        <div className="history-page">
          {error && <div className="empty">加载失败：{error}</div>}
          {!error && !items.length && <div className="empty">还没有问答记录。</div>}
          {items.map((c) => (
            <div className="history-conv" key={c.id}>
              <div style={{ display: "flex", gap: 10, alignItems: "baseline" }}>
                <h3 style={{ flex: 1, cursor: "pointer" }} onClick={() => void open(c.id)}>
                  {c.title || "（无标题）"}
                </h3>
                <span className="muted" style={{ fontSize: 12 }}>{c.msg_count} 条</span>
                <button className="badge-btn" onClick={() => void remove(c.id)}>删除</button>
              </div>
              <p>
                {c.updated_at.slice(0, 16).replace("T", " ")}
                {c.point_id ? ` · 知识点 ${c.point_id}` : ""}
              </p>
              {active === c.id && (
                <div className="history-msgs">
                  {messages.map((m) => (
                    <div key={m.id} className={`chat-msg ${m.role === "user" ? "user" : "ai"}`}
                      style={{ flexDirection: "column", alignItems: m.role === "user" ? "flex-end" : "flex-start" }}>
                      {m.role === "assistant" ? (
                        <div className="chat-bubble ai-md" style={{ maxWidth: "100%" }}
                          dangerouslySetInnerHTML={{ __html: mdToHtml(m.content) }} />
                      ) : (
                        <div className="chat-bubble" style={{ maxWidth: "100%" }}>{m.content}</div>
                      )}
                      {m.truncated && <span className="muted" style={{ fontSize: 11 }}>（生成被中断）</span>}
                    </div>
                  ))}
                  {messages.length === 0 && <p className="muted">（空会话）</p>}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
