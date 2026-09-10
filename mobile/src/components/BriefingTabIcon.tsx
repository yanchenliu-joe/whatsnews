import Svg, { Path, Rect } from "react-native-svg";

/**
 * "Newspaper article" glyph for the Briefing tab — react-native-svg rather
 * than an approximate Unicode character (⌂), matching the same reasoning
 * as SearchIcon/FilterIcon/PlayPauseIcon.
 */
type Props = {
  size?: number;
  color?: string;
};

export default function BriefingTabIcon({ size = 20, color = "#111111" }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Rect x="3.5" y="4" width="17" height="16" rx="2" stroke={color} strokeWidth={2} />
      <Rect x="6" y="6.5" width="5" height="4.5" rx="0.5" fill={color} />
      <Path
        d="M13 7h5M13 9.5h5M6 14h12M6 16.7h12"
        stroke={color}
        strokeWidth={1.6}
        strokeLinecap="round"
      />
    </Svg>
  );
}
