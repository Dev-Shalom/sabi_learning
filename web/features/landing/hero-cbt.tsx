import { CbtClock } from "./cbt-clock";

/* The hero's demo: a miniature of the JAMB CBT screen, working.
 *
 * The brief asks for "a live, animated miniature of the exam screen, not a
 * stock photo" (v2 §4.5). It is the real layout in small -- subject tabs, the
 * countdown, a question, A-D, the numbered grid -- and it plays one short
 * loop: a key is pressed, the option is chosen and saved, the grid square
 * fills, the next question arrives. All of it is CSS keyframes on transform
 * and opacity, so it costs no JavaScript beyond the clock and cannot drop a
 * frame when the page is busy loading.
 *
 * The questions are real and their keys are arithmetic, not typed opinions:
 * log 8 = 3 log 2 = 0.9030, and (2x³)² = 4x⁶. It is labelled as a demo for a
 * screen reader, and under reduced motion it is one still frame. */

const GRID = 40;
const ANSWERED = 13; // questions 1-13 already answered in the demo
const FLAGGED = 9;

const Q = [
  {
    n: 14,
    stem: (
      <>
        If log<sub>10</sub> 2 = 0.3010, find log<sub>10</sub> 8.
      </>
    ),
    options: ["0.6020", "0.9030", "1.2040", "2.4080"],
    pick: 1,
  },
  {
    n: 15,
    stem: (
      <>
        Simplify (2x<sup>3</sup>)<sup>2</sup>.
      </>
    ),
    options: ["4x⁶", "2x⁶", "4x⁵", "2x⁹"],
    pick: 0,
  },
];

export function HeroCbt() {
  return (
    <figure className="cbt" aria-label="A demonstration of Sabi's JAMB mock screen">
      <div className="cbt-bar" aria-hidden="true">
        <ul className="cbt-tabs">
          <li>English</li>
          <li className="is-on">Maths</li>
          <li>Physics</li>
          <li>Chemistry</li>
        </ul>
        <CbtClock start={1 * 3600 + 47 * 60 + 32} />
      </div>

      <div className="cbt-stage" aria-hidden="true">
        {Q.map((q, i) => (
          <div key={q.n} className={`cbt-q cbt-q-${i + 1}`}>
            <p className="cbt-count">
              Question <b className="tabular">{q.n}</b> of 40
            </p>
            <p className="cbt-stem">{q.stem}</p>
            <ol className="cbt-options">
              {q.options.map((o, j) => (
                <li key={o} className={j === q.pick ? "is-pick" : undefined}>
                  <span className="cbt-letter">{"ABCD"[j]}</span>
                  <span>{o}</span>
                </li>
              ))}
            </ol>
            <p className="cbt-key">
              <kbd>{"ABCD"[q.pick]}</kbd>
              <span>Saved</span>
            </p>
          </div>
        ))}
      </div>

      <div className="cbt-foot" aria-hidden="true">
        <ol className="cbt-grid">
          {Array.from({ length: GRID }, (_, i) => {
            const n = i + 1;
            const state =
              n === FLAGGED
                ? "is-flag"
                : n <= ANSWERED
                  ? "is-done"
                  : n === 14
                    ? "is-next-1"
                    : n === 15
                      ? "is-next-2"
                      : "";
            return (
              <li key={n} className={state}>
                {n}
              </li>
            );
          })}
        </ol>
        <p className="cbt-legend">
          <span><i className="lg-done" />Answered</span>
          <span><i className="lg-flag" />Flagged</span>
          <span><i className="lg-todo" />Not yet</span>
        </p>
      </div>
      <figcaption className="visually-hidden">
        A demonstration, not a real exam: a student presses B to answer
        question 14, the answer saves, and question 15 appears.
      </figcaption>
    </figure>
  );
}
