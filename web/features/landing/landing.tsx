import Link from "next/link";
import { Adire, DyeEdge } from "@/components/cloth";
import { Masthead, SiteFooter } from "@/features/site/site-chrome";
import { PlanCards } from "@/features/pricing/plan-cards";
import { loadPlans } from "@/features/pricing/plans";
import facts from "@/content/landing.json";
import { Deck, type DeckCard } from "./deck";
import { HeroCbt } from "./hero-cbt";
import "./landing.css";

/* The front door (v2 §4.5). A server component: every word of it renders and
 * reads with JavaScript off, which is how a parent on Opera Mini sees it. The
 * only client code is the demo clock and the deck.
 *
 * Design read (design-taste-frontend): consumer landing for Nigerian
 * secondary-school students and the parents who pay; confident, calm,
 * premium; adire indigo, saffron as evidence. VARIANCE 7, MOTION 6,
 * DENSITY 4. Every section uses a different layout family, the hero is
 * left-aligned against the working demo, and there is no eyebrow label over
 * any heading -- the headings carry the sections on their own.
 *
 * Motion: one orchestrated entrance in the hero (headline words rise out of
 * their masks, then the lede, the actions, the demo), the deck dealing, and
 * each section settling once as it scrolls in -- driven by CSS scroll
 * timelines, so it costs no JavaScript and simply does not happen in a
 * browser without them. Nothing scroll-jacks. */

export async function Landing() {
  const plans = await loadPlans();

  return (
    <>
      <Masthead />
      <main id="main">
        <Hero />
        <Exams />
        <Modes />
        <Tutor />
        <MadeForYou />
        <LightOnData />
        <section id="pricing" className="band band-quiet land-pricing">
          <DyeEdge from="paper" />
          <div className="wrap">
            <div className="land-head settle">
              <h2>Free to start. Fair when you need more.</h2>
              <p className="lede">
                Prices are in naira and you can stop any time. A parent can
                pay; nothing is charged without them seeing the amount first.
              </p>
            </div>
            <PlanCards plans={plans} />
          </div>
        </section>
        <Parents />
        <Faq />
        <FinalCta />
      </main>
      <SiteFooter />
    </>
  );
}

/* ------------------------------------------------------------------ hero */

function Hero() {
  return (
    <section className="hero on-cloth land-hero">
      <Adire />
      <div className="wrap hero-grid">
        <div>
          <h1 className="words" aria-label="Learn anything. Pass with flying colours.">
            {/* Word by word in the markup, so the rise works with no script
                and the heading is still read as one sentence. */}
            <span aria-hidden="true">
              {["Learn", "anything."].map((w) => (
                <span key={w} className="word"><b>{w}</b></span>
              ))}{" "}
              <span className="land-h1-2">
                {["Pass", "with", "flying", "colours."].map((w) => (
                  <span key={w} className="word"><b>{w}</b></span>
                ))}
              </span>
            </span>
          </h1>
          <p className="lede rise rise-2">
            Past questions, timed mocks that work like the real CBT, and a
            tutor that shows where every answer came from.
          </p>
          <div className="hero-actions rise rise-3">
            <Link href="/dashboard" className="btn btn-saffron land-cta">
              Start free
            </Link>
            <Link href="#how" className="btn btn-quiet">
              See how it works
            </Link>
          </div>
        </div>
        <div className="land-demo rise rise-4">
          <HeroCbt />
        </div>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------------- exams */

function Exams() {
  return (
    <section id="exams" className="band band-dark on-cloth land-exams">
      <div className="wrap">
        <h2 className="settle">
          Every exam you&rsquo;re sitting,
          <br /> the way it is actually written.
        </h2>
        <ul className="land-exam-list">
          {facts.exams.map((e, i) => (
            <li
              key={e.key}
              className={`settle land-exam${e.ready ? " is-ready" : ""}`}
              style={{ "--i": i } as React.CSSProperties}
            >
              <span className="land-exam-name">{e.name}</span>
              <span className="land-exam-shape">{e.shape}</span>
              <span className="land-exam-state">
                {e.ready ? <CheckMark /> : <Pending />}
                {e.state}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function CheckMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M3 8.5 6.5 12 13 4.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function Pending() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <circle cx="8" cy="8" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeDasharray="2.5 2.5" />
    </svg>
  );
}

/* ----------------------------------------------------------------- modes */

function Modes() {
  return (
    <section id="how" className="band land-modes">
      <DyeEdge from="dark" />
      <div className="wrap">
        <div className="land-head settle">
          <h2>Three ways to study. Pick the one today needs.</h2>
        </div>
        <div className="bento">
          <article className="bento-cell bento-practice settle">
            <div className="bento-copy">
              <h3>Practice</h3>
              <p>
                Pick a subject and a topic. Answer, and see at once whether
                you&rsquo;re right, why, and why the wrong option looked right.
              </p>
            </div>
            <PracticeDemo />
          </article>
          <article className="bento-cell bento-exam on-cloth settle">
            <h3>Exam</h3>
            <p className="muted-on-cloth">
              A full mock on the clock, driven by the same keys as the real
              JAMB CBT. Nothing is marked until you submit.
            </p>
            <ul className="keys land-keys" aria-label="The JAMB keys">
              <li><span><kbd>A</kbd><kbd>B</kbd><kbd>C</kbd><kbd>D</kbd></span><span>answer</span></li>
              <li><span><kbd>N</kbd><kbd>P</kbd></span><span>next, previous</span></li>
              <li><span><kbd>S</kbd></span><span>submit</span></li>
            </ul>
          </article>
          <article className="bento-cell bento-reading settle">
            <h3>Reading</h3>
            <p>
              Past questions laid out like a study book, answers and working
              beside them. Read on the bus, save what you need.
            </p>
            <div className="book" aria-hidden="true">
              <span className="book-page" />
              <span className="book-page" />
              <span className="book-page" />
            </div>
          </article>
        </div>
      </div>
    </section>
  );
}

/** A practice question, marked. The student chose B; B is wrong and says so
 * in words and with a mark, C is the answer. The keys are arithmetic:
 * 25% of 240 is 60. */
function PracticeDemo() {
  return (
    <div className="pq" aria-label="A marked practice question, as an example">
      <p className="pq-stem">What is 25% of 240?</p>
      <ol className="pq-options">
        <li><span className="pq-l">A</span>48</li>
        <li className="is-wrong">
          <span className="pq-l">B</span>72
          <span className="pq-mark"><Cross /> Wrong</span>
        </li>
        <li className="is-right">
          <span className="pq-l">C</span>60
          <span className="pq-mark"><CheckMark /> Correct answer</span>
        </li>
        <li><span className="pq-l">D</span>96</li>
      </ol>
      <p className="pq-why">
        25% is a quarter, and 240 ÷ 4 = 60. B is 30%, a common slip when
        10% is counted three times.
      </p>
    </div>
  );
}
function Cross() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <path d="m4.5 4.5 7 7m0-7-7 7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

/* ----------------------------------------------------------------- tutor */

function Tutor() {
  return (
    <section className="band band-deep on-cloth land-tutor">
      <Adire />
      <DyeEdge from="paper" />
      <div className="wrap land-tutor-grid">
        <div className="settle">
          <h2>A tutor that doesn&rsquo;t guess.</h2>
          <p className="lede">
            Every answer shows the syllabus line or worked example it came
            from. When your notes don&rsquo;t cover something, it says so,
            and shows you what it does have.
          </p>
          <p className="land-figures">
            Built on <span className="figure">{facts.figures.syllabus_documents}</span>{" "}
            syllabus documents and <span className="figure">{facts.figures.worked_examples}</span>{" "}
            worked examples, and checked against{" "}
            <span className="figure">{facts.figures.test_questions}</span> test questions
            it must answer, or refuse, correctly.
          </p>
        </div>
        <div className="settle">
          <Deck cards={facts.deck as DeckCard[]} />
        </div>
      </div>
      <div className="ticker" aria-hidden="true">
        <div className="ticker-track">
          {[...facts.ticker, ...facts.ticker].map(([loc, title], i) => (
            <span key={i} className="ticker-item">
              <b>{loc}</b>
              {title}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------- made for you */

const ONBOARDING = [
  { q: "What class are you in?", options: ["SS1", "SS2", "SS3"], pick: 2 },
  { q: "Which department?", options: ["Science", "Commercial", "Arts"], pick: 0 },
  { q: "Which exams?", options: ["JAMB", "WAEC", "NECO", "Post-UTME"], pick: [0, 1] },
  { q: "How long can you study most days?", options: ["15 min", "30 min", "1 hour", "2+ hours"], pick: 2 },
];

function MadeForYou() {
  return (
    <section className="band band-quiet land-you">
      <DyeEdge from="deep" />
      <div className="wrap land-you-grid">
        <div className="settle land-you-copy">
          <h2>Eight quick questions. Then it&rsquo;s your Sabi.</h2>
          <p className="lede">
            Your class, department, exams and dates shape everything after:
            the countdown on your home screen, today&rsquo;s plan, and the
            subject the tutor starts in. Change any answer later.
          </p>
        </div>
        <ol className="onb">
          {ONBOARDING.map((step, i) => (
            <li key={step.q} className="onb-step settle" style={{ "--i": i } as React.CSSProperties}>
              <span className="onb-n tabular">{i + 1}</span>
              <div>
                <p className="onb-q">{step.q}</p>
                <p className="onb-chips">
                  {step.options.map((o, j) => {
                    const on = Array.isArray(step.pick) ? step.pick.includes(j) : step.pick === j;
                    return (
                      <span key={o} className={`chip${on ? " is-on" : ""}`}>
                        {on && <CheckMark />}
                        {o}
                      </span>
                    );
                  })}
                </p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------- light on data */

function LightOnData() {
  return (
    <section className="band land-data">
      <DyeEdge from="quiet" />
      <div className="wrap">
        <h2 className="settle">Light on data. Kind to cheap phones.</h2>
        <dl className="data-row">
          <div className="settle" style={{ "--i": 0 } as React.CSSProperties}>
            <dt>
              <span className="data-num tabular">150</span>
              <span className="data-unit">KB</span>
            </dt>
            <dd>
              The most JavaScript any page may send before it works. It is
              measured on every build, and a page over it fails.
            </dd>
          </div>
          <div className="settle" style={{ "--i": 1 } as React.CSSProperties}>
            <dt>
              <span className="data-num tabular">360</span>
              <span className="data-unit">px</span>
            </dt>
            <dd>
              The screen width every page is designed and tested at first,
              because that is the phone most students actually have.
            </dd>
          </div>
          <div className="settle" style={{ "--i": 2 } as React.CSSProperties}>
            <dt>
              <span className="data-num">0</span>
              <span className="data-unit">ads</span>
            </dt>
            <dd>
              No adverts and no trackers, so your data bundle goes on
              studying, not on someone else&rsquo;s scripts.
            </dd>
          </div>
        </dl>
        <p className="data-note settle">
          <span className="tag">Coming</span> Offline question packs, so you
          can keep revising when the network drops.
        </p>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------------- parents */

function Parents() {
  return (
    <section id="parents" className="band band-dark on-cloth land-parents">
      <DyeEdge from="quiet" />
      <div className="wrap land-parents-grid">
        <div className="settle">
          <h2>For parents: what we keep, and why.</h2>
          <p className="lede">
            Most Sabi students are under 18. Under the Nigeria Data Protection
            Act a parent or guardian confirms the account before we keep
            anything more than sign-up needs.
          </p>
          <p className="land-parents-link">
            <Link href="/parents">Read the full guide for parents</Link>
          </p>
        </div>
        <table className="limits settle">
          <caption className="visually-hidden">What Sabi collects and why</caption>
          <tbody>
            <tr><th scope="row">Email and password</th><td>So your child can sign back in. The password is stored scrambled and nobody can read it.</td></tr>
            <tr><th scope="row">Class, exams and subjects</th><td>To build their plan and countdown. They can change or delete these.</td></tr>
            <tr><th scope="row">Answers and scores</th><td>To find weak topics. Never sold, never shown to anyone else.</td></tr>
            <tr><th scope="row">Photos of questions</th><td>Read once to get the text, then thrown away. The image is never stored.</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------------- faq */

const FAQ: [string, string[]][] = [
  ["Is Sabi free?", [
    "Yes, to start. Free includes practice every day, reading mode on sample years, timed mocks and tutor questions. Plus and Pro add more when you need it.",
  ]],
  ["Are these real past questions?", [
    "Sabi's question bank is being written now, and every question is checked by a teacher before any student sees it. Each one shows where it came from.",
  ]],
  ["Does the mock work like the real JAMB CBT?", [
    "Yes. The same layout, the same keys (A to D, N, P, S), the same timing and the same scoring out of 400, taken from JAMB's own CBT guide.",
  ]],
  ["What does the tutor do when it doesn't know?", [
    "It says so. If your subject's notes don't cover a question, it tells you and shows the nearest thing it does have. It never fills the gap with a guess.",
  ]],
  ["Can I use it on my phone?", [
    "Yes. Sabi is designed for phones first, at the width of a cheap Android screen. It needs a recent version of Chrome or another modern browser.",
  ]],
  ["Who can see my child's data?", [
    "Your child, and you once you've confirmed the account. Nobody else, and nothing is ever sold.",
  ]],
];

function Faq() {
  return (
    <section className="band land-faq">
      <DyeEdge from="dark" />
      <div className="wrap land-faq-grid">
        <h2 className="settle">Questions students and parents ask.</h2>
        <div className="faq settle">
          {FAQ.map(([q, a]) => (
            <details key={q}>
              <summary>{q}</summary>
              {a.map((p) => (
                <p key={p}>{p}</p>
              ))}
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------------- final */

function FinalCta() {
  return (
    <section className="band band-deep on-cloth land-final">
      <Adire />
      <DyeEdge from="paper" />
      <div className="wrap">
        <p className="land-final-line settle">
          Your exam is coming either way.
          <br />
          <span>Walk in ready.</span>
        </p>
        <div className="hero-actions settle">
          <Link href="/dashboard" className="btn btn-saffron land-cta">
            Start free
          </Link>
        </div>
      </div>
    </section>
  );
}
