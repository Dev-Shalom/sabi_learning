"use client";

import { useEffect, useState } from "react";

/* The demo's countdown. The only JavaScript in the hero.
 *
 * The server renders the starting time, so the first paint is complete and
 * matches hydration exactly (trap 12); it only starts moving once the page is
 * interactive. It stops when the tab is hidden -- a clock ticking nowhere is
 * battery spent on nothing -- and it never moves under reduced motion. */
export function CbtClock({ start }: { start: number }) {
  const [left, setLeft] = useState(start);

  useEffect(() => {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let id: number | undefined;
    const run = () => {
      id = window.setInterval(() => setLeft((s) => (s > 0 ? s - 1 : start)), 1000);
    };
    const onVis = () => {
      window.clearInterval(id);
      if (!document.hidden) run();
    };
    run();
    document.addEventListener("visibilitychange", onVis);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [start]);

  const h = Math.floor(left / 3600);
  const m = Math.floor((left % 3600) / 60);
  const s = left % 60;
  return (
    <span className="cbt-clock tabular">
      {h}:{String(m).padStart(2, "0")}:{String(s).padStart(2, "0")}
    </span>
  );
}
