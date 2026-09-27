import Link from "next/link";
import "./site.css";

/* The public pages' masthead and footer. Server components: no JavaScript.
 *
 * One label per intent across the whole site (design-taste-frontend): the
 * sign-up action is always "Start free", logging in is always "Log in". Two
 * labels for one action make a student wonder whether they are two things. */

const SECTIONS = [
  { href: "/#exams", label: "Exams" },
  { href: "/#how", label: "How it works" },
  { href: "/pricing", label: "Pricing" },
  { href: "/parents", label: "For parents" },
];

export function Masthead() {
  return (
    <header className="site-mast">
      <div className="wrap site-mast-inner">
        <Link href="/" className="site-wordmark" aria-label="Sabi, home">
          <SabiMark />
          <span>Sabi</span>
        </Link>
        <nav aria-label="Site" className="site-nav">
          {SECTIONS.map((s) => (
            <Link key={s.href} href={s.href} className="site-nav-link">
              {s.label}
            </Link>
          ))}
        </nav>
        <Link href="/login" className="site-nav-link site-login">
          Log in
        </Link>
        <Link href="/dashboard" className="btn btn-saffron site-cta">
          Start free
        </Link>
      </div>
    </header>
  );
}

/** Three concentric rings, slightly off-centre: the adire ring motif, and the
 * only mark Sabi has until a commissioned logo exists (placeholder). */
function SabiMark() {
  return (
    <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true" className="site-mark">
      <circle cx="13" cy="13" r="11.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="13.6" cy="12.6" r="7" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="13.2" cy="13.2" r="2.6" fill="currentColor" />
    </svg>
  );
}

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="wrap">
        <div className="footer-grid">
          <div>
            <p className="site-footer-brand">Sabi</p>
            <p className="site-footer-line">
              Learn anything. Pass with flying colours.
            </p>
          </div>
          <div>
            <h2>Study</h2>
            <ul>
              <li><Link href="/practice">Practice</Link></li>
              <li><Link href="/exam">Timed mocks</Link></li>
              <li><Link href="/reading">Reading mode</Link></li>
              <li><Link href="/tutor">The tutor</Link></li>
            </ul>
          </div>
          <div>
            <h2>Sabi</h2>
            <ul>
              <li><Link href="/pricing">Pricing</Link></li>
              <li><Link href="/parents">For parents</Link></li>
              <li><Link href="/privacy">Privacy</Link></li>
              <li><Link href="/login">Log in</Link></li>
            </ul>
          </div>
        </div>
        <div className="footer-note">
          <p>
            Sabi is independent. It is not run by, or connected to, JAMB,
            WAEC, NECO or NABTEB.
          </p>
        </div>
      </div>
    </footer>
  );
}
