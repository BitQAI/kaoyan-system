"use client";
import { useEffect, useRef, useState } from "react";
import type { Figure } from "@/lib/types";

export default function SvgFigure({ figure, onZoom }: { figure: Figure; onZoom: (f: Figure) => void }) {
  const [visible, setVisible] = useState(false);
  const ref = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) {
        setVisible(true);
        io.disconnect();
      }
    }, { rootMargin: "200px" });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <figure className="diagram" ref={ref as React.RefObject<HTMLElement>}
      onClick={() => onZoom(figure)}>
      <div className="svg-wrap">
        {visible ? (
          <div dangerouslySetInnerHTML={{ __html: figure.svg }} />
        ) : (
          <div style={{ height: 180, display: "grid", placeItems: "center" }} className="muted">
            图示加载中…
          </div>
        )}
      </div>
      {figure.caption && <figcaption>{figure.caption}</figcaption>}
    </figure>
  );
}
