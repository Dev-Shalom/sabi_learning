/* The cloth: the adire ground and the resist-dye edge.
 *
 * Server components with no client boundary, so they cost no JavaScript at
 * all. Both are decorative and hidden from assistive technology. Both draw in
 * `currentColor`, so the stylesheet decides their colour and the contrast
 * checker never has to know they exist.
 */

/** The adire tile, defined once per page.
 *
 * Four resist-dye motifs from Yoruba adire eleko: bundled parallel lines,
 * concentric rings, a dotted grid, small crosses. Stroked, and deliberately
 * not perfectly regular -- resisted cloth is drawn by hand with a feather, and
 * a machine-exact repeat reads as wallpaper.
 *
 * Defined once rather than inside every <Adire />, because a pattern id must
 * be unique in the document and several bands on one page each want the
 * ground. Every <Adire /> fills with `url(#adire-tile)`. */
export function AdireDefs() {
  return (
    <svg width="0" height="0" aria-hidden="true" focusable="false" style={{ position: "absolute" }}>
      <defs>
        <pattern id="adire-tile" width="168" height="168" patternUnits="userSpaceOnUse">
          <g fill="none" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round">
            {/* bundled lines: the comb, in an uneven group of five */}
            <path d="M14 12 L14 70 M25 10 L25 72 M36 13 L36 69 M47 11 L47 71 M58 12 L58 70" />
            {/* concentric rings, slightly off-centre from one another */}
            <circle cx="122" cy="42" r="9" />
            <circle cx="122.5" cy="42" r="17" />
            <circle cx="121.5" cy="41.5" r="25" />
            {/* a dotted grid: the paste applied in points */}
            <path
              strokeWidth="2.5"
              d="M18 106 h0 M40 106 h0 M62 106 h0 M18 128 h0 M40 128 h0 M62 128 h0 M18 150 h0 M40 150 h0 M62 150 h0"
            />
            {/* small crosses, the fourth motif */}
            <path d="M108 104 l14 14 M122 104 l-14 14 M140 132 l14 14 M154 132 l-14 14 M108 146 l10 10 M118 146 l-10 10" />
            {/* a single hairline seam, so the tile edge reads as cloth */}
            <path d="M0 88 H168" strokeWidth="0.75" opacity="0.6" />
          </g>
        </pattern>
      </defs>
    </svg>
  );
}

/** The adire ground behind a dark band. Needs <AdireDefs /> on the page. */
export function Adire() {
  return (
    <svg className="adire" aria-hidden="true" focusable="false" preserveAspectRatio="xMidYMid slice">
      <rect width="100%" height="100%" fill="url(#adire-tile)" />
    </svg>
  );
}

type DyeFrom = "deep" | "dark" | "paper" | "quiet";

/** A resist-dye edge at the top of a band.
 *
 * Where adire comes out of the indigo vat the boundary is never a straight
 * line: the paste holds the dye back unevenly and it bleeds a little past the
 * edge. This is that boundary, filled with the colour of the band ABOVE, so
 * the upper ground reads as having run down into this one. It is the reason
 * the sections of the page do not simply butt together along a ruled line. */
export function DyeEdge({ from }: { from: DyeFrom }) {
  return (
    <svg
      className={`dye-edge dye-from-${from}`}
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 1440 56"
      preserveAspectRatio="none"
    >
      <path
        fill="currentColor"
        d="M0 0h1440v22.4c-26.6 3.1-53.1 7.8-79.7 8.6-31.2.9-62.4-3.2-93.6-5.4-38.8-2.7-77.6-1.4-116.3 1.9-29.4 2.5-58.7 6.4-88.2 7.1-34.1.8-68.1-3.4-102.2-5.1-31.5-1.6-63.1-.9-94.5 2.2-26.3 2.6-52.4 6.9-78.8 8-28.9 1.2-57.8-2.2-86.6-4.6-36.7-3-73.4-4.3-110.1-1.2-30.2 2.6-60.2 7.8-90.4 9.1-31.4 1.3-62.8-2.1-94.1-4.8-37.9-3.2-75.8-4.6-113.7-1.5-25.6 2.1-51 6.1-76.6 7.4-31.3 1.6-62.6-1.2-93.9-3.6-4.4-.3-8.8-.7-13.3-1V0Z"
      />
      {/* The bleed: dye that got past the resist, thinning out as it goes. */}
      <g fill="currentColor">
        {BLEED.map(([cx, cy, r, o]) => (
          <circle key={cx} cx={cx} cy={cy} r={r} opacity={o} />
        ))}
      </g>
    </svg>
  );
}

const BLEED: [number, number, number, number][] = [
  [92, 40, 2.6, 0.55], [163, 47, 1.5, 0.35], [258, 43, 2.1, 0.45],
  [331, 51, 1.2, 0.28], [437, 41, 2.8, 0.5], [524, 48, 1.6, 0.3],
  [619, 44, 2.2, 0.42], [706, 50, 1.3, 0.26], [795, 42, 2.5, 0.48],
  [884, 49, 1.4, 0.3], [971, 45, 2.3, 0.44], [1063, 52, 1.1, 0.24],
  [1148, 43, 2.7, 0.5], [1235, 48, 1.5, 0.32], [1327, 45, 2, 0.4],
  [1402, 51, 1.2, 0.26],
];
