import Svg, { Path } from "react-native-svg";

/**
 * Classic "funnel" filter glyph — react-native-svg (already a dependency,
 * see ShareIcon.tsx/BadgeHexagon.tsx) rather than an approximate Unicode
 * character, matching the same reasoning as ShareIcon.
 */
type Props = {
  size?: number;
  color?: string;
};

export default function FilterIcon({ size = 15, color = "#111111" }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M4 6 L20 6 L14 13 L14 19 L10 19 L10 13 Z" fill={color} />
    </Svg>
  );
}
