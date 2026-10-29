export interface Scope {
  /** 选中的章节 id；空数组 = 该科全部 */
  chapters: string[];
  /** 每批条数 */
  limit: number;
}

export const DEFAULT_SCOPE: Scope = { chapters: [], limit: 20 };

const key = (sid: string) => `kaoyan.scope.v1.${sid}`;

export function readScope(sid: string): Scope {
  try {
    const raw = localStorage.getItem(key(sid));
    if (!raw) return { ...DEFAULT_SCOPE };
    const s = JSON.parse(raw);
    return {
      chapters: Array.isArray(s?.chapters) ? s.chapters.filter((x: unknown) => typeof x === "string") : [],
      limit: typeof s?.limit === "number" && s.limit > 0 ? Math.min(s.limit, 100) : DEFAULT_SCOPE.limit,
    };
  } catch {
    return { ...DEFAULT_SCOPE };
  }
}

export function writeScope(sid: string, scope: Scope): void {
  try {
    localStorage.setItem(key(sid), JSON.stringify(scope));
  } catch { /* 忽略 */ }
}

export function scopeLabel(scope: Scope, chapterNames: Record<string, string>): string {
  if (!scope.chapters.length) return "全部章节";
  if (scope.chapters.length === 1) return chapterNames[scope.chapters[0]] ?? "1 章";
  return `已选 ${scope.chapters.length} 章`;
}
