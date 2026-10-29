"use client";
import { usePathname, useSearchParams } from "next/navigation";
import { createContext, useCallback, useContext, useMemo, useState } from "react";
import AiChat from "./AiChat";
import AiFab from "./AiFab";

export interface AiTarget {
  point_id?: string;
  /** 绑定到具体题目时，问答历史按这张卡归档 */
  card_id?: string;
  title?: string;
  description?: string;
  question?: string;
}

interface AiCtx {
  open: (target?: AiTarget) => void;
  close: () => void;
  isOpen: boolean;
}

const Ctx = createContext<AiCtx>({ open: () => {}, close: () => {}, isOpen: false });

export const useAi = () => useContext(Ctx);

export function AiProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const params = useSearchParams();
  const view = params.get("view") ?? "study";
  // 听/记 每张卡都有「问 AI」，悬浮球会挡住「下一条」；我的页也不需要
  const hideFab = view === "listen" || view === "memo" || pathname.startsWith("/me");
  const [isOpen, setOpen] = useState(false);
  const [target, setTarget] = useState<AiTarget | null>(null);

  const open = useCallback((next?: AiTarget) => {
    setTarget(next ?? null);
    setOpen(true);
  }, []);
  const close = useCallback(() => setOpen(false), []);
  const value = useMemo(() => ({ open, close, isOpen }), [open, close, isOpen]);

  return (
    <Ctx.Provider value={value}>
      {children}
      {!hideFab && <AiFab open={isOpen} onToggle={() => setOpen((o) => !o)} />}
      <AiChat open={isOpen} onClose={close} target={target} />
    </Ctx.Provider>
  );
}
