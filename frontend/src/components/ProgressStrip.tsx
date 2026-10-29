"use client";
import { useState } from "react";
import type { ProgressStats } from "@/lib/types";

function pct(n: number, d: number): number {
  if (!d) return 0;
  return Math.round((n / d) * 100);
}

export default function ProgressStrip({ stats }: { stats: ProgressStats }) {
  const [open, setOpen] = useState(false);
  const overall = pct(stats.points.read, stats.points.total);

  return (
    <>
      <div className="progress-strip" onClick={() => setOpen((o) => !o)} role="button" tabIndex={0}
        onKeyDown={(e) => { if (e.key === "Enter") setOpen((o) => !o); }}>
        <span className="ps-chip">读 <b>{stats.points.read}</b>/{stats.points.total}</span>
        <span className="ps-chip">记 <b>{stats.cards.seen}</b>/{stats.cards.total}</span>
        <span className="ps-chip">听 <b>{stats.listen.heard}</b>/{stats.listen.total}</span>
        <span className="ps-bar"><i style={{ width: `${overall}%` }} /></span>
        <span className="ps-chip muted">今日 读{stats.today.read_done} 听{stats.today.listen_done} 记{stats.today.cards_seen}</span>
        <span className="ps-more">{open ? "收起 ▴" : "明细 ▾"}</span>
      </div>

      {open && (
        <div className="progress-panel">
          <div className="pp-head">
            <b>学习进度</b>
            <span className="muted" style={{ fontSize: 12 }}>
              待复习 {stats.cards.due} 张 · 已掌握 {stats.cards.mastered} 张
            </span>
          </div>
          <div className="pp-list">
            {stats.chapters.map((c) => (
              <div className="pp-row" key={c.id}>
                <span className="pp-name">{c.name}</span>
                <span className="pp-bar">
                  <i style={{ width: `${pct(c.read_n, c.total)}%` }} />
                  <em style={{ width: `${pct(c.seen_n, c.card_n)}%` }} />
                </span>
                <span className="pp-num">读 {c.read_n}/{c.total} · 记 {c.seen_n}/{c.card_n}</span>
              </div>
            ))}
          </div>
          <p className="muted" style={{ fontSize: 11.5, margin: "10px 0 0" }}>
            深色条 = 已读知识点，浅色条 = 已答卡片
          </p>
        </div>
      )}
    </>
  );
}
