import Svg, { Rect } from "react-native-svg";

/**
 * 2x2 grid glyph for the Streak tab (evokes StreakCalendar.tsx's month
 * grid) — react-native-svg rather than an approximate Unicode character
 * (⊞), matching the same reasoning as SearchIcon/FilterIcon/PlayPauseIcon.
 */
type Props = {
  size?: number;
  color?: string;
};

export default function StreakTabIcon({ size = 20, color = "#111111" }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Rect x="4" y="4" width="7.5" height="7.5" rx="1.5" stroke={color} strokeWidth={2} />
      <Rect x="12.5" y="4" width="7.5" height="7.5" rx="1.5" stroke={color} strokeWidth={2} />
      <Rect x="4" y="12.5" width="7.5" height="7.5" rx="1.5" stroke={color} strokeWidth={2} />
      <Rect x="12.5" y="12.5" width="7.5" height="7.5" rx="1.5" stroke={color} strokeWidth={2} />
    </Svg>
  );
}
