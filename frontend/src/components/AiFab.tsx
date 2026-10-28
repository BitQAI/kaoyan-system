"use client";
import { useEffect, useRef, useState } from "react";

const POS_KEY = "kaoyan.ai-fab.pos.v1";
const FAB_SIZE = 54;
const MARGIN = 8;
const LONG_PRESS_MS = 450;

function clampPos(x: number, y: number) {
  const maxX = Math.max(MARGIN, window.innerWidth - FAB_SIZE - MARGIN);
  const maxY = Math.max(MARGIN, window.innerHeight - FAB_SIZE - MARGIN);
  return { x: Math.min(Math.max(MARGIN, x), maxX), y: Math.min(Math.max(MARGIN, y), maxY) };
}

function readPos(): { x: number; y: number } | null {
  try {
    const raw = localStorage.getItem(POS_KEY);
    if (!raw) return null;
    const p = JSON.parse(raw);
    if (typeof p?.x !== "number" || typeof p?.y !== "number") return null;
    return clampPos(p.x, p.y);
  } catch {
    return null;
  }
}

export default function AiFab({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const [dragging, setDragging] = useState(false);
  const btnRef = useRef<HTMLButtonElement | null>(null);
  const timerRef = useRef<number | null>(null);
  const posRef = useRef<{ x: number; y: number } | null>(null);
  const dragRef = useRef({ active: false, startX: 0, startY: 0, origX: 0, origY: 0, suppressClick: false });

  useEffect(() => {
    const p = readPos();
    posRef.current = p;
    setPos(p);
  }, []);

  function clearTimer() {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }

  function onPointerDown(e: React.PointerEvent) {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    const d = dragRef.current;
    d.suppressClick = false;
    const r = btnRef.current?.getBoundingClientRect();
    const o = posRef.current ?? (r ? { x: r.left, y: r.top } : { x: 0, y: 0 });
    d.startX = e.clientX;
    d.startY = e.clientY;
    d.origX = o.x;
    d.origY = o.y;
    d.active = false;
    clearTimer();
    timerRef.current = window.setTimeout(() => {
      d.active = true;
      setDragging(true);
      try {
        btnRef.current?.setPointerCapture(e.pointerId);
      } catch { /* 忽略 */ }
      try {
        navigator.vibrate?.(20);
      } catch { /* 忽略 */ }
    }, LONG_PRESS_MS);
  }

  function onPointerMove(e: React.PointerEvent) {
    const d = dragRef.current;
    if (d.active) {
      const p = clampPos(d.origX + e.clientX - d.startX, d.origY + e.clientY - d.startY);
      posRef.current = p;
      setPos(p);
    } else if (timerRef.current !== null && Math.hypot(e.clientX - d.startX, e.clientY - d.startY) > 10) {
      clearTimer();
    }
  }

  function finishDrag(save: boolean) {
    clearTimer();
    const d = dragRef.current;
    if (!d.active) return;
    d.active = false;
    setDragging(false);
    d.suppressClick = true;
    if (save && posRef.current) {
      try {
        localStorage.setItem(POS_KEY, JSON.stringify(posRef.current));
      } catch { /* 忽略 */ }
    }
  }

  function onPointerCancel() {
    const d = dragRef.current;
    if (!d.active) {
      clearTimer();
      return;
    }
    const p = { x: d.origX, y: d.origY };
    posRef.current = p;
    setPos(p);
    finishDrag(false);
  }

  function onClick(e: React.MouseEvent) {
    const d = dragRef.current;
    if (d.suppressClick) {
      d.suppressClick = false;
      e.preventDefault();
      e.stopPropagation();
      return;
    }
    onToggle();
  }

  function onDoubleClick() {
    posRef.current = null;
    setPos(null);
    try {
      localStorage.removeItem(POS_KEY);
    } catch { /* 忽略 */ }
  }

  return (
    <button
      ref={btnRef}
      className={`ai-fab${dragging ? " dragging" : ""}`}
      style={pos ? { left: pos.x, top: pos.y, right: "auto", bottom: "auto" } : undefined}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={() => finishDrag(true)}
      onPointerCancel={onPointerCancel}
      onClick={onClick}
      onDoubleClick={onDoubleClick}
      title="点击问 AI · 长按拖动换位 · 双击复位"
      aria-label={open ? "关闭 AI 助手" : "AI 助手"}
    >
      {open ? "×" : "✦"}
    </button>
  );
}
