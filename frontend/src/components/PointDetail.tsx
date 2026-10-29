"use client";
import { useEffect, useState } from "react";
import { getJson, postJson } from "@/lib/api";
import { answerHtml, emphasize, examItems, paragraphs } from "@/lib/render";
import type { Figure, PointDetail as Point } from "@/lib/types";
import { useAi } from "./AiProvider";
import { PriorityBadge, StarButton, uniqueLabels } from "./Badges";
import SvgFigure from "./SvgFigure";

export default function PointDetail({
  pid, onNavigate, onRead,
}: { pid: string; onNavigate: (pid: string) => void; onRead?: () => void }) {
  const [point, setPoint] = useState<Point | null>(null);
  const [error, setError] = useState("");
  const [zoom, setZoom] = useState<Figure | null>(null);
  const [zoomScale, setZoomScale] = useState(1);
  const [source, setSource] = useState<{ text: string; note: string } | null>(null);
  const [showSource, setShowSource] = useState(false);
  const ai = useAi();

  useEffect(() => {
    setPoint(null);
    setError("");
    setShowSource(false);
    setSource(null);
    getJson<Point>(`/api/points/${encodeURIComponent(pid)}`)
      .then((p) => {
        setPoint(p);
        void postJson("/api/progress/point", { point_id: pid })
          .then(() => onRead?.())
          .catch(() => {});
      })
      .catch((e) => setError(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid]);

  async function toggleSource() {
    if (!source) {
      const data = await getJson<{ text: string; note: string }>(
        `/api/points/${encodeURIComponent(pid)}/source`).catch(() => ({ text: "", note: "溯源不可用" }));
      setSource(data);
    }
    setShowSource((s) => !s);
  }

  function openZoom(fig: Figure) {
    setZoomScale(1);
    setZoom(fig);
  }

  if (error) return <div className="empty">加载失败：{error}</div>;
  if (!point) return <div className="empty">加载中…</div>;

  const first = point.cards[0];
  return (
    <article className="study-card">
      <div className="card-top">
        {uniqueLabels(point.exam_types).map((t) => <span className="badge" key={t}>{t}</span>)}
        <PriorityBadge priority={point.priority} />
        <span className="spacer" />
        <StarButton kind="point" id={point.id} title={point.title} />
        <button
          className="ai-entry-btn"
          onClick={() => ai.open({
            point_id: point.id,
            title: point.title,
            description: point.point,
            question: `讲解「${point.title}」的要点和易错点`,
          })}
        >问 AI</button>
      </div>

      <h2 className="study-title">{point.title}</h2>
      <p className="study-point">{point.point}</p>

      <div className="study-grid">
        <section className="explain">
          <h3>考点解析</h3>
          <div className="prose" dangerouslySetInnerHTML={{ __html: paragraphs(point.explain, point.keywords) }} />
          {point.media.length > 0 && (
            <div className="media">
              {point.media.map((m, i) => <SvgFigure key={i} figure={m} onZoom={openZoom} />)}
            </div>
          )}
          <h3>怎么考</h3>
          <ul className="exam-list">
            {examItems(point.exam).map((line, i) => (
              <li key={i} dangerouslySetInnerHTML={{ __html: emphasize(line, point.keywords) }} />
            ))}
          </ul>
          {point.keywords.length > 0 && (
            <div className="chips">
              {point.keywords.map((k) => <span className="chip" key={k}>{k}</span>)}
            </div>
          )}
        </section>

        <section className="question-box">
          {first ? (
            <>
              <h3>本题 · {first.kind}</h3>
              <div className="q">{first.question}</div>
              {first.answer_points.length > 0 ? (
                <div className="block answer" style={{ marginTop: 12 }}>
                  <h4>要点</h4>
                  <ul className="answer-points">
                    {first.answer_points.map((a) => <li key={a}>{a}</li>)}
                  </ul>
                </div>
              ) : null}
              <div className="block analysis" style={{ marginTop: 12 }}>
                <h4>答案</h4>
                <div className="prose" dangerouslySetInnerHTML={{ __html: answerHtml(first.answer, point.keywords) }} />
              </div>
              {first.analysis && (
                <div className="block analysis" style={{ marginTop: 12 }}>
                  <h4>解析</h4>
                  <div className="prose" dangerouslySetInnerHTML={{ __html: paragraphs(first.analysis, point.keywords) }} />
                </div>
              )}
            </>
          ) : (
            <p className="muted">本点暂无卡片</p>
          )}
          <div style={{ marginTop: 14, display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button className="btn" onClick={() => void toggleSource()}>
              {showSource ? "收起原文" : "看原文"}
            </button>
            {point.listen.script && (
              <button
                className="btn"
                onClick={() => ai.open({
                  point_id: point.id,
                  title: point.title,
                  question: `用更通俗的方式重讲「${point.title}」`,
                })}
              >听不懂，换种讲法</button>
            )}
          </div>
          {showSource && source && (
            <div className="block analysis" style={{ marginTop: 12 }}>
              <h4>{source.note || "原文段落"}</h4>
              <p style={{ fontSize: 13, lineHeight: 1.8 }}>{source.text || "（无）"}</p>
            </div>
          )}
        </section>
      </div>

      {point.cards.length > 1 && (
        <div className="card-list">
          <h3 style={{ fontSize: 12, letterSpacing: ".14em", textTransform: "uppercase", color: "var(--accent)", margin: "0 0 10px" }}>
            本点全部卡片（{point.cards.length}）
          </h3>
          {point.cards.map((c) => (
            <details className="card-item" key={c.card_id}>
              <summary style={{ cursor: "pointer", fontWeight: 650, fontSize: 14 }}>{c.question}</summary>
              <p className="a" style={{ marginTop: 8 }}>{c.answer}</p>
              {c.answer_points.length > 0 && (
                <ul className="answer-points" style={{ marginTop: 8 }}>
                  {c.answer_points.map((a) => <li key={a}>{a}</li>)}
                </ul>
              )}
              {c.analysis && <p className="a muted" style={{ marginTop: 8 }}>{c.analysis}</p>}
            </details>
          ))}
        </div>
      )}

      <RelationsBlock relations={point.relations} onNavigate={onNavigate} />

      {zoom && (
        <div className="diagram-modal" role="dialog" aria-modal="true" aria-label="图示">
          <div className="diagram-toolbar">
            <span>图示</span>
            <span className="spacer" />
            {[1, 1.5, 2, 3].map((z) => (
              <button key={z} className={zoomScale === z ? "on" : ""}
                onClick={() => setZoomScale(z)}>{z}×</button>
            ))}
            <button onClick={() => { setZoom(null); setZoomScale(1); }} aria-label="关闭">关闭</button>
          </div>
          <div className="diagram-stage">
            <div style={{ width: `${zoomScale * 100}%`, maxWidth: "none" }}
              dangerouslySetInnerHTML={{ __html: zoom.svg }} />
          </div>
          {zoom.caption && <p className="diagram-cap">{zoom.caption}</p>}
        </div>
      )}
    </article>
  );
}

function RelationsBlock({
  relations, onNavigate,
}: {
  relations: Point["relations"];
  onNavigate: (pid: string) => void;
}) {
  const groups: { key: keyof typeof relations; label: string }[] = [
    { key: "prerequisite", label: "前置" },
    { key: "related", label: "相关" },
    { key: "confusable", label: "易混" },
  ];
  const hasAny = groups.some((g) => relations[g.key].length > 0);
  if (!hasAny) return null;
  return (
    <div className="relations">
      <h3>关联</h3>
      {groups.map(({ key, label }) => {
        const items = relations[key];
        if (!items.length) return null;
        return (
          <div key={key}>
            <div className="rel-row">
              <b>{label}</b>
              {items.filter((i) => i.point_id).map((i) => (
                <button key={`${key}-${i.point_id}`} className="rel-link"
                  onClick={() => onNavigate(i.point_id!)}>{i.name || i.point_id}</button>
              ))}
            </div>
            {key === "confusable" && items.some((i) => i.distinction) && (
              <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8 }}>
                {items.filter((i) => i.distinction).map((i, idx) => (
                  <div className="confusable" key={idx}>
                    <b>{i.name}</b>：{i.distinction}
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
