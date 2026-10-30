/**
 * 「听 / 记」批内位置：离开页面（比如去「学」看知识点）再回来时，
 * 在新拉到的批次里找同一张卡继续，而不是从第一张重来。
 * 存在 sessionStorage：只对当前标签页有效，关掉就没了，不会跨天残留。
 */
const PREFIX = "kaoyan.resume";

function key(view: string, sid: string): string {
  return `${PREFIX}.${view}.${sid}`;
}

export function readResume(view: string, sid: string): string | null {
  try {
    return sessionStorage.getItem(key(view, sid));
  } catch {
    return null;
  }
}

export function saveResume(view: string, sid: string, cardId: string): void {
  try {
    sessionStorage.setItem(key(view, sid), cardId);
  } catch {
    /* 隐私模式忽略 */
  }
}

export function clearResume(view: string, sid: string): void {
  try {
    sessionStorage.removeItem(key(view, sid));
  } catch {
    /* 忽略 */
  }
}
