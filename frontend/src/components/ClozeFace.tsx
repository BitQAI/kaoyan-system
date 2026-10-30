"use client";
import { useState } from "react";
import type { Card } from "@/lib/types";
import { checkCloze, parseCloze } from "@/lib/cloze";

/** 默写卡：正面填空自测，背面给完整段落 */
export default function ClozeFace({ card, side }:
  { card: Card; side: "front" | "back" }) {
  const segments = parseCloze(card.question);
  const blanks = Math.max(0, segments.length - 1);
  const answers = card.answer_points;
  const [values, setValues] = useState<string[]>(() => Array(blanks).fill(""));
  const [checked, setChecked] = useState(false);

  const results = checked ? checkCloze(values, answers) : [];
  const right = results.filter(Boolean).length;
  const mismatch = blanks !== answers.length;

  if (side === "back") {
    return (
      <div className="cloze-face">
        <div className="block">
          <h4>完整段落</h4>
          <div className="prose">{card.answer}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="cloze-face">
      <div className="block">
        <h4>补全句子（每空一个词）</h4>
        <div className="cloze-line">
          {segments.map((t, i) => (
            <span key={i}>
              {t}
              {i < segments.length - 1 && (
                <input
                  className={checked ? (results[i] ? "ok" : "no") : ""}
                  value={values[i] ?? ""}
                  autoComplete="off"
                  spellCheck={false}
                  onChange={(e) => {
                    const next = [...values];
                    next[i] = e.target.value;
                    setValues(next);
                    setChecked(false);
                  }}
                />
              )}
            </span>
          ))}
        </div>
        <div className="cloze-actions">
          <button className="btn primary" onClick={(e) => {
            e.stopPropagation();
            setChecked(true);
          }}>检查</button>
          {checked && (
            <span className={`cloze-result ${right === answers.length ? "ok" : "no"}`}>
              {right} / {answers.length} 正确
            </span>
          )}
        </div>
        {mismatch && (
          <div className="cloze-warn">
            答案数与空格数不一致（{answers.length} / {blanks}），这条需要回到元数据修正
          </div>
        )}
        {checked && (
          <div className="cloze-answer">
            标准答案：{answers.map((a, i) => <b key={i}>{a}</b>)}
          </div>
        )}
      </div>
    </div>
  );
}
