import Svg, { Circle, Path } from "react-native-svg";

/**
 * Person-in-circle glyph for the Account tab — react-native-svg rather
 * than an approximate Unicode character (◉), matching the same reasoning
 * as SearchIcon/FilterIcon/PlayPauseIcon.
 */
type Props = {
  size?: number;
  color?: string;
};

export default function AccountTabIcon({ size = 20, color = "#111111" }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Circle cx="12" cy="12" r="9" stroke={color} strokeWidth={2} />
      <Circle cx="12" cy="10" r="3" stroke={color} strokeWidth={2} />
      <Path
        d="M6.5 18c1.2-2.5 3.4-4 5.5-4s4.3 1.5 5.5 4"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
      />
    </Svg>
  );
}
