import {
  normalizeArray,
  normalizeBoolean,
  normalizeDailyReport,
  normalizeFeedResponse,
  normalizeNewsItem,
  normalizeNullableString,
  normalizeRelatedArticlesResponse,
  normalizeString,
  normalizeTopic,
  safeJsonParse,
} from "../dataContracts";

describe("normalizeBoolean", () => {
  it("accepts real booleans and 1/0", () => {
    expect(normalizeBoolean(true)).toBe(true);
    expect(normalizeBoolean(false)).toBe(false);
    expect(normalizeBoolean(1)).toBe(true);
    expect(normalizeBoolean(0)).toBe(false);
  });

  it("accepts string 'true'/'false'", () => {
    expect(normalizeBoolean("true")).toBe(true);
    expect(normalizeBoolean("false")).toBe(false);
  });

  it("falls back for garbage input without throwing", () => {
    expect(normalizeBoolean("garbage", true)).toBe(true);
    expect(normalizeBoolean(undefined, false)).toBe(false);
    expect(normalizeBoolean(null, true)).toBe(true);
  });
});

describe("normalizeString", () => {
  it("passes through real strings", () => {
    expect(normalizeString("hello")).toBe("hello");
  });

  it("falls back for non-strings", () => {
    expect(normalizeString(42, "fallback")).toBe("fallback");
    expect(normalizeString(null, "fallback")).toBe("fallback");
    expect(normalizeString(undefined)).toBe("");
  });
});

describe("normalizeNullableString", () => {
  it("passes through strings and null/undefined as null", () => {
    expect(normalizeNullableString("hi")).toBe("hi");
    expect(normalizeNullableString(null)).toBeNull();
    expect(normalizeNullableString(undefined)).toBeNull();
  });

  it("returns null for non-string, non-null garbage", () => {
    expect(normalizeNullableString(123)).toBeNull();
    expect(normalizeNullableString({})).toBeNull();
  });
});

describe("normalizeArray", () => {
  it("maps and drops null results", () => {
    const result = normalizeArray([1, 2, 3], (x) => (typeof x === "number" && x > 1 ? x * 10 : null));
    expect(result).toEqual([20, 30]);
  });

  it("returns [] for non-array input", () => {
    expect(normalizeArray("not an array", (x) => x)).toEqual([]);
    expect(normalizeArray(null, (x) => x)).toEqual([]);
  });
});

describe("safeJsonParse", () => {
  it("parses valid JSON", () => {
    expect(safeJsonParse('{"a":1}', {})).toEqual({ a: 1 });
  });

  it("returns the fallback for invalid JSON without throwing", () => {
    expect(safeJsonParse("not json{", { fallback: true })).toEqual({ fallback: true });
  });

  it("returns the fallback for null input", () => {
    expect(safeJsonParse(null, "default")).toBe("default");
  });
});

describe("normalizeTopic", () => {
  it("normalizes a well-formed topic", () => {
    expect(normalizeTopic({ id: 1, name: "Tech", sort_order: 2 })).toEqual({
      id: 1,
      name: "Tech",
      sort_order: 2,
    });
  });

  it("returns null when id is missing", () => {
    expect(normalizeTopic({ name: "Tech" })).toBeNull();
  });

  it("returns null when name is missing or blank", () => {
    expect(normalizeTopic({ id: 1, name: "" })).toBeNull();
    expect(normalizeTopic({ id: 1 })).toBeNull();
  });

  it("returns null for non-object input", () => {
    expect(normalizeTopic(null)).toBeNull();
    expect(normalizeTopic("string")).toBeNull();
    expect(normalizeTopic([1, 2])).toBeNull();
  });

  it("defaults sort_order to 0 when missing", () => {
    expect(normalizeTopic({ id: 1, name: "Tech" })?.sort_order).toBe(0);
  });
});

describe("normalizeNewsItem", () => {
  it("normalizes a well-formed article", () => {
    const item = normalizeNewsItem({
      title: "Headline",
      summary: "Summary text",
      source: "BBC",
      url: "https://example.com",
      why_it_matters: "It matters",
      published_at: "2026-07-13T00:00:00Z",
    });
    expect(item).toEqual({
      title: "Headline",
      summary: "Summary text",
      source: "BBC",
      url: "https://example.com",
      why_it_matters: "It matters",
      published_at: "2026-07-13T00:00:00Z",
    });
  });

  it("fills in safe defaults for missing fields", () => {
    const item = normalizeNewsItem({ url: "https://example.com" });
    expect(item?.title).toBe("Untitled");
    expect(item?.source).toBe("Unknown");
    expect(item?.summary).toBe("");
  });

  it("returns null for a record with no usable identity", () => {
    expect(normalizeNewsItem({})).toBeNull();
    expect(normalizeNewsItem({ source: "BBC" })).toBeNull();
  });

  it("returns null for non-object input", () => {
    expect(normalizeNewsItem(null)).toBeNull();
    expect(normalizeNewsItem("garbage")).toBeNull();
  });

  it("keeps a record that has only a url as its identity", () => {
    expect(normalizeNewsItem({ url: "https://example.com" })).not.toBeNull();
  });
});

describe("normalizeDailyReport", () => {
  it("returns null when date is missing (non-recoverable)", () => {
    expect(normalizeDailyReport({ topic: "Tech", items: [] })).toBeNull();
  });

  it("normalizes a well-formed report with nested items", () => {
    const report = normalizeDailyReport({
      date: "2026-07-13",
      topic: "Tech",
      items: [{ title: "A", url: "https://a.com" }],
    });
    expect(report?.date).toBe("2026-07-13");
    expect(report?.items).toHaveLength(1);
  });

  it("drops malformed items from the array rather than failing the whole report", () => {
    const report = normalizeDailyReport({
      date: "2026-07-13",
      items: [{ title: "A", url: "https://a.com" }, {}, null, "garbage"],
    });
    expect(report?.items).toHaveLength(1);
  });
});

describe("normalizeFeedResponse", () => {
  it("maps unified feed items (headline/so_what/sources) onto NewsItem shape", () => {
    const report = normalizeFeedResponse({
      topic: "Tech",
      meta: { resolved_date: "2026-07-13" },
      items: [
        {
          headline: "Big Story",
          summary: "Summary",
          so_what: "Why it matters",
          sources: ["Reuters", "AP"],
          url: "https://example.com",
        },
      ],
    });
    expect(report?.date).toBe("2026-07-13");
    expect(report?.items[0].title).toBe("Big Story");
    expect(report?.items[0].source).toBe("Reuters");
    expect(report?.items[0].why_it_matters).toBe("Why it matters");
  });

  it("falls back to report_date when resolved_date is absent (older responses)", () => {
    const report = normalizeFeedResponse({ meta: { report_date: "2026-07-01" }, items: [] });
    expect(report?.date).toBe("2026-07-01");
  });

  it("falls back to today's date when neither meta field is present", () => {
    const report = normalizeFeedResponse({ items: [] });
    expect(report?.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("skips feed items with no usable title or summary", () => {
    const report = normalizeFeedResponse({ items: [{ sources: [] }] });
    expect(report?.items).toHaveLength(0);
  });

  it("returns null for non-object input", () => {
    expect(normalizeFeedResponse(null)).toBeNull();
  });
});

describe("normalizeRelatedArticlesResponse", () => {
  it("normalizes a well-formed related-articles payload", () => {
    const items = normalizeRelatedArticlesResponse({
      items: [{ title: "Related", summary: "Sum", url: "https://x.com" }],
    });
    expect(items).toHaveLength(1);
    expect(items[0].title).toBe("Related");
  });

  it("returns [] for a payload with no items array", () => {
    expect(normalizeRelatedArticlesResponse({})).toEqual([]);
  });

  it("returns [] for non-object input", () => {
    expect(normalizeRelatedArticlesResponse(null)).toEqual([]);
    expect(normalizeRelatedArticlesResponse("garbage")).toEqual([]);
  });

  it("drops items with no title or summary", () => {
    const items = normalizeRelatedArticlesResponse({ items: [{ source: "BBC" }] });
    expect(items).toHaveLength(0);
  });
});
