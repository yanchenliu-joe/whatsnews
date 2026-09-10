/**
 * Corner radius scale (added 2026-07-11 design pass). Before this, every
 * screen hardcoded its own borderRadius literal — a scan of the codebase
 * turned up 6/8/10/12/14/20 all in use for conceptually similar elements.
 * Rolling components onto this scale is a per-file sweep (there was no
 * shared token to redirect), not a single-file change.
 */
export const radii = {
  sm: 8, // chips, small buttons, thumbnails
  md: 12, // standard cards, inputs
  lg: 16, // large feature cards, modals, sheets
  pill: 999, // fully-rounded pills/chips
} as const;
