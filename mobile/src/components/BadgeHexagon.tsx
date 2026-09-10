import { StyleSheet, Text, View } from "react-native";
import Svg, { Polygon } from "react-native-svg";
import type { BadgeColor } from "../utils/badges";

/**
 * Hexagon badge icon (2026-07-11 design pass) — react-native-svg draws the
 * hexagon (RN's StyleSheet has no polygon/clip-path support, only rects and
 * circles), the emoji glyph sits centered on top via absolute positioning.
 */

const COLOR_MAP: Record<BadgeColor, { bg: string; fg: string }> = {
  green: { bg: "#E3F2E8", fg: "#2E7D46" },
  orange: { bg: "#FDECD9", fg: "#C1671B" },
  yellow: { bg: "#FDF3D0", fg: "#B8860B" },
  blue: { bg: "#E3EDFB", fg: "#2D5FB0" },
  purple: { bg: "#EEE7FA", fg: "#6B3FA0" },
  rose: { bg: "#FBE7EC", fg: "#C43A5C" },
  navy: { bg: "#E4E6F5", fg: "#2B2E6B" },
  gold: { bg: "#FBF0D6", fg: "#A8790A" },
};

function hexagonPoints(size: number): string {
  const cx = size / 2;
  const cy = size / 2;
  const r = size / 2;
  const points: string[] = [];
  for (let i = 0; i < 6; i++) {
    const angle = (Math.PI / 180) * (60 * i - 30); // flat-top orientation
    points.push(`${(cx + r * Math.cos(angle)).toFixed(2)},${(cy + r * Math.sin(angle)).toFixed(2)}`);
  }
  return points.join(" ");
}

type Props = {
  icon: string;
  color: BadgeColor;
  locked?: boolean;
  size?: number;
};

export default function BadgeHexagon({ icon, color, locked, size = 56 }: Props) {
  const palette = COLOR_MAP[color];
  return (
    <View style={[{ width: size, height: size }, locked && styles.locked]}>
      <Svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={StyleSheet.absoluteFill}>
        <Polygon points={hexagonPoints(size - 2)} fill={palette.bg} transform="translate(1,1)" />
      </Svg>
      <View style={[StyleSheet.absoluteFill, styles.iconWrap]}>
        <Text style={{ fontSize: size * 0.42 }}>{icon}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  locked: { opacity: 0.4 },
  iconWrap: { alignItems: "center", justifyContent: "center" },
});
