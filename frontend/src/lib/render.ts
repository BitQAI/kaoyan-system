/** 文本渲染：转义 → 关键词标注 → 记下标。全部返回 HTML 字符串，调用方用
 *  dangerouslySetInnerHTML 注入；所有输入都先转义，不存在未转义插值。 */
import { notation } from "./notation";

export const esc = (s: string): string =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const KEY_LINE_RE = /易错|注意|关键|核心|因此|必须|切记|区分/;
const SENTENCE_RE = /(?<=[。！？!?])\s*/;

/** 给关键词加下划线强调，每块最多 8 个、每个词只标一次（原型口径）。 */
export function emphasize(raw: string, keywords: string[] = []): string {
  const text = esc(raw);
  const kws = keywords.filter(Boolean).sort((a, b) => b.length - a.length);
  if (!kws.length) return notation(text);
  const re = new RegExp("(" + kws.map(escapeRe).join("|") + ")", "g");
  const seen = new Set<string>();
  const marked = text.split(re).map((part) => {
    if (kws.includes(part) && !seen.has(part) && seen.size < 8) {
      seen.add(part);
      return `<mark class="kw">${part}</mark>`;
    }
    return part;
  }).join("");
  return notation(marked);
}

/** 先保留原文换行分块，块内再按中文句号每 2 句成段；关键句加左侧强调线。 */
export function paragraphs(raw: string, keywords: string[] = []): string {
  const text = (raw || "").trim();
  if (!text) return "";
  const blocks = text.split(/\n+/).map((s) => s.trim()).filter(Boolean);
  return blocks.map((block) => {
    const parts = block.split(SENTENCE_RE).filter(Boolean);
    const groups: string[] = [];
    for (let i = 0; i < parts.length; i += 2) groups.push(parts.slice(i, i + 2).join(""));
    return groups.map((p) => {
      const cls = KEY_LINE_RE.test(p) ? ' class="key-line"' : "";
      return `<p${cls}>${emphasize(p, keywords)}</p>`;
    }).join("");
  }).join("");
}

/** 作文好词好句：把 keys 里的英文片段在上文首次出现处标出来。 */
export function highlightKeys(raw: string, keys: string[] = []): string {
  let html = esc(raw);
  const frags = new Set<string>();
  for (const key of keys) {
    key.split(/[\/|]/).forEach((part) => {
      part.replace(/…/g, " ")
        .split(/[,，;；]/)
        .map((s) => s.trim().replace(/^[.。]+|[.。]+$/g, ""))
        .filter((s) => s.includes(" ") || s.length >= 12)
        .forEach((s) => frags.add(s));
    });
  }
  for (const frag of [...frags].sort((a, b) => b.length - a.length)) {
    const escFrag = esc(frag);
    const at = html.indexOf(escFrag);
    if (at >= 0) {
      html = `${html.slice(0, at)}<mark class="kw">${escFrag}</mark>`
        + html.slice(at + escFrag.length);
    }
  }
  return html;
}

/** 「怎么考」按句成列表——不识别标签，实测七成段落无前缀。 */
export function examItems(exam: string): string[] {
  return (exam || "")
    .split(SENTENCE_RE)
    .map((s) => s.trim())
    .filter(Boolean);
}

/** 答案含 ①②③ 时拆成有序列表，否则按段落。 */
export function answerHtml(raw: string, keywords: string[] = []): string {
  const text = (raw || "").trim();
  if (!text) return "";
  if (/[①②③④⑤⑥]/.test(text)) {
    const parts = text.split(/(?=[①②③④⑤⑥])/).filter(Boolean);
    return '<ol class="answer-list">' + parts.map((p) =>
      `<li>${emphasize(p.replace(/^[①②③④⑤⑥]\s*/, ""), keywords)}</li>`).join("") + "</ol>";
  }
  return paragraphs(text, keywords);
}

export interface ScriptParts {
  ask: string;
  answer: string;
  analysis: string;
  /** 其余无前缀的段落 */
  rest: string;
}

/** 把朗读稿拆成 设问 / 答案 / 解析 三段（听视图只念设问 + 解析）。 */
export function splitScript(raw: string): ScriptParts {
  const out: ScriptParts = { ask: "", answer: "", analysis: "", rest: "" };
  const text = (raw || "").trim();
  if (!text) return out;
  const parts = text.split(/(?=设问：|答案：|解析：)/).filter(Boolean);
  for (const part of parts) {
    const m = part.match(/^(设问：|答案：|解析：)([\s\S]*)$/);
    if (!m) {
      out.rest += (out.rest ? "\n" : "") + part.trim();
      continue;
    }
    const body = m[2].trim();
    if (m[1] === "设问：") out.ask += body;
    else if (m[1] === "答案：") out.answer += body;
    else out.analysis += body;
  }
  return out;
}

/** 朗读稿按 设问 / 答案 / 解析 分块。 */
export function scriptHtml(raw: string, keywords: string[] = []): string {
  const text = (raw || "").trim();
  if (!text) return "";
  const parts = text.split(/(?=设问：|答案：|解析：)/).filter(Boolean);
  if (parts.length < 2) return `<div class="prose">${paragraphs(text, keywords)}</div>`;
  return '<div class="script-blocks">' + parts.map((part) => {
    const m = part.match(/^(设问：|答案：|解析：)([\s\S]*)$/);
    if (!m) return `<div class="prose">${paragraphs(part, keywords)}</div>`;
    return `<div class="script-block"><h4>${m[1].replace("：", "")}</h4>`
      + `<div class="prose">${paragraphs(m[2], keywords)}</div></div>`;
  }).join("") + "</div>";
}
