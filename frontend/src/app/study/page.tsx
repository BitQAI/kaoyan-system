"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useAi } from "@/components/AiProvider";
import ListenView from "@/components/ListenView";
import MemoView from "@/components/MemoView";
import PointDetail from "@/components/PointDetail";
import PointNav from "@/components/PointNav";
import { HeaderProgress, ProgressPanel } from "@/components/ProgressStrip";
import RangePicker from "@/components/RangePicker";
import SearchPanel from "@/components/SearchPanel";
import SubjectPicker from "@/components/SubjectPicker";
import { getJson } from "@/lib/api";
import { DEFAULT_SCOPE, readScope, scopeLabel, writeScope, type Scope } from "@/lib/scope";
import type { Manifest, PointIndex, ProgressStats, Subject, ViewMode } from "@/lib/types";

const ACCENTS: Record<string, string> = {
  "315": "#2563eb", "812": "#2f8f5b", "101": "#d9485f", "204": "#7c5cff",
};

function StudyInner() {
  const params = useSearchParams();
  const router = useRouter();
  const view = (params.get("view") as ViewMode) || "study";
  const sid = params.get("sid") || "812";
  const pid = params.get("pid");

  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [progress, setProgress] = useState<ProgressStats | null>(null);
  const [progressOpen, setProgressOpen] = useState(false);
  const [error, setError] = useState("");
  const [scope, setScope] = useState<Scope>(DEFAULT_SCOPE);
  const [pickerOpen, setPickerOpen] = useState(false);
  const ai = useAi();

  useEffect(() => {
    getJson<Manifest>("/api/manifest").then(setManifest).catch((e) => setError(String(e)));
  }, []);

  const refreshProgress = useCallback(() => {
    getJson<ProgressStats>(`/api/stats/progress?sid=${sid}`)
      .then(setProgress).catch(() => {});
  }, [sid]);

  useEffect(() => { refreshProgress(); }, [refreshProgress, view, pid]);

  useEffect(() => {
    setScope(readScope(sid));
    const accent = ACCENTS[sid] ?? "#2f8f5b";
    document.documentElement.style.setProperty("--accent", accent);
    document.documentElement.style.setProperty("--accent-soft", hexToSoft(accent));
  }, [sid]);

  const subject: Subject | undefined = manifest?.subjects.find((s) => s.id === sid);
  const allPoints: PointIndex[] = useMemo(
    () => (manifest?.points ?? []).filter((p) => p.subject_id === sid), [manifest, sid]);

  const visibleChapters = useMemo(() => {
    if (!subject) return [];
    return scope.chapters.length
      ? subject.chapters.filter((c) => scope.chapters.includes(c.id))
      : subject.chapters;
  }, [subject, scope.chapters]);

  const points = useMemo(() => {
    const ids = new Set(visibleChapters.map((c) => c.id));
    return allPoints.filter((p) => ids.has(p.chapter_id));
  }, [allPoints, visibleChapters]);

  const activePid = useMemo(() => {
    if (pid && points.some((p) => p.id === pid)) return pid;
    return points[0]?.id ?? null;
  }, [pid, points]);

  const chapterNames = useMemo(() => {
    const map: Record<string, string> = {};
    (subject?.chapters ?? []).forEach((c) => { map[c.id] = c.name; });
    return map;
  }, [subject]);

  function go(next: { view?: ViewMode; sid?: string; pid?: string | null }) {
    const sp = new URLSearchParams();
    sp.set("view", next.view ?? view);
    sp.set("sid", next.sid ?? sid);
    const target = next.pid === undefined ? pid : next.pid;
    if (target) sp.set("pid", target);
    router.push(`/study?${sp.toString()}`);
  }

  function applyScope(next: Scope) {
    setScope(next);
    writeScope(sid, next);
    setPickerOpen(false);
    if (pid && !points.some((p) => p.id === pid)) go({ pid: null });
  }

  if (error) {
    return (
      <div className="empty">
        加载失败：{error}
        <br />
        <Link href="/login">重新登录</Link>
      </div>
    );
  }
  if (!manifest || !subject) return <div className="empty">加载中…</div>;

  return (
    <>
      <nav className="control-bar" aria-label="视图控制">
        <SubjectPicker subjects={manifest.subjects} sid={sid} onPick={(id) => go({ sid: id, pid: null })} />
        {progress && (
          <HeaderProgress stats={progress} open={progressOpen}
            onToggle={() => setProgressOpen((o) => !o)} />
        )}
      </nav>

      {progress && <ProgressPanel stats={progress} open={progressOpen} />}

      {view === "study" && (
        <>
          <div className="subbar">
            <SearchPanel sid={sid} onPick={(id) => go({ pid: id })} />
          </div>
          <div className="content">
            <PointNav points={points} chapters={visibleChapters} activePid={activePid}
              onPick={(id) => go({ pid: id })}
              onOpenRange={() => setPickerOpen(true)}
              rangeLabel={scopeLabel(scope, chapterNames)} />
            {activePid
              ? <PointDetail pid={activePid} onNavigate={(id) => go({ pid: id })}
                  onRead={() => refreshProgress()} />
              : <div className="empty">这个范围还没有知识点。</div>}
          </div>
        </>
      )}

      {view !== "study" && (
        <div className="content">
          {view === "memo"
            ? <MemoView sid={sid} chapters={subject.chapters} />
            : <ListenView sid={sid} chapters={subject.chapters} />}
        </div>
      )}

      {view === "study" && (
        <RangePicker open={pickerOpen} chapters={subject.chapters} scope={scope}
          onClose={() => setPickerOpen(false)} onApply={applyScope} />
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
