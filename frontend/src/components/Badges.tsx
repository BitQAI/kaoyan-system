"use client";
import { useFavorites } from "./FavoritesProvider";

export const PRIORITY_LABEL: Record<string, string> = {
  "★": "高频", "●": "易错", "○": "普通",
};

/** 合并多组标签并去重（kind 与 exam_types 常常重复，例如两处都是「简答」）。 */
export function uniqueLabels(...lists: (string | null | undefined)[][]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const list of lists) {
    for (const raw of list) {
      const label = (raw ?? "").trim();
      if (!label || seen.has(label)) continue;
      seen.add(label);
      out.push(label);
    }
  }
  return out;
}

export function PriorityBadge({ priority }: { priority?: string | null }) {
  if (!priority) return null;
  const label = PRIORITY_LABEL[priority];
  if (!label) return null;
  return <span className={`badge pri pri-${priority === "★" ? "hot" : priority === "●" ? "trap" : "normal"}`}>
    {priority} {label}
  </span>;
}

export function StarButton({
  kind, id, title,
}: { kind: "point" | "card"; id: string; title?: string }) {
  const { has, toggle } = useFavorites();
  const on = has(kind, id);
  return (
    <button
      className={`star-btn${on ? " on" : ""}`}
      aria-pressed={on}
      aria-label={on ? "取消收藏" : "收藏"}
      title={`${on ? "取消收藏" : "收藏"}${title ? "：" + title : ""}`}
      onClick={(e) => { e.stopPropagation(); e.preventDefault(); toggle(kind, id); }}
    >
      {on ? "★" : "☆"}
    </button>
  );
}
