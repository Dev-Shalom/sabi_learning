import Link from "next/link";
import { naira, type Plans } from "./plans";
import "./pricing.css";

/* The three plans, from config/plans.yaml.
 *
 * Cards are the right shape here and nowhere else on the page: a plan is a
 * thing you choose between, so each one is a raised object. They are not
 * three identical boxes -- the recommended plan sits on indigo, because the
 * recommendation is information, and it is also said in words.
 *
 * A feature a plan includes but that is not built yet says "Coming": a
 * parent paying for offline packs that do not exist would be buying
 * something false. */

const RECOMMENDED = "plus";

export function PlanCards({ plans }: { plans: Plans | null }) {
  if (!plans) {
    return (
      <p className="plans-missing">
        Prices can&rsquo;t be shown right now. Everything on Free works in the
        meantime.
      </p>
    );
  }

  return (
    <>
      <ul className="plans">
        {plans.plans.map((p) => {
          const rec = p.key === RECOMMENDED;
          return (
            <li key={p.key} className={`plan settle${rec ? " plan-rec on-cloth" : ""}`}>
              <div className="plan-top">
                <h3>{p.name}</h3>
                {rec && <span className="plan-badge">Most students pick this</span>}
              </div>
              <p className="plan-summary">{p.summary}</p>
              <p className="plan-price">
                <span className="plan-amount tabular">{p.monthly === 0 ? "₦0" : naira(p.monthly)}</span>
                {p.monthly > 0 && <span className="plan-per">a month</span>}
              </p>
              <p className="plan-yearly">
                {p.yearly != null && p.yearlySaving != null ? (
                  <>
                    or {naira(p.yearly)} a year, saving {naira(p.yearlySaving)}
                  </>
                ) : (
                  <>No card needed</>
                )}
              </p>
              <ul className="plan-features">
                {p.features.map((f) => (
                  <li key={f.text} className={f.ready ? "" : "is-coming"}>
                    <Tick ready={f.ready} />
                    <span>
                      {f.text}
                      {!f.ready && <span className="tag">Coming</span>}
                    </span>
                  </li>
                ))}
              </ul>
              {p.monthly === 0 ? (
                <Link href="/dashboard" className="btn btn-block plan-btn">
                  Start free
                </Link>
              ) : plans.checkoutOpen ? (
                <Link href={`/pricing?plan=${p.key}`} className="btn btn-block plan-btn">
                  Choose {p.name}
                </Link>
              ) : (
                <p className="plan-closed">Payments open soon. Free works now.</p>
              )}
            </li>
          );
        })}
      </ul>
    </>
  );
}

function Tick({ ready }: { ready: boolean }) {
  return ready ? (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true" className="plan-tick">
      <path d="M4 9.5 7.5 13 14 5.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ) : (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true" className="plan-tick">
      <circle cx="9" cy="9" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeDasharray="2.5 2.5" />
    </svg>
  );
}
