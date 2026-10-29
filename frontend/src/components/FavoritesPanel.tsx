"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { getJson } from "@/lib/api";
import { useFavorites } from "./FavoritesProvider";

interface FavCard {
  ref_id: string; question: string; point_id: string; title: string;
  subject_id: string; card_kind: string; last_result: string | null;
}
interface FavPoint {
  ref_id: string; title: string; point: string; subject_id: string;
  priority: string; chapter_name: string;
}

/** 已标记面板：听/记里随手翻回收藏过的卡，不用切到「我的」。 */
export default function FavoritesPanel({
  open, sid, onClose,
}: { open: boolean; sid: string; onClose: () => void }) {
  const [cards, setCards] = useState<FavCard[]>([]);
  const [points, setPoints] = useState<FavPoint[]>([]);
  const [tab, setTab] = useState<"card" | "point">("card");
  const { toggle } = useFavorites();

  useEffect(() => {
    if (!open) return;
    getJson<{ items: FavCard[] }>("/api/favorites?kind=card")
      .then((d) => setCards(d.items.filter((i) => i.subject_id === sid))).catch(() => {});
    getJson<{ items: FavPoint[] }>("/api/favorites?kind=point")
      .then((d) => setPoints(d.items.filter((i) => i.subject_id === sid))).catch(() => {});
  }, [open, sid]);

  if (!open) return null;

  const list = tab === "card" ? cards : points;

  return (
    <div className="picker-mask" onClick={onClose}>
      <div className="picker" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="收藏">
        <div className="picker-head">
          <b>收藏（{cards.length + points.length}）</b>
          <span className="spacer" />
          <button className="badge-btn" onClick={onClose}>关闭</button>
        </div>
        <div className="me-tabs" style={{ padding: "10px 16px 0", margin: 0 }}>
          <button className={tab === "card" ? "on" : ""} onClick={() => setTab("card")}>
            卡片（{cards.length}）
          </button>
          <button className={tab === "point" ? "on" : ""} onClick={() => setTab("point")}>
            知识点（{points.length}）
          </button>
        </div>
        <div className="picker-body">
          {list.length === 0 && (
            <div className="empty">
              这一科还没有收藏。在卡片或知识点上点 ☆ 即可标记。
            </div>
          )}
          {tab === "card" && cards.map((c) => (
            <div className="me-row" key={c.ref_id}>
              <Link href={`/study?view=memo&sid=${c.subject_id}`} className="me-main" onClick={onClose}>
                <b>{c.question}</b>
                <span className="muted">{c.title} · {c.card_kind}</span>
              </Link>
              <button className="badge-btn" onClick={() => {
                toggle("card", c.ref_id);
                setCards((prev) => prev.filter((x) => x.ref_id !== c.ref_id));
              }}>取消</button>
            </div>
          ))}
          {tab === "point" && points.map((p) => (
            <div className="me-row" key={p.ref_id}>
              <Link href={`/study?view=study&sid=${p.subject_id}&pid=${p.ref_id}`}
                className="me-main" onClick={onClose}>
                <b>{p.title}</b>
                <span className="muted">{p.chapter_name}</span>
              </Link>
              <button className="badge-btn" onClick={() => {
                toggle("point", p.ref_id);
                setPoints((prev) => prev.filter((x) => x.ref_id !== p.ref_id));
              }}>取消</button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
