"use client";
import { useFavorites } from "./FavoritesProvider";

export const PRIORITY_LABEL: Record<string, string> = {
  "★": "高频", "●": "易错", "○": "普通",
};

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
