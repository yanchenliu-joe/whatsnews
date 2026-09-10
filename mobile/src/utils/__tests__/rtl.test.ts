import { I18nManager } from "react-native";
import { backArrow, backChevron, forwardChevron, isRTL } from "../rtl";

describe("rtl helpers", () => {
  afterEach(() => {
    I18nManager.isRTL = false;
  });

  it("point forward/back correctly in LTR mode", () => {
    I18nManager.isRTL = false;
    expect(forwardChevron()).toBe("›");
    expect(backChevron()).toBe("‹");
    expect(backArrow()).toBe("←");
    expect(isRTL()).toBe(false);
  });

  it("flip direction in RTL mode", () => {
    I18nManager.isRTL = true;
    expect(forwardChevron()).toBe("‹");
    expect(backChevron()).toBe("›");
    expect(backArrow()).toBe("→");
    expect(isRTL()).toBe(true);
  });

  it("reads I18nManager.isRTL fresh on each call rather than caching", () => {
    I18nManager.isRTL = false;
    expect(isRTL()).toBe(false);
    I18nManager.isRTL = true;
    expect(isRTL()).toBe(true);
  });
});
