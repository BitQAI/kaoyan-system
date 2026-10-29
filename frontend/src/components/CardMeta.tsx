"use client";
import type { ReactNode } from "react";

const RESULT_CLASS: Record<string, string> = {
  "秒答": "cm-good",
  "吃力": "cm-warn",
  "忘了": "cm-bad",
};

function fmtDate(iso?: string | null): string {
  if (!iso) return "";
  const d = iso.slice(0, 10);
  const today = new Date().toISOString().slice(0, 10);
  if (d === today) return "今天";
  const t = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  if (d === t) return "明天";
  return d.slice(5).replace("-", "/");
}

/** 卡片底部的学习记录条：第几次 / 上次评级 / 听过几次 / 下次复习。
 *
 *  参考 Anki 的 Card Info Bar：数字放在卡片下沿，不挤进顶部徽标行。 */
export default function CardMeta({
  reviews = 0, lastResult, listenCount = 0, dueAt, lapses = 0, trailing,
}: {
  reviews?: number;
  lastResult?: string | null;
  listenCount?: number;
  dueAt?: string | null;
  lapses?: number;
  trailing?: ReactNode;
}) {
  const parts: ReactNode[] = [];
  // 记与听分开标：两者是不同动作，合并成一个「N 次」会看不懂
  if (reviews > 0) {
    parts.push(<span key="r">记 {reviews} 次</span>);
    if (lastResult) {
      parts.push(
        <span key="lr" className={RESULT_CLASS[lastResult] ?? ""}>上次 {lastResult}</span>,
      );
    }
    if (lapses > 0) parts.push(<span key="lp" className="cm-bad">失误 {lapses}</span>);
  } else {
    parts.push(<span key="new">记 0 次</span>);
  }
  parts.push(
    <span key="l" className={listenCount > 0 ? "" : "cm-dim"}>听 {listenCount} 次</span>,
  );
  if (dueAt && reviews > 0) parts.push(<span key="d">下次 {fmtDate(dueAt)}</span>);

  return (
    <div className="card-meta">
      <span className="cm-items">{parts}</span>
      {trailing}
    </div>
  );
}
