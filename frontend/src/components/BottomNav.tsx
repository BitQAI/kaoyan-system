"use client";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { getJson, getToken } from "@/lib/api";

const TABS = [
  { key: "listen", label: "听", icon: "♪" },
  { key: "study", label: "学", icon: "▤" },
  { key: "memo", label: "记", icon: "◈" },
  { key: "me", label: "我的", icon: "◍" },
];

function NavInner() {
  const pathname = usePathname();
  const params = useSearchParams();
  const sid = params.get("sid") ?? "812";
  const view = params.get("view") ?? "study";
  const onMe = pathname.startsWith("/me");
  const [due, setDue] = useState(0);

  useEffect(() => {
    if (!getToken()) return;
    getJson<{ cards: { due: number } }>(`/api/stats/progress?sid=${sid}`)
      .then((d) => setDue(d.cards.due)).catch(() => {});
  }, [sid, pathname]);

  return (
    <nav className="bottom-nav" aria-label="主导航">
      {TABS.map((t) => {
        const active = t.key === "me" ? onMe : pathname.startsWith("/study") && view === t.key;
        const href = t.key === "me" ? "/me" : `/study?view=${t.key}&sid=${sid}`;
        return (
          <Link key={t.key} href={href} className={`bn-item${active ? " on" : ""}`}>
            <span className="bn-icon">{t.icon}</span>
            <span className="bn-label">{t.label}</span>
            {t.key === "memo" && due > 0 && <span className="bn-badge">{due}</span>}
          </Link>
        );
      })}
    </nav>
  );
}

export default function BottomNav() {
  return (
    <Suspense fallback={null}>
      <NavInner />
    </Suspense>
  );
}
