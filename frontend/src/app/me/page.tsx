"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import ProgressDashboard from "@/components/ProgressDashboard";
import {
  GAPS, MODES, REPEATS, readGap, readMode, readRepeat, writeSetting,
  type ListenMode,
} from "@/lib/listen-player";
import { applyTheme, readTheme, type Theme } from "@/lib/theme";
import { delJson, getJson, setToken } from "@/lib/api";
import type { ProgressStats } from "@/lib/types";

interface FavPoint {
  ref_id: string; title: string; point: string; subject_id: string;
  priority: string; chapter_name: string;
}
interface FavCard {
  ref_id: string; question: string; point_id: string; title: string;
  subject_id: string; card_kind: string; last_result: string | null;
}
interface WeakItem {
  card_id: string; question: string; title: string; subject_id: string;
  last_result: string; lapses: number; chapter_name: string; priority: string;
}

const PRIORITY_LABEL: Record<string, string> = {
  "★": "高频", "●": "易错", "○": "普通",
};

export default function MePage() {
  const [tab, setTab] = useState<"fav" | "weak" | "plan" | "about">("fav");
  const [favPoints, setFavPoints] = useState<FavPoint[]>([]);
  const [favCards, setFavCards] = useState<FavCard[]>([]);
  const [weak, setWeak] = useState<WeakItem[]>([]);
  const [weakCounts, setWeakCounts] = useState({ forgot: 0, fuzzy: 0, total: 0 });
  const [stats, setStats] = useState<ProgressStats | null>(null);
  const [error, setError] = useState("");
  const [theme, setTheme] = useState<Theme>("auto");
  const [mode, setMode] = useState<ListenMode>("wms");
  const [repeat, setRepeat] = useState(1);
  const [gap, setGap] = useState(1);

  useEffect(() => {
    setTheme(readTheme());
    setMode(readMode());
    setRepeat(readRepeat());
    setGap(readGap());
  }, []);

  useEffect(() => {
    getJson<{ items: FavPoint[] }>("/api/favorites?kind=point")
      .then((d) => setFavPoints(d.items)).catch(() => {});
    getJson<{ items: FavCard[] }>("/api/favorites?kind=card")
      .then((d) => setFavCards(d.items)).catch(() => {});
    getJson<{ items: WeakItem[]; counts: typeof weakCounts }>("/api/review/weak?limit=200")
      .then((d) => { setWeak(d.items); setWeakCounts(d.counts); })
      .catch((e) => setError(String(e)));
    getJson<ProgressStats>("/api/stats/progress").then(setStats).catch(() => {});
  }, []);

  async function unfav(kind: string, id: string) {
    await fetch("/api/favorites", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind, ref_id: id, on: false }),
    }).catch(() => {});
    if (kind === "point") setFavPoints((list) => list.filter((x) => x.ref_id !== id));
    else setFavCards((list) => list.filter((x) => x.ref_id !== id));
  }

  function logout() {
    setToken(null);
    void delJson("/api/auth/me").catch(() => {});
    window.location.href = "/login";
  }

  return (
    <main className="me-page">
      <header className="me-head">
        <h1>我的</h1>
        {stats && (
          <p className="muted" style={{ fontSize: 12.5, margin: "4px 0 0" }}>
            已读 {stats.points.read}/{stats.points.total} 点 ·
            已答 {stats.cards.seen}/{stats.cards.total} 卡 ·
            已听 {stats.listen.heard}/{stats.listen.total}
          </p>
        )}
      </header>

      {error && <div className="empty">加载失败：{error}</div>}

      <div className="me-tabs">
        <button className={tab === "fav" ? "on" : ""} onClick={() => setTab("fav")}>
          收藏（{favPoints.length + favCards.length}）
        </button>
        <button className={tab === "weak" ? "on" : ""} onClick={() => setTab("weak")}>
          错题本（{weakCounts.total}）
        </button>
        <button className={tab === "plan" ? "on" : ""} onClick={() => setTab("plan")}>进度预测</button>
        <button className={tab === "about" ? "on" : ""} onClick={() => setTab("about")}>账号</button>
      </div>

      {tab === "fav" && (
        <section>
          {favPoints.length === 0 && favCards.length === 0 && (
            <div className="empty">还没有收藏。在知识点或卡片上点 ☆ 收藏。</div>
          )}
          {favPoints.length > 0 && <h3 className="me-sub">知识点（{favPoints.length}）</h3>}
          {favPoints.map((p) => (
            <div className="me-row" key={p.ref_id}>
              <Link href={`/study?view=study&sid=${p.subject_id}&pid=${p.ref_id}`} className="me-main">
                <b>{p.title}</b>
                <span className="muted">{p.chapter_name} · {PRIORITY_LABEL[p.priority] ?? p.priority}</span>
              </Link>
              <button className="badge-btn" onClick={() => void unfav("point", p.ref_id)}>移除</button>
            </div>
          ))}
          {favCards.length > 0 && <h3 className="me-sub">卡片（{favCards.length}）</h3>}
          {favCards.map((c) => (
            <div className="me-row" key={c.ref_id}>
              <Link href={`/study?view=memo&sid=${c.subject_id}`} className="me-main">
                <b>{c.question}</b>
                <span className="muted">{c.title} · {c.card_kind}</span>
              </Link>
              <button className="badge-btn" onClick={() => void unfav("card", c.ref_id)}>移除</button>
            </div>
          ))}
        </section>
      )}

      {tab === "weak" && (
        <section>
          <p className="muted" style={{ fontSize: 12.5, margin: "0 0 10px" }}>
            记模块评为「忘了 {weakCounts.forgot} · 吃力 {weakCounts.fuzzy}」的卡片，忘了排在前面。
          </p>
          {weak.length === 0 && <div className="empty">还没有错题，去「记」里过一轮吧。</div>}
          {weak.map((w) => (
            <div className="me-row" key={w.card_id}>
              <Link href={`/study?view=memo&sid=${w.subject_id}`} className="me-main">
                <b>{w.question}</b>
                <span className="muted">
                  {w.chapter_name} · {w.last_result} · 失误 {w.lapses} 次
                </span>
              </Link>
              <span className={`badge ${w.last_result === "忘了" ? "weak-bad" : "weak-fuzzy"}`}>
                {w.last_result}
              </span>
            </div>
          ))}
        </section>
      )}

      {tab === "plan" && <ProgressDashboard />}

      {tab === "about" && (
        <section>
          <div className="me-row">
            <span className="me-main">
              <b>问答历史</b>
              <span className="muted">所有 AI 会话</span>
            </span>
            <Link className="badge-btn" href="/history">打开</Link>
          </div>
          <div className="me-row" style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
            <span className="me-main">
              <b>外观</b>
              <span className="muted">默认跟随系统；手动选择只影响这台设备</span>
            </span>
            <div className="theme-row">
              {([["auto", "跟随系统"], ["light", "浅色"], ["dark", "深色"]] as [Theme, string][])
                .map(([k, label]) => (
                  <button key={k} className={theme === k ? "on" : ""}
                    onClick={() => { setTheme(k); applyTheme(k); }}>{label}</button>
                ))}
            </div>
          </div>
          <h3 className="me-sub">听学</h3>
          <div className="me-row" style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
            <span className="me-main">
              <b>听法</b>
              <span className="muted">单词卡按什么顺序朗读</span>
            </span>
            <div className="theme-row" role="group" aria-label="听法">
              {MODES.map((m) => (
                <button key={m.id} className={mode === m.id ? "on" : ""}
                  aria-pressed={mode === m.id}
                  onClick={() => { setMode(m.id); writeSetting("mode", m.id); }}>
                  {m.label}
                </button>
              ))}
            </div>
          </div>
          <div className="me-row" style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
            <span className="me-main">
              <b>遍数</b>
              <span className="muted">每张卡重复几遍</span>
            </span>
            <div className="theme-row" role="group" aria-label="遍数">
              {REPEATS.map((n) => (
                <button key={n} className={repeat === n ? "on" : ""}
                  aria-pressed={repeat === n}
                  onClick={() => { setRepeat(n); writeSetting("repeat", n); }}>
                  {n}
                </button>
              ))}
            </div>
          </div>
          <div className="me-row" style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
            <span className="me-main">
              <b>间隔</b>
              <span className="muted">连播时两张卡之间停几秒</span>
            </span>
            <div className="theme-row" role="group" aria-label="间隔">
              {GAPS.map((n) => (
                <button key={n} className={gap === n ? "on" : ""}
                  aria-pressed={gap === n}
                  onClick={() => { setGap(n); writeSetting("gap", n); }}>
                  {n}s
                </button>
              ))}
            </div>
          </div>
          <div className="me-row">
            <span className="me-main">
              <b>退出登录</b>
              <span className="muted">清除本机记住的登录状态</span>
            </span>
            <button className="badge-btn" onClick={logout}>退出</button>
          </div>
        </section>
      )}
    </main>
  );
}
