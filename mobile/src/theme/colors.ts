export const colors = {
  // Core
  bg: "#F9F9F7",
  ink: "#111111",
  white: "#FFFFFF",

  // Text hierarchy
  muted: "#6B6B6B",
  faint: "#ABABAB",
  summary: "#3D3D3D",
  metaText: "#8A8A8A",
  indexMuted: "#C0C0C0",
  footer: "#BEBEBE",
  bookmarkBorder: "#D4D4D4",

  // Surfaces — white cards on warm-grey bg create natural elevation
  cardBg: "#FFFFFF",
  surface: "#F2F2F0",
  surfaceElevated: "#EDECEA",
  surfaceMuted: "#E8E8E6",

  // Borders
  border: "#E4E4E2",
  borderLight: "#EEEEEC",
  borderStrong: "#CACAC8",

  // Accent — near-black. A wine-red accent (#7A2E3D) was tried during the
  // 2026-07-11 design pass and reverted the same day per explicit user
  // feedback ("不喜欢新加的颜色") — back to black, no color accent for now.
  accent: "#111111",
  accentSoft: "#EBEBEA",

  // WIM block
  whyBg: "#F4F4F2",
  wimSurface: "#F4F4F2",
  wimBorder: "#111111",
  wimText: "#2E2E2E",

  // Status
  danger: "#C0392B",
  success: "#1E7E34",
  warn: "#885500",

  // Misc
  rowBorder: "#EDEDEB",
  errorBg: "#FEF0EF",
  pipeline: "#F4F4F2",
  testPush: "#6B6B6B",
} as const;
