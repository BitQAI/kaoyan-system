"use client";
import { useEffect, useRef, useState } from "react";
import { RATE_MAX, RATE_MIN } from "@/lib/listen";

const STEP = 0.05;
const ITEM_H = 40;
const VIEW_H = 240;

const RATES: number[] = [];
for (let v = RATE_MIN; v <= RATE_MAX + 1e-9; v += STEP) {
  RATES.push(Number(v.toFixed(2)));
}

/** 语速滚轮：仿 iOS 闹钟的时间轮盘，滚动吸附、中间高亮，停下即生效。 */
export default function RateWheel({ open, value, onChange, onClose }: {
  open: boolean;
  value: number;
  onChange: (rate: number) => void;
  onClose: () => void;
}) {
  const listRef = useRef<HTMLDivElement | null>(null);
  const valueRef = useRef(value);
  const timer = useRef<number | null>(null);
  const [idx, setIdx] = useState(0);
  valueRef.current = value;

  useEffect(() => {
    if (!open) return;
    const start = Math.max(0, RATES.indexOf(Number(valueRef.current.toFixed(2))));
    setIdx(start);
    const t = window.setTimeout(() => {
      if (listRef.current) listRef.current.scrollTop = start * ITEM_H;
    }, 30);
    return () => window.clearTimeout(t);
  }, [open]);

  useEffect(() => () => {
    if (timer.current !== null) window.clearTimeout(timer.current);
  }, []);

  function onScroll() {
    const el = listRef.current;
    if (!el) return;
    const i = Math.max(0, Math.min(RATES.length - 1, Math.round(el.scrollTop / ITEM_H)));
    setIdx(i);
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      onChange(RATES[i]);
      if (navigator.vibrate) navigator.vibrate(4);
    }, 140);
  }

  function jump(i: number) {
    listRef.current?.scrollTo({ top: i * ITEM_H, behavior: "smooth" });
  }

  if (!open) return null;

  return (
    <div className="picker-mask" onClick={onClose}>
      <div className="picker rate-sheet" role="dialog" aria-label="朗读语速"
        onClick={(e) => e.stopPropagation()}>
        <div className="picker-head">
          <b>朗读语速</b>
          <span className="spacer" />
          <span className="rate-preview">{RATES[idx].toFixed(2)}×</span>
          <button className="badge-btn" onClick={onClose}>完成</button>
        </div>
        <div className="rate-wheel-wrap">
          <div className="rate-wheel-band" />
          <div className="rate-wheel" ref={listRef} onScroll={onScroll}
            role="listbox" aria-label="语速">
            <div style={{ height: (VIEW_H - ITEM_H) / 2 }} />
            {RATES.map((r, i) => (
              <button key={r} role="option" aria-selected={i === idx}
                className={`rate-item${i === idx ? " on" : ""}`}
                style={{ height: ITEM_H }} onClick={() => jump(i)}>
                {r.toFixed(2)}×
              </button>
            ))}
            <div style={{ height: (VIEW_H - ITEM_H) / 2 }} />
          </div>
          <div className="rate-wheel-fade top" />
          <div className="rate-wheel-fade bottom" />
        </div>
      </div>
    </div>
  );
}
