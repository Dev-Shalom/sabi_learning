import Link from "next/link";

/* Placeholder front door, replaced by the landing feature
 * (web/features/landing). Kept honest and minimal so the route exists and
 * reachability tests have somewhere to start. */
export default function Landing() {
  return (
    <section className="hero on-cloth">
      <div className="wrap">
        <h1>Learn anything. Pass with flying colours.</h1>
        <p className="lede">Past questions, real mocks, and a tutor that shows its sources.</p>
        <p className="hero-actions">
          <Link href="/dashboard" className="btn btn-saffron">Start free</Link>
        </p>
      </div>
    </section>
  );
}
