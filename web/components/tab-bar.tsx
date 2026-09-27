"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BookmarkSimple,
  ChatCircleDots,
  House,
  PencilSimpleLine,
  Timer,
  type Icon,
} from "@phosphor-icons/react";

/* The navigation, and the bug it exists to not repeat.
 *
 * v1 put every section in a masthead that was hidden below 1024px and left
 * nothing in its place, so Practice and the Notebook were simply unreachable
 * on a phone -- on a product whose entire audience is on phones. It was found
 * by looking at a screenshot at 360px, not by a test.
 *
 * So: one list of sections, always present. Below 1024px it is a bottom bar a
 * thumb can reach; from 1024px it is a rail down the left edge. It is the same
 * <nav> in both, so `tests/e2e/reachability.spec.ts` covers both widths.
 *
 * The saffron marker slides to the current section. It is one element moved
 * by `transform` along a track of equal cells -- no layout animation library,
 * nothing measured in JavaScript, and it composites on a cheap phone. It moves
 * because the student asked to go somewhere: a tab changes a few times a
 * visit, which is the frequency the design brief says motion is for.
 */

const TABS: { href: string; label: string; icon: Icon }[] = [
  { href: "/dashboard", label: "Home", icon: House },
  { href: "/practice", label: "Practice", icon: PencilSimpleLine },
  { href: "/exam", label: "Mocks", icon: Timer },
  { href: "/tutor", label: "Tutor", icon: ChatCircleDots },
  { href: "/notebook", label: "Saved", icon: BookmarkSimple },
];

/** Routes that belong to a section without being its root. Reading mode is
 * reached from Practice, so Practice stays lit while a student reads. */
const ALSO = { "/reading": "/practice" } as Record<string, string>;

export function TabBar() {
  const pathname = usePathname();
  const owner =
    Object.entries(ALSO).find(([p]) => pathname.startsWith(p))?.[1] ?? pathname;
  const current = TABS.findIndex(({ href }) => owner.startsWith(href));

  return (
    <nav aria-label="Sections" className="tabbar">
      <Link href="/dashboard" className="tabbar-mark" aria-label="Sabi, home">
        Sabi
      </Link>
      <ul
        className="tabbar-list"
        style={{ "--tab": Math.max(current, 0), "--tabs": TABS.length } as React.CSSProperties}
      >
        {current >= 0 && <li className="tabbar-marker" aria-hidden="true" />}
        {TABS.map(({ href, label, icon: Icon }, i) => {
          const active = i === current;
          return (
            <li key={href}>
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className="tabbar-link"
              >
                <Icon aria-hidden weight={active ? "fill" : "regular"} className="tabbar-icon" />
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
