/* The public site: landing, pricing, privacy, and the account pages.
 *
 * Server-rendered and readable with JavaScript off (v2 §5.2): a parent on
 * Opera Mini must be able to read what Sabi is, what it costs and what it
 * collects. The landing feature owns the masthead and footer it renders.
 */
export default function SiteLayout({ children }: { children: React.ReactNode }) {
  return <div id="main">{children}</div>;
}
