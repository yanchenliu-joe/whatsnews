import { estimateReadingTime, formatReadingTime } from "../readingTime";

describe("estimateReadingTime", () => {
  it("rounds up to the nearest minute", () => {
    const words = Array(250).fill("word").join(" "); // 250 words @ 200wpm = 1.25min
    expect(estimateReadingTime(words)).toBe(2);
  });

  it("returns at least 1 minute for short text", () => {
    expect(estimateReadingTime("just a few words")).toBe(1);
  });

  it("joins multiple text arguments before counting", () => {
    const summary = Array(100).fill("word").join(" ");
    const wim = Array(150).fill("word").join(" ");
    expect(estimateReadingTime(summary, wim)).toBe(estimateReadingTime(Array(250).fill("word").join(" ")));
  });

  it("ignores null/undefined arguments", () => {
    expect(estimateReadingTime(undefined, null, "hello world")).toBe(1);
  });

  it("returns 1 for entirely empty input", () => {
    expect(estimateReadingTime(undefined, null, "")).toBe(1);
  });
});

describe("formatReadingTime", () => {
  it("formats minutes with a tilde prefix", () => {
    expect(formatReadingTime(3)).toBe("~3 min read");
  });
});
