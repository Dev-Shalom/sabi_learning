import type { Viewer } from "./api";

/* Calling the auth endpoints from the browser.
 *
 * Everything mutating carries the CSRF token from `/api/auth/viewer`. It is
 * fetched immediately before the write rather than cached on load: the token
 * is tied to the viewer, so it changes the moment somebody logs in or out, and
 * a stale one is refused with a message about the page being stale — which is
 * true but unhelpful if the client caused it itself.
 */

export type AuthError = {
  /** Matches the API's problem codes, so a caller can branch on it. */
  code: string;
  /** Written to be shown to a student as it is. */
  message: string;
  /** Seconds, present only on a rate limit. */
  retryAfter?: number;
};

export type SignupResult = { viewer: Viewer; recovery_codes: string[] };

async function csrfToken(): Promise<string> {
  const res = await fetch("/api/auth/viewer", {
    headers: { accept: "application/json" },
    cache: "no-store",
  });
  if (!res.ok) throw offline();
  return ((await res.json()) as Viewer).csrf_token ?? "";
}

function offline(): AuthError {
  return {
    code: "unavailable",
    // Nothing is wrong with what the student did, and the message says so.
    message:
      "Sabi cannot be reached right now. Nothing you typed was lost — try again in a moment.",
  };
}

async function post<T>(path: string, body: unknown): Promise<T> {
  let token: string;
  try {
    token = await csrfToken();
  } catch {
    throw offline();
  }

  let res: Response;
  try {
    res = await fetch(path, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        accept: "application/json",
        "x-sabi-csrf": token,
      },
      body: JSON.stringify(body),
    });
  } catch {
    throw offline();
  }

  if (res.status === 204) return undefined as T;

  if (!res.ok) {
    const retry = res.headers.get("retry-after");
    let detail: { code?: string; message?: string } = {};
    try {
      detail = (await res.json()).detail ?? {};
    } catch {
      // A non-JSON error body is a proxy or a crash, not the API refusing.
    }
    throw {
      code: detail.code ?? "unavailable",
      message: detail.message ?? offline().message,
      retryAfter: retry ? Number(retry) : undefined,
    } satisfies AuthError;
  }

  return (await res.json()) as T;
}

export const signUp = (email: string, password: string) =>
  post<SignupResult>("/api/auth/signup", { email, password });

export const logIn = (email: string, password: string) =>
  post<Viewer>("/api/auth/login", { email, password });

export const logOut = () => post<void>("/api/auth/logout", {});
