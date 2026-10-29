"use client";
import type { ProgressStats } from "@/lib/types";

function pct(n: number, d: number): number {
  if (!d) return 0;
  return Math.round((n / d) * 100);
}

/** 顶部条里的进度摘要，点一下展开明细。 */
export function HeaderProgress({
  stats, open, onToggle,
}: { stats: ProgressStats; open: boolean; onToggle: () => void }) {
  const overall = pct(stats.points.read, stats.points.total);
  return (
    <button className="hp" onClick={onToggle} aria-expanded={open} title="学习进度">
      <span className="hp-chip">读 <b>{stats.points.read}</b>/{stats.points.total}</span>
      <span className="hp-chip">记 <b>{stats.cards.seen}</b>/{stats.cards.total}</span>
      <span className="hp-chip">听 <b>{stats.listen.heard}</b>/{stats.listen.total}</span>
      <span className="hp-bar"><i style={{ width: `${overall}%` }} /></span>
      <span className="hp-more">{open ? "▴" : "▾"}</span>
    </button>
  );
}

export function ProgressPanel({ stats, open }: { stats: ProgressStats; open: boolean }) {
  if (!open) return null;
  return (
    <div className="progress-panel">
      <div className="pp-head">
        <b>学习进度</b>
        <span className="muted" style={{ fontSize: 12 }}>
          待复习 {stats.cards.due} 张 · 已掌握 {stats.cards.mastered} 张 ·
          今日 读{stats.today.read_done} 听{stats.today.listen_done} 记{stats.today.cards_seen}
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
  );
}
