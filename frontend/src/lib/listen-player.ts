import { isWordPayload, type ListenItem, type WordPayload } from "./types";

/** 听法：词+义+句 / 词+义 / 只听句 */
export type ListenMode = "wms" | "wm" | "sent";
export const MODES: { id: ListenMode; label: string }[] = [
  { id: "wms", label: "词+义+句" },
  { id: "wm", label: "词+义" },
  { id: "sent", label: "只听句" },
];

export const REPEATS = [1, 2, 3];
export const GAPS = [0, 1, 2, 3];

export interface Segment {
  clip: string | null;   // null = 整卡音频
  label: string;
}

const MODE_KEY = "kaoyan.listen.mode";
const REPEAT_KEY = "kaoyan.listen.repeat";
const GAP_KEY = "kaoyan.listen.gap";

function readNum(key: string, fallback: number, allowed: number[]): number {
  try {
    const raw = localStorage.getItem(key);
    if (raw === null) return fallback;
    const n = Number(raw);
    return allowed.includes(n) ? n : fallback;
  } catch {
    return fallback;
  }
}

export function readMode(): ListenMode {
  try {
    const m = localStorage.getItem(MODE_KEY) as ListenMode | null;
    return MODES.some((x) => x.id === m) ? (m as ListenMode) : "wms";
  } catch {
    return "wms";
  }
}

export function writeSetting(key: "mode" | "repeat" | "gap", value: string | number): void {
  try {
    const k = key === "mode" ? MODE_KEY : key === "repeat" ? REPEAT_KEY : GAP_KEY;
    localStorage.setItem(k, String(value));
  } catch { /* 隐私模式忽略 */ }
}

export function readRepeat(): number {
  return readNum(REPEAT_KEY, 1, REPEATS);
}

export function readGap(): number {
  return readNum(GAP_KEY, 1, GAPS);
}

export function wordPayloadOf(item: ListenItem | undefined): WordPayload | null {
  return isWordPayload(item?.payload) ? item.payload : null;
}

/** 一张卡要读的片段；词卡按听法拆段，其余卡整卡读 */
export function segmentsFor(item: ListenItem, mode: ListenMode): Segment[] {
  const p = wordPayloadOf(item);
  if (!p) return [{ clip: null, label: "整卡" }];
  if (p.type === "confusable") return [{ clip: "meaning", label: "辨析" }];
  if (p.type === "phrase") {
    return mode === "sent"
      ? [{ clip: "meaning", label: "释义" }]
      : [{ clip: "word", label: "词组" }, { clip: "meaning", label: "释义" }];
  }
  if (mode === "sent") return [{ clip: "sentence", label: "例句" }];
  if (mode === "wm") {
    return [{ clip: "word", label: "单词" }, { clip: "meaning", label: "释义" }];
  }
  return [
    { clip: "word", label: "单词" },
    { clip: "meaning", label: "释义" },
    { clip: "sentence", label: "例句" },
  ];
}
