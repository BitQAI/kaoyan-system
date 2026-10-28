"use client";
import { useEffect, useState } from "react";
import { getJson } from "@/lib/api";

interface PointHit { id: string; title: string; point: string; priority: string }
interface CardHit { card_id: string; point_id: string; question: string; kind: string; title: string }

export default function SearchPanel({
  sid, onPick,
}: { sid: string; onPick: (pid: string) => void }) {
  const [q, setQ] = useState("");
  const [points, setPoints] = useState<PointHit[]>([]);
  const [cards, setCards] = useState<CardHit[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const text = q.trim();
    if (!text) {
      setPoints([]);
      setCards([]);
      return;
    }
    setLoading(true);
    const timer = window.setTimeout(() => {
      getJson<{ points: PointHit[]; cards: CardHit[] }>(
        `/api/search?q=${encodeURIComponent(text)}&sid=${sid}&limit=20`)
        .then((d) => { setPoints(d.points); setCards(d.cards); })
        .catch(() => { setPoints([]); setCards([]); })
        .finally(() => setLoading(false));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [q, sid]);

  return (
    <>
      <div className="search-box">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="搜索知识点或卡片问题…"
          aria-label="搜索"
        />
      </div>
      {q.trim() && (
        <div className="search-results">
          {loading && <p className="muted" style={{ fontSize: 12 }}>检索中…</p>}
          {!loading && !points.length && !cards.length && (
            <p className="muted" style={{ fontSize: 12 }}>没有命中，换个词试试</p>
          )}
          {points.length > 0 && <div className="search-group-title">知识点（{points.length}）</div>}
          {points.map((p) => (
            <button key={p.id} className="rel-link" style={{ textAlign: "left" }}
              onClick={() => { onPick(p.id); setQ(""); }}>
              {p.priority} {p.title}
            </button>
          ))}
          {cards.length > 0 && <div className="search-group-title">卡片（{cards.length}）</div>}
          {cards.map((c) => (
            <button key={c.card_id} className="rel-link" style={{ textAlign: "left" }}
              onClick={() => { onPick(c.point_id); setQ(""); }}>
              {c.question}
            </button>
          ))}
        </div>
      )}
    </>
  );
}
