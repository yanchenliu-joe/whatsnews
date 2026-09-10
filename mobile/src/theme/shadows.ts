/**
 * Shadow/elevation scale (added 2026-07-11 design pass). Two levels —
 * most surfaces only ever need "sits above the background" (card) or
 * "floats above other content" (elevated: modals, overlays, top-story
 * cards). Values are deliberately still subtle (this app's flat aesthetic
 * is being kept, just given more consistent depth), not a shift to heavy
 * drop shadows.
 */
export const shadows = {
  card: {
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 6,
    elevation: 2,
  },
  elevated: {
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.14,
    shadowRadius: 16,
    elevation: 6,
  },
} as const;
