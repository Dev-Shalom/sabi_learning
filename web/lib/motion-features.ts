/* Motion's animation features, as their own chunk. `MotionProvider` imports
 * this lazily so the ~40 KB it costs is fetched after the page is interactive
 * instead of counting against every route's first-load budget. */
import { domAnimation } from "motion/react";
export default domAnimation;
