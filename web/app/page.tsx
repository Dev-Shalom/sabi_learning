import Link from "next/link";
import { getExams, getSubjects, getViewer } from "@/lib/api";

/* A server component with no client boundary, so this page renders and reads
 * with JavaScript off. That is the kept-in-spirit half of the decision to
 * adopt React: the app may require a modern browser, the front door may not.
 */

export default async function Home() {
  const [subjects, exams, viewer] = await Promise.all([
    getSubjects(),
    getExams(),
    getViewer(),
  ]);

  const offline = subjects === null;

  return (
    <>
      <header className="mb-8">
        <p className="mb-2 text-sm font-medium text-primary-text">Sabi</p>
        <h1 className="mb-3 text-3xl sm:text-4xl">
          Learn anything.
          <br />
          Pass with flying colours.
        </h1>
        <p className="max-w-prose text-muted">
          Past questions, timed mocks that work like the real thing, and a tutor
          that shows you where every answer came from — and says so when it does
          not know.
        </p>
      </header>

      {offline ? (
        <Panel>
          <h2 className="mb-2 text-lg">Sabi cannot reach its library</h2>
          <p className="text-muted">
            Nothing is wrong with what you did. The question bank is not
            answering right now, so there is nothing honest to show you here.
            Try again in a moment.
          </p>
        </Panel>
      ) : (
        <>
          <Section title="Subjects open now">
            {subjects.length === 0 ? (
              <Panel>
                <p className="text-muted">
                  No subject has enough verified questions yet. A subject
                  appears here when there is real content behind it — never
                  before, because an empty practice set is worse than an honest
                  gap.
                </p>
              </Panel>
            ) : (
              <ul className="grid gap-3 sm:grid-cols-2">
                {subjects.map((s) => (
                  <li key={s.code}>
                    <Link
                      href={`/practice?subject=${s.code}`}
                      className="flex flex-col gap-1 rounded-xl border border-black/10 bg-surface p-4 no-underline dark:border-white/10"
                    >
                      <span className="font-medium text-ink">{s.name}</span>
                      <span className="text-sm text-muted">
                        {/* The generated type marks this optional because the
                            field has a default, so it is defaulted here too
                            rather than asserted away. */}
                        {(s.years_available ?? []).length > 0
                          ? `${(s.years_available ?? []).length} year${
                              (s.years_available ?? []).length === 1 ? "" : "s"
                            } · ${(s.years_available ?? [])[0]}`
                          : "No years yet"}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title="Exams Sabi simulates">
            <ul className="grid gap-3 sm:grid-cols-2">
              {(exams ?? []).map((e) => (
                <li
                  key={e.key}
                  className="rounded-xl border border-black/10 bg-surface p-4 dark:border-white/10"
                >
                  <p className="font-medium text-ink">
                    {e.exam_body} {e.exam_name}
                  </p>
                  <p className="tabular text-sm text-muted">
                    {e.sections.reduce((n, s) => n + s.question_count, 0)}{" "}
                    questions
                    {e.total_duration_minutes
                      ? ` · ${e.total_duration_minutes} minutes`
                      : ""}
                    {e.scale_max ? ` · scored /${e.scale_max}` : ""}
                  </p>
                  {/* Where the format came from, shown rather than implied.
                      Formats change between seasons and a student should be
                      able to see when this was last checked. */}
                  <p className="mt-2 text-xs text-muted">
                    Format checked {e.verified_on}
                  </p>
                </li>
              ))}
            </ul>
          </Section>
        </>
      )}

      {viewer && (
        <Section title="Today">
          <Panel>
            <p className="tabular text-ink">
              {viewer.allowance.questions_remaining} of{" "}
              {viewer.allowance.questions_cap} questions left
            </p>
            <p className="text-sm text-muted">
              They come back {viewer.allowance.resets_phrase}.
              {!viewer.authenticated &&
                " You can ask without an account — signing up gives you more and keeps your notebook."}
            </p>
          </Panel>
        </Section>
      )}
    </>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-8">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Panel({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-black/10 bg-surface p-4 dark:border-white/10">
      {children}
    </div>
  );
}
