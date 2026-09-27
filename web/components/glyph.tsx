/* Every icon in the product, drawn in one hand.
 *
 * The same open stroke as the resist motifs in cloth.tsx, so the icons read as
 * part of the cloth rather than as an icon set bought in -- the tab bar, the
 * landing page and the app all use this one component. Each subject glyph is
 * the instrument a student actually holds in that paper: compasses, a
 * pendulum, a flask, a leaf.
 *
 * `non-scaling-stroke` (set in adire.css) keeps the line the same weight at
 * 22px in the tab bar and at 44px on the landing page, which is what makes
 * them one set instead of two.
 *
 * Decorative by default: whatever the icon means is always said in words
 * beside it, because an icon alone is a guess.
 */

export type GlyphKind =
  | "maths" | "physics" | "chemistry" | "biology"
  | "home" | "practice" | "mock" | "tutor" | "saved"
  | "reading" | "phone" | "shield" | "keys" | "compass";

export function Glyph({
  kind,
  size = 44,
  className = "",
}: {
  kind: GlyphKind;
  size?: number;
  className?: string;
}) {
  return (
    <svg
      className={`glyph ${className}`}
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {PATHS[kind]}
    </svg>
  );
}

const PATHS: Record<GlyphKind, React.ReactNode> = {
  // A pair of compasses over its own arc.
  maths: (
    <>
      <circle cx="24" cy="8" r="2.6" />
      <path d="M22.7 10.4 13 38M25.3 10.4 35 38M13 38l-2.2 4M35 38l2.2 4" />
      <path d="M12 30c7.6 4.2 16.4 4.2 24 0" />
    </>
  ),
  // A pendulum at the end of its swing, with the arc it traced.
  physics: (
    <>
      <path d="M10 8h28M24 8l8 22" />
      <circle cx="32" cy="32" r="4.2" />
      <path d="M13 28c3.4 7 8.6 11 14 12" strokeDasharray="2 3.5" />
      <circle cx="13" cy="26" r="2" strokeDasharray="2 3" />
    </>
  ),
  // A conical flask, half filled, one bubble leaving.
  chemistry: (
    <>
      <path d="M19 6h10M21 6v12L11.5 36a3.2 3.2 0 0 0 2.8 4.8h19.4a3.2 3.2 0 0 0 2.8-4.8L27 18V6" />
      <path d="M15.5 28h17" />
      <circle cx="22" cy="33" r="1.6" />
      <circle cx="28" cy="36" r="1.1" />
    </>
  ),
  // A leaf with its midrib and veins.
  biology: (
    <>
      <path d="M10 38c0-15 10-26 28-28 2 18-8 30-22 30a9 9 0 0 1-6-2Z" />
      <path d="M12 40C18 30 26 22 36 14M20 30l-3-7M26 24l-2.5-7M31 19l-2-6" />
    </>
  ),
  // A compound with a doorway: home.
  home: (
    <>
      <path d="M7 22 24 8l17 14" />
      <path d="M11 19v21h26V19" />
      <path d="M20 40V29h8v11" />
    </>
  ),
  // An exercise book with ruled lines and a tick in the margin.
  practice: (
    <>
      <path d="M11 7h24a2 2 0 0 1 2 2v30a2 2 0 0 1-2 2H11Z" />
      <path d="M16 7v34M21 16h10M21 22h10M21 28h6" />
      <path d="M26.5 33.5l2 2 4-4" />
    </>
  ),
  // A timer: the clock the mock runs against.
  mock: (
    <>
      <circle cx="24" cy="27" r="14" />
      <path d="M24 19v8l5.5 4M20 6h8M24 6v7M36 13l3-3" />
    </>
  ),
  // A speech bubble carrying a citation mark: the tutor shows its source.
  tutor: (
    <>
      <path d="M8 10h32v21H20l-8 7v-7H8Z" />
      <path d="M15 18h12M15 24h8" />
      <path d="M31 17v8" strokeDasharray="1.5 2.5" />
    </>
  ),
  // A ribbon bookmark: what you saved.
  saved: <path d="M13 6h22v36l-11-8-11 8Z" />,
  // An open book, pages lifting.
  reading: (
    <>
      <path d="M24 13c-4-3-10-4-17-3v26c7-1 13 0 17 3 4-3 10-4 17-3V10c-7-1-13 0-17 3Z" />
      <path d="M24 13v26" />
    </>
  ),
  // A small phone: built for the one in your pocket.
  phone: (
    <>
      <rect x="14" y="5" width="20" height="38" rx="3.5" />
      <path d="M21 38h6" />
    </>
  ),
  // A shield with an open centre: what we keep, and what we do not.
  shield: (
    <>
      <path d="M24 6 39 11v11c0 10-6.5 17-15 20-8.5-3-15-10-15-20V11Z" />
      <path d="M18 23.5l4.5 4.5 8-8.5" />
    </>
  ),
  // Two keycaps: the JAMB CBT keyboard.
  keys: (
    <>
      <rect x="6" y="14" width="16" height="16" rx="2.5" />
      <rect x="26" y="14" width="16" height="16" rx="2.5" />
      <path d="M11 25l3-8 3 8M12.2 22.5h3.6M31 17v8h4.5a2.2 2.2 0 0 0 0-4.4H31" />
      <path d="M6 34h16M26 34h16" />
    </>
  ),
  // A compass rose: finding your way through the syllabus.
  compass: (
    <>
      <circle cx="24" cy="24" r="16" />
      <path d="M24 12l4 12-4 12-4-12Z" />
    </>
  ),
};
