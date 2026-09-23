import type { Metadata, Viewport } from "next";
import { Sora, DM_Sans } from "next/font/google";
import { TabBar } from "@/components/tab-bar";
import "./globals.css";

/* Self-hosted at build time by next/font: the files are served from this
 * origin, so there is no extra DNS and TLS handshake to Google on a 3G
 * connection, and no third party on a page aimed at minors. Latin subset only,
 * and the two weights actually used -- the budget is 120 KB for everything. */
const sora = Sora({
  subsets: ["latin"],
  weight: ["600", "700"],
  variable: "--font-sora",
  display: "swap",
});

const dmSans = DM_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-dm-sans",
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
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#F7F9FB" },
    { media: "(prefers-color-scheme: dark)", color: "#0E1B2A" },
  ],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en-NG" className={`${sora.variable} ${dmSans.variable}`}>
      <body>
        <a href="#main" className="visually-hidden">
          Skip to content
        </a>
        {/* pb-24 leaves room for the tab bar, which is fixed so a student can
            move between sections without scrolling back to a header. */}
        <main id="main" className="mx-auto w-full max-w-3xl px-4 pb-28 pt-6">
          {children}
        </main>
        <TabBar />
      </body>
    </html>
  );
}
