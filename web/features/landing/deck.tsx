"use client";

import { useEffect, useRef, useState } from "react";

/* The deck: real answers with their sources open, dealt one at a time.
 *
 * Every card is a real answer from the corpus with the sentence it cites,
 * checked against the corpus by tests/test_landing_facts.py -- and the last is
 * a refusal, because saying "that is not on your syllabus" is half of what
 * makes the other three trustworthy.
 *
 * The dealing itself is CSS (adire.css, `.deck[data-live]`): this component
 * only moves a class. It deals every 7 s, stops while a pointer or keyboard
 * focus is on it (someone is reading), stops when it is off screen, and never
 * deals on its own under reduced motion -- the dots still work. Before
 * hydration the first card is shown on its own, so with JavaScript off the
 * page still carries one complete, cited answer. */

export type DeckCard = {
  subject: string;
  state: string;
  ready: boolean;
  question: string;
  steps?: string[];
  cite_step?: number;
  answer?: string;
  refusal?: string;
  source: {
    locator: string;
    label: string;
    title: string;
    before: string;
    cited: string;
    after: string;
  };
};

const DEAL_MS = 7000;

export function Deck({ cards }: { cards: DeckCard[] }) {
  const [current, setCurrent] = useState(0);
  const [leaving, setLeaving] = useState<number | null>(null);
  const [live, setLive] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const paused = useRef(false);
  const visible = useRef(true);

  const go = (next: number) => {
    setCurrent((cur) => {
      if (next === cur) return cur;
      setLeaving(cur);
      return next;
    });
  };

  useEffect(() => {
    setLive(true);
    const el = root.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => (visible.current = e.isIntersecting));
    io.observe(el);
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return () => io.disconnect();
    const id = window.setInterval(() => {
      if (paused.current || !visible.current || document.hidden) return;
      setCurrent((cur) => {
        setLeaving(cur);
        return (cur + 1) % cards.length;
      });
    }, DEAL_MS);
    return () => {
      window.clearInterval(id);
      io.disconnect();
    };
  }, [cards.length]);

  return (
    <div
      ref={root}
      className="deck"
      data-live={live ? "" : undefined}
      onPointerEnter={() => (paused.current = true)}
      onPointerLeave={() => (paused.current = false)}
      onFocusCapture={() => (paused.current = true)}
      onBlurCapture={() => (paused.current = false)}
    >
      <div className="deck-window" aria-live="polite">
        {cards.map((c, i) => (
          <article
            key={i}
            className={[
              "deck-card artifact",
              i === current ? "is-current" : "",
              i === leaving ? "is-leaving" : "",
            ].join(" ")}
            aria-hidden={i !== current}
          >
            <header className="artifact-head">
              <span className="artifact-subject">{c.subject}</span>
              <span className={`artifact-state${c.ready ? " is-ready" : ""}`}>{c.state}</span>
            </header>
            <div className="artifact-body">
              <p className="deck-question">{c.question}</p>
              {c.steps ? (
                <ol>
                  {c.steps.map((s, j) => (
                    <li key={j}>
                      {s}
                      {j === c.cite_step && (
                        <>
                          {" "}
                          <span className="cite">[{c.source.locator}]</span>
                        </>
                      )}
                    </li>
                  ))}
                </ol>
              ) : null}
              {c.answer && <p className="deck-answer">{c.answer}</p>}
              {c.refusal && <p className="deck-refusal">{c.refusal}</p>}
              <div className="artifact-source">
                <span className="loc">
                  {c.source.locator} · {c.source.label}
                </span>
                <p>
                  {c.source.before && <>{c.source.before} </>}
                  <u>{c.source.cited}</u>
                  {c.source.after && <> {c.source.after}</>}
                </p>
              </div>
            </div>
          </article>
        ))}
      </div>
      <div className="deck-controls" role="group" aria-label="Choose an answer card">
        {cards.map((c, i) => (
          <button
            key={i}
            type="button"
            className="deck-dot"
            aria-current={i === current}
            aria-label={`Card ${i + 1}: ${c.subject}, ${c.state.toLowerCase()}`}
            onClick={() => go(i)}
          />
        ))}
      </div>
    </div>
  );
}
