import Svg, { Path } from "react-native-svg";

/**
 * The standard iOS "share" glyph (square-and-arrow-up) — react-native-svg
 * (already a dependency, see BadgeHexagon.tsx) draws it directly rather
 * than approximating with a Unicode character, since no icon font/library
 * is installed in this project and no single Unicode glyph renders this
 * shape reliably across platforms.
 */
type Props = {
  size?: number;
  color?: string;
  strokeWidth?: number;
};

export default function ShareIcon({ size = 15, color = "#111111", strokeWidth = 1.7 }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M12 3.2v11.3" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" />
      <Path
        d="M7.5 7.7 12 3.2l4.5 4.5"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M5 11v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}
