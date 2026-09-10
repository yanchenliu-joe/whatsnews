import { useAchievements } from "../context/AchievementsContext";
import BadgeUnlockedModal from "./BadgeUnlockedModal";
import AllBadgesCollectedModal from "./AllBadgesCollectedModal";

/**
 * Mounted once near the top of App.tsx's provider tree (same pattern as
 * LanguageSync.tsx) so the badge-unlock celebration can appear regardless
 * of which screen the user is on when a badge unlocks — badges can be
 * earned from actions on many different screens (reading an article,
 * sharing, playing audio, opening Watch Next), not just the Streak tab.
 * Also renders the one-time "all 32 collected" celebration (2026-07-12) —
 * see AllBadgesCollectedModal.tsx.
 */
export default function BadgeUnlockNotifier() {
  const {
    pendingUnlockedBadge,
    clearPendingBadge,
    showCompletionCelebration,
    clearCompletionCelebration,
  } = useAchievements();
  return (
    <>
      <BadgeUnlockedModal badge={pendingUnlockedBadge} onDismiss={clearPendingBadge} />
      <AllBadgesCollectedModal
        visible={showCompletionCelebration}
        onDismiss={clearCompletionCelebration}
      />
    </>
  );
}
