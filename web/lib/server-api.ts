import { cookies } from "next/headers";
import { getJSON, type ExamFormat, type Subject, type Viewer } from "./api";

/* Reads for server components, as the student.
 *
 * Found while laying the Phase 3 foundation: every server-rendered page was
 * fetching `/api/auth/viewer` without the student's cookie, so FastAPI saw a
 * stranger and the home page showed a signed-in student the anonymous
 * allowance. The browser sends the cookie on its own (same origin); a server
 * component has to forward it, and this module is the one place that does.
 *
 * It imports `next/headers`, so it can only be used from the server — which
 * is the point: a client component that needs data calls `getJSON` and lets
 * the browser attach the cookie. */

async function asStudent(): Promise<Record<string, string>> {
  const jar = await cookies();
  const cookie = jar
    .getAll()
    .map((c) => `${c.name}=${c.value}`)
    .join("; ");
  return cookie ? { cookie } : {};
}

export async function serverJSON<T>(path: string): Promise<T | null> {
  return getJSON<T>(path, await asStudent());
}

export const getSubjects = () => serverJSON<Subject[]>("/api/catalog/subjects");
export const getExams = () => serverJSON<ExamFormat[]>("/api/catalog/exams");
export const getViewer = () => serverJSON<Viewer>("/api/auth/viewer");
