import Svg, { Circle, Line } from "react-native-svg";

/**
 * Magnifying-glass search glyph — react-native-svg (already a dependency,
 * see FilterIcon.tsx/ShareIcon.tsx) rather than an approximate Unicode
 * character, matching the same reasoning as those icons.
 */
type Props = {
  size?: number;
  color?: string;
};

export default function SearchIcon({ size = 17, color = "#111111" }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Circle cx="11" cy="11" r="7" stroke={color} strokeWidth={2.2} />
      <Line x1="16.2" y1="16.2" x2="21" y2="21" stroke={color} strokeWidth={2.2} strokeLinecap="round" />
    </Svg>
  );
}
