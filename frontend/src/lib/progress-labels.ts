import type { PaceTrend } from "./progress-types";

export const STATUS_LABEL: Record<string, string> = {
  ok: "按计划",
  risk: "有风险",
  late: "来不及",
  insufficient: "数据不足",
  empty: "无记录",
  stalled: "停滞",
};

export const TREND_LABEL: Record<PaceTrend, string> = {
  up: "加速",
  down: "放缓",
  flat: "平稳",
};

export function finishLabel(dim: {
  finish_date: string | null;
  finish_earliest?: string | null;
  finish_latest?: string | null;
}): string {
  if (!dim.finish_date) return "暂无预测";
  const earliest = dim.finish_earliest ?? dim.finish_date;
  const latest = dim.finish_latest ?? dim.finish_date;
  if (earliest === latest) return `预计 ${dim.finish_date}`;
  return `预计 ${dim.finish_date}（最早 ${earliest} · 最晚 ${latest}）`;
}
