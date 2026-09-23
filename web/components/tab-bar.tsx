"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/* The navigation, and the bug it exists to not repeat.
 *
 * v1 put every section in a masthead that was hidden below 1024px and left
 * nothing in its place, so Practice and the Notebook were simply unreachable
 * on a phone -- on a product whose entire audience is on phones. It was found
 * by looking at a screenshot at 360px, not by a test.
 *
 * So: a bottom tab bar, always present, thumb-reachable, and
 * `tests/e2e/reachability.spec.ts` asserts every section can be reached at
 * 360px from the home screen. Reachability is a test now rather than an
 * intention.
 */

const TABS = [
  { href: "/", label: "Home", icon: HomeIcon },
  { href: "/practice", label: "Practice", icon: PracticeIcon },
  { href: "/exam", label: "Mocks", icon: ExamIcon },
  { href: "/tutor", label: "Tutor", icon: TutorIcon },
  { href: "/notebook", label: "Saved", icon: SavedIcon },
];

export function TabBar() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Sections"
      className="fixed inset-x-0 bottom-0 z-50 border-t border-black/10 bg-surface/95 backdrop-blur dark:border-white/10"
    >
      <ul className="mx-auto flex max-w-3xl items-stretch justify-between px-2 pb-[env(safe-area-inset-bottom)]">
        {TABS.map(({ href, label, icon: Icon }) => {
          const active =
            href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <li key={href} className="flex-1">
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={[
                  "flex min-h-[56px] flex-col items-center justify-center gap-1",
                  "px-1 py-2 text-[0.7rem] font-medium no-underline",
                  active ? "text-primary-text" : "text-muted",
                ].join(" ")}
              >
                <Icon aria-hidden />
                {/* The label is always shown, never icon-only. An icon on its
                    own is a guess, and this audience should not have to guess
                    where the mocks are. */}
                <span>{label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/* Inline SVG rather than an icon package: five icons do not justify a
 * dependency on the route that has the tightest JS budget in the product. */

const strokeProps = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

function HomeIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" {...strokeProps}>
      <path d="M3 10.5 12 3l9 7.5" />
      <path d="M5.5 9.5V20h13V9.5" />
    </svg>
  );
}

function PracticeIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" {...strokeProps}>
      <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H18v16H5.5A1.5 1.5 0 0 1 4 18.5Z" />
      <path d="M8 9h6M8 13h4" />
    </svg>
  );
}

function ExamIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" {...strokeProps}>
      <circle cx="12" cy="13" r="8" />
      <path d="M12 9v4l2.5 2M9 2h6" />
    </svg>
  );
}

function TutorIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" {...strokeProps}>
      <path d="M4 5h16v11H9l-5 4Z" />
      <path d="M9 10h6" />
    </svg>
  );
}

function SavedIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" {...strokeProps}>
      <path d="M6 3h12v18l-6-4.5L6 21Z" />
    </svg>
  );
}
