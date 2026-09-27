import type { paths } from "./api-types";

/* The typed client.
 *
 * `api-types.ts` is generated from what FastAPI actually serves, so a backend
 * change that breaks this fails `npm run typecheck` rather than production.
 * Regenerate with `npm run types:api` after `python tools/publish_openapi.py`.
 *
 * Everything goes through `/api` on this origin, which Next rewrites to
 * FastAPI. Same-origin means the session cookie is first-party and there is no
 * CORS credential dance -- and it means `credentials: "include"` is never
 * needed, because same-origin requests send cookies anyway.
 */

export type Subject =
  paths["/api/catalog/subjects"]["get"]["responses"]["200"]["content"]["application/json"][number];

export type ExamFormat =
  paths["/api/catalog/exams"]["get"]["responses"]["200"]["content"]["application/json"][number];

export type Viewer =
  paths["/api/auth/viewer"]["get"]["responses"]["200"]["content"]["application/json"];

/** Where the API lives when rendering on the server.
 *
 * A server component cannot fetch a relative URL -- there is no origin to
 * resolve it against -- so it talks to FastAPI directly. The browser uses the
 * relative path and Next's rewrite. */
const SERVER_ORIGIN = process.env.SABI_API_ORIGIN ?? "http://127.0.0.1:8020";

function url(path: string): string {
  return typeof window === "undefined" ? `${SERVER_ORIGIN}${path}` : path;
}

/** Fetch JSON, or return null.
 *
 * Null rather than a throw, deliberately: the API being unreachable should
 * render a page that says so, not an error boundary. A student on a dropped
 * connection has done nothing wrong and should not be shown a stack trace.
 *
 * `headers` exists for the server: a server component's fetch to FastAPI is a
 * request from Next, not from the student's browser, so it carries no cookie
 * unless one is forwarded. Server code goes through `lib/server-api.ts`, which
 * does that; calling this directly from the server reads as anonymous.
 */
export async function getJSON<T>(
  path: string,
  headers: Record<string, string> = {},
): Promise<T | null> {
  try {
    const res = await fetch(url(path), {
      headers: { accept: "application/json", ...headers },
      // Always current: an allowance or a subject list served from a cache is
      // a number that is quietly wrong.
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}
