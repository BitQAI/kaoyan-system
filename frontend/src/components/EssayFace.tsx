"use client";
import { highlightKeys } from "@/lib/render";
import type { EssayPayload } from "@/lib/types";

type Head = { kind: "salutation" | "title"; text: string };

/** 信件拆称呼，通知拆标题与日期，末段拆落款；其余保持正文。 */
function splitPara(format: EssayPayload["format"], raw: string, first: boolean, last: boolean) {
  let text = raw.trim();
  let head: Head | undefined;
  let sign: string[] | undefined;
  let date: string | undefined;

  if (format === "notice") {
    const d = text.match(/\n+(\d{4}[年-].*|[A-Z][a-z]+ \d{1,2}, \d{4})\s*$/);
    if (d) {
      date = d[1].trim();
      text = text.slice(0, d.index).trim();
    }
    if (first) {
      const m = text.match(/^Notice\b[.!\s]*/i);
      if (m) {
        head = { kind: "title", text: "Notice" };
        text = text.slice(m[0].length).trim();
      }
    }
  }

  if (format === "letter" && first) {
    const m = text.match(/^(Dear[^,]*,\s*)/i);
    if (m) {
      head = { kind: "salutation", text: m[1].trim() };
      text = text.slice(m[1].length).trim();
    }
  }

  if (format === "letter" && last) {
    const m = text.match(
      /((?:Yours sincerely|Yours faithfully|Sincerely yours|Yours truly|Best regards|Yours),?[\s\S]*)$/i);
    if (m) {
      sign = m[1].trim().replace(/\.$/, "").split(/,\s*|\n+/).map((s) => s.trim()).filter(Boolean);
      text = text.slice(0, m.index).trim();
    }
  }

  return { head, body: text, sign, date };
}

export default function EssayFace({ p }: { p: EssayPayload }) {
  const met = p.min_words ? p.word_count >= p.min_words : true;
  return (
    <div className="essay-face">
      <div className="essay-meta">
        {p.exam && <span className="badge">{p.exam}</span>}
        {p.scope === "full" ? (
          <span className={`essay-count${met ? " ok" : " short"}`}>
            {p.word_count} 词 · 要求 ≥{p.min_words}
          </span>
        ) : (
          <span className="essay-count">
            {p.word_count} 词{p.index && p.total ? ` · 第 ${p.index}/${p.total} 段` : ""}
          </span>
        )}
      </div>

      {p.figure && (
        <figure className="essay-figure">
          <div className="essay-figure-svg"
            dangerouslySetInnerHTML={{ __html: p.figure.svg }} />
          {p.figure.caption && <figcaption>{p.figure.caption}</figcaption>}
        </figure>
      )}

      {p.paragraphs.map((para, i) => {
        const { head, body, sign, date } = splitPara(
          p.format, para.en, i === 0, i === p.paragraphs.length - 1);
        return (
          <section className="essay-para" key={i}>
            {para.role && <div className="essay-role">{para.role}</div>}
            {head?.kind === "title" && <div className="essay-title">{head.text}</div>}
            {head?.kind === "salutation" && <div className="essay-salutation">{head.text}</div>}
            {body && (
              <div className="essay-en"
                dangerouslySetInnerHTML={{ __html: highlightKeys(body, para.keys) }} />
            )}
            {sign && (
              <div className="essay-sign">
                {sign.map((line) => <div key={line}>{line}</div>)}
              </div>
            )}
            {date && <div className="essay-date">{date}</div>}
            {para.cn && <div className="essay-cn">{para.cn}</div>}
          </section>
        );
      })}
    </div>
  );
}
