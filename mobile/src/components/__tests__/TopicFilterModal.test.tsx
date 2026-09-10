import { fireEvent, render, screen } from "@testing-library/react-native";
// Initializes the real i18next singleton (same instance TopicFilterModal's
// own useTranslation() resolves against) so t() returns real English
// strings instead of raw keys with a console.warn about a missing
// instance — jest-expo already mocks expo-localization cleanly enough for
// this, per formatTimeAgo.test.ts's own precedent.
import "../../i18n";
import TopicFilterModal from "../TopicFilterModal";
import type { Topic } from "../../types";

// "Markets"/"Politics" are used rather than e.g. "Technology" ("Tech") or
// "Artificial Intelligence" ("AI") deliberately — getTopicDisplayName()
// maps those to shorthand labels (its own concern, already covered by
// getTopicDisplayName.test.ts), and these two pass through unchanged, so
// this test stays focused on TopicFilterModal's own row/selection logic.
const TOPICS: Topic[] = [
  { id: 1, name: "Markets", sort_order: 1 },
  { id: 2, name: "Politics", sort_order: 2 },
];

describe("TopicFilterModal", () => {
  it("renders 'All Topics' plus every topic passed in", () => {
    render(
      <TopicFilterModal
        visible
        topics={TOPICS}
        selectedTopic="All"
        onSelect={jest.fn()}
        onClose={jest.fn()}
      />,
    );

    expect(screen.getByText("Markets")).toBeTruthy();
    expect(screen.getByText("Politics")).toBeTruthy();
  });

  it("shows exactly one checkmark when a listed topic is selected", () => {
    render(
      <TopicFilterModal
        visible
        topics={TOPICS}
        selectedTopic="Markets"
        onSelect={jest.fn()}
        onClose={jest.fn()}
      />,
    );

    expect(screen.getAllByText("✓")).toHaveLength(1);
  });

  it("shows no checkmark when the selected topic isn't in the list (e.g. 'All')", () => {
    render(
      <TopicFilterModal
        visible
        topics={TOPICS}
        selectedTopic="Science"
        onSelect={jest.fn()}
        onClose={jest.fn()}
      />,
    );

    expect(screen.queryAllByText("✓")).toHaveLength(0);
  });

  it("tapping a topic row calls onSelect with that topic's name", () => {
    const onSelect = jest.fn();
    render(
      <TopicFilterModal
        visible
        topics={TOPICS}
        selectedTopic="All"
        onSelect={onSelect}
        onClose={jest.fn()}
      />,
    );

    fireEvent.press(screen.getByText("Politics"));

    expect(onSelect).toHaveBeenCalledWith("Politics");
  });

  it("tapping 'All Topics' calls onSelect with 'All'", () => {
    const onSelect = jest.fn();
    render(
      <TopicFilterModal
        visible
        topics={TOPICS}
        selectedTopic="Markets"
        onSelect={onSelect}
        onClose={jest.fn()}
      />,
    );

    fireEvent.press(screen.getByText("All Topics"));

    expect(onSelect).toHaveBeenCalledWith("All");
  });

  it("tapping the close button calls onClose", () => {
    const onClose = jest.fn();
    render(
      <TopicFilterModal
        visible
        topics={TOPICS}
        selectedTopic="All"
        onSelect={jest.fn()}
        onClose={onClose}
      />,
    );

    fireEvent.press(screen.getByLabelText("Close"));

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
