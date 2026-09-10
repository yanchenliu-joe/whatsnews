import { formatTimeAgo } from "../formatTimeAgo";

describe("formatTimeAgo", () => {
  it("returns null for missing input", () => {
    expect(formatTimeAgo(null)).toBeNull();
    expect(formatTimeAgo(undefined)).toBeNull();
  });

  it("returns null for an unparseable date string", () => {
    expect(formatTimeAgo("not a date")).toBeNull();
  });

  it("says 'just now' for very recent timestamps", () => {
    const now = new Date().toISOString();
    expect(formatTimeAgo(now)).toBe("Just now");
  });

  it("reports hours ago for same-day timestamps", () => {
    const fiveHoursAgo = new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString();
    expect(formatTimeAgo(fiveHoursAgo)).toBe("5h ago");
  });

  it("says 'yesterday' for 24-48h old timestamps", () => {
    const yesterday = new Date(Date.now() - 30 * 60 * 60 * 1000).toISOString();
    expect(formatTimeAgo(yesterday)).toBe("Yesterday");
  });

  it("reports days ago for 2-6 day old timestamps", () => {
    const threeDaysAgo = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString();
    expect(formatTimeAgo(threeDaysAgo)).toBe("3d ago");
  });
});
