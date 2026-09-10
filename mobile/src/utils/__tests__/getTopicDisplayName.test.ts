import { getTopicDisplayName } from "../getTopicDisplayName";

describe("getTopicDisplayName", () => {
  it("shortens known topic names", () => {
    expect(getTopicDisplayName("Artificial Intelligence")).toBe("AI");
    expect(getTopicDisplayName("Climate Change")).toBe("Climate");
    expect(getTopicDisplayName("Entertainment")).toBe("Film & TV");
  });

  it("falls back to the raw name for an unknown topic", () => {
    expect(getTopicDisplayName("Some New Topic")).toBe("Some New Topic");
  });

  it("returns names that map to themselves unchanged", () => {
    expect(getTopicDisplayName("Markets")).toBe("Markets");
  });
});
