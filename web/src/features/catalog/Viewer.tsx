import { useCallback, useEffect, useRef, useState } from "react";
import { useT } from "../../app/useT";
import { TransformComponent, TransformWrapper, type ReactZoomPanPinchRef } from "react-zoom-pan-pinch";
import { Icon } from "../../components/ui/Icon";
import type { DocPage } from "../../lib/types";

/** Просмотр облегчённых копий (WebP): зум, перемещение, листание, полный экран. Мастер-копии не запрашиваются. */
export function Viewer({ pages, title }: { pages: DocPage[]; title: string }) {
  const { t } = useT();
  const [index, setIndex] = useState(0);
  const [full, setFull] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);
  const zoomRef = useRef<ReactZoomPanPinchRef>(null);
  const page = pages[index];
  const total = pages.length;

  const go = useCallback(
    (delta: number) => {
      setIndex((i) => Math.min(total - 1, Math.max(0, i + delta)));
      zoomRef.current?.resetTransform(0);
    },
    [total],
  );

  // ← → листают страницы, пока фокус внутри просмотрщика (на кнопках панели или миниатюрах)
  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") go(1);
      if (e.key === "ArrowLeft") go(-1);
    };
    el.addEventListener("keydown", onKey);
    return () => el.removeEventListener("keydown", onKey);
  }, [go]);

  useEffect(() => {
    const onFs = () => setFull(document.fullscreenElement === boxRef.current);
    document.addEventListener("fullscreenchange", onFs);
    return () => document.removeEventListener("fullscreenchange", onFs);
  }, []);

  const toggleFull = async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await boxRef.current?.requestFullscreen();
    } catch {
      /* полноэкранный режим недоступен — просмотр продолжает работать */
    }
  };

  if (!page) return null;

  return (
    <section aria-label={t("viewer.title")} className="card overflow-hidden">
      <div
        ref={boxRef}
        className="flex flex-col bg-surface-2"
      >
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line bg-surface px-3 py-2">
          <p className="text-sm font-medium" aria-live="polite">
            {t("viewer.page", { n: index + 1, total })}
          </p>
          <div className="flex flex-wrap items-center gap-1">
            <button type="button" className="btn-ghost btn-icon" onClick={() => go(-1)} disabled={index === 0} aria-label={t("common.prev")}>
              <Icon name="left" size={18} />
            </button>
            <button type="button" className="btn-ghost btn-icon" onClick={() => go(1)} disabled={index >= total - 1} aria-label={t("common.next")}>
              <Icon name="right" size={18} />
            </button>
            <span className="mx-1 hidden h-6 w-px bg-line sm:block" aria-hidden="true" />
            <button type="button" className="btn-ghost btn-icon" onClick={() => zoomRef.current?.zoomIn()} aria-label={t("viewer.zoomIn")}>
              <Icon name="zoomIn" size={18} />
            </button>
            <button type="button" className="btn-ghost btn-icon" onClick={() => zoomRef.current?.zoomOut()} aria-label={t("viewer.zoomOut")}>
              <Icon name="zoomOut" size={18} />
            </button>
            <button type="button" className="btn-ghost btn-icon" onClick={() => zoomRef.current?.resetTransform()} aria-label={t("viewer.reset")}>
              <Icon name="reset" size={18} />
            </button>
            <button
              type="button"
              className="btn-ghost btn-icon"
              onClick={toggleFull}
              aria-label={full ? t("viewer.exitFullscreen") : t("viewer.fullscreen")}
            >
              <Icon name="expand" size={18} />
            </button>
          </div>
        </div>
        <div className={full ? "h-[calc(100vh-7rem)]" : "h-[55vh] min-h-[320px]"}>
          <TransformWrapper ref={zoomRef} minScale={1} maxScale={8} centerOnInit wheel={{ step: 0.15 }} doubleClick={{ mode: "zoomIn" }}>
            <TransformComponent wrapperStyle={{ width: "100%", height: "100%" }} contentStyle={{ width: "100%", height: "100%" }}>
              <img
                src={page.url}
                alt={`${title} — ${t("viewer.page", { n: index + 1, total })}`}
                className="h-full w-full object-contain"
                draggable={false}
                data-keep
              />
            </TransformComponent>
          </TransformWrapper>
        </div>
        {total > 1 && (
          <ul aria-label={t("viewer.pages")} className="flex gap-2 overflow-x-auto border-t border-line bg-surface p-2">
            {pages.map((p, i) => (
              <li key={p.id}>
                <button
                  type="button"
                  onClick={() => {
                    setIndex(i);
                    zoomRef.current?.resetTransform(0);
                  }}
                  aria-current={i === index ? "true" : undefined}
                  aria-label={t("viewer.page", { n: i + 1, total })}
                  className={`block h-16 w-14 overflow-hidden rounded border-2 ${i === index ? "border-primary" : "border-transparent"}`}
                >
                  {p.thumb_url && <img src={p.thumb_url} alt="" loading="lazy" className="h-full w-full object-cover" />}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <p className="px-3 py-2 text-sm text-muted">{t("viewer.hint")}</p>
    </section>
  );
}
