"use client";

import { useEffect, useId, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { logIn, signUp, type AuthError, type SignupResult } from "@/lib/auth";

/* The login and signup form.
 *
 * One component for both, because they differ by three strings and what
 * happens on success. Two near-identical files would drift, and the half that
 * drifted would be whichever one is touched less -- which is signup, the one
 * that shows the recovery codes.
 *
 * It is a real <form>: Enter submits, the labels are joined to their inputs,
 * and the browser's own password manager works. The submit goes through fetch
 * rather than a native POST only because the API answers JSON; everything a
 * keyboard user relies on is the platform's.
 */

type Mode = "login" | "signup";

const COPY = {
  login: {
    heading: "Welcome back",
    blurb: "Your notebook, your progress and your streak are where you left them.",
    submit: "Log in",
    busy: "Logging in…",
    swapPrompt: "New to Sabi?",
    swapLabel: "Create an account",
    swapHref: "/signup",
    passwordHint: "",
    autoComplete: "current-password",
  },
  signup: {
    heading: "Create your account",
    blurb:
      "The questions you have already asked stay with you, and your daily allowance goes up.",
    submit: "Create account",
    busy: "Creating your account…",
    swapPrompt: "Already have an account?",
    swapLabel: "Log in",
    swapHref: "/login",
    passwordHint: "At least 10 characters. A short phrase you will remember is ideal.",
    autoComplete: "new-password",
  },
} as const;

export function AuthForm({ mode }: { mode: Mode }) {
  const copy = COPY[mode];
  const router = useRouter();
  const emailId = useId();
  const passwordId = useId();
  const errorId = useId();

  // Hydration. Until React has attached its handler, this is an ordinary
  // <form> with no action, so pressing Enter navigates to the same URL and
  // silently wipes everything typed. On a cheap phone on a slow connection
  // that window is real, and a student who types fast is exactly who loses
  // their password to it. The submit button is disabled until then, which
  // also suppresses implicit submission from the Enter key.
  const [ready, setReady] = useState(false);
  useEffect(() => setReady(true), []);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<AuthError | null>(null);
  const [codes, setCodes] = useState<string[] | null>(null);
  const errorRef = useRef<HTMLParagraphElement>(null);

  // Move focus to the message once React has actually committed it.
  //
  // This was a requestAnimationFrame immediately after setError, which is a
  // race: the frame can fire before the commit, the ref is still null, and
  // focus silently does not move. It passed alone and failed in the full run
  // -- so a student on a slower phone would have been the one who hit it. An
  // effect keyed on the error runs after the DOM exists, every time.
  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;

    const data = new FormData(event.currentTarget);
    const email = String(data.get("email") ?? "");
    const password = String(data.get("password") ?? "");

    setBusy(true);
    setError(null);
    try {
      if (mode === "signup") {
        const result: SignupResult = await signUp(email, password);
        // Shown, not navigated past: these exist in the clear exactly once,
        // and a redirect here would lose them for good.
        setCodes(result.recovery_codes);
      } else {
        await logIn(email, password);
        router.push("/");
        router.refresh();
      }
    } catch (e) {
      // Focus follows in the effect above, once this has been committed.
      // Without it a screen-reader user submits and hears nothing at all.
      setError(e as AuthError);
    } finally {
      setBusy(false);
    }
  }

  if (codes) return <RecoveryCodes codes={codes} />;

  return (
    <form onSubmit={onSubmit} noValidate className="max-w-sm">
      <h1 className="mb-2 text-2xl">{copy.heading}</h1>
      <p className="mb-6 text-muted">{copy.blurb}</p>

      {error && (
        <p
          ref={errorRef}
          id={errorId}
          tabIndex={-1}
          role="alert"
          className="mb-5 rounded-xl border border-danger/40 bg-danger-tint p-3 text-danger"
        >
          {/* The word "Problem" as well as the colour: roughly one student in
              twelve cannot tell the red from the green. */}
          <strong className="font-semibold">Problem: </strong>
          {error.message}
        </p>
      )}

      <Field
        id={emailId}
        name="email"
        label="Email"
        type="email"
        autoComplete="email"
        describedBy={error ? errorId : undefined}
      />
      <Field
        id={passwordId}
        name="password"
        label="Password"
        type="password"
        autoComplete={copy.autoComplete}
        hint={copy.passwordHint}
        describedBy={error ? errorId : undefined}
      />

      <button
        type="submit"
        disabled={busy || !ready}
        className="mt-2 w-full rounded-xl bg-primary px-4 py-3 font-semibold text-on-primary disabled:opacity-70"
      >
        {busy ? copy.busy : copy.submit}
      </button>

      {/* This form needs JavaScript, because the API answers JSON and the
          submit goes through fetch. Saying so beats a disabled button with no
          explanation.

          It deliberately does not offer a link "to the page that works
          without JavaScript": only /api is proxied to FastAPI, so this route
          IS the login page on this origin, and a link here would point at
          itself. Reading and the landing page stay server-rendered; signing
          in does not, and that is stated rather than implied. */}
      <noscript>
        <p className="mt-3 rounded-xl border border-danger/40 bg-danger-tint p-3 text-sm text-danger">
          Signing in needs JavaScript turned on. Reading and practice work
          without it.
        </p>
      </noscript>

      <p className="mt-6 text-sm text-muted">
        {copy.swapPrompt}{" "}
        <Link href={copy.swapHref} className="text-primary-text">
          {copy.swapLabel}
        </Link>
      </p>

      <p className="mt-4 text-sm text-muted">
        You do not need an account to ask a question. Signing up keeps your
        notebook and raises how much you can ask each day.
      </p>
    </form>
  );
}

function Field({
  id,
  name,
  label,
  type,
  autoComplete,
  hint,
  describedBy,
}: {
  id: string;
  name: string;
  label: string;
  type: string;
  autoComplete: string;
  hint?: string;
  describedBy?: string;
}) {
  const hintId = `${id}-hint`;
  return (
    <div className="mb-4">
      <label htmlFor={id} className="mb-1 block font-medium">
        {label}
      </label>
      <input
        id={id}
        name={name}
        type={type}
        required
        autoComplete={autoComplete}
        aria-describedby={[hint ? hintId : null, describedBy]
          .filter(Boolean)
          .join(" ") || undefined}
        className="w-full rounded-xl border border-black/20 bg-surface px-3 py-3 text-ink dark:border-white/20"
      />
      {hint && (
        <p id={hintId} className="mt-1 text-sm text-muted">
          {hint}
        </p>
      )}
    </div>
  );
}

function RecoveryCodes({ codes }: { codes: string[] }) {
  return (
    <div className="max-w-sm">
      <h1 className="mb-2 text-2xl">Save these five codes</h1>
      <p className="mb-4 text-muted">
        This is the only time they will ever be shown. If you forget your
        password, one of these is how you get back in — each works once.
        Screenshot them, or write them down.
      </p>

      <ul className="mb-6 rounded-xl border border-black/10 bg-surface p-4 dark:border-white/10">
        {codes.map((code) => (
          <li key={code} className="tabular py-1 text-lg tracking-wider text-ink">
            {code}
          </li>
        ))}
      </ul>

      <Link
        href="/"
        className="block rounded-xl bg-primary px-4 py-3 text-center font-semibold text-on-primary no-underline"
      >
        I have saved them
      </Link>
    </div>
  );
}
