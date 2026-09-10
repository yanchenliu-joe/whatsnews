import Svg, { Circle, Path } from "react-native-svg";

/**
 * Clock-face glyph for the Archive tab — react-native-svg rather than an
 * approximate Unicode character (◷), matching the same reasoning as
 * SearchIcon/FilterIcon/PlayPauseIcon.
 */
type Props = {
  size?: number;
  color?: string;
};

export default function ArchiveTabIcon({ size = 20, color = "#111111" }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Circle cx="12" cy="12" r="9" stroke={color} strokeWidth={2} />
      <Path
        d="M12 7.5v4.7l3.3 2"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}
