import { ViewTransition } from "react";
import { TabBar } from "@/components/tab-bar";

/* The app: every section a signed-in (or anonymous) student moves between.
 *
 * The page region is one named view transition, so moving between sections
 * crossfades and rises (styles/shell.css) while the navigation stays put --
 * the one fixed object is what tells a student they are still in the same
 * place. Onboarding and a running exam live in the (focus) group instead,
 * because neither should have a way out one thumb-tap away.
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-frame">
      <TabBar />
      <ViewTransition default="page">
        <main id="main" className="app-main">
          {children}
        </main>
      </ViewTransition>
    </div>
  );
}
