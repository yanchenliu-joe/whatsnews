import Svg, { Path, Rect } from "react-native-svg";

/**
 * Play/pause glyph drawn with react-native-svg rather than the Unicode
 * "▶"/"⏸" characters — those render as colored system emoji on iOS (a
 * blue-tinted pause icon, not a clean monochrome one), which looked
 * unprofessional on Archive's small overlay button. Same reasoning as
 * ShareIcon/FilterIcon: a real vector shape instead of an approximated
 * Unicode glyph.
 */
type Props = {
  playing: boolean;
  size?: number;
  color?: string;
};

export default function PlayPauseIcon({ playing, size = 14, color = "#FFFFFF" }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      {playing ? (
        <>
          <Rect x="6" y="4" width="4.5" height="16" rx="1" fill={color} />
          <Rect x="13.5" y="4" width="4.5" height="16" rx="1" fill={color} />
        </>
      ) : (
        <Path d="M7 4.5v15a1 1 0 0 0 1.53.85l12-7.5a1 1 0 0 0 0-1.7l-12-7.5A1 1 0 0 0 7 4.5z" fill={color} />
      )}
    </Svg>
  );
}
