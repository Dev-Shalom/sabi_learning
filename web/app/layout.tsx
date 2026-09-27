import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { AdireDefs } from "@/components/cloth";
import { PAPER_DARK, PAPER_LIGHT } from "@/lib/theme-colors";
import "./globals.css";

/* Cabinet Grotesk for the voice, Satoshi for everything read and operated.
 * Both from the Indian Type Foundry via Fontshare, under the ITF Free Font
 * Licence (commercial use allowed; recorded in web/ASSETS.md).
 *
 * Self-hosted and subset to Latin plus the maths symbols a question uses
 * (× ÷ − ± √ ≤ ≥ ≠ ° and super/subscripts): 71 KB for all five files against
 * a 120 KB budget. Neither face draws ₦, so prices fall back to the system
 * font for that one glyph -- measured, and cheaper than a third font.
 *
 * Satoshi has tabular figures and Cabinet Grotesk does not, so timers and
 * scores are set in Satoshi with `.tabular`, never in the display face. */
const cabinet = localFont({
  src: [
    { path: "./fonts/cabinet-grotesk-700.woff2", weight: "700", style: "normal" },
    { path: "./fonts/cabinet-grotesk-800.woff2", weight: "800", style: "normal" },
  ],
  variable: "--font-cabinet",
  display: "swap",
});

const satoshi = localFont({
  src: [
    { path: "./fonts/satoshi-400.woff2", weight: "400", style: "normal" },
    { path: "./fonts/satoshi-500.woff2", weight: "500", style: "normal" },
    { path: "./fonts/satoshi-700.woff2", weight: "700", style: "normal" },
  ],
  variable: "--font-satoshi",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Sabi — learn anything, pass with flying colours",
  description:
    "Practise JAMB, WAEC, NECO, NABTEB and Post-UTME past questions, sit " +
    "timed mocks that work like the real thing, and ask a tutor that shows " +
    "you where every answer came from.",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "Sabi", statusBarStyle: "default" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // Pinch-zoom is never disabled. A student with low vision reading a question
  // for two hours needs it, and locking it is a WCAG failure for the sake of
  // an app-like feel nobody asked for.
  maximumScale: 5,
  viewportFit: "cover",
  // A meta tag is read before the stylesheet exists, so these cannot be
  // var(--paper). They come from the one module allowed to name a colour, and
  // the contrast checker fails if they drift from the tokens.
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: PAPER_LIGHT },
    { media: "(prefers-color-scheme: dark)", color: PAPER_DARK },
  ],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en-NG" className={`${cabinet.variable} ${satoshi.variable}`}>
      <body>
        <a href="#main" className="skip-link">
          Skip to content
        </a>
        <AdireDefs />
        {children}
      </body>
    </html>
  );
}
