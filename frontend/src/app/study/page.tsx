"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import ChapterTree from "@/components/ChapterTree";
import ListenView from "@/components/ListenView";
import MemoView from "@/components/MemoView";
import PointDetail from "@/components/PointDetail";
import SearchPanel from "@/components/SearchPanel";
import { getJson } from "@/lib/api";
import type { Manifest, PointIndex, Subject, ViewMode } from "@/lib/types";

const ACCENTS: Record<string, string> = {
  "315": "#2563eb", "812": "#2f8f5b", "101": "#d9485f", "204": "#7c5cff",
};
const MODES: { key: ViewMode; label: string; hint: string }[] = [
  { key: "listen", label: "听", hint: "浏览器朗读朗读稿，听完自动记账；听不懂随时问 AI。" },
  { key: "study", label: "学", hint: "章节树 → 知识点详情；读不懂点「问 AI」，它会换个说法重讲。" },
  { key: "memo", label: "记", hint: "空格翻面，1/2/3 评分；答案要点可逐条核对。" },
];

function StudyInner() {
  const params = useSearchParams();
  const router = useRouter();
  const view = (params.get("view") as ViewMode) || "study";
  const sid = params.get("sid") || "812";
  const pid = params.get("pid");

  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [error, setError] = useState("");
  const [showTree, setShowTree] = useState(false);

  useEffect(() => {
    getJson<Manifest>("/api/manifest")
      .then(setManifest)
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    const accent = ACCENTS[sid] ?? "#2f8f5b";
    document.documentElement.style.setProperty("--accent", accent);
    document.documentElement.style.setProperty("--accent-soft", hexToSoft(accent));
  }, [sid]);

  const subject: Subject | undefined = manifest?.subjects.find((s) => s.id === sid);
  const points: PointIndex[] = useMemo(
    () => (manifest?.points ?? []).filter((p) => p.subject_id === sid), [manifest, sid]);
  const activePid = pid ?? points[0]?.id ?? null;

  function go(next: { view?: ViewMode; sid?: string; pid?: string | null }) {
    const sp = new URLSearchParams();
    sp.set("view", next.view ?? view);
    sp.set("sid", next.sid ?? sid);
    const target = next.pid === undefined ? pid : next.pid;
    if (target) sp.set("pid", target);
    router.push(`/study?${sp.toString()}`);
  }

  if (error) return <div className="empty">后端连不上：{error}。请确认 uvicorn 在 :8000 运行。</div>;
  if (!manifest || !subject) return <div className="empty">加载中…</div>;

  const hint = MODES.find((m) => m.key === view)?.hint ?? "";

  return (
    <>
      <nav className="control-bar" aria-label="视图控制">
        <div className="tabs subject-tabs">
          {manifest.subjects.map((s) => (
            <button key={s.id} className={`tab${s.id === sid ? " on" : ""}`}
              onClick={() => go({ sid: s.id, pid: null })}>
              <b>{s.id}</b>{s.name.replace(/^\d+\s*/, "").slice(0, 8)}
            </button>
          ))}
        </div>
        <span className="spacer" />
        <div className="mode-tabs" role="tablist">
          {MODES.map((m) => (
            <button key={m.key} role="tab" aria-selected={view === m.key}
              className={view === m.key ? "on" : ""}
              onClick={() => go({ view: m.key, pid: m.key === "study" ? activePid : null })}>
              {m.label}
            </button>
          ))}
        </div>
        <Link className="ghost" href="/history" style={{ textDecoration: "none" }}>问答历史</Link>
      </nav>

      {view === "study" ? (
        <>
          <div className="subbar">
            <SearchPanel sid={sid} onPick={(id) => go({ pid: id })} />
          </div>
          <div className="mode-hint">{hint}</div>
          <div className="content">
            <div className="study-layout">
              <button className="tree-toggle" onClick={() => setShowTree((s) => !s)}>
                {showTree ? "收起章节树 ▴" : "展开章节树 ▾"}
              </button>
              <div className={`tree-holder${showTree ? " open" : ""}`}>
                <ChapterTree subject={subject} points={points} activePid={activePid}
                  onPick={(id) => { setShowTree(false); go({ pid: id }); }} />
              </div>
              {activePid
                ? <PointDetail pid={activePid} onNavigate={(id) => go({ pid: id })} />
                : <div className="empty">这一科还没有知识点。</div>}
            </div>
          </div>
        </>
      ) : (
        <>
          <div className="mode-hint">{hint}</div>
          <div className="content">
            {view === "memo" ? <MemoView sid={sid} /> : <ListenView sid={sid} />}
          </div>
        </>
      )}
    </>
  );
}

function hexToSoft(hex: string): string {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},.14)`;
}

export default function StudyPage() {
  return (
    <Suspense fallback={<div className="empty">加载中…</div>}>
      <StudyInner />
    </Suspense>
  );
}
